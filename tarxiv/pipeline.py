import hop

from .utils import TarxivModule, clean_meta
from .data_sources import TNS, ATLAS, ASAS_SN, ZTF, append_dynamic_values
from .database import TarxivDB
from .alerts import IMAP
from astropy.time import Time
from hop.auth import Auth
from hop import Stream
import pandas as pd
import requests
import datetime
import deepdiff
import zipfile
import signal
import json
import io
import os

class TNSPipeline(TarxivModule):
    """Pipeline for TNS data processing and storage."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="tns_pipeline",
                         reporting_mode=reporting_mode,
                         debug=debug)

        # Create survey objects
        self.tns = TNS(script_name, reporting_mode, debug)
        self.atlas = ATLAS(script_name, reporting_mode, debug)
        self.ztf = ZTF(script_name, reporting_mode, debug)
        self.asas_sn = ASAS_SN(script_name, reporting_mode, debug)
        # Get email interface
        self.gmail = IMAP(script_name, reporting_mode, debug)
        # Get database
        self.db = TarxivDB("tns", "pipeline", script_name, reporting_mode, debug)
        # Hopskotch authorization
        self.hop_auth = Auth(username=os.environ["TARXIV_HOPSKOTCH_USERNAME"],
                             password=os.environ["TARXIV_HOPSKOTCH_PASSWORD"])

    def get_object(self, obj_name):
        """
        Queries TNS for an object then finds all associated survey data.

        :param obj_name: TNS object name (e.g. 2024iss); str
        :return: metadata and light curve data dictionaries
        """
        # Get data if exists already for comparison
        init_meta = self.db.get(obj_name, "objects")

        # Get initial info from TNS
        tns_meta, _ = self.tns.get_object(obj_name)
        # Return empty dicts
        if tns_meta is None:
            return {}, {}
        ra_deg, dec_deg = tns_meta["ra_deg"]["value"], tns_meta["dec_deg"]["value"]
        # Now get meta and lightcurves from the surveys
        atlas_meta, atlas_lc = self.atlas.get_object(obj_name, ra_deg, dec_deg)
        ztf_meta, ztf_lc = self.ztf.get_object(obj_name, ra_deg, dec_deg)
        asas_sn_meta, asas_sn_lc = self.asas_sn.get_object(obj_name, ra_deg, dec_deg)

        # Gent a new schema
        schema = self.db.get_object_schema()
        # Now we populate schema with our survey information
        obj_meta = self.tns.update_object_meta(schema, tns_meta)
        obj_meta = self.atlas.update_object_meta(obj_meta, atlas_meta)
        obj_meta = self.ztf.update_object_meta(obj_meta, ztf_meta)
        obj_meta = self.asas_sn.update_object_meta(obj_meta, asas_sn_meta)
        # Collate lightcurves and add peak mag measurements to schema
        lc_df = pd.concat([atlas_lc, ztf_lc, asas_sn_lc])
        if len(lc_df) > 0:
            # Sometimes we get bad negative mag/limit values (make positive when over 10 for sanity)
            lc_df['mag'] = lc_df['mag'].apply(lambda val: abs(val) if abs(val) > 10 else val)
            lc_df['limit'] = lc_df['limit'].apply(lambda val: abs(val) if abs(val) > 10 else val)

        # Cut on time (1 month before discovery, 6 months after)
        disc_mjd = Time(obj_meta["discovery_date"][0]["value"]).mjd
        if len(lc_df) > 0:
            lc_df = lc_df[((disc_mjd - lc_df["mjd"]) <= self.config['tns']['obj_prior_days'])
                          & ((lc_df["mjd"] - disc_mjd) <= self.config['tns']['obj_active_days'])]
        # Add peak magnitudes to meta
        status, obj_meta = append_dynamic_values(obj_meta, lc_df)
        status.update({"obj_name": obj_name})
        self.logger.info(status, extra=status)
        obj_meta = clean_meta(obj_meta)
        # Convert to json for submission
        obj_lc = json.loads(lc_df.to_json(orient="records"))

        # Now run a quick comparison of the initial metadata to new metadata for updates
        if init_meta is not None:            # Check to see which fields have been updated
            diff = deepdiff.DeepDiff(init_meta, obj_meta, ignore_order=True, view='tree')
            # We only care about the following fields
            relevant_fields = ['identifiers', 'object_type', 'host_name', 'redshift', 'latest_detection', 'latest_change']
            update_meta = {field: [] for field in relevant_fields}
            if 'values_changed' in diff.keys():
                for field in diff['values_changed']:
                    field_name = field.get_root_key()
                    if field_name in relevant_fields:
                        update_meta[field_name].append(field.t2)
            if 'iterable_item_added' in diff.keys():
                for field in diff['iterable_item_added']:
                    field_name = field.get_root_key()
                    if field_name in relevant_fields:
                        update_meta[field_name].append(field.t2)
            if 'dictionary_item_added' in diff.keys():
                for field in diff['dictionary_item_added']:
                    field_name = field.get_root_key()
                    if field_name in relevant_fields:
                        update_meta[field_name] += field.t2
            # Remove blank updates
            update_meta = {field: value for field, value in update_meta.items() if value}

            update_meta['status'] = "updated_entry"
        else:
            update_meta = obj_meta
            update_meta['status'] = "new_entry"

        return obj_meta, obj_lc, update_meta

    def upsert_object(self, obj_name, obj_meta, obj_lc):
        """
        Insert a TarXiv TNS object into the database.

        :param obj_name: tarxiv obj name; str
        :param obj_meta: tarxiv obj meta data; dict
        :param obj_lc: tarxiv obj light curve data; dict
        :return: void
        """
        self.db.upsert(obj_name, obj_meta, collection="objects")
        self.db.upsert(obj_name, obj_lc, collection="lightcurves")

    def download_bulk(self, include_existing=False):
        """Download bulk TNS public object csv and convert to dataframe.

        Used for bulk back-processing of TNS sources
        :return: full TNS public object dataframe
        """
        # Run request to TNS Server
        status = {"status": "retrieving TNS public object catalog"}
        self.logger.info(status, extra=status)
        get_url = (
            self.tns.site + "/system/files/tns_public_objects/tns_public_objects.csv.zip"
        )
        json_data = [
            ("api_key", (None, self.tns.api_key)),
        ]
        headers = {"User-Agent": self.tns.marker}
        response = requests.post(get_url, files=json_data, headers=headers)

        # Write to bytesio and convert to pandas
        with zipfile.ZipFile(io.BytesIO(response.content)) as myzip:
            data = myzip.read(name="tns_public_objects.csv")
        # Get list of TNS names
        all_obj_names = pd.read_csv(io.BytesIO(data), skiprows=[0])['name'].tolist()

        if not include_existing:
            # Only ingest TNS objects NOT already in the database
            db_obj_names = self.db.get_all_objects()
            obj_names = list(set(all_obj_names) - set(db_obj_names))
        else:
            # Process all TNS objects
            obj_names = all_obj_names

        status = {"status": "processing bulk object list", "n_objs": len(obj_names)}
        self.logger.info(status, extra=status)
        for obj_name in obj_names:
            # Get survey information
            obj_meta, obj_lc, _ = self.get_object(obj_name)
            # Upsert to database
            self.upsert_object(obj_name, obj_meta, obj_lc)

    def daily_update(self):
        # Get all targets still in "active" window for update
        daily_objects = self.db.get_all_active_objects(active_days=self.config['tns']['obj_active_days'])
        # Pull TNS info and update
        for obj_name in daily_objects:
            # Get survey information
            obj_meta, obj_lc, update_meta = self.get_object(obj_name)
            # Upsert to database
            self.upsert_object(obj_name, obj_meta, obj_lc)
            # Get timestamp
            timestamp = datetime.datetime.now().isoformat()
            update_meta["timestamp"] = timestamp
            stream = Stream(self.hop_auth)
            # Submit to hopskotch
            with stream.open("kafka://kafka.scimma.org/tarxiv.tns", "w") as s:
                s.write(update_meta)

    def run_pipeline(self):
        # Set signals
        signal.signal(signal.SIGINT, handler=self.signal_handler)
        # signal.signal(signal.SIGTERM, handler=self.signal_handler)

        # Start monitoring notices
        self.gmail.monitor_notices()

        # Run logic loop
        while True:
            # Get next message
            alerts = self.gmail.poll(timeout=1)

            # Repeat if none
            if not alerts:
                continue

            # Each result contains message and list of objects
            for obj_name in alerts:
                # Get survey information
                obj_meta, obj_lc, update_meta = self.get_object(obj_name)
                # Upsert to database
                self.upsert_object(obj_name, obj_meta, obj_lc)
                # Get timestamp
                timestamp = datetime.datetime.now().isoformat()
                update_meta["timestamp"] = timestamp
                stream = Stream(self.hop_auth)
                # Submit to hopskotch
                with stream.open("kafka://kafka.scimma.org/tarxiv.tns", "w") as s:
                    s.write(update_meta)

    def signal_handler(self, sig, frame):
        status = {"status": "received exit signal", "signal": str(sig), "frame": str(frame)}
        self.logger.info(status, extra=status)
        os._exit(1)
