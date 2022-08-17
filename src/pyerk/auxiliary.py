from typing import Iterable, Union
from rdflib import Literal
from colorama import Style, Fore
from . import settings

"""
Some auxiliary classes and functions for pyerk.
"""


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

    def remove_pair(self, key_a=None, key_b=None):

        if key_a is not None:
            key_b = self.a.pop(key_a)
            self.b.pop(key_b)
        elif key_b is not None:
            key_a = self.b.pop(key_b)
            self.a.pop(key_a)
        else:
            msg = "Both keys are not allowed to be `None` at the the same time."
            raise ValueError(msg)


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


def bright(txt):
    return f"{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bgreen(txt):
    return f"{Fore.GREEN}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def bred(txt):
    return f"{Fore.RED}{Style.BRIGHT}{txt}{Style.RESET_ALL}"


def byellow(txt):
    return f"{Fore.YELLOW}{Style.BRIGHT}{txt}{Style.RESET_ALL}"