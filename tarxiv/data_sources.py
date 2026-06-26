"""Pull and process lightcurves"""

from .utils import (
    TarxivModule,
    SurveyMetaMissingError,
    SurveyLightCurveMissingError,
    precision,
)

from pyasassn.client import SkyPatrolClient
from antares_client.search import cone_search
from astropy.time import Time
from astropy.coordinates import Angle, SkyCoord
import astropy.units as u
from collections import OrderedDict
from lasair import lasair_client
from alerce import Alerce
import numpy as np
import pandas as pd
import requests
import warnings
import traceback
import json
import time
import io
import re
import os


def summarize_lc_mags(obj_meta, lc_df):
    # We are interested in peak mag, most recent detection, most recent non detection, and recent change
    peak_mags = []
    recent_dets = []
    recent_nondets = []

    for filter_name, grp_df in lc_df.groupby("filter"):
        detections = grp_df[grp_df["detection"] == 1].copy()
        non_detections = grp_df[grp_df["detection"] == 0].copy()
        if len(detections) > 0:
            # Peak mag info
            peak_row = detections.loc[detections["mag"].idxmin()]
            peak_mag = {
                "filter": filter_name,
                "limit": precision(float(peak_row["mag"]), 8),
                "date": Time(peak_row["mjd"], format="mjd", scale="utc").isot.replace(
                    "T", " "
                ),
            }
            peak_mags.append(peak_mag)
            # For mag_rate first get most recent non detection if one exists
            if len(non_detections) > 0:
                # Reset detection index
                earliest_det = detections.loc[detections["mjd"].idxmin()]
                # Get all the non detections before our earliest detection with deeper limit
                valid_non_dets = non_detections[
                    (non_detections["mjd"] <= earliest_det["mjd"])
                    & (non_detections["limit"] >= earliest_det["mag"])
                ].copy()
                # Append to data frame if we have any
                if len(valid_non_dets) > 0:
                    valid_non_dets["mag"] = valid_non_dets["limit"]
                    recent_non_det = valid_non_dets.loc[valid_non_dets["mjd"].idxmax()]
                    recent_non_det = recent_non_det.to_frame().T

                    with warnings.catch_warnings():
                        warnings.simplefilter(action="ignore", category=FutureWarning)
                        detections = pd.concat(
                            [detections, recent_non_det], ignore_index=True
                        )

            # Remove duplcate MJDs if exist (avoid divide by zero)
            detections_non_dup = detections.drop_duplicates(
                subset=["mjd"], keep="first"
            )
            # Now sort and get the rate
            sorted_detections = detections_non_dup.sort_values("mjd")

            if "atlas" in obj_meta.keys():
                # Get nights then group
                sorted_detections["night"] = sorted_detections["mjd"].astype(int)
                night_sorted_detections = sorted_detections.groupby('night')[["night", "mag"]].mean()

                # Get mag rate for each point in the filter_wise group
                night_sorted_detections["mag_rate"] = -(
                    night_sorted_detections["mag"].diff() / night_sorted_detections["night"].diff()
                )
                # Replace nan
                night_sorted_detections["mag_rate"] = night_sorted_detections["mag_rate"].replace(
                    np.nan, None
                )
                # Get the most recent row and append the information
                recent_row = night_sorted_detections.loc[night_sorted_detections["night"].idxmax()]

                # Put jd back in recent row
                recent_row["mjd"] = sorted_detections.loc[sorted_detections["mjd"].idxmax()]["mjd"]

            else:
                # Get mag rate for each point in the filter_wise group
                sorted_detections["mag_rate"] = -(
                    sorted_detections["mag"].diff() / sorted_detections["mjd"].diff()
                )
                # Replace nan
                sorted_detections["mag_rate"] = sorted_detections["mag_rate"].replace(
                    np.nan, None
                )
                # Get the most recent row and append the information
                recent_row = sorted_detections.loc[sorted_detections["mjd"].idxmax()]

            recent_det = {
                "filter": filter_name,
                "mag": precision(float(peak_row["mag"]), 8),
                "mag_rate": precision(recent_row["mag_rate"], 6),
                "date": Time(recent_row["mjd"], format="mjd", scale="utc").isot.replace(
                    "T", " "
                ),
            }
            recent_dets.append(recent_det)
        # Now get the most recent non-detection value
        if len(non_detections) > 0:
            # Recent non-detection info
            nondet_row = non_detections.loc[non_detections["mjd"].idxmax()]
            recent_nondet = {
                "filter": filter_name,
                "mag": precision(float(nondet_row["limit"]), 8),
                "date": Time(nondet_row["mjd"], format="mjd", scale="utc").isot.replace(
                    "T", " "
                ),
            }
            recent_nondets.append(recent_nondet)
    # Append to meta and return
    if recent_dets:
        obj_meta["latest_detections"] = recent_dets
    if recent_nondets:
        obj_meta["latest_non_detections"] = recent_nondets
    if peak_mags:
        obj_meta["peak_mags"] = peak_mags

    return obj_meta

