from tarxiv.utils import TarxivModule, int_to_alphanumeric, deg2sex, TarxivPipelineError
from tarxiv.data_sources import ATLAS, ASAS_SN, ZTF, LSST, DummySurvey
from tarxiv.database import TarxivDB

from couchbase.exceptions import TransactionCommitAmbiguous, TransactionFailed
from pyspark.sql.types import StructType, StringType, FloatType, TimestampType
from pyspark.sql.functions import col, from_json, expr
from pyspark.sql import SparkSession
from confluent_kafka import Consumer
from hop.auth import Auth
from hop import Stream
import datetime
import shutil
import json
import os



class TarxivXMatchProcessing(TarxivModule):
    def __init__(self, worker_id, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="xmatch-alerts" + f"_worker_{worker_id:02d}",
                         reporting_mode=reporting_mode,
                         debug=debug)
        # Get database connection
        self.db = TarxivDB("xmatch", "pipeline", script_name, reporting_mode, debug)
        # Get kafka consumer
        kafka_host = os.environ["TARXIV_KAFKA_HOST"]
        conf = {'bootstrap.servers': f"{kafka_host}:9092",
                'group.id': 'xmatch_group',
                'auto.offset.reset': 'smallest',
                'enable.auto.commit': False,  # Manual commit
                'enable.auto.offset.store': True,  # Manual store/commit
                'max.poll.interval.ms': 10000,
                'session.timeout.ms': 10000,
                'heartbeat.interval.ms': 3000,
                'enable.partition.eof': False}
        self.consumer = Consumer(conf)

        # Hopskotch authorization
        self.hop_auth = Auth(user=os.environ["TARXIV_HOPSKOTCH_USERNAME"],
                             password=os.environ["TARXIV_HOPSKOTCH_PASSWORD"])

        # Get data sources
        self.data_sources = {
            "ztf": ZTF(script_name, reporting_mode, debug),
            "lsst": LSST(script_name, reporting_mode, debug),
            "test": DummySurvey(script_name, reporting_mode, debug),
        }
        # Read in schema sources
        schema_sources = os.path.join(self.config_dir, "sources.json")
        with open(schema_sources) as f:
            self.schema_sources = json.load(f)

    def run(self):
        # Subscribe to cache of new crossmatches
        self.consumer.subscribe(["spark-sink"])

        while True:
            # Get message
            msg = self.consumer.poll(timeout=1.0)
            # No message, try again
            if msg is None:
                continue
            # Raise error
            elif msg.error():
                error = {"kafka_error": msg.error().str()}
                self.logger.error(error, extra=error)

            # Process message
            else:
                cross_match = json.loads(msg.value().decode('utf-8'))
                # Split row
                detection_1 = {k[:-2]: v for k, v in cross_match.items() if k.endswith('_1')}
                detection_2 = {k[:-2]: v for k, v in cross_match.items() if k.endswith('_2')}
                # Get sexigesimal coords for both
                detection_1["ra_hms"], detection_1["dec_dms"] = deg2sex(detection_1["ra_deg"], detection_1["dec_deg"])
                detection_2["ra_hms"], detection_2["dec_dms"] = deg2sex(detection_2["ra_deg"], detection_2["dec_deg"])
                # Get full alert for both detections
                alert_1 = self.data_sources[detection_1["source"]].pull_alert(detection_1["obj_id"])
                alert_2 = self.data_sources[detection_2["source"]].pull_alert(detection_2["obj_id"])

                # Try
                try:
                    # Now we need a transaction
                    xmatch_id, meta = self.db.cluster.transactions.run(
                        lambda ctx: self.new_xmatch_transaction(ctx, detection_1, detection_2, alert_1, alert_2)
                    )

                    # Submit to hopskotch
                    stream = Stream(auth=self.hop_auth)

                    with stream.open("kafka://kafka.scimma.org/tarxiv.xmatch", "w") as s:
                        s.write({"xmatch_id": xmatch_id} | meta)
                        status = {"status": "submitted hopskotch alert", "xmatch_id": xmatch_id}
                        self.logger.info(status, extra=status)                # Commit so we dont read multiples

                except TarxivPipelineError as e:
                    status = {"pipeline_error": str(e)}
                    self.logger.error(status, extra=status)
                except (TransactionCommitAmbiguous, TransactionFailed) as e:
                    status = {"transaction_error": str(e),
                              "transaction_info": e._exc_info['inner_cause'],
                              "logs": e.logs()}
                    self.logger.error(status, extra=status)
                finally:
                    # Commit consumpiton
                    self.consumer.commit(asynchronous=False)

    def new_xmatch_transaction(self, ctx, detection_1, detection_2, alert_1, alert_2):
        # Get our collections
        hits_collection = self.db.conn.scope(self.db.scope).collection("hits")
        alerts_collection = self.db.conn.scope(self.db.scope).collection("alerts")
        idx_collection = self.db.conn.scope(self.db.scope).collection("idx")
        # We need to see if either detection already has a crossmatch in our cache
        query = (f"SELECT META().id AS xmatch_id FROM tarxiv.xmatch.hits "
                 f"WHERE ANY id IN identifiers SATISFIES id.name IN "
                 f"             [{detection_1['obj_id']}, {detection_2['obj_id']}] END")
        result = ctx.query(query).rows()

        # If nothing, then we have a new detection hit
        if not result:
            # Get current meta id count for this year
            year = str(datetime.datetime.now().year)
            # Run increment transaction
            doc = ctx.get(idx_collection, year)
            content = doc.content_as[dict]
            content["current_idx"] += 1
            ctx.replace(doc, content)

            # Full detection id will be TXV-2025-xxxxxx
            alpha_id = int_to_alphanumeric(content["current_idx"] , self.config["xmatch_id_len"])
            xmatch_id = f"TXV-{year}-{alpha_id}"

            # Split our crossmatch into separate sub documents
            meta = {
                "schema": "https://github.com/astrocatalogs/schema/README.md",
                "identifiers": [{"name": detection_1['obj_id'], "source": detection_1['source']},
                                {"name": detection_2['obj_id'], "source": detection_2['source']}],
                "coords": [
                    {"ra_deg": detection_1['ra_deg'],
                     "dec_deg": detection_1['dec_deg'],
                     "ra_hms": detection_1['ra_hms'],
                     "dec_dms": detection_1['dec_dms'],
                     "source": detection_1['source']
                     },
                    {"ra_deg": detection_2['ra_deg'],
                     "dec_deg": detection_2['dec_deg'],
                     "ra_hms": detection_2['ra_hms'],
                     "dec_dms": detection_2['dec_dms'],
                     "source": detection_2['source']}
                ],
                "timestamps": [{"value": detection_1['timestamp'], "source": detection_1['source']},
                               {"value": detection_2['timestamp'], "source": detection_2['source']}],
                "updated_at": datetime.datetime.now().replace(microsecond=0).isoformat()
                                            .replace("+00:00", "Z")
                                            .replace("T", " "),
                "sources": []
            }
            # Append source meta (citations
            for source in self.config[detection_1['source']]["associated_sources"]:
                meta["sources"].append(self.schema_sources[source])
            for source in self.config[detection_2['source']]["associated_sources"]:
                meta["sources"].append(self.schema_sources[source])

            # Insert to database
            ctx.insert(hits_collection, xmatch_id, meta)
            # Inset alert data to database
            ctx.insert(alerts_collection, detection_1["obj_id"], alert_1)
            ctx.insert(alerts_collection, detection_2["obj_id"], alert_2)

            # Log
            status = {"status": "new crossmatched detection",
                      "xmatch_id": xmatch_id,
                      "surveys": [detection_1["survey"], detection_2["survey"]],
                      "identifiers": [detection_1["obj_id"], detection_2["obj_id"]]}
            self.logger.info(status, extra=status)

        # Otherwise we have an additional detection to add to an existing hit
        else:
            # If we have more than one result send a warning (shouldn't have a detection.id in more than one document)
            if len(result) > 1:
                warning = {"status": "found multiple documents with same detection.id",
                           "offending_ids": [detection_1['obj_id'], detection_2['obj_id']]}
                self.logger.warn(warning, extra=warning)
            # Get first xmatch
            xmatch_id = result[0]["xmatch_id"]
            # Now get the document with context
            doc = ctx.get(hits_collection, xmatch_id)
            meta = doc.content_as[dict]

            # See which id is new
            hit_ids = [idx["name"] for idx in meta["identifiers"]]
            diff = list({detection_1['obj_id'], detection_2['obj_id']} - set(hit_ids))

            if len(diff) == 0:
                raise TarxivPipelineError(f"duplicate cross-match:"
                                          f"offending ids: {detection_1['obj_id']}, {detection_2['obj_id']}")
            # Here is our new detection
            det_id = diff[0]
            if det_id == detection_1['obj_id']:
                new_hit_det = detection_1
                new_hit_alert = alert_1
            elif det_id == detection_2['obj_id']:
                new_hit_det = detection_2
                new_hit_alert = alert_2
            else:
                # This should never happen
                raise TarxivPipelineError(f"database found matched hit detection id, but logic failed:"
                                          f"offending ids: {detection_1['obj_id']}, {detection_2['obj_id']}")

            # Append values to documents
            meta["identifiers"].append(
                {"name": new_hit_det["obj_id"], "source": new_hit_det["source"]}
            )
            meta["coords"].append(
                {"ra_deg": new_hit_det["ra_deg"],
                 "dec_deg": new_hit_det["dec_deg"],
                 "ra_hms": new_hit_det["ra_hms"],
                 "dec_dms": new_hit_det["dec_dms"],
                 "source": new_hit_det["source"]}
            )
            meta["timestamps"].append(
                {"value": new_hit_det["timestamp"], "source": new_hit_det["source"]}
            )
            # Append source meta
            for source in self.config[new_hit_det["source"]]["associated_sources"]:
                meta["sources"].append(self.schema_sources[source])

            meta["updated_at"] = (datetime.datetime.now().replace(microsecond=0).isoformat()
                                  .replace("+00:00", "Z")
                                  .replace("T", " "))
            # Upsert to database
            ctx.replace(doc, meta)
            # Upsert alert
            ctx.insert(alerts_collection, new_hit_det["obj_id"], new_hit_alert)

            # Log
            status = {"status": "new hit for existing detection",
                      "new_id": new_hit_det['obj_id'],
                      "new_source": new_hit_det["source"]}
            self.logger.info(status, extra=status)

        return xmatch_id, meta

