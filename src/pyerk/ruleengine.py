"""
Created: 2022-09-06 19:14:39
author: Carsten Knoll

This module contains code to enable semantic inferences based on special items (e.g. instances of I41__semantic_rule)

"""

from typing import Dict, List, Tuple, Optional, Union
import os
from collections import defaultdict
from enum import Enum
import json
import textwrap
import time
import itertools as it

import networkx as nx
from networkx.algorithms import isomorphism as nxiso

from jinja2 import Environment, PackageLoader, select_autoescape, FileSystemLoader
from jinja2.filters import FILTERS as jinja_FILTERS


# noinspection PyUnresolvedReferences
from addict import Addict as Container

# noinspection PyUnresolvedReferences
from ipydex import IPS

from . import core

# todo: replace bi. with p. etc
from . import builtin_entities as bi
from . import settings
import pyerk as p

LITERAL_BASE_URI = "erk:/tmp/literals"

VERBOSITY = False


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

    total_res = ReportingMultiRuleResult(rule_list=rules)
    for rule in rules:
        res = apply_semantic_rule(rule, mod_context_uri)
        total_res.add_partial(res)
        if res.exception:
             break

    return total_res


def apply_semantic_rule(rule: core.Item, mod_context_uri: str = None) -> List[core.Statement]:
    """
    Create a RuleApplicator instance for the rules, execute its apply-method, return the result (list of new statements)
    """
    assert rule.R4__is_instance_of == bi.I41["semantic rule"]

    if VERBOSITY:
        print("applying", rule)
    ra = RuleApplicator(rule, mod_context_uri=mod_context_uri)
    try:
        t0 = time.time()
        raw_res: core.RuleResult = ra.apply()
        res = ReportingRuleResult.get_new_instance(raw_res)
    except core.aux.RuleTermination as ex:
        res = ReportingRuleResult(raworker=None)
        res._rule = rule
        res.exception = ex
        res.apply_time = time.time() - t0

    if VERBOSITY:
        print("  ", res, "\n")
    return res


def get_all_rules():

    rule_instances: list = bi.I41["semantic rule"].get_inv_relations("R4__is_instance_of", return_subj=True)

    return rule_instances


def filter_relevant_stms(re_list: List[core.Statement], return_items=True) -> List[core.Statement]:
    """
    From a list of Statement instances select only those which are qualifiers and whose subject is an
    RE with .role == SUBJECT.
    In other words: omit those instances which are created as dual relation edges

    :param re_list:
    :return:
    """

    res_statements = []
    res_items = []

    for stm in re_list:
        assert isinstance(stm, core.Statement)
        if isinstance(stm.subject, core.Statement) and stm.subject.role == core.RelationRole.SUBJECT:
            res_statements.append(stm.subject)
        elif isinstance(stm.subject, core.Item):
            res_items.append(stm.subject)

    if return_items:
        return res_statements, res_items
    else:
        return res_statements


class PremiseType(Enum):
    GRAPH = 0
    SPARQL = 1


class LiteralWrapper:
    def __init__(self, value):
        self.value = value


