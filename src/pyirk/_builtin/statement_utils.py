"""
Statement-/relation-utility functions extracted from
:mod:`pyirk.builtin_entities`.

Like the sibling modules :mod:`pyirk._builtin.taxonomy`,
:mod:`pyirk._builtin.scopes`, :mod:`pyirk._builtin.math_expressions` and
:mod:`pyirk._builtin.operators`, this module only binds the (partially loaded)
``builtin_entities`` module object as ``_be``. All accesses to its
module-globals (items like ``I40``, ``I41``, relations like ``R20``, ``R57``,
``R62`` and already migrated helpers like ``instance_of``) happen
module-qualified and exclusively at *call* time inside the function bodies —
never at import time. ``core``/``Entity``/``Relation``/``Item``/``Statement``/
``ds``/``RuleResult`` are imported directly from :mod:`pyirk.core`.
"""

from typing import Any, List, Union

from pyirk import core
from pyirk.core import Entity, Relation, Item, Statement, ds, RuleResult

# Note: this import only binds the (already loaded) module object; its attributes
# are accessed lazily inside the function bodies (i.e. at call time, not import time).
from pyirk import builtin_entities as _be


__all__ = [
    "set_multiple_statements",
    "get_relation_properties_uris",
    "get_relation_properties",
    "label_compare_method",
    "does_not_have_relation",
    "replacer_method",
    "copy_statements",
    "reverse_statements",
    "new_instance_as_object",
    "raise_contradiction",
    "raise_reasoning_goal_reached",
]


def set_multiple_statements(subjects: Union[list, tuple], predicate: Relation, object: Any, qualifiers=None):
    """
    For every element of subjects, create a statement with predicate and object
    """

    res = []
    for sub in subjects:
        assert isinstance(sub, Entity)
        stm = sub.set_relation(predicate, object, qualifiers=qualifiers)
        res.append(stm)

    return res


def get_relation_properties_uris():
    stms: List[Statement] = ds.relation_statements[_be.R62.uri]
    uris = []
    for stm in stms:
        # stm is like: RE3064(<Relation R22["is functional"]>, <Relation R62["is relation property"]>, True)
        if stm.object == True:
            uris.append(stm.subject.uri)

    return uris


# TODO: this could be speed up by caching
def get_relation_properties(rel_entity: Entity) -> List[str]:
    """
    return a sorted list of URIs, corresponding to the relation properties corresponding to `rel_entity`.
    """

    assert isinstance(rel_entity, Relation) or rel_entity.R4__is_instance_of == _be.I40["general relation"]

    relation_properties_uris = get_relation_properties_uris()
    rel_props = []
    for rp_uri in relation_properties_uris:
        res = rel_entity.get_relations(rp_uri, return_obj=True)
        assert len(res) <= 1, "unexpectedly got multiple relation properties"
        if res == [True]:
            rel_props.append(rp_uri)
    rel_props.sort()
    return rel_props


# ######################################################################################################################
# condition functions (to be used in the premise scope of a rule)
# ######################################################################################################################


def label_compare_method(self, item1, item2) -> bool:
    """
    Condition function for rules. Returns True if label of item 1 is alphabetically smaller then that of item2
    """

    if item2.R1 is None:
        # item2 is (probably) undefined
        return True

    if item1.R1 is None:
        return False

    return item1.R1 < item2.R1


def does_not_have_relation(self, item: Item, rel: Relation) -> bool:
    """
    Condition function for rules. Returns True if item does not have any statement where rel is the predicate
    """

    res = item.get_relations(rel.uri)
    return not res


# ######################################################################################################################
# consequent functions (to be used in the assertion scope of a rule)
# ######################################################################################################################


def replacer_method(self, old_item, new_item):
    """
    replace old_item with new_item in every statement, unlink the old item
    """

    try:
        res = core.replace_and_unlink_entity(old_item, new_item)
    except core.aux.UnknownURIError:
        # if one of the two does not exist -> do nothing
        res = RuleResult()

    return res


def copy_statements(self, rel1: Relation, rel2: Relation):
    """
    For every statement like (i1, rel1, i2) create a new statement with rel2 as predicate.
    """
    res = RuleResult()
    for stm in ds.relation_statements[rel1.uri]:
        stm: Statement
        #    TODO: handle qualifiers
        new_stm = stm.subject.set_relation(rel2, stm.object, prevent_duplicate=True)
        res.add_statement(new_stm)

    # this function intentionally does not return a new item; only called for its side-effects
    return res


def reverse_statements(self, rel: Relation):
    """
    For every statement like (i1, rel1, i2) create a new statement (i2, rel, i1) (if it does not yet exist).
    """
    res = RuleResult()
    for stm in ds.relation_statements[rel.uri]:
        stm: Statement
        # TODO: handle qualifiers
        assert isinstance(stm.object, Entity)
        existing_reverse_statement_objs = stm.object.get_relations(rel.uri, return_obj=True)
        if stm.subject in existing_reverse_statement_objs:
            # the symmetrically associated statement does already exist -> do nothing
            continue

        # do not process statements which are made inside of a rule (recognizable via qualifier)
        continue_flag = False
        for qf in stm.qualifiers:
            if qf.predicate == _be.R20["has defining scope"]:
                anchor_obj = qf.object.R21__is_scope_of
                if anchor_obj.R4__is_instance_of == _be.I41["semantic rule"]:
                    continue_flag = True
                    # end iterating over qualifiers
                    break

        if continue_flag:
            continue

        new_stm = stm.object.set_relation(rel, stm.subject, prevent_duplicate=True)
        res.add_statement(new_stm)

    return res


def new_instance_as_object(self, subj, pred, obj_type, placeholder=False, name_prefix=None):
    """
    Create a new instance of obj_type and then use this as the object in a new statement.
    """

    res = RuleResult()

    if name_prefix is None:
        name_prefix = f"{obj_type.R1} of "

    name = f"{name_prefix}{subj.R1}"

    new_obj = _be.instance_of(obj_type, r1=name)

    new_stm = subj.set_relation(pred, new_obj)
    res.add_statement(new_stm)
    res.add_entity(new_obj)

    if placeholder:
        new_stm2 = new_obj.set_relation(_be.R57["is placeholder"], True)
        res.add_statement(new_stm2)
    return res


def raise_contradiction(self, msg_template, *args):
    msg = msg_template.format(*args)
    raise core.aux.LogicalContradiction(msg)


def raise_reasoning_goal_reached(self, msg_template, *args):
    msg = msg_template.format(*args)
    raise core.aux.ReasoningGoalReached(msg)