class TarxivXmatchFinder(TarxivModule):
    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="spark-xmatch-finder",
                         reporting_mode=reporting_mode,
                         debug=debug)

        # Create spark app
        self.spark = SparkSession.builder \
                .appName("spark-xmatch-finder") \
                .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1") \
                .config("spark.executor.instances", self.config['spark_executors']) \
                .config("spark.executor.cores", self.config['spark_executor_cores']) \
                .config("spark.executor.memory", self.config['spark_executor_memory']) \
                .config("spark.driver.memory", self.config['spark_driver_memory']) \
            .getOrCreate()
        # Log
        status = {"status": "connected to spark"}
        self.logger.info(status, extra=status)


    def run(self):
        # Log
        status = {"status": "starting spark crossmatch machine"}
        self.logger.info(status, extra=status)
        # Delete old checkpoints
        shutil.rmtree("/tmp/spark-checkpoints", ignore_errors=True)

        # Create Kafka DF
        kafka_host = os.environ["TARXIV_KAFKA_HOST"]
        """
        .option("kafka.consumer.timeout.ms", "10000") \
            .option("kafka.consumer.max.poll.records", "50000") \
            .option("kafka.consumer.max.poll.interval.ms", "3600000") \
            .option("kafka.session.timeout.ms", "1800000") \
            .option("kafka.heartbeat.interval.ms", "5000") \
            """
        kafka_df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "localhost:9092") \
            .option("subscribe", self.config["xmatch_ingest_topic"]) \
            .load()

        # Create Schema
        json_schema = StructType() \
            .add("obj_id", StringType()) \
            .add("source", StringType()) \
            .add("ra_deg", FloatType()) \
            .add("dec_deg", FloatType()) \
            .add("timestamp", TimestampType())

        # Get data from json
        sdf = kafka_df.selectExpr("CAST(value AS STRING)") \
            .select(from_json(col("value"), json_schema).alias("data")) \
            .select("data.*")

        # What is our comparison window
        window = self.config["xmatch_window_len"]
        # Reduce by days
        #filtered_df = sdf.filter(col("timestamp") >= expr(f"current_timestamp() - INTERVAL {window} HOURS"))
        # Partition on declination
        sdf = sdf.repartitionByRange(180, 'dec_deg')
        # Register table for crazy query
        sdf.createOrReplaceTempView("targets")

        query = """
        SELECT
            t1.obj_id AS obj_id_1,
            t1.source as source_1,
            t1.ra_deg AS ra_deg_1,
            t1.dec_deg AS dec_deg_1,
            t1.timestamp AS timestamp_1,
            t2.obj_id AS obj_id_2,
            t2.source as source_2,
            t2.ra_deg AS ra_deg_2,
            t2.dec_deg AS dec_deg_2,
            t2.timestamp AS timestamp_2
        FROM targets t1
        JOIN targets t2 
        ON 1=1 
          AND t1.obj_id != t2.obj_id                                                 -- Ensures you don't match a row with itself
          AND t1.obj_id < t2.obj_id
          AND t1.source != t2.source 
          AND CAST(t1.dec_deg AS DECIMAL(10, 3)) = CAST(t2.dec_deg AS DECIMAL(10, 3))  -- Shortcut to throwout comparison rows
          AND DEGREES(ACOS(SIN(RADIANS(t1.dec_deg)) * SIN(RADIANS(t2.dec_deg)) 
                       + COS(RADIANS(t1.dec_deg)) * COS(RADIANS(t2.dec_deg))           -- Actual Join
                       * COS(RADIANS(t1.ra_deg - t2.ra_deg)))) * 3600 <= 
        """
        # Add crossmatch radius
        query += self.config["xmatch_radius"]
        # Run the crossmatch
        match_sdf = self.spark.sql(query)

        # Back to json for kafka
        kafka_df = match_sdf.selectExpr("CAST(obj_id_1 AS STRING) AS key ",
                                           "to_json(struct(*)) AS value")

        query = kafka_df \
            .writeStream \
            .outputMode("append") \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "localhost:9092") \
            .option("topic", "spark-sink") \
            .option("checkpointLocation", "/tmp/spark-checkpoints") \
            .start()

        query.awaitTermination()
