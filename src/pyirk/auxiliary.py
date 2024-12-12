import os
import sys
import re as regex
from typing import Iterable, Union, Dict, Any
from rdflib import Literal
from colorama import Style, Fore
from addict import Addict as Container
from . import settings

"""
Some auxiliary classes and functions for pyirk.
"""

startup_workdir = os.path.abspath(os.getcwd())


# the following suffixes for base URIs are used for predicates to RDF-encode qualifiers (statements about statements)
# strongly inspired by https://en.wikibooks.org/wiki/SPARQL/WIKIDATA_Qualifiers,_References_and_Ranks#Qualifiers

# corresponds to `p` ("http://www.wikidata.org/prop/") -> links to statement nodes
STATEMENTS_URI_PART = "/STATEMENTS"

# corresponds to `ps` ("http://www.wikidata.org/prop/schema/".") -> links to main object
PREDICATES_URI_PART = "/PREDICATES"

# corresponds to `pq` ("http://www.wikidata.org/property_qualifier/" ?) -> used for qualifying pred-obj-tuples
QUALIFIERS_URI_PART = "/QUALIFIERS"


class NotYetFinishedError(NotImplementedError):
    pass


class OneToOneMapping(object):
    def __init__(self, a_dict: dict = None, **kwargs):
        if a_dict is None:
            self.a = dict(**kwargs)
            self.b = dict([(v, k) for k, v in kwargs.items()])
        else:
            # handle the case where we do not map strings
            assert len(kwargs) == 0

            # make a copy
            self.a = dict(a_dict)
            self.b = dict([(v, k) for k, v in a_dict.items()])

        # assert 1to1-property
        assert len(self.a) == len(self.b)

    def add_pair(self, key_a, key_b):
        if key_a in self.a:
            msg = f"key_a '{key_a}' does already exist."
            raise KeyError(msg)

        if key_b in self.b:
            msg = f"key_b '{key_b}' does already exist."
            raise KeyError(msg)

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


# Source: https://stackoverflow.com/a/3862957
def all_subclasses(cls):
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])


# Source: perplexity.ai (with some manual tweaking)
def print_inheritance_tree(cls, prefix=''):
    """Recursively print the inheritance tree of the given class."""
    print(prefix + cls.__name__)
    subclasses = cls.__subclasses__()
    for i, subclass in enumerate(subclasses):
        # Determine if this is the last subclass to format the tree correctly
        connector = "└── " if i == len(subclasses) - 1 else "├── "
        new_prefix = " "*len(prefix) + connector
        print_inheritance_tree(subclass, new_prefix)


class PyIRKException(Exception):
    """
    raised in situations where some IRK-specific conditions are violated
    """

class GeneralPyIRKError(Exception):
    pass


class MultilingualityError(GeneralPyIRKError):
    pass


class EmptyURIStackError(GeneralPyIRKError):
    pass


class UnknownPrefixError(GeneralPyIRKError):
    pass


class UnknownURIError(GeneralPyIRKError):
    pass


class InvalidURIError(GeneralPyIRKError):
    pass


class InvalidPrefixError(GeneralPyIRKError):
    pass


# used for syntax problems
class InvalidShortKeyError(GeneralPyIRKError):
    pass


class InvalidGeneralKeyError(GeneralPyIRKError):
    pass


class InconsistentLabelError(GeneralPyIRKError):
    pass


# used for syntactically correct keys which could not be found
class ShortKeyNotFoundError(GeneralPyIRKError):
    pass


class InvalidScopeNameError(GeneralPyIRKError):
    pass

class InvalidScopeTypeError(GeneralPyIRKError):
    pass


class InvalidScopeTypeError(GeneralPyIRKError):
    pass


class ModuleAlreadyLoadedError(GeneralPyIRKError):
    pass


class SemanticRuleError(GeneralPyIRKError):
    pass


class ExplicitlyTriggeredTestException(GeneralPyIRKError):
    pass