class RuleApplicator:
    """
    Class to handle the application of a single semantic rule. Deploys several RuleApplicatorWorkers
    (depending on the OR-subscopes)

    """

    def __init__(self, rule: core.Entity, mod_context_uri: Optional[str] = None):
        self.rule = rule
        self.mod_context_uri = mod_context_uri

        self.literals = core.aux.OneToOneMapping()

        self.premise_stm_lists, self.premise_item_lists = self.extract_premise_stm_lists()

        # TODO: rename "scp__context" -> "setting"
        self.setting_stms, self.vars = filter_relevant_stms(
            rule.scp__context.get_inv_relations("R20__has_defining_scope")
        )

        self.external_entities = rule.scp__context.get_relations("R55__uses_as_external_entity", return_obj=True)

        # get all subjects (Entities or Statements of the setting-scope)
        subjects = rule.scp__context.get_inv_relations("R20__has_defining_scope", return_subj=True)

        self.vars_for_literals = [
            s
            for s in subjects
            if (
                # TODO: fix dash-name problem for R59__has_rule_prototype_graph_mode and make R59 functional
                getattr(s, "R4__is_instance_of", None) == p.I44["variable literal"]
                and s.R59 == [3]
            )
        ]

        # this are the variables created in the assertion scope
        subjects = rule.scp__assertions.get_inv_relations("R20__has_defining_scope", return_subj=True)
        self.fiat_prototype_vars = [s for s in subjects if isinstance(s, core.Entity)]

        # this structure holds the nodes corresponding to the fiat_prototypes
        self.asserted_nodes = core.aux.OneToOneMapping()

        # this structure holds the nodes corresponding to variable literal values (different literals for every match)
        self.literal_variable_nodes = core.aux.OneToOneMapping()

        self.sparql_src = None
        self.premise_type = self.get_premise_type()

        self.create_prototypes_for_fiat_entities()
        self.create_prototypes_for_variable_literals()

        self.G: nx.DiGraph = self.create_simple_graph()

        assert len(self.premise_item_lists) == len(self.premise_stm_lists)
        pairs = zip(self.premise_stm_lists, self.premise_item_lists)
        self.ra_workers = [RuleApplicatorWorker(self, stms, itms) for stms, itms in pairs]

    def get_premise_type(self) -> PremiseType:

        self.sparql_src = self.rule.scp__premises.get_relations("R63__has_SPARQL_source", return_obj=True)

        if self.sparql_src:
            assert self.premise_stm_lists == [[]]
            return PremiseType.SPARQL
        else:
            return PremiseType.GRAPH

    def extract_premise_stm_lists(self):

        premise_stm_lists = []
        premise_item_lists = []

        direct_stms, direct_items = filter_relevant_stms(
            self.rule.scp__premises.get_inv_relations("R20__has_defining_scope")
        )

        if scope_OR := getattr(self.rule.scp__premises, "scp__OR", None):
            direct_OR_scope_stms, items = filter_relevant_stms(scope_OR.get_inv_relations("R20__has_defining_scope"))
            assert len(items) == 0, "msg creation of new items is now allowed in OR-subscopes"

            for stm in direct_OR_scope_stms:
                # every such statements triggers a new branch
                premise_stm_lists.append([*direct_stms, stm])
                premise_item_lists.append([*direct_items])

            sub_scopes = scope_OR.get_inv_relations("R21__is_scope_of", return_subj=True)

            for scope_item in sub_scopes:
                assert scope_item.R64__has_scope_type == "AND", "Only AND-subscopes are allowed here"

                sub_scopes2 = scope_item.get_inv_relations("R21__is_scope_of", return_subj=True)
                if len(sub_scopes2) > 0:
                    msg = "Subscopes of AND-subscopes are not yet supported"
                    raise NotImplementedError(msg)

                direct_AND_scope_stms, AND_scope_items = filter_relevant_stms(
                    scope_item.get_inv_relations("R20__has_defining_scope")
                )

                # those statements together form a new branch
                premise_stm_lists.append([*direct_stms, *direct_AND_scope_stms])
                premise_item_lists.append([*direct_items, *AND_scope_items])
        else:
            # there are no subscopes
            premise_stm_lists.append(direct_stms)
            premise_item_lists.append(direct_items)

        return premise_stm_lists, premise_item_lists

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

        res.creator_object = self
        return res

    def _apply(self) -> core.RuleResult:
        """
        Perform the actual application of the rule (either via aubgraph monomorphism or via SPARQL query)
        """

        # TODO: remove this when implementing the AlgorithmicRuleApplicationWorker
        if getattr(self.rule, "cheat", None):
            func = self.rule.cheat[0]
            args = self.rule.cheat[1:]
            res = func(*args)
            res._rule = self.rule
            return res
        # end of cheat (hardcoded experimental query)

        if self.premise_type == PremiseType.GRAPH:
            total_res = p.RuleResult()
            for ra_worker in self.ra_workers:
                res = ra_worker.apply_graph_premise()
                total_res.add_partial(res)
            return total_res

        else:
            assert len(self.ra_workers) == 1
            return self.ra_workers[0].apply_sparql_premise()

    def create_prototypes_for_variable_literals(self):
        for i, var in enumerate(self.vars_for_literals):
            node_name = f"vlit{i}"
            self.literal_variable_nodes.add_pair(var.uri, node_name)

    def create_prototypes_for_fiat_entities(self):

        for i, var in enumerate(self.fiat_prototype_vars):
            node_name = f"fiat{i}"
            self.asserted_nodes.add_pair(var.uri, node_name)

    def create_simple_graph(self) -> nx.DiGraph:
        """
        Create graph without regarding qualifiers. Nodes: uris (of items and relations)

        :return:
        """
        G = nx.MultiDiGraph()

        for uri, entity in list(core.ds.items.items()) + list(core.ds.relations.items()):

            # prevent items created inside scopes
            if is_node_for_simple_graph(entity):
                # TODO: rename kwarg itm to ent
                G.add_node(uri, itm=entity, is_literal=False)

        all_rels: Dict[Tuple, List] = self.get_all_node_relations()
        for uri_tup, rel_cont_list in all_rels.items():
            rel_cont_list: List[Container]  # a list of statement-describing Containers
            uri1, uri2 = uri_tup
            for rel_cont in rel_cont_list:
                if uri1 in G.nodes and uri2.startswith(LITERAL_BASE_URI):
                    literal_value = self.literals.a[uri2]
                    G.add_node(uri2, is_literal=True, value=literal_value)
                    G.add_edge(*uri_tup, itm1=core.ds.get_entity_by_uri(uri1), itm2=literal_value, **rel_cont)
                elif uri1 in G.nodes and uri2 in G.nodes:
                    G.add_edge(
                        *uri_tup, itm1=core.ds.get_entity_by_uri(uri1), itm2=core.ds.get_entity_by_uri(uri2), **rel_cont
                    )
                else:
                    pass
                    # uri1 belongs to an ignored item (eg from inside a scope)

        return G

    def get_all_node_relations(self) -> dict:
        """
        returns a dict of all graph-relevant relations {(uri1, uri2): [Container(rel_uri=uri3), ...], ....}.
        Keys: 2-tuples of uris.
        Values: Lists of Containers (due to multi-edges)
        """

        res = defaultdict(list)

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
                        res[(subj_uri, stm.corresponding_entity.uri)].append(c)
                    else:
                        # case 2: object is a literal
                        assert stm.corresponding_literal is not None
                        assert stm.corresponding_entity is None
                        c = Container(rel_uri=rel_uri, rel_props=rel_props, rel_entity=stm.predicate)
                        literal_uri = self._make_literal(stm.corresponding_literal)

                        res[(subj_uri, literal_uri)].append(c)

        return res

    def _make_literal(self, value) -> str:
        """
        create (if neccessary) and return an uri for an literal value
        """

        if uri := self.literals.b.get(value):
            return uri
        i = len(self.literals.a)
        uri = f"{LITERAL_BASE_URI}#{i}"
        self.literals.add_pair(uri, value)

        return uri


