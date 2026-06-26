# Misc. utility functions

from logstash_async.handler import AsynchronousLogstashHandler
from logstash_async.handler import LogstashFormatter
from decimal import Decimal, ROUND_HALF_UP
from astropy.coordinates import SkyCoord
from paste.translogger import TransLogger
import astropy.units as u
import cherrypy
import logging
import string
import yaml
import sys
import os
import re


# Reporting mode flags
PRINT = 1
LOGFILE = 2
DATABASE = 4


def serve_wsgi(app, host, port, debug, logger):
    """Serve a WSGI callable on the CherryPy/cheroot production server.

    :param app: WSGI callable (e.g. a Flask app or Dash's underlying server).
    :param host: host address to bind; str.
    :param port: port to bind; int.
    :param debug: enable dev-only features (autoreload, screen logging); bool.
    :param logger: module logger for status reporting.
    """
    status = {"status": "starting WSGI server", "host": host, "port": port, "debug": debug}
    logger.info(status, extra=status)
    # Mount the WSGI callable on the root directory, with Paste access logging.
    cherrypy.tree.graft(TransLogger(app), "/")
    # Configure the web server; autoreload and screen logging are dev-only.
    cherrypy.config.update({
        "engine.autoreload.on": debug,
        "log.screen": debug,
        "server.socket_host": host,
        "server.socket_port": port,
    })
    # Start the CherryPy WSGI web server and block.
    cherrypy.engine.start()
    cherrypy.engine.block()


class TarxivModule:
    """Base class for all TarXiv modules to ensure unified logging and configuration."""

    def __init__(self, script_name, module, reporting_mode, debug=False):
        """Read in configuration file and create module logger

        :param module: name of module; str
        :param debug: sets logging level to DEBUG.
        """
        # Set module
        self.module = module
        # Read in config
        self.config_dir = os.environ.get(
            "TARXIV_CONFIG_DIR", os.path.join(os.path.dirname(__file__), "../aux")
        )
        self.config_file = os.path.join(self.config_dir, "config.yml")
        with open(self.config_file) as stream:
            self.config = yaml.safe_load(stream)
        print(f"Config loaded from {self.config_file}")

        # Logger
        self.logger = logging.getLogger(self.module)
        # Set log level
        self.debug = debug
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Print log to stdout
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Print to system standard out
        if PRINT & reporting_mode:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Log to file
        if LOGFILE & reporting_mode:
            log_dir = os.getenv("TARXIV_HOST_LOG_DIR", "")
            log_file = os.path.join(log_dir, script_name + ".log")
            handler = logging.FileHandler(log_file)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Config logstash
        # Submit to logstash
        if DATABASE & reporting_mode:
            handler = AsynchronousLogstashHandler(
                host=self.config["logstash_host"],
                port=self.config["logstash_port"],
                # certfile=self.config['logstash_cert'],
                database_path=None,
            )
            formatter = LogstashFormatter({
                "module": self.module,
                "script": script_name,
            })
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Status
        status = {"status": "initializing"}
        self.logger.info(status, extra=status)


class SurveyMetaMissingError(Exception):
    """TBD"""

    pass


class SurveyLightCurveMissingError(Exception):
    """TBD"""

    pass


class TarxivPipelineError(Exception):
    """TBD"""

    pass


def clean_meta(obj_meta):
    """Removes any empty fields from object meta schema

    :param obj_meta: object meta schema; dict
    :return: clean schema; dict
    """
    obj_meta = {k: v for k, v in obj_meta.items() if v != []}
    # obj_meta = {k: v[0] for k, v in obj_meta.items() if len(v) == 1}
    return obj_meta


def precision(x, p):
    return (
        float(Decimal(x * 10**p).quantize(0, ROUND_HALF_UP) / 10**p)
        if x is not None
        else None
    )


def int_to_alphanumeric(num, n):
    """Converts int to n-significant alphanumeric string (base 36)."""
    chars = string.digits + string.ascii_uppercase  # 0-9A-Z
    base = len(chars)
    if num == 0:
        return chars[0].rjust(n, "0")
    result = []
    while num > 0:
        num, rem = divmod(num, base)
        result.append(chars[rem])
    # Pad to significant length n
    return "".join(reversed(result)).rjust(n, "0")[:n]


def deg2sex(ra_deg, dec_deg, arcsec_precision=4):
    c = SkyCoord(ra=ra_deg * u.degree, dec=dec_deg * u.degree)
    return c.to_string("hmsdms", sep=":", precision=arcsec_precision).split()


def camel_to_snake(text: str) -> str:
    # Match lowercase/digit followed by an uppercase letter and split them with an underscore
    str1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", str1).lower()
