from .utils import TarxivModule, deg2sex
from .data_sources import TNS, LSST, ASAS_SN, ZTF, Lasair
from .database import TarxivDB
from .alerts import IMAP
from confluent_kafka import Producer
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
        # Get email interface
        self.gmail = IMAP(script_name, reporting_mode, debug)
        # Get database
        self.db = TarxivDB("pipeline", script_name, reporting_mode, debug)
        # Hopskotch authorization
        self.hop_auth = Auth(
            user=os.environ["TARXIV_HOPSKOTCH_USERNAME"],
            password=os.environ["TARXIV_HOPSKOTCH_PASSWORD"],
        )

        # Get kafka configuration
        conf = {'bootstrap.servers': "pooskaus.ifa.hawaii.edu:9092",
                'delivery.timeout.ms': 10000,
                'queue.buffering.max.messages': 1000000,
                'queue.buffering.max.ms': 5000,
                'batch.num.messages': 100,
                'client.id': socket.gethostname()}
        self.kafka = Producer(conf)

        # Signal handling
        self.stop_event = mp.Event()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, sig, frame):
        self.stop_event.set()
        status = {
            "status": "received exit signal, wait to finish processing",
            "signal": str(sig),
            "frame": str(frame),
        }
        self.logger.info(status, extra=status)

    def get_object(self, object_id, data_source):
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
        # Parse coords
        ra_deg, dec_deg = tns_meta["ra_deg"], tns_meta["dec_deg"]
        ra_hms, dec_dms = deg2sex(ra_deg, dec_deg)
        # Start our meta dict
        meta = {
            "tarxiv_id": txv_id,
            "ra": ra_hms,
            "dec": dec_dms,
            "source": "tns",
            "source_id": object_id,
            "discovery_date": tns_meta["discovery_date"],
            "data_sources": {
                "tns": tns_meta
            }
        }

        # Cut on time (1 month before DISCOVERY, 6 months after)
        # IF we have a reporting date, WORK ON LATER
        disc_mjd = Time(tns_meta["discovery_date"]).mjd
        # Check if we have special min/max mjds, if not use default
        mjd_min = self.db.lookup_in(txv_id,
                                    sub_field="prior_days",
                                    scope="misc",
                                    collection="active_settings")
        if mjd_min is None:
            mjd_min = disc_mjd - self.config["tns"]["obj_prior_days"]
            self.db.set_field(txv_id,
                              key="prior_days", value=self.config["tns"]["obj_prior_days"],
                              scope="misc", collection="active_settings")

        # Now check max
        mjd_max = self.db.lookup_in(txv_id,
                                    sub_field="active_days",
                                    scope="misc",
                                    collection="active_settings")
        if mjd_min is None:
            mjd_max = disc_mjd + self.config["tns"]["obj_active_days"]
            self.db.set_field(txv_id,
                              key="active_days", value=self.config["tns"]["obj_active_days"],
                              scope="misc", collection="active_settings")

        # Now get meta and lightcurves from the surveys
        fink_ztf_meta, ztf_lc = self.ztf.get_object(object_id, ra_deg, dec_deg, mjd_min, mjd_max)
        asas_sn_meta, asas_sn_lc = self.asas_sn.get_object(object_id, ra_deg, dec_deg, mjd_min, mjd_max)
        fink_lsst_meta, lsst_lc = self.lsst.get_object(object_id, ra_deg, dec_deg, mjd_min, mjd_max)
        # Get additional meta from the survey
        lasair_meta = self.lasair.get_object(object_id, ra_deg, dec_deg)

        # Add data sources to meta dict
        if lasair_meta is not None:
            meta["data_sources"]["sherlock"] = lasair_meta
        if fink_ztf_meta is not None:
            meta["data_sources"]["fink_ztf"] = fink_ztf_meta
        if asas_sn_meta is not None:
            meta["data_sources"]["asas_sn"] = asas_sn_meta
        if fink_lsst_meta is not None:
            meta["data_sources"]["fink_lsst"] = fink_lsst_meta

        # Collate lightcurves and add peak mag measurements to schema
        lc_df = pd.concat([ztf_lc, asas_sn_lc, lsst_lc])

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

        if not include_existing:
            # Only ingest TNS objects NOT already in the database
            db_object_ids = self.db.get_all_objects()
            object_ids = list(set(tns_df["name"].tolist()) - set(db_object_ids))
            tns_df = tns_df[tns_df["name"].isin(object_ids)]

        status = {"status": "processing bulk object list", "n_objs": len(tns_df)}
        self.logger.info(status, extra=status)
        for _, obj in tns_df.iterrows():
            if self.stop_event.is_set():
                break
            # FRB Naming conventions are weird
            if obj["type"] == "FRB" and obj["name"][:3] != "FRB":
                object_id = "FRB" + obj["name"]
            else:
                object_id = obj["name"]
            try:
                # Get survey information
                object_id, obj_meta, obj_lc = self.get_object(object_id)
                # Add reporting date
                obj_meta["reporting_date"] = obj["time_received"]
                # Upsert to database
                self.upsert_object(object_id, obj_meta, obj_lc)

            except Exception:
                stack_trace = traceback.format_exc()
                self.logger.error({
                    "status": "failed pipeline operation",
                    "object_id": object_id,
                    "exception": stack_trace,
                })

    def daily_update(self):
        # Get all targets still in "active" window for update
        daily_objects = self.db.get_all_active_objects(
            active_days=self.config["tns"]["obj_active_days"]
        )
        # First get whole dataframe
        tns_df = self.get_tns_bulk_df()
        # Pull TNS info and update
        for object_id in daily_objects:
            try:
                if self.stop_event.is_set():
                    break
                # Get survey information
                obj_meta, obj_lc = self.get_object(object_id)
                # Add reporting date
                try:
                    obj = tns_df[tns_df["name"] == object_id].iloc[0].to_dict()
                    obj_meta["reporting_date"] = obj["time_received"]
                except Exception:
                    status = {
                        "status": "no cooresponding reporting date",
                        "object_id": object_id,
                    }
                    self.logger.error(status, extra=status)

                # Get timestamp
                timestamp = datetime.datetime.now().isoformat()
                # Add insertion date to internal meta as well
                obj_meta["update_date"] = timestamp

                # Upsert to database
                self.upsert_object(object_id, obj_meta, obj_lc)

            except Exception:
                stack_trace = traceback.format_exc()
                self.logger.error({
                    "status": "failed pipeline operation",
                    "object_id": object_id,
                    "exception": stack_trace,
                })

    def run_pipeline(self):

        # Start monitoring notices
        self.gmail.monitor_notices()

        # Run logic loop
        while not self.stop_event.is_set():
            # Get next message
            alerts = self.gmail.poll(timeout=1)

            # Repeat if none
            if not alerts:
                continue

            # Each result contains message and list of objects
            for object_id in alerts:
                try:
                    # Get survey information
                    obj_meta, obj_lc = self.get_object(object_id)

                    # Get timestamp
                    timestamp = datetime.datetime.now().isoformat()
                    # Add insertion date to internal meta as well
                    obj_meta["update_date"] = timestamp

                    # Upsert to database
                    self.upsert_object(object_id, obj_meta, obj_lc)

                    stream = Stream(self.hop_auth)
                    # Submit to hopskotch
                    with stream.open("kafka://kafka.scimma.org/tarxiv.tns", "w") as s:
                        # Additional information for hopskotch
                        # hop_msg = {}
                        # update_meta | {"title": "TNS Public Alert"}
                        s.write(obj_meta)
                        status = {
                            "status": "submitted hopskotch alert",
                            "object_id": object_id,
                        }
                        self.logger.info(status, extra=status)

                    # Submit kafka alert
                    msg = json.dumps(obj_meta).encode('utf-8')
                    self.kafka.produce(topic='tns', value=msg, callback=self.acked)

                except Exception:
                    stack_trace = traceback.format_exc()
                    self.logger.error({
                        "status": "failed pipeline operation",
                        "object_id": object_id,
                        "exception": stack_trace,
                    })
    def acked(self, err, msg):
        if err is not None:
            status = {"status": "failed kafka publish", "msg": msg}
            self.logger.error(status, extra=status)