class RuleApplicatorWorker:

    """
    Performs the application of one premise branch of a rule
    """

    max_subgraph_monomorphisms = 3000

    # useful for debugging: IPS(self.parent.rule.short_key=="I763")

    def __init__(self, parent: RuleApplicator, premise_stms: List[core.Statement], premise_items: List[core.Item]):
        # get all subjects (Entities or Statements of the setting-scope)

        self.parent = parent
        self.premises_stms = premise_stms
        rule = parent.rule

        # this are the variables created in the premise scope
        self.condition_func_anchor_items = premise_items

        self.sparql_src = rule.scp__premises.get_relations("R63__has_SPARQL_source", return_obj=True)
        self.assertions_stms = filter_relevant_stms(rule.scp__assertions.get_inv_relations("R20"), return_items=False)

        # for every local node (integer key) store a list of relations like:
        # {<uri1>: S5971(<Item Ia5322["rel1 (I40__general_rel)"]>, <Relation R2850["is functional activity"]>, True)}
        self.relation_statements = defaultdict(list)

        # a: {var_uri1: P_node_index1, ...}, b: {P_node_index1: var_uri1, ...}
        self.local_nodes = core.aux.OneToOneMapping()

        # {P_node_index: <node-data-dict1, ...}  # data for the P-graph, but not all these node might become
        # P-graph-nodes (due to subscope-branching);
        # this two-stage-approach prevents unconnected one-node-components from other branches
        # (see  if len(cc.main_components) > 1 below
        self.local_node_candidates = {}

        # a: {var_uri1: "imt1", ...}, b: ...
        self.local_node_names = core.aux.OneToOneMapping()

        # store I40["general relation"] instances which might serve as subject
        self.subjectivized_predicates = core.aux.OneToOneMapping()

        # store those node-tuples which correspond to a R58["wildcard relation"]-statement
        # (which has an associated proxy-item). This is used in self.get_extended_result_map
        self.stms_associated_to_proxy_items = defaultdict(list)

        # will be set when needed (holds the union of both previous structures)
        self.extended_local_nodes = None

        # list of Containers, containing triples like (node1, <Relation>, node2)
        self.asserted_relation_templates: List[Container] = None

        self.P: nx.MultiDiGraph = None
        self.create_prototype_subgraph_from_rule()

    @property
    def rule(self):
        return self.parent.rule

    def apply_sparql_premise(self) -> core.RuleResult:
        t0 = time.time()
        where_clause = textwrap.dedent(self.sparql_src[0])
        var_names = "?" + " ?".join(self.local_node_names.b.keys())  # -> e.g. "?ph1 ?ph2 ?some_itm ?rel1"

        prefixes = []
        for mod_uri, prefix in p.ds.uri_prefix_mapping.a.items():
            if mod_uri == p.settings.BUILTINS_URI:
                prefix = ""
            prefixes.append(f"PREFIX {prefix}: <{mod_uri}#>")

        prefix_block = "\n".join(prefixes)
        qsrc = f"{prefix_block}\nSELECT {var_names}\n{where_clause}"

        p.ds.rdfgraph = p.rdfstack.create_rdf_triples()
        try:
            res = p.ds.rdfgraph.query(qsrc)
        except p.rdfstack.rdflib.plugins.sparql.parser.ParseException as e:
            # prepend the qsrc with linenumbers via regex, see: https://stackoverflow.com/a/64621297/333403
            def repl(m):
                repl.cnt += 1
                return f'{repl.cnt:03d}: '

            repl.cnt = 0
            import re
            print(re.sub(r'(?m)^', repl, qsrc))
            raise

        res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        result_maps = []
        for row in res2:
            res_map = {}
            assert len(row) == len(self.parent.vars)
            for v, entity in zip(self.parent.vars, row):
                node = self.local_nodes.a[v.uri]
                res_map[node] = entity
            result_maps.append(res_map)

        res = self._process_result_map(result_maps)
        res.apply_time = time.time() - t0
        return res

    def apply_graph_premise(self) -> core.RuleResult:


        t0 = time.time()
        result_maps = self.match_subgraph_P()
        # TODO: for debugging the result_maps data structure the following things might be helpful:
        # - a mapping like self.local_nodes.a but with labels instead of uris
        # - a visualization of the prototype graph self.P
        res = self._process_result_map(result_maps)
        res.apply_time = time.time() - t0

        return res

    def _process_result_map(self, result_maps) -> core.RuleResult:
        """
        - process the found subgraphs with the assertion
        """

        condition_functions, cond_func_arg_nodes = self.get_condition_funcs_and_args()

        consequent_functions, cf_arg_nodes, anchor_node_names = self.prepare_consequent_functions()

        result = ReportingRuleResult(raworker=self, raw_result_count=len(result_maps))

        for res_dict0 in result_maps:
            # res_dict represents one situation where the assertions should be applied
            # it's a dict {<node-number>: <item>, ...} like
            # {
            #       0: <Item I2931["local ljapunov stability"]>,
            #       1: <Item I4900["local asymtotical stability"]>,
            #       2: <Item I9642["local exponential stability"]>
            #  }

            try:
                res_dict = self.get_extended_result_map(res_dict0)
            except p.aux.InconsistentEdgeRelations:
                # this might happen as a consequence of "naive subgraph matching" which cannot decide if
                # two edges correspond to the same relation or not
                # -> we ignore those matching results
                continue

            # see also builtin_items.py -> _rule__CM.new_condition_func()
            skip_to_next_flag = False
            for cond_func, node_tuple in zip(condition_functions, cond_func_arg_nodes):
                args = [res_dict[node] for node in node_tuple]
                if not cond_func(*args):
                    # if the condition function does not return True, we want to skip this res_dict
                    # and continue with the next one
                    skip_to_next_flag = True
                    break

            if skip_to_next_flag:
                # at least one of the condition function returned false -> the premises are not completely met
                # despite we have a subgraph-monomorphism match -> we skip to the next res_dict
                continue

            call_args_list = []
            for node_tuple in cf_arg_nodes:
                tmp_args = []
                for node in node_tuple:
                    if isinstance(node, LiteralWrapper):
                        # this occurs if a literal value is added to the argument tuple
                        tmp_args.append(node.value)
                    else:
                        tmp_args.append(res_dict[node])
                call_args_list.append(tmp_args)

            csq_fnc_results: List[core.RuleResult] = []
            for func, call_args in zip(consequent_functions, call_args_list):
                res = func(*call_args)
                self.unlink_unwanted_statements(res.new_statements)
                csq_fnc_results.append(res)

            asserted_new_items = []
            for cfr in csq_fnc_results:
                assert isinstance(cfr, core.RuleResult)
                result.extend_with_binding_info(cfr, res_dict)
                if ne := cfr.new_entities:
                    assert len(ne) == 1
                    asserted_new_items.append(ne[0])
                else:
                    asserted_new_items.append(None)

            # some of the functions might have returned None (called becaus of their side effects)
            # these pairs are sorted out below (via continue)

            # augment the dict with entries like {"fiat0": <Item Ia6733["some item"]>}
            search_dict = {**res_dict, **dict(zip(anchor_node_names, asserted_new_items))}

            for cntnr in self.asserted_relation_templates:

                n1, rel, n2 = cntnr.subject, cntnr.predicate, cntnr.object

                # in most cases rel is an Relation, but it could also be a proxy-item for a relation
                if isinstance(rel, p.Item):
                    # we have a proxy item
                    assert rel.R4__is_instance_of == p.I40["general relation"]
                    rel_node = self.local_nodes.a[rel.uri]
                    rel = search_dict[rel_node]

                new_subj = search_dict[n1]

                if new_subj is None:
                    # this was a result of a pure-side-effect-function -> do nothing
                    continue

                assert isinstance(rel, core.Relation)
                assert isinstance(new_subj, core.Entity)

                if isinstance(n2, LiteralWrapper):
                    new_obj = n2.value
                else:
                    new_obj = search_dict[n2]

                if new_subj.R20__has_defining_scope or getattr(new_obj, "R20__has_defining_scope", None):
                    # rules should not affect items inside scopes (maybe this will be more precise in the future)
                    continue

                # check if relation already exists and should be ommitted
                if cntnr.omit_if_existing:
                    if new_obj in new_subj.get_relations(rel.uri, return_obj=True):
                        continue
                # TODO: add qualifiers
                new_stm = new_subj.set_relation(rel, new_obj)

                result.add_bound_statement(new_stm, res_dict)

        return result

    def get_extended_result_map(self, result_map: dict) -> dict:
        """
        This function create a dict which contains every entry of `result_map` + mappings from subjectivized predicates.

        :param result_map:   mapping from P-node to G-node-item (as returned by self.match_subgraph_P)
        """

        if self.parent.premise_type == PremiseType.SPARQL:
            return result_map

        extended_result_map = {**result_map}

        for node, uri in self.subjectivized_predicates.b.items():
            if rel_entity2 := extended_result_map.get(node):
                # no need to add something
                continue

            pred_proxy_item = p.ds.get_entity_by_uri(uri)
            assert pred_proxy_item.R4__is_instance_of == p.I40["general relation"]

            P_edge_list = self.stms_associated_to_proxy_items[pred_proxy_item.uri]

            # use dict to store the found relations (this prevents double counting of the same relations)
            uri_relations_map = {}
            for n1, n2 in P_edge_list:
                itm1 = result_map[n1]
                itm2 = result_map[n2]

                rel = self._get_all_edge_predicate_relations(itm1.uri, itm2.uri, ensure_length1=True)[0]
                assert isinstance(rel, p.Relation)
                uri_relations_map[rel.uri] = rel
            if len(uri_relations_map) > 1:
                # this might happen as a consequence of "naive subgraph matching" which cannot decide if
                # two edges correspond to the same relation or not
                raise p.aux.InconsistentEdgeRelations()
            if len(uri_relations_map) == 0:
                msg = (
                    f"Unexpectedly found no relation associated to proxy item {pred_proxy_item} in {self.parent.rule}."
                )
                raise ValueError(msg)

            rel_entity = list(uri_relations_map.values())[0]

            # this is for safety. however, it would be faster to put a similar check at the beginning of the loop
            if rel_entity2 := extended_result_map.get(node):
                assert rel_entity == rel_entity2
            extended_result_map[node] = rel_entity

        return extended_result_map

    def _get_all_edge_predicate_relations(self, uri1, uri2, ensure_length1=False):

        relations = []
        edge_dicts: Dict[dict] = self.parent.G.get_edge_data(uri1, uri2)

        # because G is a MultiDiGraph this has the structure {0: <edge_dict1>, ...}
        if ensure_length1:
            assert len(edge_dicts) == 1

        for idx, edge_dict in edge_dicts.items():
            relations.append(edge_dict["rel_entity"])

        return relations

    def get_condition_funcs_and_args(self) -> (List[callable], List[Tuple[int]]):
        """ """
        self._fill_extended_local_nodes()

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
                node = self.extended_local_nodes.a[arg.uri]
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

        self._fill_extended_local_nodes()

        for var in self.parent.fiat_prototype_vars:

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
                if isinstance(arg, p.allowed_literal_types):
                    # allow literal arguments for consequent functions
                    uri = self.parent._make_literal(arg)
                    self.extended_local_nodes.add_pair(uri, LiteralWrapper(arg))
                else:
                    uri = arg.uri

                try:
                    node = self.extended_local_nodes.a[uri]
                except KeyError:
                    msg = (
                        f"Entity {arg} is unknown in local nodes of rule {self.parent.rule}. Possible reason: missing "
                        "declaration in scope('setting')."
                    )
                    raise core.aux.SemanticRuleError(msg)
                arg_nodes.append(node)
            args_node_list.append(tuple(arg_nodes))
            node_names.append(self.parent.asserted_nodes.a[var.uri])
        return func_list, args_node_list, node_names

    def get_asserted_relation_templates(self) -> List[Tuple[int, core.Relation, int]]:
        """
        Create a list like [(0, R25, 1), ...]
        """
        self._fill_extended_local_nodes()

        res = []
        for stm in self.assertions_stms:
            if stm.get_first_qualifier_obj_with_rel("R59__has_rule_prototype_graph_mode") == 4:
                # this is just an auxiliary statement for consequent function like
                #  S8409(<Item Ia9327["fiat_item0"]>, <Relation R29["has argument"]>, <Item I9040["XYZ"]>)
                # the relation itself should not be created as a consequence
                continue

            sub, pred, obj = stm.relation_tuple
            assert isinstance(pred, core.Relation)

            if isinstance(obj, p.allowed_literal_types):
                obj = LiteralWrapper(obj)
                entity_obj_flag = False
            else:
                assert isinstance(obj, core.Entity)
                entity_obj_flag = True

            if not sub.uri in self.extended_local_nodes.a:
                msg = (
                    f"unknown subject {sub} of rule {self.parent.rule} (uri not in extended_local_nodes; "
                    "maybe missing (registration as external entity) in setting)"
                )
                raise ValueError(msg)

            if entity_obj_flag and not obj.uri in self.extended_local_nodes.a:
                msg = (
                    f"unknown object {obj} of rule {self.parent.rule} (uri not in extended_local_nodes; "
                    "maybe (registration as external entity) in setting)"
                )
                raise ValueError(msg)

            if proxy_item := bi.get_proxy_item(stm, strict=False):
                if self._is_subjectivized_predicate(proxy_item):
                    pred = proxy_item

            if entity_obj_flag:
                final_obj = self.extended_local_nodes.a[obj.uri]
                if final_obj in self.parent.asserted_nodes.b or final_obj in self.parent.literal_variable_nodes.b:
                    # `final_obj` is like "fiat0", "vlit0"; it will be handled during `_process_result_map`
                    pass
                else:
                    self.ensure_node_of_P(final_obj)
            else:
                final_obj = obj  # the LiteralWrapper instance

            c = Container(subject=self.extended_local_nodes.a[sub.uri], predicate=pred, object=final_obj)
            c.omit_if_existing = (stm.get_first_qualifier_obj_with_rel("R59__has_rule_prototype_graph_mode") == 5)

            res.append(c)

        return res

    def _fill_extended_local_nodes(self, force=False):
        """
        join local_nodes + asserted_nodes + parent.literal_variable_nodes
        """
        if self.extended_local_nodes is not None and not force:
            return

        self.extended_local_nodes = core.aux.OneToOneMapping(**self.local_nodes.a)
        for k, v in self.parent.asserted_nodes.a.items():
            self.extended_local_nodes.add_pair(k, v)
        for k, v in self.parent.literal_variable_nodes.a.items():
            self.extended_local_nodes.add_pair(k, v)

    def match_subgraph_P(self) -> List[dict]:
        assert self.P is not None

        # restrictions for matching nodes: none
        # ... for matching edges: relation-uri must match
        GM = nxiso.MultiDiGraphMatcher(self.parent.G, self.P, node_match=self._node_matcher, edge_match=edge_matcher)

        # for the difference between subgraph monomorphisms and isomorphisms see:
        # https://networkx.org/documentation/stable/reference/algorithms/isomorphism.vf2.html#subgraph-isomorphism
        # jupyter notebook subgraph-matching-problem
        res = []
        i = 0
        for r in GM.subgraph_monomorphisms_iter():
            i += 1
            res.append(r)
            if i >= self.max_subgraph_monomorphisms:
                break
        # res is a list of dicts like:[{'erk:/test/zebra02#Ia1158': 0, 'erk:/tmp/literals#0': 1}, ...]
        # for some reason the order of that list is not stable accross multiple runs
        # ensure stable order for stable test results; for comparing dicts they are converted to json-strings
        res.sort(key=json.dumps)

        # invert the dicts (switching G and P does not work)
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
            return self.parent.literals.a[uri]
        else:
            try:
                return core.ds.get_entity_by_uri(uri)
            except p.aux.UnknownURIError:
                if res := core.ds.unlinked_entities.get(uri):
                    return res
                else:
                    raise

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
            if n2d.get("is_variable_literal"):
                return True
            elif n2d["is_literal"]:
                return n1d["value"] == n2d["value"]
            else:
                return False

        if n2d["is_literal"]:
            # no chance for match anymore because n1 is no literal
            return False

        e1 = n1d["itm"]
        e2 = n2d["entity"]

        rel_statements = n2d.get("rel_statements")

        # todo: this could be faster (list lookup is slow for long lists, however that list should be short)
        if e2 in self.parent.external_entities:
            # case 1: compare exact entities (nodes in graph)
            return e2 == e1
        elif rel_statements is not None:
            # case 2: the node represents also a relation with some specific properties (specified via rel_statements)
            # I40["general relation"]; use the short syntax here for performance reasons
            assert e2.R4 == bi.I40
            if not isinstance(e1, core.Relation):
                return False
            return compare_relation_statements(e1, rel_statements)
        else:
            # for all other nodes, all nodes should match
            # -> let the edges decide

            return True

    @staticmethod
    def _is_subjectivized_predicate(itm: bi.Item) -> bool:
        # This mechanism allows to ignore some nodes (because they have other roles, e.g. serving as proxy-item for
        # relations)
        if itm.R4 == bi.I40["general relation"]:
            q = itm.get_relations("R4")[0].qualifiers
            if q and q[0].predicate == bi.R59["has rule-prototype-graph-mode"] and q[0].object == 1:
                return True
        return False

    @staticmethod
    def _ignore_item(itm: bi.Item) -> bool:
        # TODO: this is likely too simple (it makes reasoning over anchor-items hard, )cannot be used in the rule))
        if itm.R4 == bi.I43["anchor item"]:
            return True
        # TODO solve R59["has rule-prototype-graph-mode"] dash problem and functionality
        if r59 := itm.R59:
            if r59[0] > 0:
                return True
        return False

    def get_premise_type(self) -> PremiseType:

        if self.sparql_src:
            assert len(self.premises_stms) == 0
            return PremiseType.SPARQL
        else:
            return PremiseType.GRAPH

    def create_prototype_subgraph_from_rule(self) -> None:
        """
        Create a prototype graph from the scopes 'setting' and 'premise'.
        """

        self._create_psg_nodes()
        self.asserted_relation_templates = self.get_asserted_relation_templates()
        if self.parent.premise_type == PremiseType.GRAPH:

            # this call might also add further nodes
            self._create_psg_edges()

        # ensure completeness (local nodes might have gotten new nodes for literals)
        self._fill_extended_local_nodes(force=True)

    def _create_psg_nodes(self) -> None:
        """
        Create P and add all nodes (except those for literal values, which will be added adhoc during processing of
        the statements, see _create_psg_edges)
        """

        self.P = nx.MultiDiGraph()

        # counter for node-values
        i = 0

        for var in self.parent.vars + self.parent.external_entities:

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
            if self._is_subjectivized_predicate(var):
                self.subjectivized_predicates.add_pair(var.uri, i)
                rel_statements: list = self.relation_statements[var.uri]
            else:
                rel_statements = None
            node_data = dict(i=i, itm=c, entity=var, is_literal=False, rel_statements=rel_statements)
            self.local_node_candidates[i] = node_data
            self.local_nodes.add_pair(var.uri, i)
            if var in self.parent.external_entities:
                # external entities will get a node in all cases (disconnected from the main component is allowed)
                self.P.add_node(i, **node_data)
            else:
                self.local_node_names.add_pair(var.uri, var.R23__has_name_in_scope)
            i += 1

    def _create_psg_edges(self) -> None:

        i = len(self.local_nodes.a)

        for stm in self.parent.setting_stms + self.premises_stms:

            subj, pred, obj = stm.relation_tuple

            if self._ignore_item(subj):
                continue

            assert isinstance(subj, core.Entity)
            assert isinstance(pred, core.Relation)

            subjectivized_predicate = self._is_subjectivized_predicate(subj)

            if pred == bi.R58["wildcard relation"]:
                # for wildcard relations we have to determine the relevant relation properties
                # like R22__is_functional etc.
                # see also function edge_matcher

                # retrieve the object of qualifier R34["has proxy item"]
                # this binds a R58["wildcard relation"]-instance to a I40["general relation"] instance
                proxy_item = bi.get_proxy_item(stm)

                # note this dict might currently be empty but might be filled later (see _is_subjectivized_predicate)
                rel_statements: list = self.relation_statements[proxy_item.uri]

                # TODO drop rel_props
                rel_props = bi.get_relation_properties(proxy_item)
            else:
                rel_statements = []

                # TODO drop rel_props
                rel_props = []
                proxy_item = None

            n1 = self.local_nodes.a[subj.uri]

            self.ensure_node_of_P(n1)

            if isinstance(obj, core.Entity):
                if obj.R59:
                    # handle variable_literal
                    n2 = self.parent.literal_variable_nodes.a[obj.uri]
                    self.P.add_node(n2, entity=obj, is_literal=False, is_variable_literal=True)
                else:
                    try:
                        n2 = self.local_nodes.a[obj.uri]
                    except KeyError:
                        msg = (
                            f"unknown object {obj} of rule {self.parent.rule} (uri not in local_nodes; "
                            "maybe missing (registration as external entity) in setting)"
                        )
                        raise ValueError(msg)
                    self.ensure_node_of_P(n2)
            elif isinstance(obj, core.allowed_literal_types):
                if subjectivized_predicate:
                    # Note: if subjectivized_predicate the literal should occur in the prototype graphe
                    pass
                else:
                    # normally handle the literal -> create a wrapper node
                    uri = self.parent._make_literal(obj)
                    n2 = self.local_nodes.a.get(uri)
                    if n2 is None:
                        n2 = i
                        i += 1
                        self.local_nodes.add_pair(uri, n2)

                    self.P.add_node(n2, value=obj, is_literal=True)

            else:
                msg = f"While processing {self.parent.rule}: unexpected type of obj: {type(obj)}"
                raise TypeError(msg)

            if subjectivized_predicate:
                # this statement is not added to the graph directly, but instead influences the edge_matcher
                self.relation_statements[subj.uri].append(stm)
            else:
                # todo: merge rel_props with rel_statements
                self.P.add_edge(n1, n2, rel_uri=pred.uri, rel_props=rel_props, rel_statements=rel_statements)

                if proxy_item:
                    self.stms_associated_to_proxy_items[proxy_item.uri].append((n1, n2))

        # components_container
        cc = self._get_weakly_connected_components(self.P)

        if len(cc.main_components) == 0:

            # TODO: remove this when implementing the AlgorithmicRuleApplicationWorker
            if getattr(self.parent.rule, "cheat", None):
                return
            # end of cheat (hardcoded experimental query)

            raise core.aux.SemanticRuleError("empty prototype graph")

        expected_main_component_number = getattr(self.parent.rule, "R70__has_number_of_prototype_graph_components")
        if expected_main_component_number is None:
            expected_main_component_number = 1

        if len(cc.main_components) != expected_main_component_number:
            # usually this is triggered by a bug in the rule. However, there are some cases where multiple components
            # are needed. Then R70__has_number_of_prototype_graph_components can be used.
            msg = (
                f"unexpected number of components of prototype graph while applying rule {self.parent.rule}."
                f"Expected: {expected_main_component_number}, but got {len(cc.main_components)}. "
                "Possible reason: unused variables in the rules context."
            )
            raise core.aux.SemanticRuleError(msg)

    def ensure_node_of_P(self, i):

        if i not in self.P.nodes:
            node_data = self.local_node_candidates[i]
            self.P.add_node(i, **node_data)

    def _get_weakly_connected_components(self, P) -> Container:
        """
        Get weakly connected components and sort them  (separate those which contain only external variables).

        Background: external variables are allowed to be disconnected from the rest
        """
        components = list(nx.weakly_connected_components(P))

        # each component is a set like {0, 1, ...}

        var_uris = [v.uri for v in self.parent.vars]
        ee_uris = [v.uri for v in self.parent.external_entities]
        res = Container(main_components=[], ee_components=[], subjectivized_predicates_components=[])

        for component in components:
            for node in component:
                uri = self.extended_local_nodes.b[node]
                if uri in var_uris:
                    if uri in self.subjectivized_predicates.a:
                        # this kind of nodes is allowed to form disconnected components
                        # (it is only related to the other nodes as predicate)
                        res.subjectivized_predicates_components.append(component)
                    else:
                        res.main_components.append(component)
                    break
                else:
                    assert uri in ee_uris

            else:
                res.ee_components.append(component)

        return res

    def unlink_unwanted_statements(self, stm_list: List[core.Statement]):
        """
        During the application of consequent functions unwanted statements might be created. This method serves to
        delete them. Unwanted statements are e.g. statements about items which are defined in scopes of rules.
        """
        pop_indices = []
        for idx, stm in enumerate(stm_list):
            if stm.subject.R20__has_defining_scope:
                stm.unlink()
                pop_indices.append(idx)

        # iterate from behind to leave lower indices unchanged by popping elements
        for idx in reversed(pop_indices):
            stm_list.pop(idx)


