# This is the settings module of pyerk (backend). It is assumed to take precedence over django settings.

import os

# for now we only support a subset of languages with wich the authors are familiar
# if you miss a language, please consider contributing
SUPPORTED_LANGUAGES = ["en", "de"]
# https://en.wikipedia.org/wiki/IETF_language_tag

DEFAULT_DATA_LANGUAGE = "en"


ACKREP_DATA_REL_PATH = "../ackrep/ackrep_data"

BUILTINS_URI = "erk:/builtins"
URI_SEP = "#"

# todo: some time in the future pyerk should become indendent from the OCSE
# for now it is convenient to have the URI stored here
OCSE_URI = "erk:/ocse/0.2"
