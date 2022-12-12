# This is the settings module of pyerk (backend). It is assumed to take precedence over django settings.

import os
import sys

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

# for now we only support a subset of languages with wich the authors are familiar
# if you miss a language, please consider contributing
SUPPORTED_LANGUAGES = ["en", "de"]
# https://en.wikipedia.org/wiki/IETF_language_tag


# TODO: This should be specifyable for every module
DEFAULT_DATA_LANGUAGE = "en"


ACKREP_DATA_REL_PATH = "../ackrep/ackrep_data"
ACKREP_DATA_UT_REL_PATH = "../ackrep/ackrep_data_for_unittests"


# get absolute path of directory of this file
source_dir = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
TEMPLATE_PATH = os.path.join(source_dir, "templates")

BUILTINS_URI = "erk:/builtins"
URI_SEP = "#"

# todo: some time in the future pyerk should become indendent from the OCSE
# for now it is convenient to have the URI stored here
OCSE_URI = "erk:/ocse/0.2"


BASE_DIR = os.getenv("PYERK_BASE_DIR", "")
if not BASE_DIR:
    BASE_DIR = "./"
BASE_DIR = os.path.abspath(BASE_DIR)


confpath = os.path.join(BASE_DIR, "erkpackage.toml")


try:
    with open(confpath, "rb") as fp:
        CONF = tomllib.load(fp)
except FileNotFoundError:
    CONF = {}