wildcard_relation_uri = bi.R58["wildcard relation"].uri


AtlasView = nx.coreviews.AtlasView
def edge_matcher(e1d: AtlasView, e2d: AtlasView) -> bool:
    """

    :param e1d:     attribute data of edgees from "main graph" (see RuleApplicator)
    :param e2d:     attribute data of edgees from "prototype graph" (see RuleApplicator)

    because we compare MultiDigraphs we get `AtlasView`-instances, i.e. read-only dicts like
    AtlasView({0: inner_dict0, 1: inner_dict1, ...}). Keys are edge-indices for that 'multi-edge', values are like
    inner_dict0 = {
        'itm1': <Relation R64["has scope type"]>,
        'itm2': <Item I16["scope"]>,
        'rel_uri': 'erk:/builtins#R8',
        'rel_entity': <Relation R8["has domain of argument 1"]>
    }


    :return:        boolean matching result

    An edge should match if
        - the relation uri is the same


    """

    msg = "multi-edges in prototype-graph not yet supported, use SPARQL premise"
    assert len(e2d) == 1, msg

    e2d = e2d[0]

    if e2d["rel_uri"] == wildcard_relation_uri:
        # wildcard relations matches any relation which has the required relation properties

        # iterate over all edges of this multiedge
        for inner_dict1 in e1d.values():
            stm_data = Container(subject=inner_dict1["itm1"], object=inner_dict1["itm2"])
            res: bool = compare_relation_statements(inner_dict1["rel_entity"], e2d["rel_statements"], stm_data=stm_data)
            if res:
                break
        return res

    # iterate over all edges of this multiedge
    for inner_dict1 in e1d.values():
        if inner_dict1["rel_uri"] == e2d["rel_uri"]:
            return True

    return False


