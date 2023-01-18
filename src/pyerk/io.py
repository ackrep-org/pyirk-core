"""
Created: 2023-01-17 17:43:51
author: Carsten Knoll

This module contains code for import and export

"""

from typing import Dict, List, Tuple, Optional  # noqa
import rdflib
from addict import Addict as Container

# noinspection PyUnresolvedReferences
from ipydex import IPS  # noqa
import pyerk as p


def export_rdf_triples(fpath: str, **kwargs):
    p.ds.rdfgraph = p.rdfstack.create_rdf_triples(**kwargs)
    p.ds.rdfgraph.serialize(fpath, format="nt", encoding="utf-8")


def import_raw_rdf_triples(fpath: str):

    g = rdflib.Graph()
    g.parse(fpath)
    return g


def import_stms_from_rdf_triples(fpath: str):
    """
    """

    g = import_raw_rdf_triples(fpath)

    # get uris of items which are created by the triples
    newly_created_item_2tuples = g.subject_objects(predicate=rdflib.URIRef(p.R4["is instance of"].uri))

    res = Container()
    res.new_items = []
    for subj_uri, obj_uri in newly_created_item_2tuples:
        subj_uri, obj_uri = str(subj_uri), str(obj_uri)
        obj_entity = p.ds.get_entity_by_uri(obj_uri)

        if p.ds.get_entity_by_uri(subj_uri, strict=False) is None:
            subj_short_key = subj_uri.split("#")[1]
            subj_entity = p.core.create_item(key_str=subj_short_key, R4__is_instance_of=obj_entity)
            res.new_items.append(subj_entity)

    new_rows = []
    qualifier_rows = []
    for row in g:
        new_row = []
        pred = row[1]
        p_pred_uri = p.aux.parse_uri(pred)
        if p_pred_uri.sub_ns:
            # this row corresponds to a qualifier (or a statement node and should be handled separately)
            qualifier_rows.append(row)
            continue

        for elt in row:
            new_row.append(p.rdfstack.convert_from_rdf_to_pyerk(elt))
        new_rows.append(new_row)

    res.new_stms = []
    for subj, pred, obj in new_rows:
        try:
            stm = subj.set_relation(pred, obj)
        except p.aux.FunctionalRelationError:
            stm = subj.overwrite_statement(pred.uri, obj)

        res.new_stms.append(stm)

    return res