class ATLAS(TarxivModule):
    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="atlas",
            reporting_mode=reporting_mode,
            debug=debug,
        )
        # Validate TOKEN
        response = requests.post(url=f"{self.config['atlas']['url']}/api-token-auth/",
                                 data={
                                     'username': os.environ['TARXIV_ATLAS_USER'],
                                     'password': os.environ['TARXIV_ATLAS_PASS']})
        if response.status_code == 200:
            token = response.json()['token']
            self.headers = {'Authorization': f'Token {token}', 'Accept': 'application/json'}
        else:
            status = {"status": "atlas falling star validation error", "error": response.json()}
            self.logger.error(status, extra=status)
            sys.exit(1)

    def get_object(self, object_id, ra_deg, dec_deg, mjd_min, mjd_max):
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"object_id": object_id}
        try:
            start_time = time.time()
            task_url = None
            while not task_url:
                with requests.Session() as s:
                    response = s.post(url=f"{self.config['atlas']['url']}/queue/", headers=self.headers,
                                      data={'ra': ra_deg, 'dec': dec_deg, 'mjd_min': mjd_min, 'mjd_max': mjd_max})
                    if response.status_code == 201:  # successfully queued
                        task_url = response.json()['url']

                    elif response.status_code == 429:  # throttled
                        message = response.json()["detail"]
                        t_sec = re.findall(r'available in (\d+) seconds', message)
                        t_min = re.findall(r'available in (\d+) minutes', message)
                        if t_sec:
                            waittime = int(t_sec[0])
                        elif t_min:
                            waittime = int(t_min[0]) * 60
                        else:
                            waittime = 10
                        time.sleep(waittime)
                    else:
                        status = {"status": "atlas falling star validation error", "error": response.json()}
                        self.logger.error(status, extra=status)
                        raise SurveyMetaMissingError

            result_url = None
            while not result_url:
                with requests.Session() as s:
                    resp = s.get(task_url, headers=self.headers)
                    if resp.status_code == 200:  # HTTP OK
                        if resp.json()['finishtimestamp']:
                            result_url = resp.json()['result_url']
                            break

                        time.sleep(10)
                    else:
                        status = {"status": "atlas falling star job error", "error": response.json()}
                        self.logger.error(status, extra=status)
                        raise SurveyMetaMissingError

            with requests.Session() as s:
                textdata = s.get(result_url, headers=self.headers).text
            # Record time for logs
            status["job_time"] = int(time.time() - start_time)
            # Here is our phot df
            lc_df = pd.read_csv(io.StringIO(textdata.replace("###", "")), sep=r"\s+")
            # Get unit
            lc_df["camera"] = lc_df["Obs"].str[:2]
            lc_df["survey"] = "atlas"
            # Put in dummy meta
            meta = {
                "atlas": "dummy value",
                "ra_deg": precision(float(lc_df.iloc[0].RA), 6),
                "dec_deg": precision(float(lc_df.iloc[0].Dec), 6),
            }

            # Rename columns
            lc_df = lc_df.rename(columns={
                "MJD": "mjd",
                "m": "mag",
                "dm": "mag_err",
                "mag5sig": "limit",
                "maj": "fwhm",
                "F": "filter",
            })
            # Make mags positive
            lc_df["mag"] = np.sign(lc_df['limit']) * lc_df['mag'].abs()

            # Calculate detections
            lc_df["detection"] = np.where(lc_df["limit"] > lc_df["mag"], 0, 1)
            # If we have no detections, dont bother
            if not lc_df["detection"].any():
                raise SurveyLightCurveMissingError
            # Parse down columns
            lc_df = lc_df[
                [
                    "mjd",
                    "mag",
                    "mag_err",
                    "limit",
                    "fwhm",
                    "filter",
                    "detection",
                    "camera",
                    "survey",
                ]
            ]
            # Append information on recent detections and peak mags, etc
            meta = summarize_lc_mags(obj_meta=meta, lc_df=lc_df)
            del meta["atlas"]
            # Update
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"

        except SurveyLightCurveMissingError:
            status["status"] += "|no light curve"
        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
                })

        self.logger.info(status, extra=status)
        return meta, lc_df


