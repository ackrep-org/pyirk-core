import os
import sys
import re as regex
from typing import Iterable, Union, Dict, Any
from rdflib import Literal
from colorama import Style, Fore
from . import settings

"""
Some auxiliary classes and functions for pyerk.
"""

startup_workdir = os.path.abspath(os.getcwd())


class NotYetFinishedError(NotImplementedError):
    pass


class OneToOneMapping(object):
    def __init__(self, **kwargs):
        self.a = dict(**kwargs)
        self.b = dict([(v, k) for k, v in kwargs.items()])

        # assert 1to1-property
        assert len(self.a) == len(self.b)

    def add_pair(self, key_a, key_b):
        self.a[key_a] = key_b
        self.b[key_b] = key_a

        # assert 1to1-property
        assert len(self.a) == len(self.b)

    def remove_pair(self, key_a=None, key_b=None, strict=True):

        try:
            if key_a is not None:
                key_b = self.a.pop(key_a)
                self.b.pop(key_b)
            elif key_b is not None:
                key_a = self.b.pop(key_b)
                self.a.pop(key_a)
            else:
                msg = "Both keys are not allowed to be `None` at the the same time."
                raise ValueError(msg)
        except KeyError:
            if strict:
                raise
            # else -> pass


def ensure_list(arg):
    if not isinstance(arg, list):
        return [arg]
    else:
        return arg


class ListWithAttributes(list):
    """
    This subclass of list can have attributes
    """

    var: Iterable


def apply_func_to_table_cells(func: callable, table: Iterable, *args, **kwargs) -> ListWithAttributes:
    res = ListWithAttributes()
    for row in table:
        new_row = []
        for cell in row:
            new_row.append(func(cell, *args, **kwargs))
        res.append(new_row)

    return res


def ensure_rdf_str_literal(arg, allow_none=True) -> Union[Literal, None]:

    if allow_none and arg is None:
        return arg

    # note: rdflib.Literal is a subclass of str (also if the value is e.g. a float)
    if isinstance(arg, Literal):
        assert arg.language in settings.SUPPORTED_LANGUAGES
        res = arg
    elif isinstance(arg, str):
        res = Literal(arg, lang=settings.DEFAULT_DATA_LANGUAGE)
    else:
        msg = f"Unexpected type {type(arg)} of object {arg}."
        raise TypeError(msg)

    return res


class PyERKError(Exception):
    """
    raised in situations where some ERK-specific conditions are violated
    """

    pass


class EmptyURIStackError(PyERKError):
    pass


class UnknownPrefixError(PyERKError):
    pass


class UnknownURIError(PyERKError):
    pass


class InvalidURIError(PyERKError):
    pass


class InvalidPrefixError(PyERKError):
    pass


class InvalidShortKeyError(PyERKError):
    pass


class ModuleAlreadyLoadedError(PyERKError):
    pass


class SemanticRuleError(PyERKError):
    pass


def ensure_valid_short_key(txt: str, strict: bool = True) -> bool:
    conds = [isinstance(txt, str)]

    re_short_key = regex.compile(r"^((Ia?)|(Ra?)|(RE))(\d+)$")
    # produces 5 groups: [{outer-parenthesis}, {inner-p1}, {inner-p2}, {inner-p3}, {last-p}]
    # first (index: 1) and last are the only relevant groups

    match = re_short_key.match(txt)

    if match is None:
        conds += [False]
    else:
        type_str = match.group(1)
        num_str = match.group(5)

        conds += [type_str is not None]
        conds += [num_str is not None]

    cond = all(conds)
    if not cond and strict:
        msg = f"This seems not to be a valid short_key: {txt}. Condition protocoll: {conds}"
        raise InvalidShortKeyError(msg)

    return cond


