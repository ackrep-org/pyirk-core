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


def apply_all_semantic_rules(mod_context_uri=None) -> List[core.Statement]:
    """
    Extract all semantic rules and apply them.

    :returns:  list of newly created statements
    """
    rule_instances = get_all_rules()
    total_res = core.RuleResult()
    for rule in rule_instances:
        res = apply_semantic_rule(rule, mod_context_uri)
        total_res.add_partial(res)

    return total_res

def apply_semantic_rules(*rules: List, mod_context_uri: str = None) -> List[core.Statement]:

    total_res = core.RuleResult()
    for rule in rules:
        res = apply_semantic_rule(rule, mod_context_uri)
        total_res.add_partial(res)

    return total_res

def apply_semantic_rule(rule: core.Item, mod_context_uri: str = None) -> List[core.Statement]:
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


def filter_relevant_stms(re_list: List[core.Statement]) -> List[core.Statement]:
    """
    From a list of Statement instances select only those which are qualifiers and whose subject is an
    RE with .role == SUBJECT.
    In other words: omit those instances which are created as dual relation edges

    :param re_list:
    :return:
    """

    res = []
    for stm in re_list:
        assert isinstance(stm, core.Statement)
        if isinstance(stm.subject, core.Statement) and stm.subject.role == core.RelationRole.SUBJECT:
            res.append(stm.subject)
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

        # this are the variables created in the assertion scope
        subjects = rule.scp__assertions.get_inv_relations("R20__has_defining_scope", return_subj=True)
        self.fiat_prototype_vars = [s for s in subjects if isinstance(s, core.Entity)]

        # this are the variables created in the premise scope
        subjects = rule.scp__premises.get_inv_relations("R20__has_defining_scope", return_subj=True)
        self.condition_func_anchor_items = [s for s in subjects if isinstance(s, core.Item)]

        # TODO: rename "context" -> "setting"
        self.setting_stms = filter_relevant_stms(rule.scp__context.get_inv_relations("R20"))
        self.premises_stms = filter_relevant_stms(rule.scp__premises.get_inv_relations("R20"))
        self.assertions_stms = filter_relevant_stms(rule.scp__assertions.get_inv_relations("R20"))
        self.literals = {}

        # a: {rule_sope_uri1: P_node_index1, ...}, b: {P_node_index1: rule_sope_uri1, ...}
        self.local_nodes = core.aux.OneToOneMapping()

        # this structure holds the nodes corresponding to the fiat_prototypes
        self.asserted_nodes = core.aux.OneToOneMapping()

        # will be set when needed (holds the union of both previous structures)
        self.extended_local_nodes = None

        self.G: nx.DiGraph = self.create_simple_graph()

        self.P: nx.DiGraph = self.create_prototype_subgraph_from_rule()

        self.create_prototypes_for_fiat_entities()

    def apply(self) -> core.RuleResult:
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

    def _apply(self) -> core.RuleResult:
        """
        Perform the actual application of the rule:
            - perform subgraph matching
            - process the found subgraphs with the assertion
        """

        result_map = self.match_subgraph_P()

        # TODO: for debugging this the following things might be helpful:
        # - a mapping like self.local_nodes.a but with labels instead of uris
        # - a visualization of the prototype graph self.P

        condition_functions, cond_func_arg_nodes = self.get_condition_funcs_and_args()

        consequent_functions, cf_arg_nodes, anchor_node_names = self.prepare_consequent_functions()
        asserted_relation_templates = self.get_asserted_relation_templates()

        result = core.RuleResult()

        for res_dict in result_map:
            # res_dict represents one situation where the assertions should be applied
            # it's a dict {<node-number>: <item>, ...} like
            # {
            #       0: <Item I2931["local ljapunov stability"]>,
            #       1: <Item I4900["local asymtotical stability"]>,
            #       2: <Item I9642["local exponential stability"]>
            #  }

            # see also builtin_items.py -> _rule__CM.new_condition_func()
            continue_flag = False
            for cond_func, node_tuple in zip(condition_functions, cond_func_arg_nodes):
                args = [res_dict[node] for node in node_tuple]
                if not cond_func(*args):
                    # if the condition function does not return True, we want to continue with the next res_dict
                    continue_flag = True
                    break

            if continue_flag:
                # at least one of the condition function returned false -> the premises are not completely met
                # despite we have a subgraph-monomorphism match
                continue

            call_args_list = []
            for node_tuple in cf_arg_nodes:
                call_args_list.append((res_dict[node] for node in node_tuple))
            cf_results = [
                func(*call_args) for func, call_args in zip(consequent_functions, call_args_list)
            ]

            cf_results: List[core.RuleResult]
            asserted_new_items = []
            for cfr in cf_results:
                assert isinstance(cfr, core.RuleResult)
                if ne := cfr.new_entities:
                    assert len(ne) == 1
                    asserted_new_items.append(ne[0])
                else:
                    asserted_new_items.append(None)

            # some of the functions might have returned None (called becaus of their side effects)
            # these pairs are sorted out below (via continue)

            # augment the dict with entries like {"fiat0": <Item Ia6733["some item"]>}
            search_dict = {**res_dict, **dict(zip(anchor_node_names, asserted_new_items))}

            for n1, rel, n2 in asserted_relation_templates:

                new_subj = search_dict[n1]

                if new_subj is None:
                    # this was a result of a pure-side-effect-function -> do nothing
                    continue

                new_obj = search_dict[n2]

                assert isinstance(rel, core.Relation)
                assert isinstance(new_subj, core.Entity)

                # TODO: add qualifiers
                new_stm = new_subj.set_relation(rel, new_obj)
                result.new_statements.append(new_stm)

        return result

    def get_condition_funcs_and_args(self) -> (List[callable], List[Tuple[int]]):
        """
        """
        func_list = []
        args_node_list = []

        for anchor_item in self.condition_func_anchor_items:
            condition_func = getattr(anchor_item, "condition_func", None)

            # TODO: doc
            if not condition_func:
                msg = f"The anchor item {anchor_item} unexpectedly has no method `condition_func`."
                raise core.aux.SemanticRuleError(msg)
            func_list.append(condition_func)

            arg_nodes = []
            call_args = anchor_item.get_relations("R29__has_argument", return_obj=True)
            for arg in call_args:
                node = self.local_nodes.a[arg.uri]
                arg_nodes.append(node)
            args_node_list.append(tuple(arg_nodes))

        return func_list, args_node_list

    def prepare_consequent_functions(self) -> (List[callable], List[Tuple[int]], List[str]):
        """
        Creates 3 lists:
            - a list of the consequent functions (might create a new item, new statement or have other side effects)
            - a list of argument nodes (which will serve as keys for the actual arguments)
            - a list of the node names
        """
        func_list = []
        args_node_list = []
        node_names = []

        for var in self.fiat_prototype_vars:

            call_args = var.get_relations("R29", return_obj=True)
            fiat_factory = getattr(var, "fiat_factory", None)

            # TODO: doc
            if not fiat_factory:
                msg = f"The asserted new item {var} unexpectedly has no method `fiat_factory`."
                raise core.aux.SemanticRuleError(msg)
            func_list.append(fiat_factory)

            # now pepare the arguments
            arg_nodes = []
            for arg in call_args:
                node = self.local_nodes.a[arg.uri]
                arg_nodes.append(node)
            args_node_list.append(tuple(arg_nodes))
            node_names.append(self.asserted_nodes.a[var.uri])
        return func_list, args_node_list, node_names

    def get_asserted_relation_templates(self) -> List[Tuple[int, core.Relation, int]]:
        """
        Create a list like [(0, R25, 1), ...]
        """

        # join local_nodes and asserted_nodes:
        assert self.extended_local_nodes is None
        self.extended_local_nodes = core.aux.OneToOneMapping(**self.local_nodes.a)
        for k, v in self.asserted_nodes.a.items():
            self.extended_local_nodes.add_pair(k, v)

        res = []
        for stm in self.assertions_stms:
            sub, pred, obj = stm.relation_tuple
            assert isinstance(pred, core.Relation)

            # todo: handle literals here
            assert isinstance(obj, core.Entity)

            if not sub.uri in self.extended_local_nodes.a:
                msg = (
                    f"unknown subject {sub} of rule {self.rule} (uri not in extended_local_nodes; "
                    "maybe missing (registration as external entity) in setting)"
                )
                raise ValueError(msg)

            if not obj.uri in self.extended_local_nodes.a:
                msg = (
                    f"unknown object {obj} of rule {self.rule} (uri not in extended_local_nodes; "
                    "maybe (registration as external entity) in setting)"
                )
                raise ValueError(msg)
            res.append((self.extended_local_nodes.a[sub.uri], pred, self.extended_local_nodes.a[obj.uri]))

        return res

    def match_subgraph_P(self) -> List[dict]:
        assert self.P is not None

        # restrictions for matching nodes: none
        # ... for matching edges: relation-uri must match
        GM = nxiso.DiGraphMatcher(self.G, self.P, node_match=self._node_matcher, edge_match=edge_matcher)

        # for the difference between subgraph monomorphisms and isomorphisms see:
        # https://networkx.org/documentation/stable/reference/algorithms/isomorphism.vf2.html#subgraph-isomorphism
        # jupyter notebook subgraph-matching-problem
        res = list(GM.subgraph_monomorphisms_iter())
        # res = list(GM.subgraph_isomorphisms_iter())

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

    def create_prototypes_for_fiat_entities(self) -> nx.DiGraph:

        for i, var in enumerate(self.fiat_prototype_vars):
            node_name = f"fiat{i}"
            self.asserted_nodes.add_pair(var.uri, node_name)

    @staticmethod
    def _ignore_item(itm: bi.Item) -> bool:
        # This mechanism allows to ignore some nodes (because they have other roles, e.g. serving as proxy-item for
        # relations)
        if itm.R4 == bi.I40["general relation"]:
            q = itm.get_relations("R4")[0].qualifiers
            if q and q[0].predicate == bi.R59["has rule-prototype-graph-mode"] and q[0].object == 1:
                return True
        # TODO: this is likely too simple (it makes reasoning over anchor-items hard, )cannot be used in the rule))
        if itm.R4 == bi.I43["anchor item"]:
            return True
        return False

    def create_prototype_subgraph_from_rule(self) -> nx.DiGraph:
        """
        Create a prototype graph from the scopes 'setting' and 'premise'.
        """

        P = nx.DiGraph()

        # counter for node-values
        i = 0

        for var in self.vars + self.external_entities:

            assert isinstance(var, core.Entity)

            # omit vars which are already registered
            if var.uri in self.local_nodes.a:
                continue

            if self._ignore_item(var):
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

        for stm in self.setting_stms + self.premises_stms:

            subj, pred, obj = stm.relation_tuple

            if self._ignore_item(subj):
                continue

            assert isinstance(subj, core.Entity)
            assert isinstance(pred, core.Relation)

            if pred == bi.R58["wildcard relation"]:
                # for wildcard relations we have to determine the relevant relation properties
                # like R22__is_functional etc.
                # see also function edge_matcher
                proxy_item = bi.get_proxy_item(stm)

                rel_props = bi.get_relation_properties(proxy_item)
            else:
                rel_props = []

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

            P.add_edge(n1, n2, rel_uri=pred.uri, rel_props=rel_props)

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
        Create graph without regarding qualifiers. Nodes: uris (of items and relations)

        :return:
        """
        G = nx.DiGraph()

        for uri, entity in list(core.ds.items.items()) + list(core.ds.relations.items()):

            # prevent items created inside scopes
            if is_node_for_simple_graph(entity):
                # TODO: rename kwarg itm to ent
                G.add_node(uri, itm=entity, is_literal=False)

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

        # core.ds.statements
        # {'erk:/builtins#R1': {'erk:/builtins#R1': [S(...), ...], ...}, ..., 'erk:/builtins#I1': {...}}
        for subj_uri, stm_dict in core.ds.statements.items():
            entity = core.ds.get_entity_by_uri(subj_uri, strict=False)
            if not isinstance(entity, core.Entity):
                # this omits all Qualifiers
                continue

            for rel_uri, stm_list in stm_dict.items():
                for stm in stm_list:
                    assert isinstance(stm, core.Statement)
                    assert len(stm.relation_tuple) == 3

                    rel_props = bi.get_relation_properties(stm.predicate)

                    if stm.corresponding_entity is not None:
                        # case 1: object is not a literal. must be an item (otherwise ignore)
                        assert stm.corresponding_literal is None

                        c = Container(rel_uri=rel_uri, rel_props=rel_props, rel_entity=stm.predicate)
                        res[(subj_uri, stm.corresponding_entity.uri)] = c
                        # TODO: support multiple relations in the graph (MultiDiGraph)
                        break
                    else:
                        # case 2: object is a literal
                        assert stm.corresponding_literal is not None
                        assert stm.corresponding_entity is None
                        c = Container(rel_uri=rel_uri, rel_props=rel_props, rel_entity=stm.predicate)
                        literal_uri = self._make_literal(stm.corresponding_literal)

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


wildcard_relation_uri = bi.R58["wildcard relation"].uri


def edge_matcher(e1d: dict, e2d: dict) -> bool:
    """

    :param e1d:     attribute data of edge from "main graph" (see RuleApplicator)
    :param e2d:     attribute data of edge from "prototype graph" (see RuleApplicator)

    :return:        boolean matching result

    An edge should match if
        - the relation uri is the same


    """

    if e2d["rel_uri"] == wildcard_relation_uri:
        # wildcard relations matches any relation which has the required relation properties
        if set(e2d["rel_props"]).issubset(e1d["rel_props"]):
            return True

    if e1d["rel_uri"] != e2d["rel_uri"]:
        return False

    return True


def is_node_for_simple_graph(entity: core.Entity) -> bool:
    """
    exclude nodes which are defined inside certain scopes

    :param item:
    :return:
    """
    assert isinstance(entity, core.Entity)
    r20_rels = entity.get_relations("R20__has_defining_scope")

    if not r20_rels:
        return True
    assert len(r20_rels) == 1  # R20 is functional (R22)

    obj = r20_rels[0].relation_tuple[-1]
    assert obj.R4__is_instance_of == bi.I16["scope"]

    # TODO: maybe add some exceptions (allowed scopes for inferrencing) here

    return False


def get_simple_properties(item: core.Item) -> dict:

    stm_dict = item.get_relations()
    res = {}
    for rel_uri, stm_list in stm_dict.items():

        for stm in stm_list:
            assert isinstance(stm, core.Statement)
            assert len(stm.relation_tuple) == 3
            if stm.corresponding_entity is None:
                assert stm.corresponding_literal is not None
                res[rel_uri] = stm.corresponding_literal
                # TODO: support multiple relations in the graph (MultiDiGraph)
                break

    return res
