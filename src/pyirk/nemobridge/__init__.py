"""
pyirk.nemobridge — bridge between pyirk DataStore and the Nemo Datalog engine.

Public API (re-exported from submodules):
  from pyirk.nemobridge import (
      export_datastore, export_relation_facts, is_scope_internal,
      classify_rules, generate_transitivity_facts, generate_rls,
      classification_to_json, RuleClassification,
  )
"""

from .exporter import (  # noqa: F401
    export_datastore,
    export_relation_facts,
    is_scope_internal,
)

from .translator import (  # noqa: F401
    RuleClassification,
    classify_rules,
    generate_transitivity_facts,
    generate_rls,
    classification_to_json,
)
