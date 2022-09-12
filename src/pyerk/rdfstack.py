"""
This module serves to perform integrity checks on the knowledge base
"""
from typing import Union

from . import core as pyerk, auxiliary as aux

# noinspection PyUnresolvedReferences
from ipydex import IPS
from rdflib import Graph, Literal, URIRef
from rdflib.plugins.sparql.processor import SPARQLResult
from rdflib.query import Result


# noinspection PyUnresolvedReferences
# (imported here to be used in gui-view)
from pyparsing import ParseException


ERK_URI = f"{pyerk.settings.BUILTINS_URI}{pyerk.settings.URI_SEP}"


def create_rdf_triples() -> Graph:

    # based on https://rdflib.readthedocs.io/en/stable/gettingstarted.html
    g = Graph()

    for re_uri, re in pyerk.ds.relation_edge_uri_map.items():
        row = []
        for entity in re.relation_tuple:
            if isinstance(entity, pyerk.Entity):
                row.append(URIRef(f"{entity.uri}"))
            else:
                # no entity but a literal value
                row.append(Literal(entity))
        # noinspection PyTypeChecker
        g.add(row)
    return g


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
    for rel_key, re_list in pyerk.ds.relation_relation_edges.items():
        for re in re_list:
            re: pyerk.RelationEdge
            subj, pred, obj = re.relation_tuple
            pred: pyerk.Relation

            # TODO: get rid of ensure_list here
            expected_domain1_list = aux.ensure_list(pred.R8)
            expected_range_list = aux.ensure_list(pred.R11)



            for expected_entity_type in expected_domain1_list:
                IPS()
                pass
"""
