"""
Created: 2022-09-06 19:14:39
author: Carsten Knoll

This module contains code to enable semantic inferences based on special items (e.g. instances of I41__semantic_rule)

"""

from typing import List, Tuple, Optional

import networkx as nx
from networkx.algorithms import isomorphism as nxiso
# noinspection PyUnresolvedReferences
from addict import Addict as Container

# noinspection PyUnresolvedReferences
from ipydex import IPS

from . import core
from . import builtin_entities as bi
from . import builtin_entities as b


def apply_all_semantic_rules(mod_context_uri=None):
    rule_instances = get_all_rules()
    new_rledg_list = []
    for rule in rule_instances:
        ra = RuleApplicator(rule, mod_context_uri=mod_context_uri)
        res = ra.apply()
        new_rledg_list.extend(res)


def get_all_rules():

    rule_instances: list = b.I41["semantic rule"].get_inv_relations("R4__is_instance_of", return_subj=True)

    return rule_instances


def filter_relevant_rledgs(re_list: List[core.RelationEdge]) -> List[core.RelationEdge]:
    """
    From a list of RelationEdge instances select only those which are qualifiers and whose subject is an
    RE with .role == SUBJECT.
    In other words: omit those instances which are created as dual relation edges

    :param re_list:
    :return:
    """

    res = []
    for rledg in re_list:
        assert isinstance(rledg, core.RelationEdge)
        if isinstance(rledg.subject, core.RelationEdge) and rledg.subject.role == core.RelationRole.SUBJECT:
            res.append(rledg.subject)
    return res


class RuleApplicator:
    """
    Class to handle the application of a single semantic rule.
    """
    def __init__(self, rule: core.Entity, mod_context_uri: Optional[str] = None):
        self.rule = rule
        self.mod_context_uri = mod_context_uri

        self.vars = rule.scp__context.get_inv_relations("R20__has_defining_scope", return_subj=True)
        self.premises_rledgs = filter_relevant_rledgs(rule.scp__premises.get_inv_relations("R20"))
        self.assertions_rledgs = filter_relevant_rledgs(rule.scp__assertions.get_inv_relations("R20"))

        # a: {rule_sope_uri1: P_node_index1, ...}, b: {P_node_index1: rule_sope_uri1, ...}
        self.local_nodes = core.aux.OneToOneMapping()

        self.G: nx.DiGraph = create_simple_graph()

        self.P: nx.DiGraph = self.create_prototype_subgraph_from_rule()

    def apply(self) -> List[core.RelationEdge]:

        if self.mod_context_uri is None:
            assert core.get_active_mod_uri(strict=True)
            res = self._apply()
        else:
            core.aux.ensure_valid_baseuri(self.mod_context_uri)
            with core.uri_context(self.mod_context_uri):
                res = self._apply()
        return res

    def _apply(self) -> List[core.RelationEdge]:

        result_map = self.match_subgraph_P()

        asserted_relation_templates = self.get_asserted_relation_templates()

        new_rledg_list = []

        for res_dict in result_map:
            # res_dict represents one situation where the assertions should be applied
            # it's a dict like
            # {
            #       0: <Item I2931["local ljapunov stability"]>,
            #       1: <Item I4900["local asymtotical stability"]>,
            #       2: <Item I9642["local exponential stability"]>
            #  }

            for n1, rel, n2 in asserted_relation_templates:

                new_subj = res_dict[n1]
                new_obj = res_dict[n2]

                assert isinstance(rel, core.Relation)
                assert isinstance(new_subj, core.Entity)

                # TODO: add qualifiers
                new_rledg = new_subj.set_relation(rel, new_obj)
                new_rledg_list.append(new_rledg)

        return new_rledg_list

    def get_asserted_relation_templates(self) -> List[Tuple[int, core.Relation, int]]:

        res = []
        for rledg in self.assertions_rledgs:
            sub, pred, obj = rledg.relation_tuple
            assert isinstance(pred, core.Relation)

            # todo: handle literals here
            assert isinstance(obj, core.Entity)
            res.append((self.local_nodes.a[sub.uri], pred, self.local_nodes.a[obj.uri]))

        return res

    def match_subgraph_P(self) -> List[dict]:
        assert self.P is not None
        GM = nxiso.DiGraphMatcher(self.G, self.P, node_match=None, edge_match=edge_matcher)
        res = list(GM.subgraph_isomorphisms_iter())

        # invert the dicts (todo: find out why switching G and P does not work)
        # and introduce items for uris

        new_res = []
        for d in res:
            new_res.append(dict((v, core.ds.get_entity_by_uri(k)) for k, v in d.items()))

        # new_res is a list of dicts like
        # [{
        #   0: <Item I2931["local ljapunov stability"]>,
        #   1: <Item I4900["local asymtotical stability"]>,
        #   2: <Item I9642["local exponential stability"]>
        #  }, ... ]

        return new_res

    def create_prototype_subgraph_from_rule(self) -> nx.DiGraph:

        P = nx.DiGraph()

        # counter for node-values
        i = 0

        for var in self.vars:

            assert isinstance(var, core.Entity)

            if var.uri in self.local_nodes.a:
                continue

            c = Container()
            for relname in ["R3", "R4"]:
                try:
                    value = getattr(var, relname)
                except (AttributeError, KeyError):
                    value = None
                c[relname] = value
            P.add_node(i, itm=c)
            self.local_nodes.add_pair(var.uri, i)
            i += 1

        for rledg in self.premises_rledgs:

            subj, pred, obj = rledg.relation_tuple
            assert isinstance(subj, core.Entity)
            assert isinstance(pred, core.Relation)
            assert isinstance(obj, core.Entity)

            n1 = self.local_nodes.a[subj.uri]
            n2 = self.local_nodes.a[obj.uri]

            P.add_edge(n1, n2, rel_uri=pred.uri)

        components = list(nx.weakly_connected_components(P))
        if len(components) != 1:
            msg = (
                f"unexpected number of components of prototype graph while applying rule {self.rule}."
                f"Expected: 1, but got ({len(components)}). Possible reason: unuesed variables in the rules context."
            )
            raise core.aux.SemanticRuleError(msg)

        return P