class ReportingRuleResult(core.RuleResult):

    def __init__(
            self, raworker: RuleApplicatorWorker, raw_result_count: int = None, rule: core.Item = None
        ):
        super().__init__()

        self.raworker = raworker
        self.statement_reports = []

        if rule is None and raworker is not None:
            self._rule = self.raworker.rule
            self.explanation_text_template = self._rule.R69__has_explanation_text_template
        else:
            self._rule = None
            self.explanation_text_template = None
        self.raw_result_count = raw_result_count

    @classmethod
    def get_new_instance(cls: type, res: core.RuleResult):
        """
        Create an instance of this class based on the instance of a super class.
        """
        assert isinstance(res, core.RuleResult)
        assert isinstance(res.creator_object, RuleApplicator)

        inst = cls(raworker=None, rule=res.creator_object.rule)
        for key, value in res.__dict__.items():
            setattr(inst, key, value)

        return inst


    def add_bound_statement(self, stm: core.Statement, raw_binding_info: dict):
        """
        :param stm:
        :param raw_binding_info:   dict like  {0: <Item Ia1555["x1"]>, 1: <Item Ia4365["x2"]>, 'vlit0': 42}

        """

        self.add_statement(stm)
        self._add_statement_report(stm, raw_binding_info)

    def _add_statement_report(self, stm: core.Statement, raw_binding_info: dict):
        bindinfo = []
        for node, result_entity in raw_binding_info.items():
            uri = self.raworker.extended_local_nodes.b.get(node)
            assert uri
            premise_entity = self.raworker._get_by_uri(uri)
            bindinfo.append( (premise_entity, result_entity) )

        c = Container(stm=stm, bindinfo=bindinfo)
        self.statement_reports.append(c)

    def extend_with_binding_info(self, part: core.RuleResult, raw_binding_info: dict):
        super().extend(part)

        # this has to be done separately because that data structure does not exist in the base class
        for stm in part.new_statements:
            self._add_statement_report(stm, raw_binding_info)

    def report(self, max=None, sep=""):
        print(self.report_str(max=max, sep=sep))

    def report_str(self, max=None, sep=""):

        res = []
        for i, c in enumerate(self.statement_reports):
            stm_str = f"[{c.stm.subject.R1} | {c.stm.predicate.R1} | {c.stm.object.R1}]"
            explanation_text = self.get_explanation(c.bindinfo)

            res.append(f"{stm_str}  because  {explanation_text}{sep}")
            if i >= max:
                break

        return "\n".join(res)

    def get_explanation(self, bindinfo: List[Tuple[p.Entity]]):
        """
        :param bindinfo:    list of 2-tuples like [(<Item Ia7458["p1"]>, <Item Ia1158["person1"]>),...]

        The bindinfo contains pairs of (<placeholder-item>, <real-item>) tuples. This function uses this information
        together with the rule-specific explanation_text_template (like "{p1}  {rel1}  {p2}") to create strings like:
        "person1  has_neighbour  person2".
        """
        if self.explanation_text_template:
            format_kwargs = {}
            for a, b in bindinfo:
                a_name = a.R23__has_name_in_scope
                if isinstance(b, core.Entity):
                    format_kwargs[a_name] = core.format_entity_html(b)
                else:
                    format_kwargs[a_name] = repr(b)
            return self.explanation_text_template.format(**format_kwargs)

        else:
            explanation_text = " ".join([f"({crpr(a)}: {crpr(b)})" for a, b in bindinfo])
            explanation_text = explanation_text.replace(" (I40__general_relation)", "")

        return explanation_text

    def _get_statement_report_count(self):

        if self.raworker is None:
            # this object is only a container for its partial results
            return sum([p._get_statement_report_count() for p in self.partial_results])
        else:
            return len(self.statement_reports)

    def _get_stm_container_list(self):

        stm_container_list = []
        if self.raworker is None:
            # this object is only a container for its partial results
            for part_res in self.partial_results:
                stm_container_list.extend(part_res._get_stm_container_list())
            return stm_container_list

        for i, c in enumerate(self.statement_reports):

            # create a container for statement and explanation -> let the template do the formatting
            stm_container = Container()
            stm_str = f"[{c.stm.subject.R1} | {c.stm.predicate.R1} | {crpr(c.stm.object)}]"
            stm_container.explanation_text = self.get_explanation(c.bindinfo)
            stm_container.txt = f"{stm_str}  because  {stm_container.explanation_text}"
            stm_container.stm = c.stm


            stm_container_list.append(stm_container)

        return stm_container_list


