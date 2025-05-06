# This is the settings module of pyirk (backend). It is assumed to take precedence over django settings.

import os
import sys
import logging

import platformdirs

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

logger = logging.getLogger("pyirk")



# load config.toml via platformdirs
# this file can be created by pyirk --bootstrap-config

config_path = platformdirs.user_config_dir("pyirk")
config_file = os.path.join(config_path, "config.toml")

CONF = {}

if os.path.isfile(config_file):
    try:
        with open(config_file, "rb") as f:
            CONF = tomllib.load(f)
    except Exception as e:
        msg = (
            f"Warning: Could not load existing config file {config_file}. Maybe syntax error?\n"
            f"Original exception ({type(e)}):\n\n{str(e)}"
        )
        logger.warning(msg)


DEBUG = False


# for now we only support a subset of languages with wich the authors are familiar
# if you miss a language, please consider contributing
SUPPORTED_LANGUAGES = ["en", "de", "fr", "it", "es"]
# https://en.wikipedia.org/wiki/IETF_language_tag


# TODO: This should be specifyable for every module
DEFAULT_DATA_LANGUAGE = "en"


ACKREP_DATA_REL_PATH = "../ackrep/ackrep_data"
ACKREP_DATA_UT_REL_PATH = "../ackrep/ackrep_data_for_unittests"


# get absolute path of directory of this file
source_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEMPLATE_PATH = os.path.join(source_dir, "templates")

# assume package is installed via `pip install -e` then the repo root is two levels up
PYIRK_REPO_ROOT_PATH = os.path.dirname(os.path.dirname(source_dir))

BUILTINS_URI = "irk:/builtins"
URI_SEP = "#"

# todo: some time in the future pyirk should become indendent from the OCSE
# for now it is convenient to have the URI stored here
OCSE_URI = "irk:/ocse/0.2"


# this is relevant to look for pyirk-data to load (specified by a configuration file)
BASE_DIR = os.path.abspath(os.getenv("PYIRK_BASE_DIR", "./"))


# this might be changed by unittests to trigger some warnings
STRICT = False
