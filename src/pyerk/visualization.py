"""
This module contains code for the visualization of ERK-entities.
"""
from typing import Union, List, Tuple, Optional
import os
import urllib

import networkx as nx
import nxv  # for graphviz visualization of networkx graphs

# TODO: this should be a relative import of the *package*
import pyerk as p
from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()

# TODO: make this a  dict to speedup lookup
#  tuple of Relation keys which are not displayed by default
REL_BLACKLIST = ("erk:/builtins#R1", "erk:/builtins#R2")

# from semantictools import core as smt

from abc import ABC

REPLACEMENTS = {}

NEWLINE_REPLACEMENTS = [("__newline-center__", r"\n"), ("__newline-left__", r"\l")]

# default matplotlib colors
mpl_colors = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


class AbstractGraphObject(ABC):
    """
    Common base class for nodes and edges
    """

    def __init__(self):
        self.uri = None
        self.short_key = None
        self.repr_str: str = ""  # TODO: obsolete ?
        self.label: str = ""
        self.smart_label: str = ""  # TODO: obsolete
        self.replaced_repr_str = None
        self.id = None
        self.sep: str = ""

        # default shape
        self.shape = None

        self.maxlen: Union[int, None] = None
        self.url_template: Union[None, str] = None

        # will be set in some subclasses calling self._perform_label_segmentation
        self.label_segment_keys = None
        self.label_segments = None
        self.label_segment_items = None
        self.dot_label_str = None

    def _perform_label_segmentation(self) -> None:
        """
        handle label formatting (segmentation into multiple lines and later wrapping by html tags)

        labels of Nodes should be centered (dot file should contain r"\n" bewteen segments)
        hower neither using "\n" nor r"\n" inside the nxv-node-labels leads to the desired results
        thus: use a dummy which will be replaced later
        """

        # TODO: replace this by prefixed short_key
        unformated_repr_str = f'{self.short_key}["{self.label}"]'
        self.label_segment_keys, self.label_segments = create_label_segments(unformated_repr_str, maxlen=self.maxlen)
        self.label_segment_items = zip(self.label_segment_keys, self.label_segments)

        # wrap the each key with curly braces to allow application of .format(...) later]
        self.dot_label_str = self.sep.join([f"{{{key_str}}}" for key_str in self.label_segment_keys])

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self.short_key}>"

    def get_dot_label(self):
        return repr(self)

    def perform_html_wrapping(self, use_html=True) -> None:
        """
        Assigns the segment key to the actual html-wrapped string. This pair will be used later by .format
        to modify the generated svg-data

        This two-step process is necessary due to the internal escaping of the graph-viz rendering.

        :return:    None
        """

        if self.url_template is None:
            # do nothing
            return

        # noinspection PyUnresolvedReferences
        quoted_uri = urllib.parse.quote(self.uri, safe="")
        url = self.url_template.format(quoted_uri=quoted_uri)

        for seg_key, segment in self.label_segment_items:
            if use_html:
                REPLACEMENTS[seg_key] = f'<a href="{url}">{segment}</a>'
            else:
                REPLACEMENTS[seg_key] = segment


def key_generator(template="k{:04d}"):
    i = -1
    while True:
        i += 1
        yield template.format(i)


# for label segments
label_segment_key_gen = key_generator(template="LS{:04d}_")
literal_node_key_gen = key_generator(template="LN{:04d}")
relation_key_gen = key_generator(template="R{:04d}")


class EntityNode(AbstractGraphObject):
    """
    Container to represent a node in a networkx graph (for visualization)
    """

    def __init__(self, entity: p.Entity, url_template: str):
        super().__init__()

        self.short_key = entity.short_key
        self.uri = entity.uri

        # TODO: replace this by prefixed short_key
        self.id = f"node_{self.short_key}"  # this serves to recognize the nodes in svg code
        self.url_template = url_template

        if isinstance(entity, p.Item):
            self.shape = "circle"
        elif isinstance(entity, p.Relation):
            self.shape = "hexagon"
        elif isinstance(entity, p.RelationEdge):
            self.shape = "cds"
        else:
            msg = f"Unexpected entity type: {type(entity)} during creation of EntityNode in visualization."
            raise TypeError(msg)

        # TODO: handle different languages here
        self.label = self.smart_label = entity.R1

        self.maxlen = 17
        self.sep = "__newline-center__"  # see NEWLINE_REPLACEMENTS
        self._perform_label_segmentation()

    def get_dot_label(self, render=False) -> str:

        if render:
            return render_label(self.dot_label_str)
        else:
            return self.dot_label_str