class ReportingMultiRuleResult(ReportingRuleResult):

    def __init__(self, rule_list: List[core.Item]):
        core.check_type(rule_list, Union[list, tuple])
        self.rule_list = rule_list

        super().__init__(raworker=None)

    @property
    def rule(self):
        # for this class a single rule attribute is not meaningful
        return None

    def save_html_report(self, fpath: str, write_file=True, verbose=False):
        """
        Create a readable html version of the report
        :param fpath:   str; path of output file
        """

        jin_env = Environment(loader=FileSystemLoader(settings.TEMPLATE_PATH))
        template_doc = jin_env.get_template("rule-application-report-page.html")

        context = Container()
        context.css_path = os.path.join(settings.TEMPLATE_PATH, "base.css")
        context.content = self.get_report_content()

        res = template_doc.render(c=context)

        if write_file:
            with open(fpath, "w") as resfile:
                resfile.write(res)
            if verbose:
                print(os.path.abspath(fpath), "written.")

    def get_report_content(self):
        """
        """

        content = Container()
        content.title = self._get_report_title()
        content.rule_res_list = self._get_rule_res_list()

        return content

    def _get_report_title(self):
        return f"Result of {len(self.rule_list)} rule(s)"

    def _get_rule_res_list(self):
        rule_res_list = []
        for part in self.partial_results:
            c = Container(rule=part.rule, length=part._get_statement_report_count())
            c.stm_container_list = part._get_stm_container_list()
            rule_res_list.append(c)

        return rule_res_list


