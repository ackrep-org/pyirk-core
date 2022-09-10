"""
Created: 2022-09-06 19:14:39
author: Carsten Knoll

This module contains code to enable semantic inferences based on special items (e.g. instances of I41__semantic_rule)

"""

from typing import List

from ipydex import IPS

from . import core as pyerk, auxiliary as aux
from . import builtin_entities as b


def apply_all_semantic_rules():
    rule_instances = get_all_rules()
    for rule in rule_instances:
        apply_rule(rule)


def get_all_rules():

    rule_instances: list = b.I41["semantic rule"].get_inv_relations("R4__is_instance_of", return_subj=True)

    return rule_instances


def filter_subject_rledges(re_list: List[pyerk.RelationEdge]) -> List[pyerk.RelationEdge]:
    """
    From a list of RelationEdge instances select only those with .role == SUBJECT.
    In other words: omit those instances which are created as dual relation edges

    :param re_list:
    :return:
    """

    res = []
    for rledg in re_list:
        assert isinstance(rledg, pyerk.RelationEdge)
        if rledg.role == pyerk.RelationRole.SUBJECT:
            res.append(rledg)
    return res


def apply_rule(rule: pyerk.Entity) -> None:

    # noinspection PyShadowingBuiltins
    vars = rule.scp__context.get_inv_relations("R20__has_defining_scope")
    premises_rledgs = filter_subject_rledges(rule.scp__premises.get_inv_relations("R20__has_defining_scope"))
    assertions_rledgs = filter_subject_rledges(rule.scp__assertions.get_inv_relations("R20__has_defining_scope"))

    # IPS()  # ← continue here