def ensure_valid_uri(txt: str, strict: bool = True) -> bool:
    conds = [isinstance(txt, str)]
    conds += ["#" in txt]

    parts = txt.split("#")
    conds += [len(parts) == 2]

    conds += [ensure_valid_baseuri(parts[0], strict=strict)]

    cond = all(conds)
    if not cond and strict:
        msg = f"This seems not to be a valid URI: {txt}. Condition protocoll: {conds}"
        raise InvalidURIError(msg)

    return cond


def ensure_valid_prefix(txt: str, strict: bool = True) -> bool:
    """
    To avoid confusion with base_uris prefixes have to meet certain conditions.

    :param txt:
    :param strict:
    :return:
    """
    conds = [isinstance(txt, str)]
    conds += [
        txt.isidentifier()
    ]  # prefixes are assumed to be valid python-names (keywords like "in" are allowed though)
    conds += ["__" not in txt]

    cond = all(conds)
    if not cond and strict:
        msg = f"This seems not to be a valid prefix: {txt}. Condition protocoll: {conds}"
        raise InvalidPrefixError(msg)

    return cond


def ensure_valid_baseuri(txt: str, strict: bool = True) -> bool:
    """

    :param txt:
    :param strict:
    :return:
    """
    conds = [isinstance(txt, str)]
    conds += [":" in txt]  # rdflib wants this
    conds += ["/" in txt]
    conds += [settings.URI_SEP not in txt]
    conds += ["__" not in txt]

    cond = all(conds)
    if not cond and strict:
        msg = f"This seems not to be a valid base uri: {txt}. Condition protocoll: {conds}"
        raise InvalidURIError(msg)

    return cond


def make_uri(base_uri: str, short_key):
    ensure_valid_baseuri(base_uri)
    assert "_" not in short_key  # TODO: replace by regex match
    assert isinstance(short_key, str) and len(short_key) >= 2
    return f"{base_uri}{settings.URI_SEP}{short_key}"


# This function was once part of the key-recycling mechanism.
# Currently it is not needed but might be useful in the future.
def convert_key_str_to_num(key_str: str) -> int:

    import regex  # this import is "parked here" as long as the function is not used

    re_short_key = regex.compile(r"^((Ia?)|(Ra?)|(RE))(\d+)$")
    # produces 5 groups: [{outer-parenthesis}, {inner-p1}, {inner-p2}, {inner-p3}, {last-p}]
    # first (index: 1) and last are the only relevant groups

    match = re_short_key.match(key_str)

    type_str = match.group(1)
    num_str = match.group(5)
    assert type_str is not None
    assert num_str is not None

    return int(num_str)


def clean_dict(dikt: Dict[Any, Union[list, dict]]) -> Dict[Any, Union[list, dict]]:
    """
    Recursively remove all keys where the corresponding value is an empty list or dict.

    :param dikt:
    :return:
    """

    obsolete_keys = []
    for key, value in dikt.items():
        if len(value) == 0 and isinstance(value, (list, dict)):
            obsolete_keys.append(key)
        elif isinstance(value, dict):
            tmp_dict = clean_dict(value)
            if len(tmp_dict) == 0:
                obsolete_keys.append(key)

    for key in obsolete_keys:
        dikt.pop(key)

    return dikt


def bright(txt):
    return f"{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bblue(txt):
    return f"{Fore.BLUE}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bcyan(txt):
    return f"{Fore.CYAN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bmagenta(txt):
    return f"{Fore.MAGENTA}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bred(txt):
    return f"{Fore.RED}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def byellow(txt):
    return f"{Fore.YELLOW}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def get_erk_root_dir() -> str:
    """
    Return the absolute path of the erk-root (assuming the directory structure documented in README.md)

    :return:
    """

    current_dir = os.path.abspath(os.getcwd())

    # this allows to have a local-deployment copy of the erk-root which does not change on every edit of the
    # knowledge base
    # TODO: obsolete? (this should respect pyerkconf.toml)
    if os.path.isfile(os.path.join(current_dir, "__erk-root__")):
        return current_dir
    dir_of_this_file = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
    erk_root = os.path.abspath(os.path.join(dir_of_this_file, "..", "..", ".."))
    return erk_root
