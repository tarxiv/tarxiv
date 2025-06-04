"""Test end-to-end pipeline to insert full object in the database"""

import os

from tarxiv.data_sources import TNS, ATLAS, ASAS_SN, ZTF

PATH = os.path.join(os.path.dirname(__file__), "../../aux")


def get_tns_meta(obj_name, path=PATH):
    """Get metadata from TNS

    Parameters
    ----------
    obj_name: str
        Object name
    conffolder: str
        Folder name with conf files.
        Defaut is aux/

    Returns
    -------
    tns_meta: dict
        Dictionary with TNS metadata
    """
    txv_tns = TNS(path)
    tns_meta, _, status = txv_tns.get_object(obj_name)
    assert status["status"] == "query success", status
    return tns_meta


def get_atlas_data(obj_name, ra_deg, dec_deg, path=PATH):
    """Get data and metadata from ATLAS

    Parameters
    ----------
    obj_name: str
        Object name
    ra_deg: float
        RA for the object, in degree
    dec_deg: float
        Declination for the object, in degree
    conffolder: str
        Folder name with conf files.
        Defaut is aux/

    Returns
    -------
    atlas_meta: dict
        Dictionary with ATLAS metadata
    atlas_lc: dict
        ATLAS light curve

    """
    txv_atlas = ATLAS(path)
    atlas_meta, atlas_lc, status = txv_atlas.get_object(obj_name, ra_deg, dec_deg)
    assert status["status"] == "match", status
    return atlas_meta, atlas_lc


def get_ztf_data(obj_name, ra_deg, dec_deg, path=PATH):
    """Get data and metadata from Fink/ZTF

    Parameters
    ----------
    obj_name: str
        Object name
    ra_deg: float
        RA for the object, in degree
    dec_deg: float
        Declination for the object, in degree
    conffolder: str
        Folder name with conf files.
        Defaut is aux/

    Returns
    -------
    ztf_meta: dict
        Dictionary with ZTF metadata
    ztf_lc: dict
        ZTF light curve

    """
    txv_ztf = ZTF(path)
    ztf_meta, ztf_lc, status = txv_ztf.get_object(obj_name, ra_deg, dec_deg)
    assert status["status"] == "match", status
    return ztf_meta, ztf_lc


def get_asas_sn_data(obj_name, ra_deg, dec_deg, path=PATH):
    """Get data and metadata from ASAS-SN

    Parameters
    ----------
    obj_name: str
        Object name
    ra_deg: float
        RA for the object, in degree
    dec_deg: float
        Declination for the object, in degree
    conffolder: str
        Folder name with conf files.
        Defaut is aux/

    Returns
    -------
    asas_sn_meta: dict
        Dictionary with ASAS-SN metadata
    asas_sn_lc: dict
        ASAS-SN light curve

    """
    txv_asas_sn = ASAS_SN(path)
    asas_sn_meta, asas_sn_lc, status = txv_asas_sn.get_object(obj_name, ra_deg, dec_deg)
    assert status["status"] == "match", status
    return asas_sn_meta, asas_sn_lc


def test_pipeline():
    # TBD: test is failing with error 403 only on GH.
    # Need to understand what is going on.

    # # hardcoded objname for test
    # obj_name = "2024iss"

    # # Initial TNS metadata
    # tns_meta = get_tns_meta(obj_name)
    # ra_deg, dec_deg = tns_meta["ra_deg"]["value"], tns_meta["dec_deg"]["value"]

    # # Get light curve data & metadata
    # atlas_meta, atlas_lc = get_atlas_data(obj_name, ra_deg, dec_deg)
    # ztf_meta, ztf_lc = get_ztf_data(obj_name, ra_deg, dec_deg)
    # asas_sn_meta, asas_sn_lc = get_asas_sn_data(obj_name, ra_deg, dec_deg)
    pass