def crpr(obj):
    """
    custom representation function which accepts Entities and literals
    """

    if isinstance(obj, core.Entity):
        return core.format_entity_html(obj)
    else:
        return core.format_literal_html(obj)

jinja_FILTERS["crpr"] = crpr


# Note this function will be called very often -> check for speedup possibilites
def compare_relation_statements(rel1: core.Relation, stm_list: List[core.Statement], stm_data: Container = None):
    """
    decide whether a given relation fulfills all given statements
    """

    for stm in stm_list:
        raw_res = rel1.get_relations(stm.predicate.uri, return_obj=True)
        if raw_res == []:
            return False
        # omit labels for performance: R4__is_instance_of; I40__general_relation
        if getattr(stm.object, "R4", None) == p.I40:

            # Note: this might be too general, but false positives will be filtered out in the postprocessing
            return isinstance(raw_res[0], core.Relation)
        # builtin: p.R71__enforce_matching_result_type
        elif stm.predicate == p.R71 and stm.object:
            if stm_data is None:
                # we are in node-compare mode -> ignore this statement
                continue

            rel1_result_type = getattr(rel1, "R11", [None])[0]
            if rel1_result_type is None:
                return False

            actual_res_type = getattr(stm_data.object, "R4", None)
            if rel1_result_type != actual_res_type:
                return False

        elif raw_res[0] != stm.object:
            # no special handling of relation statement
            return False

    # all statements have matched
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

