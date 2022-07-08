"""
This module serves to perform integrity checks on the knowledge base
"""

from . import core as pyerk, auxiliary as aux

from ipydex import IPS, activate_ips_on_exception
from rdflib import Graph, Literal, RDF, URIRef


def create_rdf_triples():
    g = Graph()

    triple_list = []
    for re in pyerk.ds.relation_edge_list:
        row = []
        for entity in re.relation_tuple:
            if isinstance(entity, pyerk.Entity):
                row.append(URIRef(f"erk:/{entity.short_key}"))
            else:
                # no entity but a literal value
                row.append(Literal(entity))
        g.add(row)
    return g


def check_subclass(entity, class_item):

    # Hier müsste man prüfen ob es eine instanz-subklassen*-Beziehung gibt
    # das wird insbesondere dann spannend, wenn es sowas wie pseudo-mehrfachvererbung gibt
    res = []
    res.extend(aux.ensure_list(entity.R4__is_instance_of))
    res.extend(aux.ensure_list(entity.R3__is_subclass_of))


def check_all_relation_types():
    rdfgraph = create_rdf_triples()

    query = """
    
        PREFIX : <erk:/>
        SELECT *
        WHERE {
            ?s :R4 ?o.
        }
    """
    res = rdfgraph.query(query)


    IPS()
    return

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