class LiteralStrNode(AbstractGraphObject):
    def __init__(self, arg: str):
        super().__init__()

        self.value = arg
        self.id = next(literal_node_key_gen)

        self.shape = "rectangle"  # will be overwritten by subclasses

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self.value}>"

    def get_dot_label(self):
        return self.value


class Edge(AbstractGraphObject):
    """
    This class models the graphviz representation of an edge between two nodes
    """

    def __init__(self, relation: p.Relation, url_template: str):
        super().__init__()

        self.uri = relation.uri
        self.short_key = relation.short_key
        self.label = relation.R1
        self.url_template = url_template
        self.id = next(relation_key_gen)
        self.sep = "__newline-left__"  # see NEWLINE_REPLACEMENTS
        self.maxlen = 17

        self._perform_label_segmentation()

    def _perform_label_segmentation(self) -> None:
        super()._perform_label_segmentation()

        # add self.sep at the end to ensure that the last line segment is also left adjusted
        self.dot_label_str = f"{self.dot_label_str}{self.sep}"

    def get_dot_label(self):
        return self.dot_label_str


def create_node(arg: Union[p.Entity, object], url_template: str):

    if isinstance(arg, p.Entity):
        return EntityNode(arg, url_template)
    elif isinstance(arg, str):
        return LiteralStrNode(f'"{arg}"')
    else:
        return LiteralStrNode(f"{type(arg).__name__}({str(arg)})")


def create_key_with_length(basic_key_gen: callable, length: int) -> str:

    base_key = next(basic_key_gen)

    relevant_length = length - 2  # (account for curly braces (see REMARK__curly_braces_wrapping))

    if relevant_length <= len(base_key):
        key_str = base_key
    else:

        assert relevant_length > 0
        assert length < 36, "unexpected long length"

        key_str = f"{base_key}1234567890abcdefghijklmnopqrstuvwxyz"[:length]

    return key_str


def create_label_segments(label: str, maxlen: int) -> Tuple[List[str], List[str]]:
    """
    Split label string into segments and assign a key to each. Return items.

    Examples:
    - I4321["quite long label with many words"] ->
        [("key0", 'I4321'), ("key1", '["quite long label'), ("key2", 'with many words"]')]

    :param label:   label string
    :param maxlen:  maximum length of each line

    :return:    (keys, segments)
    """

    # TODO: this should be ensured during data loading
    assert "\n" not in label
    assert label == label.strip()

    res_keys = []
    res_segments = []

    if len(label) < maxlen:
        # short labels stay unchanged
        key = create_key_with_length(label_segment_key_gen, len(label))
        res_segments.append(label)
        res_keys.append(key)
        return res_keys, res_segments

    # for now only create the segments, and create the keys later at once
    idx1 = label.find("[")
    if idx1 >= 0:
        res_segments.append(label[:idx1])
        rest = label[idx1:]
    else:
        # nothing was found
        rest = label

    split_chars = (" ", "-", "_", ":")

    while len(rest) > maxlen:

        first_part = rest[:maxlen]

        # handle special case where the next character is a space
        if rest[maxlen] == " ":
            res_segments.append(first_part)
            rest = rest[maxlen + 1 :]
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
        res_segments.append(new_line)
        rest = rest[first_part_split_index:]

    res_segments.append(rest)

    for segment in res_segments:
        key = create_key_with_length(label_segment_key_gen, len(segment))
        res_keys.append(key)

    return res_keys, res_segments


class CustomizedDiGraph(nx.DiGraph):
    def add_node(self, node: AbstractGraphObject, **kwargs):

        # set defaults
        # note: adding an id keyword here does not influence the id in the svg
        new_kwargs = dict(label=node.get_dot_label(), id=node.id, shape=node.shape)

        node.perform_html_wrapping()

        # overwrite with explicitly given kwargs
        new_kwargs.update(kwargs)

        super().add_node(node, **new_kwargs)


