"""
Created: 2023-01-17 17:43:51
author: Carsten Knoll

This module contains code for import and export

"""

from typing import Dict, List, Tuple, Optional  # noqa
import rdflib

# noinspection PyUnresolvedReferences
from ipydex import IPS  # noqa
import pyerk as p


def export_rdf_triples(fpath: str, **kwargs):
    p.ds.rdfgraph = p.rdfstack.create_rdf_triples(**kwargs)
    p.ds.rdfgraph.serialize(fpath, format="nt", encoding="utf-8")


def import_rdf_triples(fpath: str):

    g = rdflib.Graph()
    g.parse(fpath)
    return g
