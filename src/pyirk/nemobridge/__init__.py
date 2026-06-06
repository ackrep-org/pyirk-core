"""
pyirk.nemobridge — bridge between pyirk DataStore and the Nemo Datalog engine.

Public API (re-exported from submodules):
  from pyirk.nemobridge import export_datastore, export_relation_facts, is_scope_internal
"""

from .exporter import (  # noqa: F401
    export_datastore,
    export_relation_facts,
    is_scope_internal,
)
