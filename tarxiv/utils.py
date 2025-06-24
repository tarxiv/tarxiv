# Misc. utility functions
import logging
import yaml
import sys
import os

class TarxivModule:
    """Base class for all TarXiv modules to ensure unified logging and configuration."""

    def __init__(self, module, log_name, debug=False):
        """Read in configuration file and create module logger

        :param module: name of module; str
        :param debug: sets logging level to DEBUG.
        """
        # Set module
        self.module = module
        # Read in config
        self.config_dir = os.environ["TARXIV_CONFIG_DIR"]
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
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # If set in config, log to file
        if self.config["log_dir"]:
            log_file = os.path.join(self.config["log_dir"], log_name + ".log")
            handler = logging.FileHandler(log_file)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Status
        self.logger.info({"status": "initializing", "module": self.module})


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
