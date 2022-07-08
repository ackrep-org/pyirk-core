"""
This module serves to perform integrity checks on the knowledge base
"""
from typing import Iterable

from . import core as pyerk, auxiliary as aux

from ipydex import IPS
from rdflib import Graph, Literal, URIRef

# noinspection PyUnresolvedReferences  # imported to be used in gui-view
from pyparsing import ParseException


ERK_URI = "erk:/"


def create_rdf_triples() -> Graph:

    # based on https://rdflib.readthedocs.io/en/stable/gettingstarted.html
    g = Graph()

    for re in pyerk.ds.relation_edge_list:
        row = []
        for entity in re.relation_tuple:
            if isinstance(entity, pyerk.Entity):
                row.append(URIRef(f"erk:/{entity.short_key}"))
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


def perform_sparql_query(qsrc: str, return_raw=False) -> Iterable:

    if pyerk.ds.rdfgraph is None:
        pyerk.ds.rdfgraph = create_rdf_triples()

    res = pyerk.ds.rdfgraph.query(qsrc)

    if return_raw:
        return res
    else:
        return aux.apply_func_to_table_cells(convert_from_rdf_to_pyerk, res)

    return list(res)


def convert_from_rdf_to_pyerk(rdfnode) -> object:
    if isinstance(rdfnode, URIRef):
        short_key = rdfnode.lstrip(ERK_URI)
        entity_object = pyerk.ds.get_entity(short_key)
    else:
        IPS()
        1/0

    res = entity_object

    return res


def get_sparql_example_query():

    qsrc = f"""
    
        PREFIX : <{ERK_URI}>
        SELECT *
        WHERE {{
            ?s :R4 ?o.
        }}
    """
    return qsrc


def check_all_relation_types():
    rdfgraph = create_rdf_triples()

    query = get_sparql_example_query()
    res = rdfgraph.query(query)
    print(res)

    n = list(res)[0][0]

    res2 = aux.apply_func_to_table_cells(convert_from_rdf_to_pyerk, res)
    IPS()

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