class ASAS_SN(TarxivModule):  # noqa: N801
    """Interface to ASAS-SN SkyPatrol."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="asas-sn",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Also need ASAS-SN client
        self.client = SkyPatrolClient(verbose=False)

    def get_object(self, object_id, ra_deg, dec_deg, mjd_min, mjd_max, radius=5):
        """Get ASAS-SN Lightcurve curve from coordinates using cone_search.

        :param object_id: name of object (used for logging); str
        :param ra_deg: right ascension in degrees; float
        :param dec_deg: declination in degrees; float
        :param radius: radius in arcseconds; int
        return asas-sn metadata and lightcurve dataframe
        """
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"object_id": object_id}

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
            if lcs is None or len(lcs) == 0:
                raise SurveyMetaMissingError
            # Get meta
            nearest = lcs.catalog_info.iloc[0]
            nearest_id = nearest["asas_sn_id"]
            meta = {
                "object_id": str(nearest_id),
                "source_id_name": "asas_sn_id",
                "ra_deg": float(nearest["ra_deg"]),
                "dec_deg": float(nearest["dec_deg"]),
                "cross_match_distance": float(nearest["angular_dist"]),
                "catalog_sources": list(nearest["catalog_sources"]),
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
            lc_df = lc_df.rename({"phot_filter": "filter"}, axis=1)
            # Do not return data from bad images
            lc_df = lc_df[lc_df["quality"] != "B"]
            # Flag non-detections
            lc_df["detection"] = np.where(lc_df["mag_err"] > 99, 0, 1)
            lc_df["mag"] = np.where(lc_df["mag_err"] > 99, np.nan, lc_df["mag"])
            lc_df["mag_err"] = np.where(lc_df["mag_err"] > 99, np.nan, lc_df["mag_err"])
            # Set survey
            lc_df["survey"] = "asas-sn"
            # Change name
            lc_df = lc_df.rename(columns={"camera": "camera"})
            # Reorder cols
            lc_df = lc_df[
                [
                    "mjd",
                    "mag",
                    "mag_err",
                    "limit",
                    "fwhm",
                    "filter",
                    "detection",
                    "camera",
                    "survey",
                ]
            ]
            # Now let us cut the mjd of this
            lc_df = lc_df[(mjd_min <= lc_df["mjd"]) & (lc_df["mjd"] <= mjd_max)]
            # Append information on recent detections and peak mags, etc
            meta = summarize_lc_mags(obj_meta=meta, lc_df=lc_df)
            # Update
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"
        except SurveyLightCurveMissingError:
            status["status"] += "|no light curve"
        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


class ZTF(TarxivModule):
    """Interface to ZTF Fink broker."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="fink_ztf",
            reporting_mode=reporting_mode,
            debug=debug,
        )

    def get_object(self, object_id, ra_deg, dec_deg, mjd_min, mjd_max, radius=5):
        """Get ZTF Lightcurve from coordinates using cone_search.

        :param object_id: name of object (used for logging); str
        :param ra_deg: right ascension in degrees; float
        :param dec_deg: declination in degrees; float
        :param radius: radius in arcseconds; int
        return ztf metadata and lightcurve dataframe
        """
        # Set meta and lc_df empty to start
        meta, lc_df = None, pd.DataFrame()
        # Initial status
        status = {"object_id": object_id}
        try:
            # Hit FINK API
            result = requests.post(
                f"{self.config['fink_ztf']['url']}/api/v1/conesearch",
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
                f"{self.config['fink_ztf']['url']}/api/v1/objects",
                json={
                    "objectId": ztf_name,
                    "withupperlim": True,
                    "output-format": "json",
                },
            )
            # check status
            if result.status_code != 200 or result.json() == []:
                raise SurveyLightCurveMissingError

            # Get most recent line of data for meta
            df = pd.DataFrame(result.json())
            meta_line = df.iloc[df["i:jd"].idxmax()].dropna().to_dict()
            meta_line = {k[2:]: v for k, v in meta_line.items()}
            meta_columns = [
                "classification",
                'DR3Name',
                'anomaly_score',
                'blazar_stats_m0',
                'blazar_stats_m1',
                'blazar_stats_m2',
                'cdsxmatch',
                'gaiaClass',
                'gaiaVarFlag',
                'gcvs',
                'is_transient',
                'mangrove_2MASS_name',
                'mangrove_HyperLEDA_name',
                'mangrove_ang_dist',
                'mangrove_lum_dist',
                'mulens',
                'rf_kn_vs_nonkn',
                'rf_snia_vs_nonia',
                'slsn_score',
                'snn_sn_vs_all',
                'snn_snia_vs_nonia',
                'spicy_class',
                'spicy_id',
                'tns',
                'vsx',
                'x3hsp',
                'x4lac',
            ]
            meta = {
                k: v
                for k, v in meta_line.items()
                if k in meta_columns
                if v not in [None, "nan", "None"]
            }
            meta["object_id"] = ztf_name
            meta["source_id_name"] = "objectId"

            # Lightcurve columns and values
            cols = {
                "i:magpsf": "mag",
                "i:sigmapsf": "mag_err",
                "i:fid": "filter",
                "i:jd": "jd",
                "i:diffmaglim": "limit",
                "d:tag": "detection",
                "i:fwhm": "fwhm",
            }
            filter_map = {"1": "g", "2": "r", "3": "i"}
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
            lc_df["camera"] = "main"
            lc_df["survey"] = "ztf"

            # Reorder cols
            lc_df = lc_df[
                [
                    "mjd",
                    "mag",
                    "mag_err",
                    "limit",
                    "fwhm",
                    "filter",
                    "detection",
                    "camera",
                    "survey",
                ]
            ]

            # Now let us cut the mjd of this
            lc_df = lc_df[(mjd_min <= lc_df["mjd"]) & (lc_df["mjd"] <= mjd_max)]
            # Append information on recent detections and peak mags, etc
            meta = summarize_lc_mags(obj_meta=meta, lc_df=lc_df)
            # Report count
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"
        except SurveyLightCurveMissingError:
            status["status"] += "|no light curve"

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


