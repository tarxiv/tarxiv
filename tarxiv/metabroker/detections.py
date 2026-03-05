from tarxiv.utils import TarxivModule
from tarxiv.database import TarxivDB
from tarxiv.utils import PRINT, LOGFILE, DATABASE

from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StringType, FloatType, IntegerType
from pyspark.sql import SparkSession
from confluent_kafka import Consumer
import multiprocessing as mp
import argparse
import shutil
import uuid
import json


class TarxivDetectionAlerts(TarxivModule):
    def __init__(self, worker_id, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="detections-alerts" + f"_worker_{worker_id:02d}",
                         reporting_mode=0,
                         debug=debug)
        # Get database connection
        self.db = TarxivDB("detections", "pipeline", script_name, reporting_mode, debug)
        # Get kafka consumer
        conf = {'bootstrap.servers': "localhost:9092",
                'group.id': 'detection_group',
                'auto.offset.reset': 'smallest',
                'enable.auto.commit': False,  # Manual commit
                'enable.auto.offset.store': True,  # Manual store/commit
                'max.poll.interval.ms': 10000,
                'session.timeout.ms': 10000,
                'heartbeat.interval.ms': 3000,
                'enable.partition.eof': False}
        self.consumer = Consumer(conf)

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

                # For this cross match
                # we need to see if either detection already has a crossmatch in our cache
                query = (f"SELECT META().id AS doc_id, * FROM tarxiv.detections.hits "
                         f"WHERE ANY det IN detections SATISFIES det.id IN [{cross_match['id_1']}, {cross_match['id_2']}] END")
                result = self.db.query(query).execute()

                # If nothing, then we have a new detection hit
                if not result:
                    new_id = str(uuid.uuid4())
                    # Split our crossmatch into separate sub documents
                    det_1 = {k[:-2]: v for k, v in cross_match.items() if k.endswith('_1')}
                    det_2 = {k[:-2]: v for k, v in cross_match.items() if k.endswith('_2')}
                    document = {"detections": [det_1, det_2]}
                    # Upsert to database
                    self.db.upsert(new_id, document, "hits")
                    # Log
                    status = {"status": "new crossmatched detection", "detection_hit": document}
                    self.logger.info(status, extra=status)

                # Otherwise we have an additional detection to add to an existing hit
                else:
                    # If we have more than one result send a warning (shouldn't have a detection.id in more than one document)
                    if len(result) > 1:
                        warning = {"status": "found multiple documents with same detection.id",
                                   "offending_ids": [cross_match['id_1'], cross_match['id_2']]}
                        self.logger.warn(warning, extra=warning)
                    # Now we need to figure out which "side" of our new detection is not in the existing hit
                    document = result[0]
                    new_hit_det = {}
                    for detection in document['hits']['detections']:
                        # Neither
                        if detection['id'] not in [cross_match['id_1'], cross_match['id_2']]:
                            break
                        # If det hit id = 1, then the new hit is id = 2
                        if detection['id'] == cross_match['id_1']:
                            new_hit_det =  {k[:-2]: v for k, v in cross_match.items() if k.endswith('_2')}
                            break
                        # Vis-a versa
                        if detection['id'] == cross_match['id_2']:
                            new_hit_det =  {k[:-2]: v for k, v in cross_match.items() if k.endswith('_1')}
                            break
                    # Logically, shouldn't get this, but if non of the detection id's matched either "side" then warn
                    if not new_hit_det:
                        warning = {"status": "database found matched hit detection id, but logic failed",
                                   "document": document,
                                   "offending_ids": [cross_match['id_1'], cross_match['id_2']]}
                        self.logger.warn(warning, extra=warning)
                    # Otherwise, append new detection hit to alert and send
                    else:
                        document['hits']['detections'].append(new_hit_det)
                    # Upsert to database
                    self.db.upsert(document['doc_id'], document['hits'], "hits")
                    # Log
                    status = {"status": "new hit for existing detection",
                              "detection_hit": document['hits'],
                              "new_source": new_hit_det["source"]}
                    self.logger.info(status, extra=status)

                # HOPSKOTCH LATER

                # Commit so we dont read multiples
                self.consumer.commit(asynchronous=False)

