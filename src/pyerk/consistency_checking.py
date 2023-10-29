"""
pyerk module for consitency checking.


"""

from typing import Tuple

from . import core
from . import builtin_entities as bi
from .core import Item


from ipydex import IPS


class ErkTypeError(core.aux.PyERKError):
    pass


class WrongArgNumber(ErkTypeError):
    pass


class WrongArgType(ErkTypeError):
    pass


def check(itm: Item):
    operator_itm = itm.R35__is_applied_mapping_of
    if operator_itm:
        check_applied_operator(itm)
    else:
        # no checks implemented yet for other types of items
        # IPS()
        pass


def check_applied_operator(itm: Item):
    operator_itm = itm.R35__is_applied_mapping_of
    assert operator_itm is not None

    args = itm.get_arguments()
    arg_type_items = [arg.R4__is_instance_of for arg in args]

    expected_arg_types = get_expected_arg_types(operator_itm)

    if len(arg_type_items) != len(expected_arg_types):
        msg = f"While checking {itm}: got {len(arg_type_items)} arg(s) but " f"{len(expected_arg_types)} where expected"
        raise WrongArgNumber(msg)

    # the lengths match, now check the types

    for i, (actual, expected) in enumerate(zip(arg_type_items, expected_arg_types)):
        if actual == expected:
            continue
        if bi.is_subclass_of(actual, expected):
            continue
        msg = f"expected {expected} but got {actual}, while checking" f"arg type {i} for {itm}"
        raise WrongArgType(msg)


def get_expected_arg_types(itm: Item) -> Tuple[Item]:
    arg1_dom = itm.R8__has_domain_of_argument_1
    arg2_dom = itm.R9__has_domain_of_argument_2
    arg3_dom = itm.R10__has_domain_of_argument_3

    domains = [arg1_dom, arg2_dom, arg3_dom]

    # replace empty lists with None
    domains = [None if not elt else elt for elt in domains]

    match domains:
        case [None, _, _]:
            msg = "unexpected: R8__has_domain_of_argument_1 is undefined for " f"operator {itm}"
            raise ErkTypeError(msg)

        case [_, None, a3] if a3 is not None:
            msg = f"inconsistency for operator {itm}: domain for arg3 defined " "but not for arg 2"
            raise ErkTypeError(msg)
        case [a1, None, None]:
            arity = 1
        case [a1, a2, None]:
            arity = 2
        case [a1, a2, a3]:
            arity = 3
        case _:
            msg = f"unexpected domain structure for {itm}: {domains}"
            raise ErkTypeError(msg)

    domains = domains[:arity]

    # flatten the list
    res = []
    for i, dom in enumerate(domains):
        assert isinstance(dom, list)
        if len(dom) != 1:
            msg = f"multi-valued domains are not yet supported (arg {i+1}) " f"of {itm}"
            raise core.aux.NotYetFinishedError(msg)
        res.append(dom[0])

    return res


def enable_consitency_checking():
    core.register_hook("post-finalize-item", check)
