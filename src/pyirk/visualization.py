"""
This module contains code for the visualization of IRK-entities.
"""

from typing import Union, List, Tuple, Optional
import os
import urllib
from rdflib import Literal
import subprocess
import re
import time

import networkx as nx
import nxv  # for graphviz visualization of networkx graphs

# prevent deprecation warning because nxv is not as up-to-date as nx (of which it depends)
if hasattr(nx, "OrderedDiGraph"):
    # usage of OrderedDiGraph is deprecated
    nxv._util.GRAPH_TYPES[True, False, True] = nx.DiGraph

# TODO: this should be a relative import of the *package*
import pyirk as p
from pyirk.utils import render_template
from ipydex import IPS, activate_ips_on_exception

__all__ = ["visualize_entity", "visualize_all_entities"]

activate_ips_on_exception()

# TODO: make this a  dict to speedup lookup
#  tuple of Relation keys which are not displayed by default

from abc import ABC

REPLACEMENTS = {}

NEWLINE_REPLACEMENTS = [("__newline-center__", r"\n"), ("__newline-left__", r"\l")]

# default matplotlib colors, orange and blue swapped
mpl_colors = [
    "#ff7f0e",
    "#1f77b4",
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

        labels of Nodes should be centered (dot file should contain r"\n" between segments)
        however neither using "\n" nor r"\n" inside the nxv-node-labels leads to the desired results
        thus: use a dummy which will be replaced later
        """

        # TODO: replace this by prefixed short_key
        if self.short_key.startswith("Ia"):
            unformatted_repr_str = f"{self.short_key}"
        else:
            unformatted_repr_str = f"{self.short_key}[{self.label}]"
        self.label_segment_keys, self.label_segments = create_label_segments(
            unformatted_repr_str, maxlen=self.maxlen
        )
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
            self.shape = "octagon"
        elif isinstance(entity, p.Statement):
            self.shape = "cds"
        else:
            msg = f"Unexpected entity type: {type(entity)} during creation of EntityNode in visualization."
            raise TypeError(msg)

        # TODO: handle different languages here
        self.label = self.smart_label = entity.R1

        self.maxlen = 12
        self.sep = "__newline-center__"  # see NEWLINE_REPLACEMENTS
        self._perform_label_segmentation()

    def get_dot_label(self, render=False) -> str:
        if render:
            return vm.render_label(self.dot_label_str)
        else:
            return self.dot_label_str

    def get_color(self) -> str:
        if self.short_key.startswith("Ia"):
            return "grey"
        else:
            return "black"


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

    def get_color(self) -> str:
        clr = mpl_colors[(int(self.short_key[1:]) - 1) % len(mpl_colors)]
        return clr


def create_node(arg: Union[p.Entity, object], url_template: str) -> AbstractGraphObject:
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
        [("key0", 'I4321'), ("key1", '[quite long label'), ("key2", 'with many words]')]
        # note: for the sake of brevity we skip quotes inside of [...]

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

        # rstrip to eliminate trailing spaces but not dashes etc
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

class VisualizationManager():

    def __init__(self):
        self.REL_BLACKLIST = [
            "irk:/builtins#R1",
            "irk:/builtins#R2",
        ]



    def create_nx_graph_from_entity(self, uri, url_template="") -> nx.DiGraph:
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
            if rel_key in self.REL_BLACKLIST:
                continue

            re_list: List[p.Statement]
            # TODO: Make this hack visible from the outside
            # we only display a limited amount of automatically created ("Ia") items or literals
            a_node_cnt = 0
            for re in re_list:
                assert len(re.relation_tuple) == 3
                subj, pred, obj = re.relation_tuple

                edge = Edge(pred, url_template)
                edge.perform_html_wrapping()
                if re.role == p.RelationRole.SUBJECT:

                    if not isinstance(obj, p.Entity):
                        # we do not display literals
                        continue

                    if "Ia" in obj.short_key and a_node_cnt > 2:
                        continue
                    other_node = create_node(obj, url_template)
                    G.add_node(other_node, color=other_node.get_color())
                    G.add_edge(
                        base_node,
                        other_node,
                        edge=edge,
                        short_key=edge.short_key,
                        label=edge.get_dot_label(),
                        color=edge.get_color(),
                    )
                else:
                    if "Ia" in subj.short_key and a_node_cnt > 2:
                        continue
                    other_node = create_node(subj, url_template)
                    G.add_node(other_node, color=other_node.get_color())
                    G.add_edge(
                        other_node,
                        base_node,
                        edge=edge,
                        hort_key=edge.short_key,
                        label=edge.get_dot_label(),
                        color=edge.get_color(),
                    )

                if "Ia" in other_node.short_key:
                    a_node_cnt += 1

        return G


    def get_color_for_item(self, item: p.Item) -> str:
        # TODO: add color by base_uri
        if "Ia" in item.short_key:
            return "grey"
        # if item.short_key == "I14":
        #     return "red"
        return "black"


    def get_color_for_stm(self, stm: p.Statement) -> str:
        # TODO: unfuck this
        return mpl_colors[(int(stm.rsk[1:]) - 1) % len(mpl_colors)]


    def create_complete_graph(
        self,
        url_template="",
        limit: Optional[int] = None,
        skip_auto_items: bool = False,
        vis_relations: bool = False,
    ) -> nx.DiGraph:
        """
        :param url_template:    template to insert links based on uris
        :param limit:
        :return:
        """

        added_items_nodes = {}
        added_statements = {}

        # using this subclass ensures our html-wrapping is called when a node is added
        G = CustomizedDiGraph()

        i = 0
        relation_dict: dict
        for item_uri, relation_dict in list(p.ds.statements.items()):
            item = p.ds.get_entity_by_uri(item_uri, strict=None)
            if item is None:
                # this is the case for some statements which are subject of a qualifier relation
                assert item_uri in p.ds.statement_uri_map
                continue
            if item.short_key in ["I000"]:
                continue
            if vis_relations:
                if (not isinstance(item, p.Item) and not isinstance(item, p.Relation)):
                    continue # what possible type could item have to get here?
            else:
                if not isinstance(item, p.Item):
                    continue
            if skip_auto_items and "Ia" in item.short_key:
                continue
            # count only items
            i += 1
            if limit and i == limit:
                break

            if node := added_items_nodes.get(item_uri):
                pass
            else:
                node = create_node(item, url_template)
            G.add_node(node)
            added_items_nodes[item_uri] = node

            # iterate over relation edges
            for relation_uri, stm_list in relation_dict.items():
                stm: p.Statement
                for stm in stm_list:
                    if stm.role != p.RelationRole.SUBJECT:
                        continue
                    if stm.relation_tuple[1].uri in self.REL_BLACKLIST:
                        continue

                    subj, pred, obj = stm.relation_tuple
                    if isinstance(obj, p.Item):
                        if skip_auto_items and "Ia" in obj.short_key:
                            continue
                        if other_node := added_items_nodes.get(obj.uri):
                            pass
                        else:
                            other_node = create_node(obj, url_template)
                            G.add_node(other_node)
                            added_items_nodes[obj.uri] = other_node
                    else:
                        # obj is a literal, we omit that for now
                        continue

                    G.add_edge(node, other_node, edge=pred)

                    assert stm.uri not in added_statements
                    added_statements[stm.uri] = 1

        # for easier uri-based access to the nodes we store these dicts as attributes to the Graph
        G._items = added_items_nodes
        G._statements = added_statements
        return G


    def render_graph_to_dot(self, G: nx.DiGraph, center_node=None) -> str:
        """

        :param G:       nx.DiGraph; the graph to render
        :return:        dot_data
        """

        ecm = self.build_edge_color_map(G)
        def get_node_color(node):
            if node.short_key.startswith("Ia"):
                return "grey"
            elif node == center_node:
                return "red"
            else:
                return "black"

        # for styling see https://nxv.readthedocs.io/en/latest/reference.html#styling
        style = nxv.Style(
            graph={
                "layout": "sfdp",
                "overlap": "prism",
                # "overlap_shrink": True,
                "dim": 2,
                "dimen": 2,
                # "beautify": True,
                # "overlap_scaling": -5.5,
                # "beautify": False,
                # "overlap_scaling": -3.0,
                "outputorder": "edgesfirst",
            },
            # u: node, d: its attribute dict
            node=lambda u, d: {
                "fixedsize": True,
                "width": 1.3,
                "height": 1.3,
                "shape": d.get("shape", "circle"),  # see also AbstractNode.shape
                "style": "filled",
                "color": get_node_color(u),
                "fillcolor": "#eeeeeedd" if "Ia" not in u.short_key else "#dddddddd",
                # Label
                "label": u.get_dot_label(),
                "fontsize": 20,
                "fontcolor": "grey" if u.short_key.startswith("Ia") else "black",
                "URL": f"{u.short_key}.html",   # for interactive map
                "target": "_self",              # for interactive map

            },
            # u,v: nodes, d: edge attribute dict
            edge=lambda u, v, d: {
                # arrow
                "style": "solid",
                "arrowType": "normal",
                "penwidth": 2,
                # label
                "label": d["edge"].short_key,
                "fontsize": 20,
                "color": ecm.get(d["edge"].short_key, "black"),
                "URL":  d["edge"].R1.value, # this will be replaced later
            },
        )

        edge_first = True
        # edge_first = False

        def node_sort_func(args: Tuple[AbstractGraphObject, dict]):
            u, d = args
            if edge_first:
                # get edge that starts or ends at this node
                for (_u, _v), _d in G.edges.items():
                    if _u == u:
                        return float(_d["edge"].short_key[1:])
                    elif _v == u:
                        return float(_d["edge"].short_key[1:]) + 0.5
                else:
                    print(f"Node {u} has no edge")
            return u.short_key

        def edge_sort_func(args: Tuple[AbstractGraphObject, AbstractGraphObject, dict]):
            u, v, d = args
            if edge_first:
                return int(d["edge"].short_key[1:])
            else:
                return 0

        # sort the graph
        og = nxv.to_ordered_graph(G, node_key=node_sort_func, edge_key=edge_sort_func)
        # noinspection PyTypeChecker
        dot_data: str = nxv.render(og, style, format="raw")

        return dot_data


    def build_edge_color_map(self, G):
        # count the appearances of all edges
        key_counts = {}
        for u, v, e in G.edges.data("edge"):
            skey = e.short_key
            if skey in key_counts:
                key_counts[skey] += 1
            else:
                key_counts[skey] = 1
        # sort them by number of their appearance
        ranked_keys = [k for k, cnt in sorted(key_counts.items(), key=lambda x: x[1], reverse=True)]
        # color them using the mpl colors in descending order
        edge_color_map = dict(zip(ranked_keys, mpl_colors))

        return edge_color_map


    def svg_replace(self, raw_svg_data: str, REPLACEMENTS: dict) -> str:
        assert isinstance(raw_svg_data, str)

        # prevent some latex stuff to interfere with the handing of the `REPLACEMENTS`
        # TODO: handle the whole problem more elegantly

        latex_replacements = [(r"\dot{x}", "__LATEX1__")]
        for orig, subs in latex_replacements:
            raw_svg_data = raw_svg_data.replace(orig, subs)

        svg_data1: str = raw_svg_data.format(**REPLACEMENTS)

        for orig, subs in latex_replacements:
            svg_data1 = svg_data1.replace(subs, orig)

        return svg_data1


    def visualize_entity(self, uri: str, url_template="", write_tmp_files: Union[bool, str] = False, radius=1, graph=None, vis_relations=False) -> str:
        """

        :param uri:             entity uri (like "irk:/my/module#I0123")
        :param url_template:    url template for creation of a-tags (html links) for the labels
        :param write_tmp_files: flag whether to write debug output. if true, writes to cwd, if pathlike, writes to that dir or file.

        :return:                svg_data as string
        """
        if graph is None:
            big_G = self.create_complete_graph(url_template, vis_relations=vis_relations)
        else:
            big_G = graph
        try:
            node_of_interest = big_G._items[uri]
        except KeyError:
            msg = f"URI '{uri}' could not be found in the complete knowledge graph"
            raise p.InvalidURIError(msg)

        small_G = nx.ego_graph(big_G, node_of_interest, radius, undirected=True) #! perfomance of this operation sucks
        raw_dot_data = self.render_graph_to_dot(small_G, node_of_interest)

        dot_data0 = raw_dot_data
        for old, new in NEWLINE_REPLACEMENTS:
            dot_data0 = dot_data0.replace(old, new)

        # work around curly braces in first and last line
        dot_lines = dot_data0.split("\n")
        inner_dot_code = "\n".join(dot_lines[1:-1])

        dot_data = "\n".join((dot_lines[0], inner_dot_code, dot_lines[-1]))

        # noinspection PyUnresolvedReferences,PyProtectedMember
        raw_svg_data = nxv._graphviz.run(dot_data, algorithm="dot", format="svg", graphviz_bin=None)
        raw_svg_data = raw_svg_data.decode("utf8")
        svg_data1 = self.svg_replace(raw_svg_data, REPLACEMENTS)
        # todo legend for relations

        # Extract relations from the rendered graph and build color mapping

        # Get unique relations from the graph edges
        unique_relations = {}
        for u, v, edge_data in small_G.edges(data=True):
            if 'edge' in edge_data:
                relation = edge_data['edge']
                unique_relations[relation.short_key] = relation

        list_of_relations = list(unique_relations.values())
        relation_color_map = self.build_edge_color_map(small_G)

        # for interactive graph, we need hyperlinks. these mess up the svg with <> inside attributes -> remove
        svg_data1 = re.sub(r'(?<=xlink:title=").+?(?=" target=)', "", svg_data1)

        if 1:
            # add legend
            svg_data_legend = self.add_legend(svg_data1, relation_color_map, list_of_relations)
        else:
            svg_data_legend = None

        if write_tmp_files:
            self.save_data_to_file(write_tmp_files, dot_data, svg_data1, svg_data_legend)

        return svg_data1

    def add_legend(self, svg_data, relation_color_map, list_of_relations):
        # Parse SVG to get dimensions
        # Extract SVG viewBox or width/height to determine positioning
        # currently the legend is added into the `svg-data`-graphics (and its width is changed).
        # I want a different behavior: The legend should be returned as a separate svg file.
        # The original svg_data should not be changed.

        viewbox_match = re.search(r'viewBox="([^"]*)"', svg_data)
        if viewbox_match:
            viewbox = viewbox_match.group(1).split()
            original_svg_width = float(viewbox[2])
            svg_height = float(viewbox[3])
        else:
            # Fallback to width/height attributes
            width_match = re.search(r'width="([^"]*)"', svg_data)
            height_match = re.search(r'height="([^"]*)"', svg_data)
            if width_match and height_match:
                original_svg_width = float(width_match.group(1).replace('pt', ''))
                svg_height = float(height_match.group(1).replace('pt', ''))
            else:
                # Default fallback
                original_svg_width, svg_height = 800, 600

        # Calculate new SVG width to accommodate legend
        legend_width = 220  # Space needed for legend
        new_svg_width = original_svg_width + legend_width

        # Update SVG dimensions
        if viewbox_match:
            # Update viewBox
            new_viewbox = f"0 0 {new_svg_width} {svg_height}"
            svg_data = re.sub(r'viewBox="[^"]*"', f'viewBox="{new_viewbox}"', svg_data)
        else:
            # Update width attribute
            svg_data = re.sub(r'width="[^"]*"', f'width="{new_svg_width}pt"', svg_data)

        # Legend positioning (upper right corner of expanded SVG)
        legend_x = original_svg_width + 20  # Start legend after original content with some padding
        legend_y = 20
        line_height = 45
        line_width = 180

        # Build legend SVG elements
        legend_elements = []

        for i, relation in enumerate(list_of_relations):
            y_pos = legend_y + i * line_height
            color = relation_color_map.get(relation.short_key, "black")

            # Get the name_labeled_key (assuming it's the R1 label)
            label = getattr(relation, 'name_labeled_key', relation.short_key)
            # if hasattr(relation, 'R1') and relation.R1:
            #     if hasattr(relation.R1, 'value'):
            #         label = relation.R1.value
            #     else:
            #         label = str(relation.R1)

            # Add text label above the line
            legend_elements.append(f'<text x="{legend_x}" y="{y_pos}" font-family="Arial" font-size="20" fill="black">{label}</text>')

            # Add colored horizontal line
            legend_elements.append(f'<line x1="{legend_x}" y1="{y_pos + 5}" x2="{legend_x + line_width}" y2="{y_pos + 5}" stroke="{color}" stroke-width="2"/>')

        # Insert legend into SVG before closing </svg> tag
        legend_svg = '\n'.join(legend_elements)
        svg_data = svg_data.replace('</svg>', f'{legend_svg}\n</svg>')

        return svg_data


    def get_label(self, entity):
        res = entity.get("label", "undefined label")
        if isinstance(res, Literal):
            return res.value
        return res


    def visualize_all_entities(self, url_template="", write_tmp_files: Union[bool, str] = False, skip_auto_items: bool = False, vis_relations=False) -> str:
        """visualize all entities loaded in datastore. output svg graph.

        Args:
            url_template (str, optional): _description_. Defaults to "".
            write_tmp_files (Union[bool, str], optional): if true, files will be saved to cwd. if pathlike, files will \
                be saved to that folder or file. Defaults to False.

        Returns:
            str: svg graph
        """
        G = self.create_complete_graph(url_template, skip_auto_items=skip_auto_items, vis_relations=vis_relations)

        print(f"Visualizing {len(G.nodes)} nodes and {len(G.edges)} edges.")
        ecm = self.build_edge_color_map(G)

        def edge_style(u, v, d):
            e = d["edge"]
            clr = ecm.get(e.short_key, "grey")
            return {
                "style": "solid",
                "arrowhead": "vee",
                "arrowsize": 0.3,
                "color": clr,
                "label": d["edge"].short_key,
                "URL":  d["edge"].R1.value, # this will be replaced later
            }

        # styling and rendering
        style = nxv.Style(
            graph={
                # layout algorithm
                "layout": "sfdp",
                "overlap": "prism",
                # "overlap_shrink": -10,
                "overlap_scaling": -10,
                # global settings
                "outputorder": "edgesfirst",  # such that nodes are above the edges
            },
            node=lambda u, d: {
                # shape and size of node symbol
                "shape": "circle",
                "fixedsize": True,
                "width": 0.3,
                "height": 0.3,
                "style": "filled",
                "color": "black" if "Ia" not in u.short_key else "gray",
                "fillcolor": "#bbbbbbdd" if "Ia" not in u.short_key else "#dddddddd",
                # shape size and content of node label
                "fontsize": 8,
                "fontcolor": "#555555" if "Ia" not in u.short_key else "#777777",
                # "label": None,
                # "label": u.short_key,
                "label": f"{u.short_key}\n{u.label.value}",
                "URL": f"{u.short_key}.html",   # for interactive map
                "target": "_self",              # for interactive map

            },
            edge=edge_style,
        )

        # noinspection PyTypeChecker
        raw_dot_data: str = nxv.render(G, style, format="raw")
        # optional: preprocessing
        dot_data = raw_dot_data
        # noinspection PyUnresolvedReferences,PyProtectedMember
        raw_svg_data = nxv._graphviz.run(dot_data, algorithm="sfdp", format="svg", graphviz_bin=None)
        svg_data1 = self.svg_replace(raw_svg_data.decode("utf8"), REPLACEMENTS)

        if write_tmp_files:
            self.save_data_to_file(write_tmp_files, dot_data, svg_data1)

        print(G.number_of_nodes(), "nodes")
        print(G.number_of_edges(), "edges")

        return svg_data1

    def save_data_to_file(self, mode, dot_data, svg_data, svg_data_legend=None):
        if isinstance(mode, str):
            if os.path.isdir(mode):
                dot_fpath = os.path.join(mode, "tmp_dot.dot")
                svg_fpath = os.path.join(mode, "tmp_svg.txt")
            else:
                dot_fpath = mode.split(".")[0] + ".dot"
                svg_fpath = mode.split(".")[0] + ".svg"
        else:
            svg_fpath = "./tmp.svg"
            dot_fpath = "./tmp_dot.txt"

        with open(dot_fpath, "wt", encoding="utf-8") as txtfile:
            txtfile.write(dot_data)
        print("File written:", os.path.abspath(dot_fpath))

        with open(svg_fpath, "wt", encoding="utf-8") as txtfile:
            txtfile.write(svg_data)
        print("File written:", os.path.abspath(svg_fpath))

        if svg_data_legend:
            svg_legend_fpath = svg_fpath.replace(".svg", "_legend.svg")
            with open(svg_legend_fpath, "wt", encoding="utf-8") as txtfile:
                txtfile.write(svg_data_legend)
            print("File written:", os.path.abspath(svg_legend_fpath))


    def render_label(self, label: str):
        res = label
        for old, new in NEWLINE_REPLACEMENTS:
            res = res.replace(old, new)

        return res.format(**REPLACEMENTS)

    def create_interactive_graph(self, url_template="", output_dir="graph_site", radius=1, skip_auto_items=True, skip_existing=False, vis_relations=False):
        os.makedirs(output_dir, exist_ok=True)

        G = self.create_complete_graph(url_template, skip_auto_items=skip_auto_items, vis_relations=vis_relations)
        print(f"Visualizing {len(G.nodes)} nodes and {len(G.edges)} edges.")

        for node in G.nodes:
            node_name = node.short_key
            # if skip_auto_items and "Ia" in node_name:
            #     continue
            print(node_name)
            dot_path = os.path.join(output_dir, f"{node_name}.dot")
            if skip_existing and os.path.isfile(dot_path):
                continue
            self.visualize_entity(node.uri, write_tmp_files=dot_path, radius=radius, graph=G)

            # create map
            cmapx_path = os.path.join(output_dir, f"{node_name}.map")
            res2 = subprocess.run(["dot", "-Tcmapx", "-o", cmapx_path, dot_path])
            assert res2.returncode == 0, f"{res2.stderr}"

            with open(cmapx_path, "r", encoding="utf-8") as f:
                image_map = f.read()

            # clean image map of replacement strings
            image_map = re.sub(r'(?<=href=")(.+?)(\.html".+?title=")(.+?)(?=")', lambda mo: mo.group(1)+mo.group(2)+mo.group(1), image_map)
            # correct tooltip for relations.
            # Expl.: tooltip attribute in style does not work since map area poly will not be rendered. so we use URL
            # to trick graphviz to render rect and then replace href and title to create tooltip
            image_map = re.sub(r'(?<=shape="rect")(.+?)(href=")(.+?)(" title=")(.+?)(?=")', lambda mo: mo.group(1)+mo.group(2)+""+mo.group(4)+mo.group(3), image_map)

            if node_name.startswith("I"):
                item = p.ds.items[node.uri]
            else:
                item = p.ds.relations[node.uri]

            desc = item.R2.value if item.R2 else ""
            # add usage hint, sometimes more expressive than R2
            desc += "<br>" + " ".join(item.R18) if item.R18 else ""

            context = {
                "title": node_name + " " + item.R1.value,
                "img_source": f"{node_name}.svg",
                "map": image_map,
                "desc": desc
            }
            res = render_template("node_template.html", context)
            with open(os.path.join(output_dir, f"{node_name}.html"), "w", encoding="utf-8") as f:
                f.write(res)

        # Index page
        dot_path = os.path.join(output_dir, "index.dot")
        self.visualize_all_entities(write_tmp_files=dot_path, skip_auto_items=skip_auto_items, vis_relations=vis_relations)

        # create map
        cmapx_path = os.path.join(output_dir, f"index.map")
        res2 = subprocess.run(["dot", "-Tcmapx", "-o", cmapx_path, dot_path])
        assert res2.returncode == 0, f"{res2.stderr}"

        with open(cmapx_path, "r", encoding="utf-8") as f:
            image_map = f.read()

        image_map = re.sub(
            r'(?<=shape="rect")(.+?)(href=")(.+?)(" title=")(.+?)(?=")',
            lambda mo: mo.group(1)+mo.group(2)+""+mo.group(4)+mo.group(3),
            image_map
        )

        context = {
            "title": "Overview",
            "img_source": f"index.svg",
            "map": image_map,
            "desc": f"Total number of Nodes: {len(G.nodes)}"
        }
        res = render_template("node_template.html", context)
        with open(os.path.join(output_dir, f"index.html"), "w", encoding="utf-8") as f:
            f.write(res)

vm = VisualizationManager()
# todo refactor this
visualize_entity = vm.visualize_entity
visualize_all_entities = vm.visualize_all_entities
create_nx_graph_from_entity = vm.create_nx_graph_from_entity

if __name__ == "__main__":
    # visualize_all_entities(write_tmp_files=True, skip_auto_items=True)
    vm.create_interactive_graph(vis_relations=True)
    # nl = p.irkloader.load_mod_from_path("output.py", "nl", "nonlinear")
    # visualize_entity("irk:/builtins#I31", write_tmp_files=True, radius=1)