class InconsistentEdgeRelations(SemanticRuleError):
    pass

class InvalidObjectValue(SemanticRuleError):
    pass


class MissingQualifierError(GeneralPyIRKError):
    pass


class AmbiguousQualifierError(GeneralPyIRKError):
    pass


class FunctionalRelationError(GeneralPyIRKError):
    pass


class UndefinedRelationError(GeneralPyIRKError):
    pass


class TaxonomicError(GeneralPyIRKError):
    pass


class RuleTermination(PyIRKException):
    pass


class LogicalContradiction(RuleTermination):
    pass


class ReasoningGoalReached(RuleTermination):
    pass


class ContinueOuterLoop(PyIRKException):
    """
    This is not an error but indicated that an outside loop should continue.
    """
    pass


def ensure_valid_short_key(txt: str, strict: bool = True) -> bool:
    conds = [isinstance(txt, str)]

    re_short_key = regex.compile(r"^((Ia?)|(Ra?)|(S))(\d+)$")
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
        msg = f"This seems not to be a valid short_key: {txt}. Condition protocol: {conds}"
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
        msg = f"This seems not to be a valid URI: {txt}. Condition protocol: {conds}"
        raise InvalidURIError(msg)

    return cond


def ensure_valid_relation_uri(txt: str, strict=True):
    conds = [ensure_valid_uri(txt, strict)]
    conds.append(txt.split("#")[1].startswith("R"))

    cond = all(conds)
    if not cond and strict:
        msg = f"This is not a valid relation URI: {txt}. Condition protocol: {conds}"
        raise InvalidURIError(msg)


def ensure_valid_item_uri(txt: str, strict=True):
    conds = [ensure_valid_uri(txt, strict)]
    conds.append(txt.split("#")[1].startswith("I"))

    cond = all(conds)
    if not cond and strict:
        msg = f"This is not a valid item URI: {txt}. Condition protocol: {conds}"
        raise InvalidURIError(msg)


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
        msg = f"This seems not to be a valid prefix: {txt}. Condition protocol: {conds}"
        raise InvalidPrefixError(msg)

    return cond


def parse_uri(txt: str) -> Container:
    res = Container(full_uri=txt)
    res.base_uri, res.short_key = txt.split("#")

    for uri_part in (STATEMENTS_URI_PART, PREDICATES_URI_PART, QUALIFIERS_URI_PART):
        if res.base_uri.endswith(uri_part):
            res.sub_ns = uri_part
            break
    else:
        res.sub_ns = None

    return res


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
        msg = f"This seems not to be a valid base uri: {txt}. Condition protocol: {conds}"
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
    import re as regex  # this import is "parked here" as long as the function is not used

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


def uri_set(*args):
    res = []
    for arg in args:
        res.append(arg.uri)
    return set(res)


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


def get_irk_root_dir() -> str:
    """
    Return the absolute path of the irk-root (assuming the directory structure documented in README.md)

    :return:
    """

    current_dir = os.path.abspath(os.getcwd())

    # this allows to have a local-deployment copy of the irk-root which does not change on every edit of the
    # knowledge base
    # TODO: obsolete? (this should respect pyirkconf.toml)
    if os.path.isfile(os.path.join(current_dir, "__irk-root__")):
        return current_dir
    dir_of_this_file = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))
    irk_root = os.path.abspath(os.path.join(dir_of_this_file, "..", "..", ".."))
    return irk_root


def get_irk_path(dirname=None):

    if dirname is None:
        return get_irk_root_dir()

    dir_of_this_file = os.path.dirname(os.path.abspath(sys.modules.get(__name__).__file__))

    # this assumes pyirk is installed with `pip install -e .` from the repo
    pyirk_root = os.path.abspath(os.path.join(dir_of_this_file, "..", ".."))
    if dirname == "pyirk-core-test_data":
        return os.path.join(pyirk_root, "tests", "test_data")

    msg = f"unexpected dirname: {dirname}"
    raise ValueError(msg)
