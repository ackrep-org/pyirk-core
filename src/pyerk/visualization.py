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

REPLACEMENTS = {}


class AbstractNode(ABC):
    def __init__(self):
        self.repr_str: str = ""
        self.smart_label: str = ""

    def __repr__(self):
        return self.repr_str


def replacement_key_generator(template="_rk_{:04d}"):
    i = -1
    while True:
        i += 1
        yield template.format(i)


rep_key_gen = replacement_key_generator()


class EntityNode(AbstractNode):
    """
    Container to represent a node in a networkx graph (for visualization)
    """

    def __init__(self, entity: p.Entity, url_template: str):
        super().__init__()

        self.short_key = entity.short_key
        self.url_template = url_template

        # TODO: handle different languages here
        self.label = self.smart_label = entity.R1

        unformated_repr_str = f'{self.short_key}["{self.smart_label}"]'
        self.repr_str = format_repr_str(unformated_repr_str)

    def __repr__(self) -> str:
        """
        Set the label to a string which will be later replaced by a link-wrapped label.
        This two-step process is necessary due to the internal escaping of the graph-viz rendering.

        :return:
        """

        url = self.url_template.format(short_key=self.short_key)
        res = []

        # this loop is to handle multiline lables (wich are introduced in self.smart_label for better space efficiency)
        for substr in self.repr_str.split("\n"):
            rep_key = next(rep_key_gen)
            REPLACEMENTS[rep_key] = f'<a href="{url}">{substr}</a>'
            res.append(f"{{{rep_key}}}")  # create a string like "{_rk_0123}" which will be replaced later

        return "\n".join(res)


class LiteralStrNode(AbstractNode):
    def __init__(self, arg: str):
        super().__init__()

        self.repr_str = arg


def create_node(arg: Union[p.Entity, object], url_template: str):

    if isinstance(arg, p.Entity):
        return EntityNode(arg, url_template)
    elif isinstance(arg, str):
        return LiteralStrNode(f'"{arg}"')
    else:
        return LiteralStrNode(f"{type(arg).__name__}({str(arg)})")


def rel_label(rel: p.Relation):
    return f'{rel.short_key}["{rel.R1}"]'


def format_repr_str(label: str, maxlen: int = 17) -> str:
    """
    Introduce newlines into entity repr_strings for better space usage and readibility

    Examples:
    - I4321["quite long label with many words"] -> I4321\n["quite long label\nwith many words"]
    - I4321["not so long"] -> I4321\n["not so long"]

    :param label:   label string
    :param maxlen:  maximum length of each line

    :return:    strings with newlines
    """

    # TODO: this should be ensured during data loading
    assert "\n" not in label
    assert label == label.strip()

    if len(label) < maxlen:
        # short labels stay unchanged
        return label

    idx1 = label.find("[")
    if idx1 >= 0:
        result = [label[:idx1]]
        rest = label[idx1:]
    else:
        # nothing was found
        result = []
        rest = label

    split_chars = (" ", "-", "_")

    while len(rest) > maxlen:

        first_part = rest[:maxlen]

        # handle special case where the next character is a space
        if rest[maxlen] == " ":
            result.append(first_part)
            rest = rest[maxlen+1:]
            continue

        # make first_part as long as possible -> find the last split-char index
        for i, c in enumerate(first_part[::-1]):
            if c in split_chars:
                break
        else:
            # there was no break (no split char) -> split after first_part
            i = 0

        first_part_split_index = maxlen - i

        # rstrip to eliminate trainling spaces but not dashes etc
        new_line = first_part[:first_part_split_index].rstrip()
        result.append(new_line)
        rest = rest[first_part_split_index:]

    result.append(rest)

    return "\n".join(result)


def visualize_entity(ek, fpath=None, print_path=False, return_svg_data=False, url_template="") -> Union[bytes, nx.DiGraph]:
    entity = p.ds.get_entity(ek)
    re_dict = entity.get_relations()
    inv_re_dict = entity.get_inv_relations()

    G = nx.DiGraph()
    base_node = create_node(entity, url_template)
    G.add_node(base_node, color="#2ca02c", label=repr(base_node))

    for rel_key, re_list in list(re_dict.items()) + list(inv_re_dict.items()):
        if rel_key in REL_BLACKLIST:
            continue

        re_list: List[p.RelationEdge]
        for re in re_list:
            assert len(re.relation_tuple) == 3
            subj, pred, obj = re.relation_tuple

            if re.role == p.RelationRole.SUBJECT:
                other_node = create_node(obj, url_template)
                G.add_node(other_node, label=repr(other_node))
                G.add_edge(base_node, other_node, label=rel_label(pred))
            else:
                other_node = create_node(subj, url_template)
                G.add_node(other_node, label=repr(other_node))
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
            "label": d.get("label", "undefined label")
        },
        # u: node1, v: node1, d: its attribute dict
        edge=lambda u, v, d: {**edge_defaults, "label": d["label"]},
    )

    svg_data = nxv.render(G, style, format="svg")

    # insert links (circumvent escaping)
    svg_data = svg_data.decode("utf8").format(**REPLACEMENTS).encode("utf8")

    if return_svg_data:
        return svg_data

    if fpath is None:
        fpath = "./tmp.svg"

    with open(fpath, "wb") as svgfile:
        svgfile.write(svg_data)

    if print_path:
        print(p.aux.bcyan(f"File written: {os.path.abspath(fpath)}"))

    # return the graph for unittest purposes
    return G
