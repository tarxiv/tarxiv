"""Pull and process lightcurves"""
from .utils import TarxivModule, SurveyMetaMissingError, SurveyLightCurveMissingError

from pyasassn.client import SkyPatrolClient
from astropy.time import Time
from collections import OrderedDict
import numpy as np
import pandas as pd
import requests
import traceback
import json
import time
import io
import re
import os


def append_dynamic_values(obj_meta, obj_lc_df):
    """Once we have all the object dataframes collated; find peak mag for each filter and append to object_meta.

    :param obj_meta: object meta schema; dict
    :param obj_lc_df: light curve dataframe; pd.DataFrame
    :return:object_meta; updated object meta dictionary
    """
    if len(obj_lc_df) == 0:
        return {"status": "empty lc"}, obj_meta
    # We are interested in peak mag, most recent detection, most recent non detection, and recent change
    peak_mags = []
    recent_dets = []
    recent_nondets = []
    recent_changes = []
    status = {"status": "appending dynamic values"}
    try:
        # Get derived mag information by filter
        filter_df = obj_lc_df.groupby("filter")
        for filter_name, filter_grp_df in filter_df:
            if len(filter_grp_df[filter_grp_df["detection"] == 1]) > 0:
                # Peak mag info
                peak_row = filter_grp_df.loc[filter_grp_df[filter_grp_df["detection"] == 1]["mag"].idxmin()]
                peak_mag = {
                    "filter": filter_name,
                    "value": peak_row["mag"],
                    "date": Time(peak_row["mjd"], format="mjd", scale="utc").isot.replace("T", " "),
                    "source": peak_row["survey"],
                }
                peak_mags.append(peak_mag)
                # Recent detection info
                det_row = filter_grp_df.loc[filter_grp_df[filter_grp_df["detection"] == 1]["mjd"].idxmax()]
                recent_det = {
                    "filter": filter_name,
                    "value": det_row["mag"],
                    "date": Time(det_row["mjd"], format="mjd", scale="utc").isot.replace("T", " "),
                    "source": det_row["survey"],
                }
                recent_dets.append(recent_det)
                # Get recent change
                sorted_grp_df = filter_grp_df.sort_values(by="mjd")
                sorted_grp_df["change"] = sorted_grp_df["mag"].diff()
                sorted_grp_df["change"] = np.where(sorted_grp_df["change"] > 0, "increasing", "fading")
                recent_row = sorted_grp_df.loc[sorted_grp_df["mjd"].idxmax()]
                recent_change = {
                    "filter": filter_name,
                    "value": recent_row["change"],
                    "date": Time(recent_row["mjd"], format="mjd", scale="utc").isot.replace("T", " "),
                    "source": recent_row["survey"]
                }
                recent_changes.append(recent_change)
            if len(filter_grp_df[filter_grp_df["detection"] == 0]) > 0:
                # Recent non-detection info
                nondet_row = filter_grp_df.loc[filter_grp_df[filter_grp_df["detection"] == 0]["mjd"].idxmax()]
                recent_nondet = {
                    "filter": filter_name,
                    "value": nondet_row["limit"],
                    "date": Time(nondet_row["mjd"], format="mjd", scale="utc").isot.replace("T", " "),
                    "source": nondet_row["survey"],
                }
                recent_nondets.append(recent_nondet)
                status = {"status": "sucessfully appended dynamic values!"}
    except Exception as e:
        status ={
            "status": "encontered unexpected error",
            "error_message": str(e),
            "details": traceback.format_exc(),
        }

    # Append and return
    obj_meta["peak_mag"] = peak_mags
    obj_meta["latest_detection"] = recent_dets
    obj_meta["latest_nondetection"] = recent_nondets
    obj_meta["latest_change"] = recent_changes
    return status, obj_meta


