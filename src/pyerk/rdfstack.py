"""
This module serves to perform integrity checks on the knowledge base
"""
from typing import Union

from . import core as pyerk, auxiliary as aux
from . auxiliary import STATEMENTS_URI_PART, PREDICATES_URI_PART, QUALIFIERS_URI_PART

# noinspection PyUnresolvedReferences
from ipydex import IPS
import rdflib
from rdflib import Literal, URIRef
from rdflib.plugins.sparql.processor import SPARQLResult
from rdflib.query import Result


# noinspection PyUnresolvedReferences
# (imported here to be used in gui-view)
from pyparsing import ParseException  # noqa


ERK_URI = f"{pyerk.settings.BUILTINS_URI}{pyerk.settings.URI_SEP}"


def _make_rel_uri_with_suffix(rel_uri: str, suffix: str):
    pyerk.aux.ensure_valid_relation_uri(rel_uri)
    new_uri = rel_uri.replace("#", f"{suffix}#")
    assert len(new_uri) == len(rel_uri) + len(suffix)
    return new_uri


def make_statement_uri(rel_uri: str):
    return _make_rel_uri_with_suffix(rel_uri, STATEMENTS_URI_PART)


def make_predicate_uri(rel_uri: str):
    return _make_rel_uri_with_suffix(rel_uri, PREDICATES_URI_PART)


def make_qualifier_uri(rel_uri: str):
    return _make_rel_uri_with_suffix(rel_uri, QUALIFIERS_URI_PART)


def serialize_object(obj):
    if isinstance(obj, pyerk.Entity):
        return URIRef(f"{obj.uri}")

    else:
        assert isinstance(obj, pyerk.allowed_literal_types)
        # no entity but a literal value
        return Literal(obj)


def get_statement_rows(stm: pyerk.Statement):
    row1 = [URIRef(stm.subject.uri), URIRef(make_statement_uri(stm.predicate.uri)), URIRef(stm.uri)]
    row2 = [URIRef(stm.uri), URIRef(make_predicate_uri(stm.predicate.uri)), serialize_object(stm.object)]

    return row1, row2


def create_rdf_triples(add_qualifiers=False, add_statements=False, modfilter=None) -> rdflib.Graph:
    """
    :param add_qualifiers:     bool; implies add_statements
    :param add_statements:     bool;
    """

    # based on https://rdflib.readthedocs.io/en/stable/gettingstarted.html
    g = rdflib.Graph()

    processed_statements = {}
    qualifier_statements = []

    if isinstance(modfilter, str):
        modfilter = set([modfilter])

    for stm_uri, stm in pyerk.ds.statement_uri_map.items():
        if not check_uri_in_modfilter(stm.uri, modfilter):
            continue

        row = []
        for i, entity in enumerate(stm.relation_tuple):
            if isinstance(entity, pyerk.Statement):
                # stm is a qualifier-statement which has another statement as subject
                assert i == 0
                qualifier_statements.append(stm)
                break
            row.append(serialize_object(entity))

        # noinspection PyTypeChecker
        if row:
            g.add(row)

        if add_statements or add_qualifiers:
            row1, row2 = get_statement_rows(stm)
            g.add(row1)
            g.add(row2)
            processed_statements[stm.uri] = stm

    if add_qualifiers:
        # this is strongly inspired by
        # https://en.wikibooks.org/wiki/SPARQL/WIKIDATA_Qualifiers,_References_and_Ranks#Qualifiers
        for qstm in qualifier_statements:
            if not check_uri_in_modfilter(qstm.uri, modfilter):
                continue

            qstm: pyerk.Statement
            subj_stm, pred, obj = qstm.relation_tuple

            if qstm.uri not in processed_statements:
                # create the row for the statement node
                row1, row2 = get_statement_rows(qstm)
                g.add(row1)
                g.add(row2)
                processed_statements[qstm.uri] = qstm

            # add the actual qualifier information
            g.add([URIRef(subj_stm.uri), URIRef(make_qualifier_uri(pred.uri)), serialize_object(obj)])
    return g


def check_uri_in_modfilter(uri, modfilter):
    if modfilter is None:
        return True
    part0: str = uri.split("#")[0]

    if part0.endswith(STATEMENTS_URI_PART):
        part0 = part0[:-len(STATEMENTS_URI_PART)]
        IPS()
    elif part0.endswith(QUALIFIERS_URI_PART):
        part0 = part0[:-len(QUALIFIERS_URI_PART)]
        IPS()

    return part0 in modfilter


def check_subclass(entity, class_item):

    # wip!

    # Hier müsste man prüfen ob es eine instanz-subklassen*-Beziehung gibt
    # das wird insbesondere dann spannend, wenn es sowas wie pseudo-mehrfachvererbung gibt
    res = []
    res.extend(aux.ensure_list(entity.R4__is_instance_of))
    res.extend(aux.ensure_list(entity.R3__is_subclass_of))

    res.append(class_item)
    raise aux.NotYetFinishedError


Sparql_results_type = Union[aux.ListWithAttributes, SPARQLResult, Result]


def perform_sparql_query(qsrc: str, return_raw=False) -> Sparql_results_type:

    if pyerk.ds.rdfgraph is None:
        pyerk.ds.rdfgraph = create_rdf_triples()

    res = pyerk.ds.rdfgraph.query(qsrc)

    if return_raw:
        return res
    else:
        res2 = aux.apply_func_to_table_cells(convert_from_rdf_to_pyerk, res)
        res2.vars = res.vars
        return res2


def convert_from_rdf_to_pyerk(rdfnode) -> object:
    if isinstance(rdfnode, URIRef):
        uri = rdfnode.toPython()
        entity_object = pyerk.ds.get_entity_by_uri(uri)
    elif isinstance(rdfnode, Literal):
        entity_object = rdfnode.value
    elif rdfnode is None:
        # this is the case when a variable from the SELECT-clause is not bound by the WHERE-clause
        # (or when there is a blank rdf node in the triples?)
        entity_object = None
    else:
        msg = f"Unexpected Type: {type(rdfnode)} of object {rdfnode} while parsing rdf graph."
        raise TypeError(msg)

    return entity_object


def get_sparql_example_query():

    qsrc = f"""

        PREFIX : <{ERK_URI}>
        SELECT ?s ?o
        WHERE {{
            ?s :R5 ?o.
        }}
    """
    return qsrc


def get_sparql_example_query2():

    qsrc = f"""
        PREFIX : <{ERK_URI}>
        PREFIX ocse: <erk:/ocse/0.2#>
        SELECT ?s
        WHERE {{
            ?s :R16 ocse:I7733.

        }}
        """
    return qsrc


# noinspection PyUnusedLocal
def check_all_relation_types():
    rdfgraph = create_rdf_triples()

    query = get_sparql_example_query()
    res = rdfgraph.query(query)
    print(res)

    n = list(res)[0][0]

    res2 = aux.apply_func_to_table_cells(convert_from_rdf_to_pyerk, res)
    # IPS()
    raise aux.NotYetFinishedError


"""
    for rel_key, re_list in pyerk.ds.relation_statements.items():
        for re in re_list:
            re: pyerk.Statement
            subj, pred, obj = re.relation_tuple
            pred: pyerk.Relation

            # TODO: get rid of ensure_list here
            expected_domain1_list = aux.ensure_list(pred.R8)
            expected_range_list = aux.ensure_list(pred.R11)



            for expected_entity_type in expected_domain1_list:
                IPS()
                pass
"""