class AlgorithmicRuleApplicationWorker:
    """
    This class executes algorithmic rules.
    """
    def __init__(self):
        # simple hack
        self.parent = Container(rule=None)

    @staticmethod
    def hardcoded_I810(zb, consequent_function: callable):
        """
        Convert 4 negative facts into one positive fact
        """
        t0 = time.time()

        # in the future this logic will be parsed from the graph
        h_list = p.get_instances_of(zb.I7435["human"])
        rel_list = p.ds.get_subjects_for_relation(zb.R6020["is opposite of functional activity"].uri)
        result_filters = [p.is_relevant_item]
        result_conditions = [lambda res: len(res) == 4]

        result_list = []
        for subj, pred in it.product(h_list, rel_list):
            tmp_res_list = subj.get_relations(pred.uri, return_obj=True)

            for rf in result_filters:
                tmp_res_list = [res for res in tmp_res_list if p.is_relevant_item(res)]

            for cond_func in result_conditions:
                if not cond_func(tmp_res_list):
                    break
            else:
                # all conditions are met
                result_list.append((subj, pred, *tmp_res_list))

        # raworker=self, raw_result_count=len(result_list)
        final_result = ReportingRuleResult(raworker=None)
        final_result.apply_time = time.time() - t0
        for args in result_list:
            cfr = consequent_function(None, *args)

            # TODO: add result.extend_with_binding_info(cfr, res_dict), see above
            final_result.extend_with_binding_info(cfr, {})
        return final_result

    @staticmethod
    def hardcoded_I830(zb, consequent_function: callable, *args):
        """
        Raise exception if one person is different from more than 4 non-placeholder persons
        """
        t0 = time.time()

        # in the future this logic will be parsed from the graph
        h_list = p.get_instances_of(zb.I7435["human"], filter=lambda itm: not itm.R20__has_defining_scope)
        rel_list = [p.R50["is different from"]]

        # filter out R57__is_placeholder items
        result_filters = [p.is_relevant_item]
        result_conditions = [lambda res: len(res) > 4]

        result_list = []
        for subj, pred in it.product(h_list, rel_list):
            tmp_res_list = subj.get_relations(pred.uri, return_obj=True)

            for rf in result_filters:
                tmp_res_list = [res for res in tmp_res_list if rf(res)]

            for cond_func in result_conditions:
                if not cond_func(tmp_res_list):
                    break
            else:
                # all conditions are met
                result_list.append((subj, pred, *tmp_res_list))

        final_result = p.core.RuleResult()

        for result_args in result_list:

            assert len(args) == 1  # this is like ("{} has too many `R50__is_differnt_from` statements",)
            tmp_res = consequent_function(None, *args, result_args[0])

            # TODO: add result.extend_with_binding_info(cfr, res_dict), see above
            final_result.extend(tmp_res)

        final_result.apply_time = time.time() - t0
        return final_result

    @staticmethod
    def hardcoded_I840(zb, consequent_function: callable, *args):
        t0 = time.time()

        h_list = p.get_instances_of(zb.I7435["human"], filter=p.is_relevant_item)
        rel_list = p.ds.get_subjects_for_relation(zb.R2850["is functional activity"].uri, filter=True)

        # filter out the two person-person-activities (TODO: test if this is neccessary)
        # otherwise we would have 7 statements per person
        rel_list = [r for r in rel_list if r not in (
            zb.R2353["lives immediately right of"], zb.R8768["lives immediately left of"]
        )]

        result_filters = [p.is_relevant_item]
        result_conditions = [lambda res: len(res) == 1]

        result_list = []
        for subj, pred in it.product(h_list, rel_list):
            tmp_res_list = subj.get_relations(pred.uri, return_obj=True)

            for rf in result_filters:
                tmp_res_list = [res for res in tmp_res_list if rf(res)]

            for cond_func in result_conditions:
                if not cond_func(tmp_res_list):
                    break
            else:
                # all conditions are met
                result_list.append((subj, pred, *tmp_res_list))

        if len(result_list) == 25:
            # raise the respective success-exception
            consequent_function(None, *args)

        final_result = p.core.RuleResult()
        final_result.apply_time = time.time() - t0
        final_result.dbg = result_list

        return final_result

    def get_single_predicate_report(self, pred):
        subj_type = pred.R8__has_domain_of_argument_1[0]
        obj_type = pred.R11__has_range_of_result[0]

        subj_items = subj_type.R51__instances_are_from[0].R39__has_element
        obj_items = obj_type.R51__instances_are_from[0].R39__has_element

        all_combination_tuples = [tuple(zip(subj_items, perm)) for perm in list(it.permutations(obj_items))]
        # list like [((A, X), (B, Y), (C, Z)), ((A, Y), (B, X), (C, Z)), ...]

        possible_combination_tuples = []
        pred_opposite_list = p.ds.get_subjects_for_relation(p.R43["is opposite of"].uri, filter=pred)
        if not pred_opposite_list:
            return []
        pred_opposite = pred_opposite_list[0]

        for comb_tup in all_combination_tuples:
            for subj, obj in comb_tup:
                if obj in subj.get_relations(pred_opposite.uri, return_obj=True):
                    # this combination leads to a contradiction
                    break
            else:
                # no contradiction took place
                good_tuple = []
                for subj, obj in comb_tup:
                    good_tuple.append((subj, pred, obj))
                possible_combination_tuples.append(tuple(good_tuple))

        return possible_combination_tuples

    def get_predicates_report(self, predicate_list):
        """
        Gather data for each relevant predicate how many possibilities of subject-object-pairs exisit, which do
        not contradict an `oppo_pred`-statement, where `oppo_pred` is 'R43__is_opposite_of' the considered predicate.
        """


        pred_report = Container()
        pred_report.counters = []
        pred_report.total_sum = 0
        pred_report.total_prod = 1
        pred_report.predicates = []
        pred_report.stable_candidates = Container()
        pred_report.hypothesis_candidates = []
        for pred in predicate_list:
            possible_combination_tuples = self.get_single_predicate_report(pred)
            if len(possible_combination_tuples) == 0:
                continue
            pred_report[pred.uri] = possible_combination_tuples
            pred_report.counters.append(len(possible_combination_tuples))
            pred_report.predicates.append(pred)
            pred_report.total_sum += len(possible_combination_tuples)
            pred_report.total_prod *= len(possible_combination_tuples)

            # find (subject, object)-pairs which are stable among all combinations

            # pred_report.stable_candidates[pred.uri] = defaultdict(dict)
            tmp_def_dict = defaultdict(dict)
            for comb_tup in possible_combination_tuples:
                for subj, _, obj in comb_tup:
                    tmp_def_dict[subj.uri][obj.uri] = 1

            pred_report.stable_candidates[pred.uri] = []
            for sub_uri, obj_dict in tmp_def_dict.items():
                pred_report.stable_candidates[pred.uri].append((len(obj_dict), sub_uri))

                # store a list which allows easy access to remaining possibilities
                tmp_list = [len(obj_dict), Container(pred=pred.uri, subj=sub_uri, objs=tuple(obj_dict.keys()))]
                pred_report.hypothesis_candidates.append(tmp_list)

        pred_report.hypothesis_candidates.sort(key=lambda elt: elt[0])
        return pred_report

class HypothesisReasoner:

    uri_suffix = "HYPOTHESIS"

    def __init__(self, zb, base_uri):
        self.zb = zb  # the base module (currently zebra-puzzle base data)
        self.base_uri = base_uri
        self.contex_uri = f"{base_uri}/{self.uri_suffix}"

    def register_module(self):
        keymanager = p.KeyManager()
        p.register_mod(self.contex_uri, keymanager, check_uri=False)

    def hypothesis_reasoning_step(self, rule_list):

        # generate hypothesis
        araw = AlgorithmicRuleApplicationWorker()
        func_act_list = p.ds.get_subjects_for_relation(self.zb.R2850["is functional activity"].uri, filter=True)
        pred_report = araw.get_predicates_report(predicate_list=func_act_list)

        for pos_count, hypo_container in pred_report.hypothesis_candidates:
             if pos_count == 1:
                 # this information is already fixed. there is only this one possibility
                 continue

             subj = p.ds.get_entity_by_uri(hypo_container.subj)
             pred = p.ds.get_entity_by_uri(hypo_container.pred)
             objs = [p.ds.get_entity_by_uri(uri) for uri in hypo_container.objs]
             break
        else:
            msg = "Unexpectedly only trivial remaining possibilities have been found."
            raise NotImplementedError(msg)

        result = Container()
        result.stm_triples = [(subj, pred, obj) for obj in objs]
        result.reasoning_results = []


        # currently the good solution is the first by accident.
        # TODO: test the other direction

        for subj, pred, obj in result.stm_triples[1:]:

            # test the consequences of an hypothesis inside an isolated module (which can be deleted if it failed)
            self.register_module()
            with p.uri_context(uri=self.contex_uri):
                stm = subj.set_relation(pred, obj)
                k = 0
                if VERBOSITY:
                    print("\n"*2, "    Assuming", stm, "and testing\n\n")
                while True:
                    k += 1
                    # TODO: this might provoke a FunctionalRelationError in case of wrong hypothesis
                    res = apply_semantic_rules(*rule_list)
                    if res.exception or not res.new_statements:
                        break
                if isinstance(res.exception, p.core.aux.ReasoningGoalReached):
                    print(p.aux.bgreen("puzzle solved"))
                    result.reasoning_results.append(res)
                    break  # break the for loop

            if isinstance(res.exception, p.core.aux.LogicalContradiction):
                print(p.aux.byellow("This hypothesis led to a contradiction:"), stm)

                # delete all statements from this context
                p.unload_mod(self.contex_uri)
