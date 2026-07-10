"""
Key-/short-key-management helpers extracted from :mod:`pyirk.core`.

The symbols defined here are import-time safe: none of them needs any
module-global of ``core`` while this module is being imported. Symbols that use
``core`` module-globals (``ds``, the compiled key regexes, the uri-stacks,
``uri_context`` etc.) at *call* time access them module-qualified via the
``_core`` module object, whose attributes are only read once the functions are
actually called. This keeps the import monodirectional: ``core`` imports this
module (early), this module only binds the (partially loaded) ``core`` module
object.
"""

import random
import re
from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, Optional, Union

from pyirk import auxiliary as aux
from pyirk import settings

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the function bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = [
    "EType",
    "SType",
    "VType",
    "ProcessedStmtKey",
    "unpack_l1d",
    "process_key_str",
    "_resolve_prefix",
    "check_processed_key_label",
    "ilk2nlk",
    "u",
    "KeyManager",
    "pop_uri_based_key",
    "generate_new_key",
    "print_new_keys",
]


@unique
class EType(Enum):
    """
    Entity types.
    """

    ITEM = 0
    RELATION = 1
    LITERAL = 2


@unique
class SType(Enum):
    """
    Statement types.
    """

    CREATION = 0
    EXTENSION = 1
    UNDEFINED = 2


@unique
class VType(Enum):
    """
    Dict value types.
    """

    LITERAL = 0
    ENTITY = 1
    LIST = 2
    DICT = 3


@dataclass
class ProcessedStmtKey:
    """
    Container for processed statement key
    """

    short_key: str = None
    # entity type (enum)
    etype: EType = None
    # statement type (enum)
    stype: SType = None
    # value type (enum)
    vtype: VType = None

    content: object = None
    delimiter: str = None
    label: str = None
    prefix: str = None
    uri: str = None
    lang_indicator: str = None

    original_key_str: str = None


def unpack_l1d(l1d: Dict[str, object]):
    """
    unpack a dict of length 1
    :param l1d:
    :return:
    """
    assert len(l1d) == 1
    return tuple(*l1d.items())


def process_key_str(
    key_str: str,
    check: bool = True,
    resolve_prefix: bool = True,
    mod_uri: str = None,
) -> ProcessedStmtKey:
    """
    In IRK there are the following kinds of keys:
        - a) short_key like `R1234`
        - b) name-labeled key like `R1234__my_relation` (consisting of a short_key, a delimiter (`__`) and a label)
        - c) prefixed short_key like `bi__R1234`
        - d) prefixed name-labeled key like `bi__R1234__my_relation`

        - e) index-labeled key like  `R1234["my relation"]`
        - f) prefixed index-labeled key like  `bi__R1234["my relation"]`

    See also: userdoc/overview.html#keys-in-pyirk

    Also, the leading character indicates the entity type (EType).

    This function expects any of these cases.
    :param key_str:     a string like "R1234__my_relation" or "R1234" or "bi__R1234__my_relation"
    :param check:       boolean flag; determines if the label part should be checked wrt its consistency to
    :param resolve_prefix:
                        boolean flag; determines if
    :param mod_uri:     optional uri of the module


    :return:            a data structure which allows to access short_key, type and label separately
    """

    res = ProcessedStmtKey()
    res.original_key_str = key_str

    match1 = _core.re_prefix_shortkey_suffix.match(key_str)

    errmsg = f"unexpected key_str: `{key_str}` (maybe a literal or syntax error)"
    if not match1:
        raise aux.InvalidGeneralKeyError(errmsg)

    if match1.group(3) is None or match1.group(7) is None:
        raise aux.InvalidGeneralKeyError(errmsg)

    res.prefix = match1.group(2)  # this might be None
    res.short_key = match1.group(3) + match1.group(7)

    suffix = match1.group(8) or ""

    match2 = _core.re_suffix_underscore.match(suffix)
    match3 = _core.re_suffix_square_brackets.match(suffix)

    errmsg = f"invalid suffix of key_str `{key_str}` (probably syntax error)"
    if match2 and match3:
        # key seems to mix underscores and square brackets
        raise aux.InvalidGeneralKeyError(errmsg)

    if suffix and (not match2) and (not match3):
        # syntax of suffix seems to be wrong (e., g. missing bracket)
        raise aux.InvalidGeneralKeyError(errmsg)

    if match2:
        res.label = match2.group(1)
    elif match3:
        res.label = match3.group(1)
    else:
        res.label = None

    if res.short_key.startswith("I"):
        res.etype = EType.ITEM
        res.vtype = VType.ENTITY
    elif res.short_key.startswith("R"):
        res.etype = EType.RELATION
        res.vtype = VType.ENTITY
    else:
        msg = f"unexpected shortkey: '{res.short_key}' (maybe a literal)"
        raise aux.InvalidShortKeyError(msg)

    if resolve_prefix:
        _resolve_prefix(res, passed_mod_uri=mod_uri)

    if res.label:
        match_list = _core.langcode_end_pattern.findall(res.label)
        if match_list:
            assert len(match_list) == 1
            (match,) = match_list
            assert match.startswith("__")
            res.label = _core.langcode_end_pattern.sub("", res.label)

            res.lang_indicator = match[2:]

    if check:
        aux.ensure_valid_short_key(res.short_key)
        check_processed_key_label(res)

    return res


