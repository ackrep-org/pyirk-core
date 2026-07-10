"""
Arithmetic operator helper functions extracted from
:mod:`pyirk.builtin_entities`.

Like the sibling modules :mod:`pyirk._builtin.taxonomy`,
:mod:`pyirk._builtin.scopes` and :mod:`pyirk._builtin.math_expressions`, this
module only binds the (partially loaded) ``builtin_entities`` module object as
``_be``. All accesses to its module-globals (operator items like ``I55``,
``I56``, ``I57`` and ``I58``) happen module-qualified and exclusively at *call*
time inside the function bodies — never at import time. References to functions
that also live in this module (e.g. ``add_items``, ``mul_items``) stay direct
names.
"""

# Note: this import only binds the (already loaded) module object; its attributes
# are accessed lazily inside the function bodies (i.e. at call time, not import time).
from pyirk import builtin_entities as _be


__all__ = [
    "add_items",
    "radd_items",
    "sub_items",
    "reflective_sub_items",
    "mul_items",
    "rmul_items",
    "div_items",
    "reflective_div_items",
    "pow_items",
    "reflective_pow_items",
    "neg_item",
    "unpack_tuple_item",
]


def add_items(*args):
    if len(args) == 2:
        return _be.I55["add"](*args)
    else:
        return _be.I55["add"](add_items(*args[:-1]), args[-1])


def radd_items(a, b):
    return _be.I55["add"](b, a)


# todo do we need this with for args of arbitrary length?


def sub_items(a, b):
    return _be.I55["add"](a, _be.I56["mul"](-1, b))


def reflective_sub_items(a, b):
    return _be.I55["add"](b, _be.I56["mul"](-1, a))


def mul_items(*args):
    if len(args) == 2:
        return _be.I56["mul"](*args)
    else:
        return _be.I56["mul"](mul_items(*args[:-1]), args[-1])


def rmul_items(a, b):
    return _be.I56["mul"](b, a)


def div_items(a, b):
    return _be.I56["mul"](a, _be.I57["pow"](b, -1))


def reflective_div_items(a, b):
    return _be.I56["mul"](b, _be.I57["pow"](a, -1))


def pow_items(a, b):
    return _be.I57["pow"](a, b)


def reflective_pow_items(a, b):
    return _be.I57["pow"](b, a)


def neg_item(a):
    return _be.I58["neg"](a)


def unpack_tuple_item(tuple_item):
    """
    This is just a convenience alias for .R39__has_element
    """

    # this will return a list (as R29 is not functional)
    return tuple_item.R39__has_element
