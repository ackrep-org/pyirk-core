"""
Query / rule-result helpers extracted from :mod:`pyirk.core`.

The symbols defined here are import-time safe: none of them needs any
module-global of ``core`` while this module is being imported. Symbols that use
``core`` module-globals (``Entity``, ``Relation``) at *call* time access them
module-qualified via the ``_core`` module object, whose attributes are only read
once the functions are actually called. This keeps the import monodirectional:
``core`` imports this module (early), this module only binds the (partially
loaded) ``core`` module object.

PEP 563 (``from __future__ import annotations``) is active so that all
forward-reference annotations (``Entity``, ``Item``, ``Statement``, etc.) become
lazy strings rather than immediately evaluated names.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the function bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = [
    "RuleResult",
    "is_true",
    "is_subclass",
    "is_instance",
    "is_subproperty",
]


class RuleResult:
    def __init__(self):
        self.new_statements = []
        self.changed_statements = []
        self.new_entities = []
        self.unlinked_entities = []
        self.partial_results = []
        self.replacements = []
        self._rule = None
        self.apply_time = None
        self.exception = None
        self.creator_object = None

        # dict like {rel_uri1: [stm1, stm2, ...]}
        # maps a relation uri to a list of statements which have this relation as predicate
        self.rel_map = defaultdict(list)

    def add_statement(self, stm: _core.Statement):
        if stm is None:
            return
        assert stm not in self.new_statements
        self.new_statements.append(stm)
        self.rel_map[stm.predicate.uri].append(stm)

    def add_statements(self, stms: List[_core.Statement]):
        for stm in stms:
            self.add_statement(stm)

    def add_entity(self, entity: _core.Entity):
        self.new_entities.append(entity)

    def extend(self, part: RuleResult):
        assert isinstance(part, RuleResult)
        self.add_statements(part.new_statements)
        self.new_entities.extend(part.new_entities)
        self.unlinked_entities.extend(part.unlinked_entities)
        self.replacements.extend(part.replacements)
        if part.exception:
            self.exception = part.exception

    def add_partial(self, part: RuleResult):
        if self.apply_time is None:
            self.apply_time = 0

        self.apply_time += part.apply_time
        self.extend(part)
        self.partial_results.append(part)

    def __repr__(self):
        if self.apply_time is None:
            aplt = "? s"
        else:
            aplt = f"{round(self.apply_time, 3)} s"
        res = (
            f"{type(self).__name__} ({aplt}): new_stms: {len(self.new_statements)}, parts: {len(self.partial_results)}"
        )
        return res

    @property
    def rule(self):
        """
        Convenience property for easy access to the corresponding rule
        """
        if self._rule is None:
            if self.partial_results:
                return self.partial_results[0].rule

        return self._rule

    def get_new_triples(self) -> list[tuple[_core.Entity]]:
        return [stm.relation_tuple for stm in self.new_statements]


def is_true(subject: _core.Entity, predicate: _core.Relation, object) -> tuple[bool, None]:
    if not isinstance(subject, _core.Entity):
        raise AssertionError()
    if not isinstance(predicate, _core.Relation):
        raise AssertionError()

    res = subject.get_relations(predicate.uri, return_obj=True)
    if isinstance(res, list):
        res = res[0]
    return res == object


def is_subclass(item: _core.Item, parent_item: _core.Item):
    if item.R3 is None:
        return False
    elif item.R3 == parent_item:
        return True
    else:
        return is_subclass(item.R3, parent_item)


def is_instance(item: _core.Item, parent_item: _core.Item):

    msg = "`core.is_instance` is deprecated in favor of `builtins.is_instance_of`"
    raise DeprecationWarning(msg)
    parent = item.R4
    if parent is None:
        return False
    elif parent == parent_item:
        return True
    else:
        return is_subclass(parent, parent_item)


def is_subproperty(item: _core.Item, parent_property: _core.Item):
    """check if item is subproperty of parent_property. item == parent_p will return True as well."""
    if item == parent_property:
        return True
    if not hasattr(item, "R17"):
        return False
    elif item.R17 is None:
        return False
    elif parent_property in item.R17:
        return True
    else:
        return is_subproperty(item.R17, parent_property)
