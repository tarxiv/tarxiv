# Misc. utility functions
from logstash_async.handler import AsynchronousLogstashHandler
from logstash_async.handler import LogstashFormatter
from decimal import Decimal, ROUND_HALF_UP
import logging
import yaml
import sys
import os

# Reporting mode flags
PRINT = 1
LOGFILE = 2
DATABASE = 4


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
            log_file = os.path.join(self.config["log_dir"], script_name + ".log")
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