class Survey(TarxivModule):
    """Base class to interact with a Tarxiv survey or data source."""

    def __init__(self, *args, **kwargs):
        """Read in data for survey sources from config directory"""
        super().__init__(*args, **kwargs)

        # Read in schema sources
        schema_sources = os.path.join(self.config_dir, "sources.json")
        with open(schema_sources) as f:
            self.schema_sources = json.load(f)

    def get_object(self, *args, **kwargs):
        """Query the survey for object at a given set of coordinates.

        Must return metadata dict containing at least
        one survey designation, and any additional meta
                e.g. {"identifiers" : [{"name": ATLAS25XX, "source": 3}, ...],
                     {"meta": {"redshift": {"value": 0.003, "source": 8},
                               "hostname": [{"value": "NCGXXXX", "source": 9},
                                            {"value": "2MASS XXXXX", "source": 10}]
                               ...}}
        Also return lightcurve dataframe with columns [mjd, mag, mag_err, limit, filter, unit, survey],
            mjd: modified julian date,
            mag: magnitude,
            mag_err: magnitude error,
            limit: 5-sigma limiting magnitude,
            filter: bandpass filter,
            unit: telescope or camera for given measurement (if survey only has one unit, use "main")
            survey: survey name.

        :return: survey_meta; dict (None if no results), survey_lc; DataFrame (empty df if no results)
        """
        raise NotImplementedError(
            "each survey must implement their own logic to get meta/lightcurve"
        )

    def update_object_meta(self, obj_meta, survey_meta):
        """Update the object meta schema with data from the survey meta returned by get_object.

        :param obj_meta: existing object meta schema; dict
        :param survey_meta: survey meta returned from get_object; dict
        :return:updated object meta dictionary
        """
        # Only update if we get returned object
        if survey_meta is not None:
            # Append sources to schema
            for source in self.config[self.module]["associated_sources"]:
                obj_meta["sources"].append(self.schema_sources[source])

            for field, meta in survey_meta.items():
                if type(meta) is list:
                    for item in meta:
                        obj_meta[field].append(item)
                else:
                    obj_meta[field].append(meta)

        return obj_meta


