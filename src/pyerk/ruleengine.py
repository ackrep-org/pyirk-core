"""
Created: 2022-09-06 19:14:39
author: Carsten Knoll

This module contains code to enable semantic inferences based on special items (e.g. instances of I41__semantic_rule)

"""

from typing import List, Tuple, Optional
from collections import defaultdict
from enum import Enum
import json
import textwrap

import networkx as nx
from networkx.algorithms import isomorphism as nxiso

# noinspection PyUnresolvedReferences
from addict import Addict as Container

# noinspection PyUnresolvedReferences
from ipydex import IPS

from . import core

# todo: replace bi. with p. etc
from . import builtin_entities as bi
from . import builtin_entities as b
import pyerk as p

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
        return res

    def _apply(self) -> core.RuleResult:
        """
        Perform the actual application of the rule (either via aubgraph monomorphism or via SPARQL query)
        """

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
        G = nx.DiGraph()

        for uri, entity in list(core.ds.items.items()) + list(core.ds.relations.items()):

            # prevent items created inside scopes
            if is_node_for_simple_graph(entity):
                # TODO: rename kwarg itm to ent
                G.add_node(uri, itm=entity, is_literal=False)

        all_rels = self.get_all_node_relations()
        for uri_tup, rel_cont in all_rels.items():
            uri1, uri2 = uri_tup
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

        # will be set when needed (holds the union of both previous structures)
        self.extended_local_nodes = None

        # list of Containers, containing triples like (node1, <Relation>, node2)
        self.asserted_relation_templates: List[Container] = None

        self.P: nx.DiGraph = None
        self.create_prototype_subgraph_from_rule()

    def apply_sparql_premise(self) -> core.RuleResult:
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
        res = p.ds.rdfgraph.query(qsrc)
        res2 = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        result_maps = []
        for row in res2:
            res_map = {}
            assert len(row) == len(self.parent.vars)
            for v, entity in zip(self.parent.vars, row):
                node = self.local_nodes.a[v.uri]
                res_map[node] = entity
            result_maps.append(res_map)

        return self._process_result_map(result_maps)

    def apply_graph_premise(self) -> core.RuleResult:

        result_maps = self.match_subgraph_P()
        # TODO: for debugging the result_maps data structure the following things might be helpful:
        # - a mapping like self.local_nodes.a but with labels instead of uris
        # - a visualization of the prototype graph self.P
        res = self._process_result_map(result_maps)

        return res

    def _process_result_map(self, result_maps) -> core.RuleResult:
        """
        - process the found subgraphs with the assertion
        """

        condition_functions, cond_func_arg_nodes = self.get_condition_funcs_and_args()

        consequent_functions, cf_arg_nodes, anchor_node_names = self.prepare_consequent_functions()

        result = ReportingRuleResult(raworker=self)


        for res_dict in result_maps:
            # res_dict represents one situation where the assertions should be applied
            # it's a dict {<node-number>: <item>, ...} like
            # {
            #       0: <Item I2931["local ljapunov stability"]>,
            #       1: <Item I4900["local asymtotical stability"]>,
            #       2: <Item I9642["local exponential stability"]>
            #  }

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

            csq_fnc_results: List[core.RuleResult] = [
                func(*call_args) for func, call_args in zip(consequent_functions, call_args_list)
            ]

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

                if new_subj.R20__has_defining_scope:
                    # rules should not affect items inside scopes (maybe this will be more precise in the future)
                    continue

                if isinstance(n2, LiteralWrapper):
                    new_obj = n2.value
                else:
                    new_obj = search_dict[n2]

                # check if relation already exists and should be ommitted
                if cntnr.omit_if_existing:
                    if new_obj in new_subj.get_relations(rel.uri, return_obj=True):
                        continue
                # TODO: add qualifiers
                new_stm = new_subj.set_relation(rel, new_obj)

                result.add_bound_statement(new_stm, res_dict)

        return result

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
        GM = nxiso.DiGraphMatcher(self.parent.G, self.P, node_match=self._node_matcher, edge_match=edge_matcher)

        # for the difference between subgraph monomorphisms and isomorphisms see:
        # https://networkx.org/documentation/stable/reference/algorithms/isomorphism.vf2.html#subgraph-isomorphism
        # jupyter notebook subgraph-matching-problem
        res = list(GM.subgraph_monomorphisms_iter())
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

        self.P = nx.DiGraph()

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

            n1 = self.local_nodes.a[subj.uri]

            self.ensure_node_of_P(n1)

            if isinstance(obj, core.Entity):
                if obj.R59:
                    # handle variable_literal
                    n2 = self.parent.literal_variable_nodes.a[obj.uri]
                    self.P.add_node(n2, entity=obj, is_literal=False, is_variable_literal=True)
                else:
                    n2 = self.local_nodes.a[obj.uri]
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

        # components_container
        cc = self._get_weakly_connected_components(self.P)

        if len(cc.main_components) == 0:
            raise core.aux.SemanticRuleError("empty prototype graph")

        if len(cc.main_components) > 1:
            msg = (
                f"unexpected number of components of prototype graph while applying rule {self.parent.rule}."
                f"Expected: 1, but got {len(cc.main_components)}. Possible reason: unused variables in the rules context."
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
                uri = self.local_nodes.b[node]
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

        return compare_relation_statements(e1d["rel_entity"], e2d["rel_statements"])

        # if set(e2d["rel_props"]).issubset(e1d["rel_props"]):
        #     return True

    if e1d["rel_uri"] != e2d["rel_uri"]:
        return False

    return True


class ReportingRuleResult(core.RuleResult):

    def __init__(self, raworker: RuleApplicatorWorker):
        super().__init__()
        self.raworker = raworker
        self.statement_reports = []

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
        for i, c in enumerate(self.statement_reports):
            print(c.stm, "  because  ",  c.bindinfo, sep)
            if i >= max:
                break


# Note this function will be called very often -> check for speedup possibilites
def compare_relation_statements(rel1: core.Relation, stm_list: List[core.Statement]):
    """
    decide whether a given relation fulfills all given statements
    """

    for stm in stm_list:
        raw_res = rel1.get_relations(stm.predicate.uri, return_obj=True)
        if raw_res == []:
            return False
        if raw_res[0] != stm.object:
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
