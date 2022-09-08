# This is the settings module of pyerk (backend). It is assumed to take precedence over django settings.

# for now we only support a subset of languages with wich the authors are familiar
# if you miss a language, please consider contributing
SUPPORTED_LANGUAGES = ["en", "de"]
# https://en.wikipedia.org/wiki/IETF_language_tag

DEFAULT_DATA_LANGUAGE = "en"

BUILTINS_URI = "pyerk/builtins"