def create_nx_graph_from_entity(uri, url_template="") -> nx.DiGraph:
    """

    :param uri:
    :param url_template:
    :return:
    """

    entity = p.ds.get_entity_by_uri(uri)
    re_dict = entity.get_relations()
    inv_re_dict = entity.get_inv_relations()

    G = CustomizedDiGraph()
    base_node = create_node(entity, url_template)
    G.add_node(base_node, color="#2ca02c")

    for rel_key, re_list in list(re_dict.items()) + list(inv_re_dict.items()):
        if rel_key in REL_BLACKLIST:
            continue

        re_list: List[p.RelationEdge]
        for re in re_list:
            assert len(re.relation_tuple) == 3
            subj, pred, obj = re.relation_tuple

            edge = Edge(pred, url_template)
            edge.perform_html_wrapping()
            if re.role == p.RelationRole.SUBJECT:
                other_node = create_node(obj, url_template)
                G.add_node(other_node)
                G.add_edge(base_node, other_node, label=edge.get_dot_label())
            else:
                other_node = create_node(subj, url_template)
                G.add_node(other_node)
                G.add_edge(other_node, base_node, label=edge.get_dot_label())

    return G


def get_color_for_item(item: p.Item) -> str:
    # TODO: add color by base_uri
    if item.short_key == "I14":
        return "red"
    return "black"


def get_color_for_rledg(rledg: p.RelationEdge) -> str:
    cmap = {"R3": mpl_colors[0], "R4": mpl_colors[1]}

    return cmap.get(rledg.rsk, "black")


def create_complete_graph(
    url_template="",
    limit: Optional[int] = None,
) -> nx.DiGraph:
    """
    :param url_template:    template to insert links based on uris
    :param limit:
    :return:
    """

    added_items_nodes = {}
    added_relation_edges = {}
    G = nx.DiGraph()

    i = 0
    relation_dict: dict
    for item_uri, relation_dict in p.ds.relation_edges.items():
        item = p.ds.get_entity_by_uri(item_uri)
        if not isinstance(item, p.Item) or item.short_key in ["I000"]:
            continue
        # count only items
        i += 1
        if limit and i == limit:
            break

        if node := added_items_nodes.get(item_uri):
            pass
        else:
            node = create_node(item, url_template)
        G.add_node(node, label=item.short_key, color=get_color_for_item(item))
        added_items_nodes[item_uri] = node

        # iterate over relation edges
        for relation_uri, rledg_list in relation_dict.items():
            rledg: p.RelationEdge
            for rledg in rledg_list:
                if rledg.role != p.RelationRole.SUBJECT:
                    continue
                if rledg.relation_tuple[1].uri in REL_BLACKLIST:
                    continue

                obj = rledg.relation_tuple[-1]
                if isinstance(obj, p.Item):
                    if other_node := added_items_nodes.get(obj.uri):
                        pass
                    else:
                        other_node = create_node(obj, url_template)
                        G.add_node(other_node, label=obj.short_key, color=get_color_for_item(obj))
                        added_items_nodes[obj.uri] = other_node
                else:
                    # obj is a literal, we omit that for now
                    continue

                # edge_label = f"{rledg.relation_tuple[1].short_key}"
                edge_label = f"{rledg.relation_tuple[1].short_key}"
                G.add_edge(node, other_node, label=edge_label, color=get_color_for_rledg(rledg))

                assert rledg.uri not in added_relation_edges
                added_relation_edges[rledg.uri] = 1

    return G


def render_graph_to_dot(G: nx.DiGraph) -> str:
    """

    :param G:       nx.DiGraph; the graph to render
    :return:        dot_data
    """

    # for styling see https://nxv.readthedocs.io/en/latest/reference.html#styling
    # matplotlib default colors:
    # ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    edge_defaults = {
        "style": "solid",
        "arrowType": "normal",
        "fontsize": 10,
        # "labeljust": "r",
    }
    style = nxv.Style(
        graph={"rankdir": "BT"},
        # u: node, d: its attribute dict
        node=lambda u, d: {
            "fixedsize": True,
            "width": 1.3,
            "fontsize": 10,
            "color": d.get("color", "black"),
            "label": d.get("label", "undefined label"),
            "shape": d.get("shape", "circle"),  # see also AbstractNode.shape
        },
        # u: node1, v: node1, d: its attribute dict
        edge=lambda u, v, d: {**edge_defaults, "label": d["label"]},
    )

    # noinspection PyTypeChecker
    dot_data: str = nxv.render(G, style, format="raw")

    return dot_data


