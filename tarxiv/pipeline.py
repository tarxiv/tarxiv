from .utils import TarxivModule, clean_meta, SurveyMetaMissingError
from .data_sources import TNS, ATLAS, ASAS_SN, ZTF
from .database import TarxivDB
from astropy.time import Time
import pandas as pd

class TNSPipeline(TarxivModule):
    def __init__(self,  *args, **kwargs):
        super().__init__("pipeline", *args, **kwargs)
        # Create survey objects
        self.tns = TNS(*args, **kwargs)
        self.atlas = ATLAS(*args, **kwargs)
        self.ztf = ZTF(*args, **kwargs)
        self.asas_sn = ASAS_SN(*args, **kwargs)
        # Get database
        self.db = TarxivDB("tns", "pipeline", *args, **kwargs)


    def get_object(self, obj_name):
        """
        Queries TNS for an object then finds all associated survey data.
        :param obj_name: TNS object name (e.g. 2024iss); str
        :return: meta data and light curve data dictionaries
        """
        # Get initial info from TNS
        tns_meta, _ = self.tns.get_object(obj_name)
        if tns_meta is None:
            raise SurveyMetaMissingError("invalid TNS object name")
        ra_deg, dec_deg = tns_meta['ra_deg']["value"], tns_meta['dec_deg']["value"]
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
        # Cut on time (1 month before discovery, 6 months after)
        disc_mjd = Time(obj_meta['discovery_date']['value']).mjd
        lc_df = lc_df[((disc_mjd - lc_df['mjd']) <= 30) & ((lc_df['mjd'] - disc_mjd) <= 60)]
        # Add peak magnitudes to meta
        obj_meta = self.tns.meta_add_peak_mags(obj_meta, lc_df)
        obj_meta = clean_meta(obj_meta)
        # Convert to json for submission
        obj_lc = lc_df.to_dict(orient="records")

        return obj_meta, obj_lc

    def upsert_object(self, obj_name, obj_meta, obj_lc):
        """
        Insert a TarXiv TNS object into the database.
        :param obj_name: tarxiv obj name; str
        :param obj_meta: tarxiv obj meta data; dict
        :param obj_lc: tarxiv obj light curve data; dict
        :return: void
        """
        self.db.upsert(obj_name, obj_meta, collection="objects")
        self.db.upsert(obj_name, obj_meta, collection="lightcurves")