def _resolve_prefix(pr_key: ProcessedStmtKey, passed_mod_uri: str = None) -> None:
    """
    get uri from prefix or from passed argument or from active module
    """
    active_mod_uri = _core.get_active_mod_uri(strict=False)
    if _core._search_uri_stack:
        search_uri = _core._search_uri_stack[-1]
    else:
        search_uri = None

    if pr_key.prefix is None:
        if active_mod_uri is None and search_uri is None:
            if passed_mod_uri:
                mod_uri = passed_mod_uri
            else:
                # assume that `builtin_entities` is meant
                mod_uri = settings.BUILTINS_URI
        else:
            # Situation: create_item(..., R321="some value") within an active module
            # (no prefix). short_key R321 could refer to
            # a) the module where the function is defined which performs this call (search_uri)),
            # b) the active module or c) builtin_entities -> search in this order

            # 1. check that passed_mod_uri does not contradict
            if passed_mod_uri and (passed_mod_uri not in (active_mod_uri, search_uri)):
                msg = (
                    f"Encountered inconsistent uris for object with key_str {pr_key.original_key_str}. "
                    f"Explicitly passed: '{passed_mod_uri}'."
                    f"expected one of: '{active_mod_uri}' (active mod) or '{search_uri}' (search_uri)."
                )
                raise aux.InvalidURIError(msg)

            # 2a) check search_uri context
            if search_uri:
                candidate_uri = aux.make_uri(search_uri, pr_key.short_key)
                res_entity = _core.ds.get_entity_by_uri(candidate_uri, strict=False)

                if res_entity is not None:
                    pr_key.uri = candidate_uri
                    return

            # 2b) check active mod
            if active_mod_uri:
                candidate_uri = aux.make_uri(active_mod_uri, pr_key.short_key)
                res_entity = _core.ds.get_entity_by_uri(candidate_uri, strict=False)

                if res_entity is not None:
                    pr_key.uri = candidate_uri
                    return

            # 2c) try builtin_entities as fallback
            candidate_uri = aux.make_uri(settings.BUILTINS_URI, pr_key.short_key)
            res_entity = _core.ds.get_entity_by_uri(candidate_uri, strict=False)

            if res_entity is not None:
                pr_key.uri = candidate_uri
                return
            else:
                # if res_entity is still None no entity could be found
                msg = (
                    f"No entity could be found for short_key {pr_key.short_key}, neither in active module "
                    f"({active_mod_uri}) nor in builtin_entities ({settings.BUILTINS_URI})"
                )
                raise aux.ShortKeyNotFoundError(msg)
    else:
        # prefix was not not None
        mod_uri = _core.ds.get_uri_for_prefix(pr_key.prefix)

        if passed_mod_uri and (passed_mod_uri != active_mod_uri):
            msg = (
                f"encountered inconsistent uris for object with key_str {pr_key.original_key_str}. "
                f"from prefix mod: '{mod_uri}' vs explicitly passed: '{passed_mod_uri}'."
            )
            raise aux.InvalidURIError(msg)

    pr_key.uri = aux.make_uri(mod_uri, pr_key.short_key)


def check_processed_key_label(pkey: ProcessedStmtKey) -> None:
    """
    Check if the used label of a key_str matches the actual label (R1) of that entity

    :param pkey:
    :return:
    """

    # TODO: check prefix

    if not pkey.label:
        return

    try:
        entity = _core.ds.get_entity_by_uri(pkey.uri)
    except KeyError:
        # entity does not exist -> no label to compare with
        return

    if getattr(entity, "_ignore_mismatching_adhoc_label", False):
        # This entity is 'magically' allowed to have any adhoc label
        # used for I000 and R000
        return

    if entity.R1 is None:
        # no label was set for the default language -> nothing to compare
        return

    # note: this includes Literal
    assert isinstance(entity.R1, str)

    label_compare_str1 = entity.R1
    label_compare_str2 = ilk2nlk(entity.R1)

    label = pkey.label.lower()

    error_condition = label not in (label_compare_str1.lower(), label_compare_str2.lower())
    if error_condition:
        msg = (
            f"check of label consistency failed for key {pkey.original_key_str}. Expected:  one of "
            f'("{label_compare_str1}", "{label_compare_str2}") but got  "{pkey.label}". '
            "Note: this test is *not* case-sensitive."
        )
        raise ValueError(msg)