class ASAS_SN(Survey):  # noqa: N801
    """Interface to ASAS-SN SkyPatrol."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="asas-sn",
                         reporting_mode=reporting_mode,
                         debug=debug)

        # Also need ASAS-SN client
        self.client = SkyPatrolClient(verbose=False)

    def get_object(self, obj_name, ra_deg, dec_deg, radius=15):
        """Get ASAS-SN Lightcurve curve from coordinates using cone_search.

        :param obj_name: name of object (used for logging); str
        :param ra_deg: right ascension in degrees; float
        :param dec_deg: declination in degrees; float
        :param radius: radius in arcseconds; int
        return asas-sn metadata and lightcurve dataframe
        """
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"obj_name": obj_name}

        try:
            # Query client
            query = (
                f"WITH sources AS                "
                f"  (                            "
                f"      SELECT                   "
                f"          asas_sn_id,          "
                f"          ra_deg,              "
                f"          dec_deg,             "
                f"          catalog_sources,     "
                f"          DISTANCE(ra_deg, dec_deg, {ra_deg}, {dec_deg}) AS angular_dist "
                f"     FROM master_list          "
                f"  )                            "
                f"SELECT *                       "
                f"FROM sources                   "
                f"WHERE angular_dist <= ARCSEC({radius}) "
                f"ORDER BY angular_dist ASC      "
            )

            query = re.sub(r"(\s+)", " ", query)
            lcs = self.client.adql_query(query, download=True)
            if lcs is None:
                raise SurveyMetaMissingError
            # Get meta
            nearest = lcs.catalog_info.iloc[0]
            nearest_id = nearest["asas_sn_id"]
            meta = {
                "identifiers": [{"name": str(nearest_id), "source": "asas-sn"}],
                "ra_deg": [{"value": nearest["ra_deg"], "source": "asas-sn"}],
                "dec_deg": [{"value": nearest["dec_deg"], "source": "asas-sn"}],
            }
            # Log
            status.update({"status": "match", "id": str(nearest_id)})
            # Sometimes we have meta but no database object (will fix later)
            if lcs.data is None or len(lcs.data) == 0:
                raise SurveyLightCurveMissingError
            # Get LC
            lc_df = lcs[nearest_id].data
            lc_df["mjd"] = lc_df.apply(
                lambda row: Time(row["jd"], format="jd").mjd, axis=1
            )
            lc_df = lc_df.rename({"phot_filter": "filter", "camera": "unit"}, axis=1)
            # Do not return data from bad images
            lc_df = lc_df[lc_df["quality"] != "B"]
            # Flag non-detections
            lc_df["detection"] = np.where(lc_df["mag_err"] > 99, 0, 1)
            lc_df["mag"] = np.where(lc_df["mag_err"] > 99, np.nan, lc_df["mag"])
            lc_df["mag_err"] = np.where(lc_df["mag_err"] > 99, np.nan, lc_df["mag_err"])
            lc_df["survey"] = "asas-sn"
            # Reorder cols
            lc_df = lc_df[["mjd", "mag", "mag_err", "limit", "fwhm", "filter", "detection", "unit", "survey"]]
            # Update
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"
        except SurveyLightCurveMissingError:
            status["status"].append("|no light curve")
        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


class ZTF(Survey):
    """Interface to ZTF Fink broker."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="ztf",
                         reporting_mode=reporting_mode,
                         debug=debug)

    def get_object(self, obj_name, ra_deg, dec_deg, radius=15):
        """Get ZTF Lightcurve from coordinates using cone_search.

        :param obj_name: name of object (used for logging); str
        :param ra_deg: right ascension in degrees; float
        :param dec_deg: declination in degrees; float
        :param radius: radius in arcseconds; int
        return ztf metadata and lightcurve dataframe
        """
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"obj_name": obj_name}
        try:
            # Hit FINK API
            result = requests.post(
                f"{self.config["fink_url"]}/api/v1/conesearch",
                json={
                    "ra": ra_deg,
                    "dec": dec_deg,
                    "radius": radius,
                    "columns": "i:objectId",
                },
            )
            # check status
            if result.status_code != 200:
                raise SurveyMetaMissingError

            # get data for the match
            matches = [val["i:objectId"] for val in result.json()]

            if len(matches) == 0:
                raise SurveyMetaMissingError

            # Show ztf name
            ztf_name = matches[0]
            status.update({"status": "match", "id": ztf_name})

            # Query
            result = requests.post(
                f"{self.config["fink_url"]}/api/v1/objects",
                json={"objectId": ztf_name, "withupperlim": True, "output-format": "json"},
            )
            # check status
            if result.status_code != 200 or result.json() == []:
                raise SurveyLightCurveMissingError

            # Metadata on each line of photometry, we only take first row (d prefix are non-phot)
            result_meta = result.json()[0]
            meta = {
                "identifiers": [{"name": ztf_name, "source": "ztf"}],
                "ra_deg": [{"value": result_meta["i:ra"], "source": "ztf"}],
                "dec_deg": [{"value": result_meta["i:dec"], "source": "ztf"}],
            }

            meta["host_name"] = []
            if (
                "d:mangrove_2MASS_name" in result_meta.keys()
                and result_meta["d:mangrove_2MASS_name"] != "None"
            ):
                host_name = {"name": result_meta["d:mangrove_2MASS_name"], "source": "magrove"}
                meta["host_name"].append(host_name)
            if (
                "d:mangrove_2MASS_name" in result_meta.keys()
                and result_meta["d:mangrove_HyperLEDA_name"] != "None"
            ):
                host_name = {
                    "name": result_meta["d:mangrove_HyperLEDA_name"],
                    "source": "magrove",
                }
                meta["host_name"].append(host_name)
            if len(meta["host_name"]) == 0:
                del meta["host_name"]

            # Lightcurve columns and values
            cols = {
                "i:magpsf": "mag",
                "i:sigmapsf": "mag_err",
                "i:fid": "filter",
                "i:jd": "jd",
                "i:diffmaglim": "limit",
                "d:tag": "detection",
                "i:fwhm": "fwhm"
            }
            filter_map = {"1": "g", "2": "R", "3": "i"}
            detection_map = {"valid": 1, "badquality": -1, "upperlim": 0}
            # Push into DataFrame
            lc_df = pd.read_json(io.BytesIO(result.content))
            lc_df = lc_df.rename(cols, axis=1)
            lc_df = lc_df[list(cols.values())]
            lc_df["mjd"] = lc_df.apply(
                lambda row: Time(row["jd"], format="jd").mjd, axis=1
            )
            lc_df["filter"] = lc_df["filter"].astype(str).map(filter_map)
            lc_df["detection"] = lc_df["detection"].astype(str).map(detection_map)
            # Throw out bad quality
            lc_df = lc_df[lc_df["detection"] >= 0]
            # JD now unneeded
            lc_df = lc_df.drop("jd", axis=1)
            # Add unit/survey columns
            lc_df["unit"] = "main"
            lc_df["survey"] = "ztf"
            # Reorder cols
            lc_df = lc_df[["mjd", "mag", "mag_err", "limit", "fwhm", "filter", "detection", "unit", "survey"]]
            # Report count
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"
        except SurveyLightCurveMissingError:
            status["status"].append("|no light curve")

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