def edge_matcher(e1d: dict, e2d: dict) -> bool:
    """

    :param e1d:     attribute data of edge from "main graph" (see below)
    :param e2d:     attribute data of edge from "prototype graph" (see below)

    :return:        boolean matching result

    An edge should match if
        - the relation uri is the same


    """

    if e1d["rel_uri"] != e2d["rel_uri"]:
        return False

    return True


def create_simple_graph() -> nx.DiGraph:
    """
    Create graph without regarding qualifiers. Nodes: uris

    :return:
    """
    G = nx.DiGraph()

    for item_uri, item in core.ds.items.items():

        if is_node_for_simple_graph(item):
            G.add_node(item_uri, itm=item)

    all_rels = get_all_node_relations()
    for uri_tup, rel_cont in all_rels.items():
        uri1, uri2 = uri_tup
        if uri1 in G.nodes and uri2 in G.nodes:
            G.add_edge(*uri_tup, itm1=core.ds.get_entity_by_uri(uri1), itm2=core.ds.get_entity_by_uri(uri2), **rel_cont)

    return G


def is_node_for_simple_graph(item: core.Item) -> bool:
    """
    exclude nodes which are defined inside certain scopes

    :param item:
    :return:
    """
    assert isinstance(item, core.Item)
    r20_rels = item.get_relations("R20__has_defining_scope")

    if not r20_rels:
        return True
    assert len(r20_rels) == 1  # R20 is functional (R22)

    obj = r20_rels[0].relation_tuple[-1]
    assert obj.R4__is_instance_of == bi.I16["scope"]

    # TODO: maybe add some exceptions (allowed scopes for inferrencing) here

    return False


def get_simple_properties(item: core.Item) -> dict:

    rledg_dict = item.get_relations()
    res = {}
    for rel_uri, rledg_list in rledg_dict.items():

        for rledg in rledg_list:
            assert isinstance(rledg, core.RelationEdge)
            assert len(rledg.relation_tuple) == 3
            if rledg.corresponding_entity is None:
                assert rledg.corresponding_literal is not None
                res[rel_uri] = rledg.corresponding_literal
                # TODO: support multiple relations in the graph (MultiDiGraph)
                break

    return res


def get_all_node_relations() -> dict:

    res = {}
    for entity_uri, rledg_dict in core.ds.relation_edges.items():
        entity = core.ds.get_entity_by_uri(entity_uri, strict=False)
        if not isinstance(entity, core.Item):
            continue

        for rel_uri, rledg_list in rledg_dict.items():
            for rledg in rledg_list:
                assert isinstance(rledg, core.RelationEdge)
                assert len(rledg.relation_tuple) == 3
                if rledg.corresponding_entity is not None:
                    assert rledg.corresponding_literal is None
                    if not isinstance(rledg.corresponding_entity, core.Item):
                        # some relation edges point to an relation-type
                        # (maybe this will change in the future)
                        continue
                    c = Container(rel_uri=rel_uri)
                    res[(entity_uri, rledg.corresponding_entity.uri)] = c
                    # TODO: support multiple relations in the graph (MultiDiGraph)
                    break
    return res