class TarxivDetectionFinder(TarxivModule):
    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="spark-detection-finder",
                         reporting_mode=reporting_mode,
                         debug=debug)

        # Create spark app
        self.spark = SparkSession.builder \
                .appName("spark-detections-finder") \
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
        kafka_df = self.spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "localhost:9092") \
            .option("subscribe", self.config["kafka_ingest_topic"]) \
            .load()

        # Create Schema
        json_schema = StructType() \
            .add("det_id", IntegerType()) \
            .add("source", StringType()) \
            .add("name", StringType()) \
            .add("ra_deg", FloatType()) \
            .add("dec_deg", FloatType()) \
            .add("detection_score", FloatType())

        # Get data from json
        sdf = kafka_df.selectExpr("CAST(value AS STRING)") \
            .select(from_json(col("value"), json_schema).alias("data")) \
            .select("data.*")

        # Partition on declination
        sdf = sdf.repartitionByRange(180, 'dec_deg')
        # Register table for crazy query
        sdf.createOrReplaceTempView("targets")

        query = """
        SELECT
            t1.det_id AS id_1,
            t1.name AS name_1,
            t1.source as source_1,
            t1.ra_deg AS ra_deg_1,
            t1.dec_deg AS dec_deg_1,
            t1.detection_score AS detection_score_1,
            t2.det_id AS id_2,
            t2.name AS name_2,
            t2.source as source_2,
            t2.ra_deg AS ra_deg_2,
            t2.dec_deg AS dec_deg_2,
            t2.detection_score AS detection_score_2,
            CAST(DEGREES(ACOS(SIN(RADIANS(t1.dec_deg)) * SIN(RADIANS(t2.dec_deg)) 
                       + COS(RADIANS(t1.dec_deg)) * COS(RADIANS(t2.dec_deg)) 
                       * COS(RADIANS(t1.ra_deg - t2.ra_deg)))) as DECIMAL(10,4)) * 3600 AS separation_distance
        FROM targets t1
        JOIN targets t2 
        ON 1=1 
          AND t1.det_id != t2.det_id                                                 -- Ensures you don't match a row with itself
          AND t1.det_id < t2.det_id
          AND t1.source != t2.source 
          AND CAST(t1.dec_deg AS DECIMAL(10, 3)) = CAST(t2.dec_deg AS DECIMAL(10, 3))  -- Shortcut to throwout comparison rows
          AND DEGREES(ACOS(SIN(RADIANS(t1.dec_deg)) * SIN(RADIANS(t2.dec_deg)) 
                       + COS(RADIANS(t1.dec_deg)) * COS(RADIANS(t2.dec_deg))           -- Actual Join
                       * COS(RADIANS(t1.ra_deg - t2.ra_deg)))) * 3600 <= 
        """
        # Add crossmatch radius
        query += self.config["cross_match_radius"]
        # Run the crossmatch
        match_sdf = self.spark.sql(query)

        # Back to json for kafka
        kafka_df = match_sdf.selectExpr("CAST(id_1 AS STRING) AS key ",
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

def detection_alert_worker(idx):
    txv_det_finder = TarxivDetectionAlerts(worker_id=idx,
                                           script_name="tarxiv-kafka-detection-alerts",
                                           reporting_mode=(PRINT | LOGFILE),
                                           debug=args.debug)
    txv_det_finder.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("tarxiv_detections")
    parser.add_argument('--debug', action='store_true', default=False,
                        help='set to enable printing/logging in debug mode')
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--finder", action="store_true", help="run spark instance to find new detections")
    group.add_argument("--alerts", action="store_true",
                       help="run kafka listener to collate new detections and send alerts")
    parser.add_argument("--threads", type=int, default=1, help="number of detection alert threads to run")
    args = parser.parse_args()

    if args.finder:
        txv_det_finder = TarxivDetectionFinder(script_name="tarxiv-spark-detection-finder",
                                               reporting_mode=(PRINT | LOGFILE),
                                               debug=args.debug)
        txv_det_finder.run()

    elif args.alerts:
        with mp.Pool(processes=args.threads) as pool:
            results = [pool.apply_async(detection_alert_worker, args=(idx+1,)) for idx in range(args.threads)]

            success = sum([r.get() for r in results])