class ATLAS(Survey):
    """Interface to ATLAS Transient Web Server."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="atlas",
                         reporting_mode=reporting_mode,
                         debug=debug)

    def get_object(self, obj_name, ra_deg, dec_deg, radius=15):
        """Get ATLAS Lightcurve from coordinates using cone_search.

        :param obj_name: name of object (used for logging); str
        :param ra_deg: right ascension in degrees; float
        :param dec_deg: declination in degrees; float
        :param radius: radius in arcseconds; int
        return ztf metadata and lightcurve dataframe
        """
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"obj_name": obj_name}
        try:
            # First run cone search to get id
            # Set up the headers with the token
            headers = {
                "Authorization": "Token {}".format(os.getenv("TARXIV_ATLAS_TOKEN", "")),
            }
            cone_res = requests.post(
                f"{self.config["atlas_url"]}/cone/",
                {
                    "ra": ra_deg,
                    "dec": dec_deg,
                    "radius": radius,
                    "requestType": "nearest",
                },
                headers=headers,
            )
            if cone_res.status_code != 200:
                raise AssertionError("{}".format(cone_res.content))

            if "object" not in cone_res.json().keys():
                raise SurveyMetaMissingError(
                    "ATLAS error code {}".format(cone_res.status_code)
                )

            # Get atlas id and query for data
            atlas_id = cone_res.json()["object"]
            status.update({"status": "match", "id": atlas_id})
            # Get light curve
            curve_res = requests.get(
                f"{self.config["atlas_url"]}/objects/",
                {"objects": str(atlas_id)},
                headers=headers,
            )
            if curve_res.status_code == 504:
                # handle timeout
                pass
            elif curve_res.status_code != 200:
                raise SurveyLightCurveMissingError(
                    "ATLAS error code {}: {}".format(
                        curve_res.status_code, curve_res.content
                    )
                )

            # Contains meta and lc
            result = curve_res.json()[0]

            # Insert meta data
            meta = {
                "identifiers": [{"name": result["object"]["id"], "source": "atlas"}],
                "ra_deg": [{"value": result["object"]["ra"], "source": "atlas"}],
                "dec_deg": [{"value": result["object"]["dec"], "source": "atlas"}],
            }

            if result["object"]["atlas_designation"] is not None:
                atlas_name = {
                    "name": result["object"]["atlas_designation"],
                    "source": "atlas_twb",
                }
                meta["identifiers"].append(atlas_name)
            # Add sherlock crossmatch if exists
            if result["sherlock_crossmatches"]:
                result["sherlock"] = result["sherlock_crossmatches"][0]
                if result["sherlock"]["z"] is not None:
                    meta["redshift"] = {"value": result["sherlock"]["z"], "source": "sherlock"}

            # DETECTIONS
            det_df = pd.DataFrame(result["lc"])[
                ["mjd", "mag", "magerr", "mag5sig", "filter", "expname", "major"]
            ]
            det_df.columns = ["mjd", "mag", "mag_err", "limit", "filter", "expname", "fwhm"]
            det_df["detection"] = 1
            # NON DETECTIONS
            non_df = pd.DataFrame(result["lcnondets"])[
                    ["mjd", "mag5sig", "filter", "expname"]
            ]
            non_df.columns = ["mjd", "limit", "filter", "expname"]
            non_df["mag"] = np.nan
            non_df["mag_err"] = np.nan
            non_df["fwhm"] = np.nan
            non_df["detection"] = 0
            lc_df = pd.concat([det_df, non_df])

            # Add a column to record which ATLAS unit the value was taken from
            lc_df["unit"] = lc_df["expname"].str[:3]
            lc_df = lc_df.drop("expname", axis=1)
            lc_df["survey"] = "atlas"
            # Reorder cols
            lc_df = lc_df[["mjd", "mag", "mag_err", "limit", "fwhm", "filter", "detection", "unit", "survey"]]
            # Report count
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"
        except SurveyLightCurveMissingError:
            status["status"] += "|no light curve"

        except Exception as e:
            status.update({
                "status": "encountered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


class TNS(Survey):
    """Interface to Transient Name Server API."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="tns",
                         reporting_mode=reporting_mode,
                         debug=debug)

        # Set attributes
        self.site = self.config["tns"]["site"]
        self.api_key = os.getenv("TARXIV_TNS_API_KEY", "")

        # Create marker
        tns_marker_dict = {
            "tns_id": os.getenv("TARXIV_TNS_ID", 0),
            "type": self.config["tns"]["type"],
            "name": self.config["tns"]["name"],
        }
        self.marker = "tns_marker" + json.dumps(tns_marker_dict, separators=(",", ":"))

    def get_object(self, obj_name):
        """Get TNS metadata for a given object name.

        :param obj_name: TNS object name, e.g., 2025xxx; str
        :return: metadata dictionary and empty dataframe (since we are not pulling lightcurve)
        """
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"obj_name": obj_name}
        try:
            # Wait to avoid rate limiting
            time.sleep(self.config["tns"]["rate_limit"])
            # Run request to TNS server
            get_url = self.site + "/api/get/object"
            headers = {"User-Agent": self.marker}
            obj_request = OrderedDict([
                ("objid", ""),
                ("objname", obj_name),
                ("photometry", "0"),
                ("spectra", "0"),
            ])
            get_data = {"api_key": self.api_key, "data": json.dumps(obj_request)}
            response = requests.post(get_url, headers=headers, data=get_data)

            if response.status_code != 200:
                status["explanation"] = response.content
                raise SurveyMetaMissingError
            response_json = response.json()

            # Meta
            if "data" not in response_json.keys():
                raise SurveyMetaMissingError

            # Reduce meta to what we want
            status["status"] = "query success"
            result = response_json["data"]
            meta = {
                "identifiers": {"name": result["objname"], "source": "tns"},
                "ra_deg": {"value": result["radeg"], "source": "tns"},
                "dec_deg": {"value": result["decdeg"], "source": "tns"},
                "ra_hms": {"value": result["ra"], "source": "tns"},
                "dec_dms": {"value": result["dec"], "source": "tns"},
                "object_type": [
                    {"value": result["name_prefix"], "source": "tns"},
                    {"value": result["object_type"]["name"], "source": "tns"},
                ],
                "discovery_date": {"value": result["discoverydate"], "source": "tns"},
                "reporting_group": {
                    "value": result["reporting_group"]["group_name"],
                    "source": "tns",
                },
                "discovery_data_source": {
                    "value": result["discovery_data_source"]["group_name"],
                    "source": "tns",
                },
            }
            if result["redshift"] is not None:
                meta["redshift"] = {"value": result["redshift"], "source": "tns"}
            if result["hostname"] is not None:
                meta["host_name"] = {"value": result["hostname"], "source": "tns"}

        except SurveyMetaMissingError:
            status["status"] = "failed to get TNS metadata"

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


if __name__ == "__main__":
    """Execute the test suite"""
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])