def visualize_entity(uri: str, url_template="", write_tmp_files: bool = False) -> str:
    """

    :param uri:             entity uri (like "erk:/my/module#I0123")
    :param url_template:    url template for creation of a-tags (html links) for the labels
    :param write_tmp_files: boolean flag whether to write debug output

    :return:                svg_data as string
    """

    G = create_nx_graph_from_entity(uri, url_template)
    raw_dot_data = render_graph_to_dot(G)

    dot_data0 = raw_dot_data
    for old, new in NEWLINE_REPLACEMENTS:
        dot_data0 = dot_data0.replace(old, new)

    # work arround curly braces in first and last line
    dot_lines = dot_data0.split("\n")
    inner_dot_code = "\n".join(dot_lines[1:-1])

    dot_data = "\n".join((dot_lines[0], inner_dot_code, dot_lines[-1]))

    # noinspection PyUnresolvedReferences,PyProtectedMember
    raw_svg_data = nxv._graphviz.run(dot_data, algorithm="dot", format="svg", graphviz_bin=None)

    svg_data1: str = raw_svg_data.decode("utf8").format(**REPLACEMENTS)

    if write_tmp_files:
        # for debugging

        dot_fpath = "./tmp_dot.txt"
        with open(dot_fpath, "w") as txtfile:
            txtfile.write(dot_data)
        print("File written:", os.path.abspath(dot_fpath))

        svg_fpath = "./tmp.svg"
        with open(svg_fpath, "w") as txtfile:
            txtfile.write(svg_data1)
        print("File written:", os.path.abspath(svg_fpath))

    return svg_data1


def visualize_all_entities(url_template="", write_tmp_files: bool = False) -> str:

    G = create_complete_graph(url_template)

    print(f"Visualizing {len(G.nodes)} nodes and {len(G.edges)} edges.")

    # styling and rendering

    edge_defaults = {
        "style": "solid",
        "arrowType": "normal",
        "fontsize": 10,
        # "labeljust": "r",
    }
    style = nxv.Style(
        graph={"rankdir": "BT"},
        # u: node, d: its attribute dict
        node=lambda u, d: {
            "fixedsize": True,
            "width": 1.3,
            "fontsize": 10,
            "color": d.get("color", "black"),
            "label": d.get("label", "undefined label"),
            "shape": d.get("shape", "circle"),  # see also AbstractNode.shape
        },
        # u: node1, v: node1, d: its attribute dict
        edge=lambda u, v, d: {
            **edge_defaults,
            # "label": d["label"]
        },
    )

    style = nxv.Style(
        graph={"rankdir": "BT", "nodesep": 0.2},
        node=lambda u, d: {
            # "shape": "point",
            "shape": "circle",
            "style": "filled",
            "fixedsize": True,
            "color": d.get("color", "black"),
            "width": .3,
            "fontsize": 2,
            "label": d.get("label", "undefined label"),
            "fillcolor": "#45454533",
        },
        edge=lambda u, v, d: {
            "style": "solid",
            "arrowhead": "normal",
            "color": d.get("color", "#959595ff"),
            "arrowsize": 0.5,
            # "label": d["label"]
        },
    )

    # noinspection PyTypeChecker
    raw_dot_data: str = nxv.render(G, style, format="raw")

    # optional: preprocessing
    dot_data = raw_dot_data
    # noinspection PyUnresolvedReferences,PyProtectedMember
    raw_svg_data = nxv._graphviz.run(dot_data, algorithm="dot", format="svg", graphviz_bin=None)
    svg_data1: str = raw_svg_data.decode("utf8").format(**REPLACEMENTS)

    if write_tmp_files:
        # for debugging

        dot_fpath = "./t#mp_dot.txt"
        with open(dot_fpath, "w") as txtfile:
            txtfile.write(dot_data)
        print("File written:", os.path.abspath(dot_fpath))

        svg_fpath = "./tmp.svg"
        with open(svg_fpath, "w") as txtfile:
            txtfile.write(svg_data1)
        print("File written:", os.path.abspath(svg_fpath))

    print(G.number_of_nodes(), "nodes")
    print(G.number_of_edges(), "edges")

    return svg_data1


def render_label(label: str):
    res = label
    for old, new in NEWLINE_REPLACEMENTS:
        res = res.replace(old, new)

    return res.format(**REPLACEMENTS)