def ilk2nlk(ilk: str) -> str:
    """
    convert index labeled key (R1234["my relation"]) to name labeled key (R1234__my_relation)
    """
    assert isinstance(ilk, str)

    return ilk.replace(" ", "_").replace("-", "_")


def u(key_str: str) -> str:
    """
    Convenience function converting "[prefix__]I1234__my_label"  to "[moduri#]I1234".
    If no prefix is given the active module and `builtin_entities` are searched for (in this order).

    :param key_str:
    :return:
    """

    processed_key = process_key_str(key_str)
    assert processed_key.short_key is not None
    return processed_key.uri


class KeyManager:
    """
    Class for a flexible and comprehensible key management. Every pyirk module must have its own (passed via)
    """

    # TODO: the term "maxval" is misleading because it will be used in range where the upper bound is exclusive
    # however, using range(minval, maxval+1) would results in different shuffling and thus will probably need some
    # refactoring of existing modules
    def __init__(self, minval=1000, maxval=99999, keyseed=None):
        """

        :param minval:  int
        :param maxval:  int
        :param keyseed: int; This allows a module to create its own random key order
        """

        self.instance = self
        self.minval = minval
        self.maxval = maxval
        self.keyseed = keyseed

        self.key_reservoir = None

        self._generate_key_numbers()

    def pop(self, index: int = -1) -> int:
        key = self.key_reservoir.pop(index)
        return key

    def _generate_key_numbers(self) -> None:
        """
        Creates a reservoir of keynumbers, e.g. for automatically created entities. Due to the hardcoded seed value
        these numbers are stable between runs of the software, which simplifies development and debugging.

        This function is also called after unloading a module because the respective keys are "free" again

        Rationale behind random keys: During creation of knowledge bases it frees the mind of thinking too much
        about a meaningful order in which to create entities.

        :return:    list of integers
        """

        assert self.key_reservoir is None

        # passing seed (arg `x`) ensures "reproducible randomness" across runs
        if not self.keyseed:
            # use hardcoded fallback
            self.keyseed = 1750
        random_ng = random.Random(x=self.keyseed)
        self.key_reservoir = list(range(self.minval, self.maxval))
        random_ng.shuffle(self.key_reservoir)


def pop_uri_based_key(prefix: Optional[str] = None, prefix2: str = "") -> Union[int, str]:
    """
    Create a short key (int or str) (optionally with prefixes) from the reservoir.

    :param prefix:
    :param prefix2:
    :return:
    """

    active_mod_uri = _core.get_active_mod_uri()
    km: KeyManager = _core.ds.uri_keymanager_dict[active_mod_uri]
    num_key = km.pop()
    if prefix is None:
        assert not prefix2
        return num_key

    assert prefix in ("I", "R")

    short_key = f"{prefix}{prefix2}{num_key}"
    return short_key


def generate_new_key(prefix, prefix2="", mod_uri=None):
    """
    Utility function for the command line.

    :param prefix:
    :param prefix2:
    :param mod_uri:
    :return:
    """

    assert prefix in ("I", "R")

    if mod_uri is None:
        mod_uri = settings.BUILTINS_URI
        msg = f"Creating key based on module {mod_uri}, which is probably unintended"
        if settings.STRICT:
            raise Warning(msg)
        else:
            print(aux.byellow(f"Warning: {msg}"))

    with _core.uri_context(mod_uri):
        while True:
            key = f"{prefix}{prefix2}{pop_uri_based_key()}"
            uri = aux.make_uri(mod_uri, key)
            try:
                _core.ds.get_entity_by_uri(uri)
            except aux.UnknownURIError:
                # the key was new -> no problem
                return key
            else:
                continue


def print_new_keys(n=30, loaded_mod=None):
    """
    print n random integer keys from the pregenerated list.

    :return:
    """

    if loaded_mod:
        # this ensures that the new keys are created wrt the loaded module (see also: script.py)
        mod_uri = loaded_mod.__URI__
    else:
        mod_uri = None
    if n > 0:
        print(aux.bcyan("supposed keys:    "))
    for i in range(n):
        k = generate_new_key("I", mod_uri=mod_uri)[1:]

        print(f"I{k}      R{k}")
