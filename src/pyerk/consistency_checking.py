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

    # prevent unnoticed module reload issues
    assert not itm.get_arguments()[0].R4._unlinked

    args = itm.get_arguments()
    arg_type_items = [arg.R4__is_instance_of for arg in args]

    expected_arg_types = get_expected_arg_types(operator_itm)

    if len(arg_type_items) != len(expected_arg_types):
        msg = f"While checking {itm}: got {len(arg_type_items)} arg(s) but " f"{len(expected_arg_types)} where expected"
        raise WrongArgNumber(msg)

    # the lengths match, now check the types

    for i, (actual_type, expected_type) in enumerate(zip(arg_type_items, expected_arg_types)):
        if bi.is_subclass_of(actual_type, expected_type, allow_id=True):
            continue

        # the main type does not match. One of the secondary types might still match
        continue_outer_loop = False
        for secondary_class_item in args[i].R30__is_secondary_instance_of:
            if bi.is_subclass_of(secondary_class_item, expected_type, allow_id=True):
                continue_outer_loop = True
                break
        if continue_outer_loop:
            continue

        # handle some special cases (TODO: I41["semantic rule"]-instances for this, see zebra puzzle test data)
        if bi.is_subclass_of(actual_type, bi.I34["complex number"], allow_id=True) and expected_type == bi.I18["mathematical expression"]:
            continue

        # if we reach this there was no match -> error
        msg = f"expected {expected_type} but got {actual_type}, while checking type of arg{i+1} for {itm}\n{get_error_location()}"
        raise WrongArgType(msg)


def get_error_location():
    # TODO: This function gives only useful results if error occurs during module loading
    # but not if it occurs in a test_method
    import inspect
    import os
    f = inspect.currentframe()
    MAX_STACK_DEPTH = 100
    for i in range(MAX_STACK_DEPTH):
        fi = inspect.getframeinfo(f)
        if fi.function == "<module>":
            break
        f = f.f_back
    else:
        # break was not reached
        msg = "<could not find pyerk module in stack>"
        return msg
    fname = os.path.split(fi.filename)[-1]
    code_context = "\n".join(fi.code_context).strip()

    msg = f"{fname}:{fi.lineno}: `{code_context}`"
    return msg


def get_expected_arg_types(itm: Item) -> Tuple[Item]:
    arg1_dom = itm.R8__has_domain_of_argument_1
    arg2_dom = itm.R9__has_domain_of_argument_2
    arg3_dom = itm.R10__has_domain_of_argument_3

    domains = [arg1_dom, arg2_dom, arg3_dom]

    # replace empty lists with None
    domains = [None if not elt else elt for elt in domains]

    match domains:
        case [None, _, _]:
            msg = f"unexpected: R8__has_domain_of_argument_1 is undefined for operator {itm}\n{get_error_location()}"
            raise ErkTypeError(msg)

        case [_, None, a3] if a3 is not None:
            msg = f"inconsistency for operator {itm}: domain for arg3 defined but not for arg2\n{get_error_location()}"
            raise ErkTypeError(msg)
        case [a1, None, None]:
            arity = 1
        case [a1, a2, None]:
            arity = 2
        case [a1, a2, a3]:
            arity = 3
        case _:
            msg = f"unexpected domain structure for {itm}: {domains}\n {get_error_location()}"
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


def apply_constraint_rules_to_entity(entity: bi.Entity):
    """
    Basic idea: every module should formulate its own constraint rules (as part of the graph).

    These rules are (indirect) instances I41["semantic rule"]. If they apply, they result in a
    ConstraintViolationStatement.
    """
    pass