class TNS(TarxivModule):
    """Interface to Transient Name Server API."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="tns",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Set attributes
        self.site = self.config["tns"]["url"]
        self.api_key = os.getenv("TARXIV_TNS_API_KEY", "")

        # Create marker
        tns_marker_dict = {
            "tns_id": os.getenv("TARXIV_TNS_ID", 0),
            "type": self.config["tns"]["type"],
            "name": self.config["tns"]["name"],
        }
        self.marker = "tns_marker" + json.dumps(tns_marker_dict, separators=(",", ":"))

    def get_object(self, object_id):
        """Get TNS metadata for a given object name.

        :param object_id: TNS object name, e.g., 2025xxx; str
        :return: metadata dictionary
        """
        # Set meta empty to start
        meta = None
        # Initial status
        status = {"object_id": object_id}
        try:
            # Wait to avoid rate limiting
            time.sleep(self.config["tns"]["rate_limit"])
            # Run request to TNS server
            get_url = self.site + "/api/get/object"
            headers = {"User-Agent": self.marker}
            obj_request = OrderedDict([
                ("objid", ""),
                ("objname", object_id),
                ("photometry", "0"),
                ("spectra", "0"),
            ])
            get_data = {"api_key": self.api_key, "data": json.dumps(obj_request)}
            response = requests.post(get_url, headers=headers, data=get_data)
            if response.status_code != 200:
                raise SurveyMetaMissingError(response.content)

            # Convert to json
            response_json = response.json()
            if "data" not in response_json.keys():
                raise SurveyMetaMissingError("no 'data' in response")

            # Reduce meta to what we want
            status["status"] = "query success"
            result = response_json["data"]
            meta = {
                "object_id": result["objname"],
                "source_id_name": "objname",
                "ra_deg": result["radeg"],
                "dec_deg": result["decdeg"],
                "ra_hms": result["ra"],
                "dec_dms": result["dec"],
                "object_type": result["object_type"]["name"],
                "redshift": result["redshift"],
                "hostname": result["hostname"],
                "discovery_date": result["discoverydate"].replace(" ", "T"),
                "reporting_group": result["reporting_group"]["group_name"],
                "discovery_data_source": result["discovery_data_source"]["group_name"],
            }
        except SurveyMetaMissingError:
            status["status"] = "no match"

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })
        self.logger.info(status, extra=status)
        return meta


class Lasair(TarxivModule):
    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="lasair",
            reporting_mode=reporting_mode,
            debug=debug,
        )
        # Get client
        api_key = os.getenv("TARXIV_LASAIR_TOKEN", "")
        self.client = lasair_client(api_key, endpoint=self.config["lasair"]["url"])

    def get_object(self, object_id=None, ra_deg=None, dec_deg=None):
        status = {"object_id": object_id}
        meta = None
        try:
            # Run a sherlock query on this information
            result = self.client.sherlock_position(ra=ra_deg, dec=dec_deg)
            if len(result["crossmatches"]) == 0:
                raise SurveyMetaMissingError("no 'crossmatches' in response")

            # Get first crossmatch
            meta = result["crossmatches"][0]
            # Rename fields
            meta["ra_deg"] = meta["raDeg"]
            meta["dec_deg"] = meta["decDeg"]
            meta["redshift"] = meta["z"]
            del meta["transient_object_id"], meta["raDeg"], meta["decDeg"], meta["z"]

            status["status"] = "query success"

        except SurveyMetaMissingError:
            status["status"] = "no match"

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta


class LSST(TarxivModule):
    """Survey adapter for LSST alerts pulled through Lasair."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="fink_lsst",
            reporting_mode=reporting_mode,
            debug=debug,
        )

    def get_object(self, object_id, ra_deg, dec_deg, mjd_min, mjd_max, radius=5):
        status = {"object_id": object_id}
        meta = None
        lc_df = pd.DataFrame()
        try:
            # Get the diaObjectId for the alert(s) within a circle on the sky
            r0 = requests.post(
                "https://api.lsst.fink-portal.org/api/v1/conesearch",
                json={
                    "ra": str(ra_deg),
                    "dec": str(dec_deg),
                    "radius": str(radius),
                    "columns": "r:diaObjectId,r:midpointMjdTai",
                },
            )
            # Get list of objects
            objects = r0.json()
            if not objects:
                raise SurveyMetaMissingError

            # Get nearest
            nearest = objects[
                np.argmin([obj["v:separation_degree"] for obj in objects])
            ]

            # Query fink
            r1 = requests.post(
                f"{self.config['fink_lsst']['url']}/api/v1/sources",
                json={
                    "diaObjectId": str(nearest["r:diaObjectId"]),
                    "output-format": "json",
                },
            )

            # Load and rename
            df = pd.read_json(io.BytesIO(r1.content))
            # Get meta line from most recent measurement
            meta_line = df.iloc[df["r:midpointMjdTai"].idxmax()].dropna().to_dict()
            meta = {}
            meta["object_id"] = nearest["r:diaObjectId"]
            meta["source_id_name"] = "diaObjectId"
            meta["ra_deg"] = ra_deg
            meta["dec_deg"] = dec_deg
            # Put all the rest of the meta in
            for k, v in meta_line.items():
                if k[0] == "f" and v != "nan" and "tns" not in k and "version" not in k:
                    meta[k[2:]] = v

            # Format output in a DataFrame
            df["mag"] = -2.5 * np.log10(df["r:psfFlux"]) + 31.4
            df["mag_err"] = np.abs(1.0857 * df["r:psfFluxErr"] / df["r:psfFlux"])
            # Specific to lightcurves
            df["limit"] = None
            df["camera"] = "main"
            df["detection"] = 1

            df = df.rename(
                {"r:midpointMjdTai": "mjd", "r:band": "filter", "r:snr": "snr"}, axis=1
            )
            lc_df = df[
                [
                    "mjd",
                    "mag",
                    "mag_err",
                    "filter",
                    "snr",
                    "detection",
                    "limit",
                    "camera",
                ]
            ]
            lc_df["survey"] = "lsst"

            # Now let us cut the mjd of this
            lc_df = lc_df[(mjd_min <= lc_df["mjd"]) & (lc_df["mjd"] <= mjd_max)]
            # Append information on recent detections and peak mags, etc
            meta = summarize_lc_mags(obj_meta=meta, lc_df=lc_df)
            # Report count
            status["lc_count"] = len(lc_df)

        except SurveyMetaMissingError:
            status["status"] = "no match"
        except SurveyLightCurveMissingError:
            status["status"] += "|no light curve"

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })

        self.logger.info(status, extra=status)
        return meta, lc_df


