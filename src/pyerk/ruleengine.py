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

LITERAL_BASE_URI = "erk:/tmp/literals"


def apply_all_semantic_rules(mod_context_uri=None) -> List[core.RelationEdge]:
    """
    Extract all semantic rules and apply them.
    
    :returns:  list of newly created statements
    """
    rule_instances = get_all_rules()
    new_rledg_list = []
    for rule in rule_instances:
        res = apply_semantic_rule(rule, mod_context_uri)
        new_rledg_list.extend(res)
        
    return new_rledg_list

def apply_semantic_rule(rule: core.Item, mod_context_uri: str = None) -> List[core.RelationEdge]:
    """
    Create a RuleApplicator instance for the rules, execute its apply-method, return the result (list of new statements)
    """
    assert rule.R4__is_instance_of == b.I41["semantic rule"]
    ra = RuleApplicator(rule, mod_context_uri=mod_context_uri)
    res = ra.apply()
    return res
    


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

        # get all subjects (Entities or Statements of the setting-scope)
        subjects = rule.scp__context.get_inv_relations("R20__has_defining_scope", return_subj=True)
        self.vars = [s for s in subjects if isinstance(s, core.Entity)] 
        self.external_entities = rule.scp__context.get_relations("R55__uses_as_external_entity", return_obj=True)
        self.premises_rledgs = filter_relevant_rledgs(rule.scp__premises.get_inv_relations("R20"))
        self.assertions_rledgs = filter_relevant_rledgs(rule.scp__assertions.get_inv_relations("R20"))
        self.literals = {}

        # a: {rule_sope_uri1: P_node_index1, ...}, b: {P_node_index1: rule_sope_uri1, ...}
        self.local_nodes = core.aux.OneToOneMapping()

        self.G: nx.DiGraph = self.create_simple_graph()

        self.P: nx.DiGraph = self.create_prototype_subgraph_from_rule()

    def apply(self) -> List[core.RelationEdge]:
        """
        Application of a semantic rule either in a specified module context or in the currently active module.
        
        (A rule has to be applied in a module context because newly created entities must belong to some module)
        """

        if self.mod_context_uri is None:
            assert core.get_active_mod_uri(strict=True)
            res = self._apply()
        else:
            core.aux.ensure_valid_baseuri(self.mod_context_uri)
            with core.uri_context(self.mod_context_uri):
                res = self._apply()
        return res

    def _apply(self) -> List[core.RelationEdge]:
        """
        Perform the actual application of the rule:
            - perform subgraph matching
            - process the found subgraphs with the assertion
        """

        result_map = self.match_subgraph_P()

        asserted_relation_templates = self.get_asserted_relation_templates()

        new_rledg_list = []

        for res_dict in result_map:
            # res_dict represents one situation where the assertions should be applied
            # it's a dict {<node-number>: <item>, ...} like
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
            
            if not sub.uri in self.local_nodes.a:
                msg = f"unknown subject {sub} of rule {self.rule} (uri not in local_nodes; maybe missing in setting)"
                raise ValueError(msg)
            
            if not obj.uri in self.local_nodes.a:
                msg = f"unknown object {obj} of rule {self.rule} (uri not in local_nodes; maybe missing in setting)"
                raise ValueError(msg)
            res.append((self.local_nodes.a[sub.uri], pred, self.local_nodes.a[obj.uri]))

        return res

    def match_subgraph_P(self) -> List[dict]:
        assert self.P is not None
        
        # restrictions for matching nodes: none
        # ... for matching edges: relation-uri must match
        GM = nxiso.DiGraphMatcher(self.G, self.P, node_match=self._node_matcher, edge_match=edge_matcher)
        res = list(GM.subgraph_isomorphisms_iter())

        # invert the dicts (todo: find out why switching G and P does not work)
        # and introduce items for uris

        new_res = []
        for d in res:
            new_res.append(dict((v, self._get_by_uri(k)) for k, v in d.items()))

        # new_res is a list of dicts like
        # [{
        #   0: <Item I2931["local ljapunov stability"]>,
        #   1: <Item I4900["local asymtotical stability"]>,
        #   2: <Item I9642["local exponential stability"]>
        #  }, ... ]

        return new_res
    
    def _get_by_uri(self, uri):
        """
        return literal or entity based on uri
        """
        if uri.startswith(LITERAL_BASE_URI):
            return self.literals[uri]
        else:
            return core.ds.get_entity_by_uri(uri)
        
    def _node_matcher(self, n1d: dict, n2d: dict) -> bool:
        """
    
        :param n1d:     attribute data of node from "main graph"
                        e.g. {'itm': <Item I22["mathematical knowledge artifact"]>}
        :param n2d:     attribute data of node from "prototype graph"
                        e.g. {
                            'itm': {'R3': None, 'R4': <Item I1["general item"]>},
                            'entity': <Item Ia8139["P1"]>
                          }
    
        :return:        boolean matching result
    
        a pair of nodes should match if
            - n2 is an external entitiy for self and the uris match
            - n2 is not an external entity (no further restrictions)
    
        see also: function edge_matcher
        """
        
        if n1d["is_literal"]:
            if n2d["is_literal"]:
                return n1d["value"] == n2d["value"]
            else:
                return False

        if n2d["is_literal"]:
            # no chance for match anymore because n1 is no literal
            return False
            
        
        e1 = n1d["itm"]
        e2 = n2d["entity"]
        
        # todo: this could be faster (list lookup is slow for long lists, however that list should be short)
        if e2 in self.external_entities:
            return e2 == e1
        else: 
            # for non-external entities, all nodes should match
            # -> let the edges decide
            
            return True
        

    def create_prototype_subgraph_from_rule(self) -> nx.DiGraph:
        """
        Create a prototype graph from the scopes 'setting' and 'premise'.
        """

        P = nx.DiGraph()

        # counter for node-values
        i = 0

        for var in self.vars + self.external_entities:

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
            P.add_node(i, itm=c, entity=var, is_literal=False)
            self.local_nodes.add_pair(var.uri, i)
            i += 1

        for rledg in self.premises_rledgs:

            subj, pred, obj = rledg.relation_tuple
            assert isinstance(subj, core.Entity)
            assert isinstance(pred, core.Relation)
            
            n1 = self.local_nodes.a[subj.uri]
            
            if isinstance(obj, core.Entity):
                n2 = self.local_nodes.a[obj.uri]
            elif isinstance(obj, core.allowed_literal_types):
                # create a wrapper node
                P.add_node(i, value=obj, is_literal=True)
                uri = self._make_literal(obj)
                self.local_nodes.add_pair(uri, i)
                n2 = i
                i += 1
                
            else:
                msg = f"While processing {self.rule}: unexpected type of obj: {type(obj)}"
                raise TypeError(msg)

            P.add_edge(n1, n2, rel_uri=pred.uri)

        # components_container 
        cc = self._get_weakly_connected_components(P)
        
        if len(cc.var_components) != 1:
            msg = (
                f"unexpected number of components of prototype graph while applying rule {self.rule}."
                f"Expected: 1, but got ({len(cc.var_components)}). Possible reason: unused variables in the rules context."
            )
            raise core.aux.SemanticRuleError(msg)

        return P
    
    def _get_weakly_connected_components(self, P) -> Container:
        """
        Get weakly connected components and sort them  (separate those which contain only external variables).
        
        Background: the external variables are allowed to be disconnected from the rest
        """
        components = list(nx.weakly_connected_components(P))
        
        # each component is a set like {0, 1, ...}
        
        var_uris = [v.uri for v in self.vars]
        ee_uris = [v.uri for v in self.external_entities]
        res = Container(var_components=[], ee_components=[])
        
        for component in components:
            for node in component:
                uri = self.local_nodes.b[node]
                if uri in var_uris:
                    res.var_components.append(component)
                    break
                else:
                    assert uri in ee_uris
                
            else:
                res.ee_components.append(component)
                
        return res

    def create_simple_graph(self) -> nx.DiGraph:
        """
        Create graph without regarding qualifiers. Nodes: uris
    
        :return:
        """
        G = nx.DiGraph()
    
        for item_uri, item in core.ds.items.items():
    
            # prevent items created inside scopes
            if is_node_for_simple_graph(item):
                G.add_node(item_uri, itm=item, is_literal=False)
    
        all_rels = self.get_all_node_relations()
        for uri_tup, rel_cont in all_rels.items():
            uri1, uri2 = uri_tup
            if uri1 in G.nodes and uri2 in G.nodes:
                G.add_edge(
                    *uri_tup, itm1=core.ds.get_entity_by_uri(uri1), itm2=core.ds.get_entity_by_uri(uri2), **rel_cont
                )
            elif uri1 in G.nodes and uri2.startswith(LITERAL_BASE_URI):
                literal_value = self.literals[uri2]
                G.add_node(uri2, is_literal=True, value=literal_value)
                G.add_edge(*uri_tup, itm1=core.ds.get_entity_by_uri(uri1), itm2=literal_value, **rel_cont)
    
        return G
    
    def get_all_node_relations(self) -> dict:
        """
        returns a dict of all graph-relevant relations {(uri1, uri2): Container(rel_uri=uri3), ...}
        """

        res = {}
        
        # core.ds.relation_edges
        # {'erk:/builtins#R1': {'erk:/builtins#R1': [RE(...), ...], ...}, ..., 'erk:/builtins#I1': {...}}
        for subj_uri, rledg_dict in core.ds.relation_edges.items():
            entity = core.ds.get_entity_by_uri(subj_uri, strict=False)
            if not isinstance(entity, core.Item):
                # this omits all relations
                continue

            for rel_uri, rledg_list in rledg_dict.items():
                for rledg in rledg_list:
                    assert isinstance(rledg, core.RelationEdge)
                    assert len(rledg.relation_tuple) == 3
                    if rledg.corresponding_entity is not None:
                        # case 1: object is not a literal. must be an item (otherwise ignore)
                        assert rledg.corresponding_literal is None
                        if not isinstance(rledg.corresponding_entity, core.Item):
                            # some relation edges point to an relation-type
                            # (maybe this will change in the future)
                            continue
                        c = Container(rel_uri=rel_uri)
                        res[(subj_uri, rledg.corresponding_entity.uri)] = c
                        # TODO: support multiple relations in the graph (MultiDiGraph)
                        break
                    else:
                        # case 2: object is a literal
                        assert rledg.corresponding_literal is not None
                        assert rledg.corresponding_entity is None
                        c = Container(rel_uri=rel_uri)
                        literal_uri = self._make_literal(rledg.corresponding_literal)
                        
                        res[(subj_uri, literal_uri)] = c
                    
        return res
    
    def _make_literal(self, value) -> str:
        """
        create and return an uri for an literal value
        """
        
        i = len(self.literals)
        uri = f"{LITERAL_BASE_URI}#{i}"
        self.literals[uri] = value
        
        return uri

    
    
def edge_matcher(e1d: dict, e2d: dict) -> bool:
    """

    :param e1d:     attribute data of edge from "main graph" (see RuleApplicator)
    :param e2d:     attribute data of edge from "prototype graph" (see RuleApplicator)

    :return:        boolean matching result

    An edge should match if
        - the relation uri is the same


    """

    if e1d["rel_uri"] != e2d["rel_uri"]:
        return False

    return True


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
