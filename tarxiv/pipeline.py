
from .utils import TarxivModule, TarxivPipelineError, deg2sex
from .data_sources import TNS, LSST, ASAS_SN, ZTF, Lasair, ANTARES, AlerceMod, ATLAS
from .database import TarxivDB
from confluent_kafka import Producer, Consumer, KafkaError
from astropy.time import Time
from hop.auth import Auth
from hop import Stream
import multiprocessing as mp
import pandas as pd
import requests
import datetime
import traceback
import zipfile
import socket
import signal
import json
import io
import os


class TNSPipeline(TarxivModule):
    """Pipeline for TNS data processing and storage."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="tns_pipeline",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Create survey objects
        self.tns = TNS(script_name, reporting_mode, debug)
        self.ztf = ZTF(script_name, reporting_mode, debug)
        self.asas_sn = ASAS_SN(script_name, reporting_mode, debug)
        self.lsst = LSST(script_name, reporting_mode, debug)
        self.lasair = Lasair(script_name, reporting_mode, debug)
        self.antares = ANTARES(script_name, reporting_mode, debug)
        self.alerce = AlerceMod(script_name, reporting_mode, debug)

        # Specify data source
        self.data_sources = {
            "tns": self.tns,
            "fink_ztf": self.ztf,
            "fink_lsst": self.lsst,
            "asas_sn": self.asas_sn,
            "sherlock": self.lasair,
            "antares": self.antares,
            "alerce": self.alerce,
        }

        # Get database
        self.db = TarxivDB("pipeline", script_name, reporting_mode, debug)

        # Hopskotch authorization
        self.hop_auth = Auth(
            user=os.environ["TARXIV_HOPSKOTCH_USERNAME"],
            password=os.environ["TARXIV_HOPSKOTCH_PASSWORD"],
        )

        # Get kafka configuration
        conf = {'bootstrap.servers': os.environ['TARXIV_KAFKA_HOST'] + ":9092",
                'delivery.timeout.ms': 10000,
                'queue.buffering.max.messages': 1000000,
                'queue.buffering.max.ms': 5000,
                'batch.num.messages': 100,
                'client.id': socket.gethostname()}
        self.producer = Producer(conf)
        self.consumer = None

        # Signal handling
        if not debug:
            self.stop_event = mp.Event()
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        else:
            self.stop_event = None
    def signal_handler(self, sig, frame):
        status = {
            "status": "received exit signal, wait to finish processing",
            "signal": str(sig),
            "frame": str(frame),
        }
        self.logger.info(status, extra=status)
        self.stop_event.set()

    def print_assignment(self, consumer, partitions):
        # Logging for kafka
        status = {"status": "consumer subscribed", "partitions": partitions}
        self.logger.info(status, extra=status)

    def get_object(self, object_id):
        """
        Queries TNS for an object then finds all associated survey data.

        Same as get object, but with split schema

        :param object_id:
        :return:
        """
        # Get initial info from TNS
        tns_meta = self.tns.get_object(object_id)
        # Return empty dicts
        if tns_meta is None:
            return None

        # Get a tarxiv unique id
        txv_id = self.db.get_txv_id(year=object_id[:4], object_id=object_id)
        if txv_id is None:
            raise TarxivPipelineError("Unable to generate new tarxiv_idx")
        # Parse coords
        ra_deg, dec_deg = tns_meta["ra_deg"], tns_meta["dec_deg"]
        ra_hms, dec_dms = deg2sex(ra_deg, dec_deg)
        # Start our meta dict
        meta = {
            "tarxiv_id": txv_id,
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "ra_hms": ra_hms,
            "dec_dms": dec_dms,
            "source": "tns",
            "source_id": object_id,
            "discovery_date": tns_meta["discovery_date"],
            "data_sources": {"tns": tns_meta},
        }

        # Cut on time (1 month before DISCOVERY, 6 months after)
        # IF we have a reporting date, WORK ON LATER
        disc_mjd = Time(tns_meta["discovery_date"]).mjd

        # Check if we have a document giving the settings
        active_settings = self.db.get(
            txv_id, scope="misc", collection="active_settings"
        )
        if active_settings is None:
            active_settings = {
                "prior_days": self.config["tns_sources"]["obj_prior_days"],
                "active_days": self.config["tns_sources"]["obj_active_days"],
            }
            self.db.upsert(
                txv_id, active_settings, scope="misc", collection="active_settings"
            )
        # Check if we have special min/max mjds, if not use default
        mjd_min = disc_mjd - active_settings["prior_days"]
        mjd_max = disc_mjd + active_settings["active_days"]

        # Now get meta and lightcurves from the surveys
        fink_ztf_meta, ztf_lc = self.ztf.get_object(txv_id, ra_deg, dec_deg, mjd_min, mjd_max)
        asas_sn_meta, asas_sn_lc = self.asas_sn.get_object(txv_id, ra_deg, dec_deg, mjd_min, mjd_max)
        fink_lsst_meta, lsst_lc = self.lsst.get_object(txv_id, ra_deg, dec_deg, mjd_min, mjd_max)
        # Get additional meta from the survey
        lasair_meta = self.lasair.get_object(txv_id, ra_deg, dec_deg)
        antares_meta = self.antares.get_object(txv_id, ra_deg, dec_deg)
        alerce_meta = self.alerce.get_object(txv_id, ra_deg, dec_deg)

        # Add data sources to meta dictSelf
        if lasair_meta is not None:
            meta["data_sources"]["sherlock"] = lasair_meta
        if alerce_meta is not None:
            meta["data_sources"]["alerce"] = alerce_meta
        if antares_meta is not None:
            meta["data_sources"]["antares"] = antares_meta
        if fink_ztf_meta is not None:
            meta["data_sources"]["fink_ztf"] = fink_ztf_meta
        if fink_lsst_meta is not None:
            meta["data_sources"]["fink_lsst"] = fink_lsst_meta
        if asas_sn_meta is not None:
            meta["data_sources"]["asas_sn"] = asas_sn_meta

        # Collate lightcurves and add peak mag measurements to schema
        lc_df = pd.concat([ztf_lc, asas_sn_lc, lsst_lc])

        # Convert to json for submission
        obj_lc = json.loads(lc_df.to_json(orient="records"))

        return txv_id, meta, obj_lc

    def update_active_object(self, txv_id):
        meta = self.db.get(txv_id, scope="objects", collection="meta")
        lc = self.db.get(txv_id, scope="objects", collection="lightcurves")
        # Read in lc to dataframe
        lc_df = pd.DataFrame(lc)

        # Get active days
        active_settings = self.db.get(txv_id, scope="misc", collection="active_settings")

        # See which data sources we need to update now
        update_date = datetime.datetime.fromisoformat(meta["update_date"])
        discovery_date = datetime.datetime.fromisoformat(meta["discovery_date"])

        # IF we have a reporting date, WORK ON LATER
        disc_mjd = Time(discovery_date).mjd
        # Check if we have special min/max mjds, if not use default
        mjd_min = disc_mjd - active_settings["prior_days"]
        mjd_max = disc_mjd + active_settings["active_days"]

        for source_name, source_class in self.data_sources.items():
            # How often does this need to be updated
            update_freq = self.config[source_name]["update_frequency"]
            # Update if past frequency threshold
            if update_date + datetime.timedelta(days=update_freq) >= datetime.datetime.now():
                # Meta only or lightcurve
                if self.config[source_name]["meta_only"]:
                    source_meta = source_class.get_object(object_id=txv_id, ra_deg=meta["ra_deg"], dec_deg=meta["dec_deg"])
                    if source_meta is not None:
                        meta["data_sources"][source_name] = source_meta
                else:
                    # We are going to pull the whole new C
                    source_meta, source_lc = source_class.get_object(object_id=txv_id,
                                                                     ra_deg=meta["ra_deg"],
                                                                     dec_deg=meta["dec_deg"],
                                                                     mjd_min=mjd_min,
                                                                     mjd_max=mjd_max)
                    if source_meta is not None:
                        meta["data_sources"][source_name] = source_meta
                        # Drop all previous source points and replace
                        source_mask = lc_df["survey"] == self.config[source_name]["survey_name"]
                        lc_df = lc_df[~source_mask]
                        # Replace
                        lc_df = pd.concat([lc_df, source_lc])

        # Convert to json for submission
        obj_lc = json.loads(lc_df.to_json(orient="records"))
        return txv_id, meta, obj_lc


    def upsert_object(self, object_id, obj_meta, obj_lc):
        """
        Insert a TarXiv TNS object into the database.

        :param object_id: tarxiv obj name; str
        :param obj_meta: tarxiv obj meta data; dict
        :param obj_lc: tarxiv obj light curve data; dict
        :return: void
        """
        # Before we upsert, we will add a couple lookup fields
        self.db.upsert(object_id, obj_meta, scope="objects", collection="meta")
        self.db.upsert(object_id, obj_lc, scope="objects", collection="lightcurves")

    def get_tns_bulk_df(self):
        # Run request to TNS Server
        status = {"status": "retrieving TNS public object catalog"}
        self.logger.info(status, extra=status)
        get_url = (
            self.tns.site
            + "/system/files/tns_public_objects/tns_public_objects.csv.zip"
        )
        json_data = [
            ("api_key", (None, self.tns.api_key)),
        ]
        headers = {"User-Agent": self.tns.marker}
        response = requests.post(get_url, files=json_data, headers=headers)

        # Write to bytesio and convert to pandas
        with zipfile.ZipFile(io.BytesIO(response.content)) as myzip:
            data = myzip.read(name="tns_public_objects.csv")
        # Get list of TNS names and reporting dates
        tns_df = pd.read_csv(io.BytesIO(data), skiprows=[0])
        # Order in reverse
        sorted_df = tns_df.sort_values("name", ascending=False).reset_index()
        return sorted_df

    def update_bulk(self, include_existing=False):
        """Download bulk TNS public object csv and convert to dataframe.

        Used for bulk back-processing of TNS sources
        :return: full TNS public object dataframe
        """
        # First get whole dataframe
        tns_df = self.get_tns_bulk_df()
        all_tns_ids = tns_df["name"].tolist()

        if not include_existing:
            # Only ingest TNS objects NOT already in the database
            cur_tns_df = self.db.get_all_catalog_objects("tns")
            cur_tns_ids = cur_tns_df["source_id"].tolist()
            missing_ids = list(set(all_tns_ids) - set(cur_tns_ids))
            tns_df = tns_df[tns_df["name"].isin(missing_ids)]

        status = {"status": "processing bulk object list", "n_objs": len(tns_df)}
        self.logger.info(status, extra=status)
        for _, obj in tns_df.iterrows():
            # FRB Naming conventions are weird
            if obj["type"] == "FRB" and obj["name"][:3] != "FRB":
                object_id = "FRB" + obj["name"]
            else:
                object_id = obj["name"]

            # Push to bulk update
            self.producer.produce(topic="internal_tns_bulk", value=object_id, callback=self.acked)

    def daily_update(self):
        # Get all targets still in "active" window for update
        daily_obj_df = self.db.get_all_active_objects("tns")
        daily_tns_ids = daily_obj_df["source_id"].tolist()

        # Also see if there are missing objects
        all_tns_df = self.get_tns_bulk_df()
        all_tns_ids = all_tns_df["name"].tolist()
        cur_tns_df = self.db.get_all_catalog_objects("tns")
        cur_tns_ids = cur_tns_df["source_id"].tolist()

        # Submit missing IDs for bulk pulls
        missing_ids = list(set(all_tns_ids) - set(cur_tns_ids))
        for object_id in missing_ids:
            self.producer.produce(topic="internal_tns_bulk", value=object_id, callback=self.acked)

        # Submit updates to update pipeline
        for object_id in missing_ids:
            self.producer.produce(topic="internal_tns_updates", value=object_id, callback=self.acked)

        # Finish by flushing
        self.producer.flush(timeout=10.0)

    def run_pipeline(self, topic):
        # Connect to kafka consumer
        conf = {'bootstrap.servers': os.environ['TARXIV_KAFKA_HOST'] + ":9092",
                'group.id': "internal_kafka_pipeline",
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': False,
                'max.poll.interval.ms': 3600000,
                'session.timeout.ms': 1200000,
                'heartbeat.interval.ms': 3000}
        self.consumer = Consumer(conf)
        self.consumer.subscribe([topic], on_assign=self.print_assignment)
        # Start up
        status = {"status": "running pipeline"}
        self.logger.info(status, extra=status)

        while self.stop_event is None or self.stop_event.is_set() is False:
            # Get next message
            msg = self.consumer.poll(timeout=1.0)
            # No message, try again
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    status = {"status": "reached end of partition"}
                else:
                    status = {"status": "kafka error", "error": msg.error()}
                self.logger.error(status, extra=status)
            else:
                tns_object_id = msg.value().decode("utf-8")
                try:
                    if topic in ["internal_tns_alerts", "internal_tns_bulk"]:
                        # Get survey information
                        txv_id, obj_meta, obj_lc = self.get_object(tns_object_id)
                        # Get timestamp
                        timestamp = datetime.datetime.now().replace(microsecond=0).isoformat()
                        # Add insertion date to internal meta as well
                        obj_meta["update_date"] = timestamp
                        # Upsert to database
                        self.upsert_object(txv_id, obj_meta, obj_lc)

                        # Submit to hopskotch
                        stream = Stream(self.hop_auth)
                        with stream.open("kafka://kafka.scimma.org/tarxiv.tns", "w") as s:
                            # Additional information for hopskotch
                            s.write(obj_meta)
                            status = {
                                "status": "submitted hopskotch alert",
                                "object_id": tns_object_id,
                            }
                            self.logger.info(status, extra=status)
                        # Submit kafka alert
                        msg = json.dumps(obj_meta).encode('utf-8')
                        self.producer.produce(topic='tns', value=msg, callback=self.acked)
                        self.consumer.commit(asynchronous=False)

                    elif topic in ["internal_tns_updates"]:
                        txv_id, obj_meta, obj_lc = self.update_active_object(tns_object_id)
                        # Get timestamp
                        timestamp = datetime.datetime.now().replace(microsecond=0).isoformat()
                        # Add insertion date to internal meta as well
                        obj_meta["update_date"] = timestamp
                        # Upsert to database
                        self.upsert_object(txv_id, obj_meta, obj_lc)
                        self.consumer.commit(asynchronous=False)

                    else:
                        status = {"status": "bad topic somehow", "topic": topic}
                        self.logger.error(status, extra=status)


                except Exception:
                    stack_trace = traceback.format_exc()
                    status = {
                        "status": "failed pipeline operation",
                        "object_id": tns_object_id,
                        "exception": stack_trace,
                    }
                    self.logger.error(status, extra=status)

        # Close out at end of loop
        self.consumer.close()
        self.producer.flush()

    def acked(self, err, msg):
        if err is not None:
            status = {"status": "failed kafka publish", "msg": msg}
            self.logger.error(status, extra=status)


class ForcedPhotWorker(TarxivModule):
    """Forced phot pipeline to be agnostic of data collection. Also will be run as a multiprocess."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="forced_phot_worker",
            reporting_mode=reporting_mode,
            debug=debug,
        )
        # Collection of all our forced photometry services
        self.forced_phot_services = {
            "atlas": ATLAS(script_name, reporting_mode, debug)
        }

        # Get database
        self.db = TarxivDB("pipeline", script_name, reporting_mode, debug)
        self.consumer = None

    def run_pipeline(self, survey_name, worker_id, stop_event):
        # Connect to kafka consumer
        conf = {'bootstrap.servers': os.environ['TARXIV_KAFKA_HOST'] + ":9092",
                'group.id': "internal_kafka_pipeline_pool",
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': False,
                'max.poll.interval.ms': 3600000,
                'session.timeout.ms': 1200000,
                'heartbeat.interval.ms': 3000}
        self.consumer = Consumer(conf)
        # Topic name will be given by our survey name
        topic = f"internal_{survey_name}_forced_phot"
        self.consumer.subscribe([topic], on_assign=self.print_assignment)
        # Start up
        status = {"status": "running pipeline", "worker_id": worker_id}
        self.logger.info(status, extra=status)

        while stop_event.is_set() is False:
            # Get next message
            msg = self.consumer.poll(timeout=1.0)
            # No message, try again
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    status = {"status": "reached end of partition", "worker_id": worker_id}
                else:
                    status = {"status": "kafka error", "error": msg.error(), "worker_id": worker_id}
                self.logger.error(status, extra=status)
            else:

                try:
                    # This message will give us a tarxiv_id and a survey to run force phot
                    txv_id = msg.value().decode("utf-8")
                    status = {"status": "submitting phot", "object_id": txv_id, "worker_id": worker_id, "survey_name": survey_name}
                    self.logger.info(status, extra=status)
                    self.append_forced_phot(txv_id, survey_name)
                    self.consumer.commit(asynchronous=False)
                except Exception:
                    stack_trace = traceback.format_exc()
                    status = {
                        "status": "failed pipeline operation",
                        "object_id": txv_id,
                        "survey_name": survey_name,
                        "exception": stack_trace,
                        "worker_id": worker_id,
                    }
                    self.logger.error(status, extra=status)

        # Close out at end of loop
        self.consumer.close()

    def append_forced_phot(self, txv_id, survey_name, drop_init=True):
        # Get existing data
        meta = self.db.get(txv_id, scope="objects", collection="meta")
        init_lc = self.db.get(txv_id, scope="objects", collection="lightcurves")
        init_df = pd.DataFrame(init_lc)

        # Cut on time (1 month before DISCOVERY, 6 months after)
        # IF we have a reporting date, WORK ON LATER
        disc_mjd = Time(meta["discovery_date"]).mjd

        # Check if we have a document giving the settings
        active_settings = self.db.get(
            txv_id, scope="misc", collection="active_settings"
        )
        if active_settings is None:
            active_settings = {
                "prior_days": self.config["tns_sources"]["obj_prior_days"],
                "active_days": self.config["tns_sources"]["obj_active_days"],
            }
            self.db.upsert(
                txv_id, active_settings, scope="misc", collection="active_settings"
            )
        # Check if we have special min/max mjds, if not use default
        mjd_min = disc_mjd - active_settings["prior_days"]
        mjd_max = disc_mjd + active_settings["active_days"]

        # Now get atlas data
        ra_deg = meta["ra_deg"]
        dec_deg = meta["dec_deg"]
        # Get survey object
        survey = self.forced_phot_services[survey_name]
        obj_meta, lc_df = survey.get_object(txv_id, ra_deg, dec_deg, mjd_min, mjd_max)

        # If we got something, upsert it
        if obj_meta is not None:
            meta["data_sources"]["atlas"] = obj_meta
            # Drop phot from init lc to
            if drop_init and init_df.empty is False:
                existing = init_df["survey"] == survey_name
                init_df = init_df[~existing]
            # Join new phot
            lc_df = pd.concat([init_df, lc_df])
            obj_lc = lc_df.to_dict(orient="records")

            # Get timestamp
            timestamp = datetime.datetime.now().replace(microsecond=0).isoformat()
            # Add insertion date to internal meta as well
            meta["update_date"] = timestamp
            self.upsert_object(txv_id, meta, obj_lc)


    def print_assignment(self, consumer, partitions):
        # Logging for kafka
        status = {"status": "consumer subscribed", "partitions": partitions}
        self.logger.info(status, extra=status)

    def upsert_object(self, object_id, obj_meta, obj_lc):
        """
        Insert a TarXiv TNS object into the database.

        :param object_id: tarxiv obj name; str
        :param obj_meta: tarxiv obj meta data; dict
        :param obj_lc: tarxiv obj light curve data; dict
        :return: void
        """
        # Before we upsert, we will add a couple lookup fields
        self.db.upsert(object_id, obj_meta, scope="objects", collection="meta")
        self.db.upsert(object_id, obj_lc, scope="objects", collection="lightcurves")


class ForcedPhotPipelineUtil(TarxivModule):

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="forced_phot_util",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Get database
        self.db = TarxivDB("pipeline", script_name, reporting_mode, debug)
        # Get kafka configuration
        conf = {'bootstrap.servers': os.environ['TARXIV_KAFKA_HOST'] + ":9092",
                'delivery.timeout.ms': 10000,
                'queue.buffering.max.messages': 1000000,
                'queue.buffering.max.ms': 5000,
                'batch.num.messages': 100,
                'client.id': socket.gethostname()}
        self.producer = Producer(conf)


    def queue_phot_job(self, txv_id, survey_name):
        topic = f"internal_{survey_name}_forced_phot"
        status = {"status": "submitting phot job", "topic": topic, "txv_id": txv_id}
        self.logger.info(status, extra=status)
        self.producer.produce(topic=topic, value=txv_id, callback=self.acked)
        self.producer.flush()

    def acked(self, err, msg):
        if err is not None:
            status = {"status": "failed kafka publish", "msg": msg}
            self.logger.error(status, extra=status)