class ANTARES(TarxivModule):
    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="antares",
            reporting_mode=reporting_mode,
            debug=debug,
        )
    def get_object(self, object_id=None, ra_deg=None, dec_deg=None, radius=5):
        status = {"object_id": object_id}
        meta = None
        try:
            center = SkyCoord(ra=ra_deg, dec=dec_deg, unit="deg")
            radius = Angle(radius * u.arcsec)
            result = list(cone_search(center, radius))
            if not result:
                raise SurveyMetaMissingError
            # Get meta from our result object
            meta = dict()
            locus = result[0]
            meta["object_id"] = locus.locus_id
            meta["ra_deg"] = locus.ra
            meta["dec_deg"] = locus.dec
            hit = SkyCoord(locus.ra, locus.dec, unit="deg")
            meta["cross_match_distance"] = precision(float(center.separation(hit).arcsec), 6)
            meta["tags"] = locus.tags

        except SurveyMetaMissingError:
            status["status"] = "no match"

        except Exception as e:
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })
        self.logger.info(status, extra=status)
        return meta


class AlerceMod(TarxivModule):
    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="alerce",
            reporting_mode=reporting_mode,
            debug=debug,
        )
        self.client = Alerce()

    def get_object(self, object_id=None, ra_deg=None, dec_deg=None, radius=5):
        # Check both ztf and lsst
        status = {"object_id": object_id}
        meta = {}

        try:
            # Now get lsst
            lsst_df = self.client.query_objects(ra=ra_deg, dec=dec_deg, radius=radius, survey="lsst")
            if not lsst_df.empty:
                # Get object
                lsst_id = lsst_df.iloc[0].to_dict()["oid"]
                meta["lsst_object_id"] = str(lsst_id)

                # Get probabilities
                result = self.client.query_probabilities(oid=lsst_id, survey="lsst")
                prob_df = pd.DataFrame(result)
                if not prob_df.empty:
                    prob_df["probability"] = prob_df["probability"].replace(np.nan, None)
                    prob_info = prob_df[
                        (prob_df["classifier_name"] == self.config["alerce"]["lsst_classifier"])
                        & (prob_df["ranking"] == 1)]
                    # Might not have info for this classifier
                    if not prob_info.empty:
                        prob_info = prob_info.iloc[0].to_dict()
                        # Add to meta
                        meta["lsst_classifier"] = prob_info["classifier_name"] if type(prob_info["classifier_name"]) == str else prob_info["classifier_name"][0]
                        meta["lsst_class_name"] = prob_info["class_name"] if type(prob_info["class_name"]) == str else prob_info["class_name"][0]
                        meta["lsst_class_prob"] = prob_info["probability"] if type(prob_info["probability"]) == float else prob_info["probability"][0]
                        meta["lsst_class_version"] = prob_info["classifier_version"]

            # Now get ZTF
            ztf_df = self.client.query_objects(ra=ra_deg, dec=dec_deg, radius=radius, survey="ztf")
            if not ztf_df.empty:
                # Get object
                ztf_id = ztf_df.iloc[0].to_dict()["oid"]
                meta["ztf_object_id"] = str(ztf_id)

                # Get probabilities
                result = self.client.query_probabilities(oid=ztf_id, survey="ztf")
                prob_df = pd.DataFrame(result)
                if not prob_df.empty:
                    prob_df["probability"] = prob_df["probability"].replace(np.nan, None)
                    prob_info = prob_df[
                        (prob_df["classifier_name"] == self.config["alerce"]["ztf_classifier"])
                        & (prob_df["ranking"] == 1)]
                    # Might not have info for this classifier
                    if not prob_info.empty:
                        prob_info = prob_info.iloc[0].to_dict()
                        # Add to meta
                        meta["ztf_classifier"] = prob_info["classifier_name"] if type(prob_info["classifier_name"]) == str else prob_info["classifier_name"][0]
                        meta["ztf_class_name"] = prob_info["class_name"] if type(prob_info["class_name"]) == str else prob_info["class_name"][0]
                        meta["ztf_class_prob"] = prob_info["probability"] if type(prob_info["probability"]) == float else prob_info["probability"][0]
                        meta["ztf_class_version"] = prob_info["classifier_version"]

                # Get featurs
                result = self.client.query_features(oid=ztf_id, survey="ztf")
                feat_df = pd.DataFrame(result)
                if not feat_df.empty:
                    # Reduce to SPM features
                    feat_df = feat_df[feat_df["name"].str.startswith("SPM")]
                    # Replace nans
                    feat_df["value"] = feat_df["value"].replace(np.nan, None)
                    # Band lookup
                    bands = {1: "g", 2: "r", 3: "i"}
                    feat_df["filter"] = feat_df["fid"].map(bands)

                    meta["features"] = []

                    for _, row in feat_df.iterrows():
                        feat = {"name": row["name"], "value": row["value"], "survey": "ZTF", "filter": row["filter"]}
                        meta["features"].append(feat)
                    meta["ztf_feature_version"] = feat_df.iloc[0]["version"]

            # If we have nothing then raise error
            if not meta:
                meta = None
                raise SurveyMetaMissingError

        except SurveyMetaMissingError:
            status["status"] = "no match"

        except Exception as e:
            meta = None
            status.update({
                "status": "encontered unexpected error",
                "error_message": str(e),
                "details": traceback.format_exc(),
            })
        self.logger.info(status, extra=status)
        return meta


if __name__ == "__main__":
    """Execute the test suite"""
    import sys
    import doctest

    sys.exit(doctest.testmod()[0])
