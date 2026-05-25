"""
Serialization-/formatting helpers extracted from :mod:`pyirk.core`.

The symbols defined here are import-time safe: none of them needs any
module-global of ``core`` while this module is being imported (their parameter
and return annotations use only builtins, stdlib types or directly-imported
``rdflib.Literal``). Symbols that use ``core`` module-globals (``ds``) at *call*
time access them module-qualified via the ``_core`` module object, whose
attributes are only read once the functions are actually called. This keeps the
import monodirectional: ``core`` imports this module (early), this module only
binds the (partially loaded) ``core`` module object.

Note: ``format_entity_html`` intentionally stays in :mod:`pyirk.core` because
its parameter annotation references the core class ``Entity`` (evaluated at
import time, not yet defined when this module is imported). Likewise the
module-level ``LanguageCode`` instances (``df``, ``en``, ``de`` ...) remain in
the facade; only the ``LanguageCode`` class definition is migrated here.
"""

import os
from typing import Union

import yaml
from rdflib import Literal
from ipydex import IPS

from pyirk import settings

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the function bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = [
    "get_language_of_str_literal",
    "LanguageCode",
    "format_literal_html",
    "script_main",
    "export_entities",
]


# TODO: obsolete?
def get_language_of_str_literal(obj: Union[str, Literal]):
    if isinstance(obj, Literal):
        return obj.language

    return None


class LanguageCode:
    def __init__(self, langtag):
        assert langtag in settings.SUPPORTED_LANGUAGES

        self.langtag = langtag

    def __rmatmul__(self, arg: str) -> Literal:
        """
        This enables syntax like `"test string" @ en` (where `en` is a LanguageCode instance)

        :param arg:     the string for which the language ist to be specified

        :return:        Literal instance with `.lang` attribute set
        """

        # note that Literal is a subclass of str
        assert not isinstance(arg, Literal) and isinstance(arg, str)

        res = Literal(arg, lang=self.langtag)

        return res


def format_literal_html(obj):
    return f'<span class="literal">{repr(obj)}</span>'


def script_main(fpath):
    IPS()


def export_entities(path: str = None, to_file=True, uris=True):
    d = {}
    entities = [_core.ds.items, _core.ds.relations]
    for entity in entities:
        for k, v in entity.items():
            if "a" in k.split("#")[-1]:
                continue
            out = v.R1.value + "\n"
            for items in [v.get_relations().items(), v.get_inv_relations().items()]:
                for rk, stmts in items:
                    if rk.endswith("#R1"):
                        continue
                    for stm in stmts:
                        for e in stm.relation_tuple:
                            # add uri
                            if uris and hasattr(e, "uri"):
                                out += f"'{e.uri} "
                            else:
                                out += "'"
                            # normal items
                            if hasattr(e, "R1"):
                                out += f"{e.R1.value}'"
                            # Literals
                            elif hasattr(e, "value"):
                                out += f"{e.value}'"
                            # other literals
                            elif isinstance(e, str):
                                out += f"{e}'"
                            # numbers and others
                            else:
                                out += f"{str(e)}'"
                            out += " "
                        out += "\n"
            d[k] = out
    # todo do we want uris in these statements?
    if to_file:
        assert os.path.isfile(path), "invalid filepath"
        with open(path, "w") as f:
            yaml.dump(d, f)
    return d
