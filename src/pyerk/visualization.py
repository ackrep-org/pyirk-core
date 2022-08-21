"""
This module contains code for the visualization of ERK-entities.
"""
from typing import Union, List
import os

import networkx as nx
import nxv  # for graphviz visualization of networkx graphs

# TODO: this should be a relative import of the *package*
import pyerk as p
from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()

#  tuple of Relation keys which are not displayed by default
REL_BLACKLIST = ("R1", "R2")

from semantictools import core as smt

from abc import ABC


class AbstractNode(ABC):
    def __init__(self):
        self.repr_str: str = ""
        self.smart_label: str = ""

    def __repr__(self):
        return self.repr_str


class EntityNode(AbstractNode):
    """
    Container to represent a node in a networkx graph (for visualization)
    """

    def __init__(self, entity: p.Entity):
        super().__init__()

        self.short_key = entity.short_key

        # TODO: handle different languages here
        self.label = self.smart_label = entity.R1

        if len(self.label) > 12:
            tmp = self.label  # "-".join(camel_case_split(self.label))
            self.smart_label = tmp.replace(" ", "\n").replace("_", "_\n").replace("-", "-\n")

        self.repr_str = f'{self.short_key}["{self.smart_label}"]'


class LiteralStrNode(AbstractNode):
    def __init__(self, arg: str):
        super().__init__()

        self.repr_str = arg


def create_node(arg: Union[p.Entity, str]):

    if isinstance(arg, p.Entity):
        return EntityNode(arg)
    elif isinstance(arg, str):
        return LiteralStrNode(arg)
    else:
        msg = f"unexpected type: {type(arg)}"
        raise TypeError(msg)


def rel_label(rel: p.Relation):
    return f'{rel.short_key}["{rel.R1}"]'


def visualize_entity(ek, fpath=None, print_path=False) -> nx.DiGraph:
    entity = p.ds.get_entity(ek)
    re_dict = entity.get_relations()
    inv_re_dict = entity.get_inv_relations()

    G = nx.DiGraph()
    base_node = create_node(entity)
    G.add_node(base_node, color="#2ca02c")

    for rel_key, re_list in list(re_dict.items()) + list(inv_re_dict.items()):
        if rel_key in REL_BLACKLIST:
            continue

        re_list: List[p.RelationEdge]
        for re in re_list:
            assert len(re.relation_tuple) == 3
            subj, pred, obj = re.relation_tuple

            if re.role == p.RelationRole.SUBJECT:
                other_node = create_node(obj)
                G.add_node(other_node)
                G.add_edge(base_node, other_node, label=rel_label(pred))
            else:
                other_node = create_node(subj)
                G.add_node(other_node)
                G.add_edge(other_node, base_node, label=rel_label(pred))

    # for styling see https://nxv.readthedocs.io/en/latest/reference.html#styling
    # matplotlib default colors:
    # ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    edge_defaults = {
        "style": "solid",
        "arrowType": "normal",
        "fontsize": 10,
    }
    style = nxv.Style(
        graph={"rankdir": "BT"},
        # u: node, d: its attribute dict
        node=lambda u, d: {
            "shape": "circle",
            "fixedsize": True,
            "width": 1.2,
            "fontsize": 10,
            "color": d.get("color", "black"),
        },
        # u: node1, v: node1, d: its attribute dict
        edge=lambda u, v, d: {**edge_defaults, "label": d["label"]},
    )

    # svg_data = nxv.render(G, style)
    svg_data = nxv.render(G, style, format="svg")

    if fpath is None:
        fpath = "./tmp.svg"

    with open(fpath, "wb") as svgfile:
        svgfile.write(svg_data)

    if print_path:
        print(p.aux.bcyan(f"File written: {os.path.abspath(fpath)}"))

    # return the graph for unittest purposes
    return G
