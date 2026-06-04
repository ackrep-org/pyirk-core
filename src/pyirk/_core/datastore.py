"""
DataStore class extracted from :mod:`pyirk.core`.

The class defined here is import-time safe: its ``__init__`` only uses
``aux``, ``settings``, and ``defaultdict`` — no core classes are touched
until individual methods are called. Methods that need core globals
(``Entity``, ``process_key_str``, ``EType``, ``allowed_literal_types``,
``get_active_mod_uri``, ``get_language_of_str_literal``) access them lazily
via the ``_core`` module object, whose attributes are only read at call time.

The singleton ``ds = DataStore()`` stays in :mod:`pyirk.core` (not here).
PEP 563 is active so forward-reference annotations are lazy strings.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import List, Union

from rdflib import Literal

from pyirk import auxiliary as aux
from pyirk import settings
from pyirk.auxiliary import UnknownPrefixError

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes (Entity, EType, process_key_str, allowed_literal_types,
# get_active_mod_uri, get_language_of_str_literal) are accessed lazily inside
# method bodies (i.e. at call time, not import time).
from pyirk import core as _core


__all__ = [
    "DataStore",
]


class DataStore:
    """
    Provides objects to store all data that would be global otherwise
    """

    def __init__(self):
        self.items = {}
        self.relations = {}

        # dict of lists store keys of the entities (not the entities itself, to simplify deletion)
        self.entities_created_in_mod = defaultdict(list)

        self.stms_created_in_mod = defaultdict(dict)

        # mappings like .a = {"my/mod/uri": "/path/to/mod.py"} and .b = {"/path/to/mod.py": "my/mod/uri"}
        self.mod_path_mapping = aux.OneToOneMapping()

        # for every entity uri store a dict that maps relation uris to lists of corresponding relation-edges
        self.statements = defaultdict(dict)

        # also do this for the inverse relations (for easy querying)
        self.inv_statements = defaultdict(lambda: defaultdict(list))

        # for every scope-item key store the relevant relation-edges
        self.scope_statements = defaultdict(list)

        # for every relation key store the relevant relation-edges
        self.relation_statements = defaultdict(list)

        # store a map {uri: Statement-instance} of all relation edges
        self.statement_uri_map = {}

        # this will be set on demand
        self.rdfgraph = None

        # dict to store important QualifierFactory instances which are created in builtin_entities but needed in core
        self.qff_dict = {}

        # mapping like {uri_1: keymanager_1, ...}
        self.uri_keymanager_dict = {}

        # mapping like .a = {uri_1: prefix_1, ...} and .b = {prefix_1: uri_1}
        self.uri_prefix_mapping = aux.OneToOneMapping()

        # initialize:
        self.uri_prefix_mapping.add_pair(settings.BUILTINS_URI, "bi")

        # mapping like {uri1: modname1, ...}
        self.modnames = {}

        # dict like {uri1: <mod1>, ...}
        self.uri_mod_dict = {}

        # this flag (default False) might be changed during irkloader calls
        self.reuse_loaded_module = False

        # this list serves to keep track of nested scopes
        self.scope_stack = []

        # store unlinked entities
        self.unlinked_entities = {}

        # store hook functions
        self.hooks = self.initialize_hooks()

        # data structure to facilitate scope-copying
        # keys: 2-tuples: (new_scope_uri, old_var_uri)
        # values: new_var_item
        self.scope_var_mappings = {}

    def initialize_hooks(self) -> dict:
        self.hooks = {
            "post-create-entity": [],
            "post-create-item": [],
            "post-create-relation": [],
            "post-finalize-entity": [],
            "post-finalize-item": [],
            "post-finalize-relation": [],
        }
        return self.hooks

    def get_item_by_label(self, label) -> _core.Entity:
        """
        Search over all item and return the first item which has the provided label.
        Useful during interactive debugging. Not useful for production!
        """
        for uri, itm in self.items.items():
            if itm.R1.value == label:
                return itm

    def get_entity_by_key_str(self, key_str, mod_uri=None) -> _core.Entity:
        """
        :param key_str:     str like I1234 or I1234__some_label
        :param mod_uri:     optional uri of the module; if None the active module is assumed

        :return:            corresponding entity
        """

        processed_key = _core.process_key_str(key_str, mod_uri=mod_uri)
        assert processed_key.etype in (_core.EType.ITEM, _core.EType.RELATION)

        if mod_uri is None:
            uri = processed_key.uri
        else:
            uri = aux.make_uri(mod_uri, processed_key.short_key)

        res = self.get_entity_by_uri(uri, processed_key.etype, strict=False)
        if res is None:
            mod_uri = _core.get_active_mod_uri(strict=False)
            msg = (
                f"Could not find entity with key '{processed_key.short_key}'; Entity type: '{processed_key.etype}'; "
                f"Active mod: '{mod_uri}'"
            )
            raise KeyError(msg)

        return res

    def get_entity_by_uri(self, uri: str, etype=None, strict=True) -> Union[_core.Entity, None]:
        if etype is not None:
            # only one lookup is needed
            if etype == _core.EType.ITEM:
                res = self.items.get(uri)
            else:
                res = self.relations.get(uri)
        else:
            # two lookups might be necessary
            res = self.items.get(uri)
            if res is None:
                # try relation (might also be None)
                res = self.relations.get(uri)

        if strict and res is None:
            msg = f"No entity found for URI {uri}."
            raise aux.UnknownURIError(msg)

        return res

    @staticmethod
    def _default_subject_filter(entity):
        """
        used to prevent items from scopes showing up inside the results of `get_subjects_for_relation`.
        """
        # R20["has defining scope"]>
        return getattr(entity, "R20") is None

    def get_subjects_for_relation(self, rel_uri: str, filter=None):
        stm_list: List[_core.Statement] = self.relation_statements[rel_uri]

        res = []
        if isinstance(filter, _core.allowed_literal_types) or isinstance(filter, _core.Entity):
            cond_func = lambda obj: obj == filter
        else:
            cond_func = lambda obj: True
        for stm in stm_list:
            if cond_func(stm.object) and self._default_subject_filter(stm.subject):
                res.append(stm.subject)

        return res

    def get_statements(self, entity_uri: str, rel_uri: str) -> List[_core.Statement]:
        """
        self.statements maps an entity_key to an inner_dict.
        The inner_dict maps an relation_key to a Statement or List[Statement].

        :param entity_uri:
        :param rel_uri:
        :return:
        """
        aux.ensure_valid_uri(rel_uri)
        aux.ensure_valid_uri(entity_uri)

        # We return an empty list if the entity has no such relation.
        # TODO: model this as defaultdict?
        return self.statements[entity_uri].get(rel_uri, list())

    def set_statement(self, stm: _core.Statement) -> None:
        """
        Insert a Statement into the relevant data structures of the DataStorage (self)

        This method does not handle the dual relation. It must be created and stored separately.

        :param stm:   Statement instance
        :return:
        """

        subj_uri = stm.relation_tuple[0].uri
        try:
            subj_label = str(stm.relation_tuple[0].R1)
        except:
            subj_label = "<unknown label>"

        rel_uri = stm.relation_tuple[1].uri
        aux.ensure_valid_uri(subj_uri)
        aux.ensure_valid_uri(rel_uri)

        self.relation_statements[rel_uri].append(stm)
        self.statement_uri_map[stm.uri] = stm

        relation = self.relations[rel_uri]

        # stm_list will be either a list of statements or None
        # for some R22-related reason (see below) we cannot use a default dict here,
        # thus we need to do the case distinction manually
        stm_list = self.statements[subj_uri].get(rel_uri, None)

        if stm_list is None or len(stm_list) == 0:
            self.statements[subj_uri][rel_uri] = [stm]

        elif isinstance(stm_list, list):
            exception_flag = stm.get_first_qualifier_obj_with_rel(
                "R65__allows_alternative_functional_value", tolerate_key_error=True
            )
            if relation.R22 and not exception_flag:
                # R22__is_functional, this means there can only be one value for this relation and this item
                msg = (
                    f"for subject {subj_uri} there already exists a statement for relation {stm.predicate}. "
                    f"This relation is functional (R22), thus another statement is not allowed."
                )
                raise aux.FunctionalRelationError(msg)
            elif relation.R32 and not exception_flag:
                if not isinstance(stm.object, Literal):
                    stm.object = Literal(stm.object, settings.DEFAULT_DATA_LANGUAGE)
                lang_list = [_core.get_language_of_str_literal(s.object) for s in stm_list]
                if stm.object.language in lang_list:
                    msg = (
                        f"for subject {subj_uri} ({subj_label}) there already exists statements for relation "
                        f"{stm.predicate} with the object languages {lang_list}. This relation is functional for "
                        f"each language (R32). Thus another statement with language `{stm.object.language}` is not allowed."
                    )
                    raise aux.FunctionalRelationError(msg)
            stm_list.append(stm)

        else:
            msg = (
                f"unexpected type ({type(stm_list)}) of dict content for entity {subj_uri} and "
                f"relation {rel_uri}. Expected list or None"
            )
            raise TypeError(msg)

    def get_uri_for_prefix(self, prefix: str) -> str:
        res = self.uri_prefix_mapping.b.get(prefix)

        if res is None:
            msg = f"Unknown prefix: '{prefix}'. No matching URI found."
            raise UnknownPrefixError(msg)
        return res

    def preprocess_query(self, query, sanity_check=True):
        if "__" in query:
            if sanity_check:
                prefixes = re.findall(r"[\w]*:[ ]*<.*?>", query)
                prefix_dict = {}
                for prefix in prefixes:
                    parts = prefix.split(" ")
                    key = parts[0]
                    value = parts[-1].replace("<", "").replace(">", "")
                    if value.split("/")[-1].upper() == value.split("/")[-1]:
                        # this removes special qualifier prefixes that lead to uri not found error
                        value = "/".join(value.split("/")[:-1]) + "#"
                    prefix_dict[key] = value
                # print(prefix_dict)

                entities = re.findall(r"[\w]*:[\w]+__[\w]+(?:–_instance)?", query)
                for e in entities:
                    # check sanity
                    prefix, rest = e.split(":")
                    prefix = prefix + ":"
                    irk_key, description = rest.split("__")

                    entity_uri = prefix_dict.get(prefix) + irk_key
                    entity = self.get_entity_by_uri(entity_uri)

                    label = description.replace("_", " ")

                    assert isinstance(entity.R1, Literal)
                    r1 = entity.R1.value

                    if r1 != label:
                        msg = f"Entity label '{r1}' for entity '{e}' and given label '{label}' do not match!"
                        raise aux.InconsistentLabelError(msg)
                    # todo: do not raise if wrong entity is in comment

            new_query = re.sub(r"__[\w]+(?:–_instance)?", "", query)
        else:
            new_query = query

        return new_query

    def append_scope(self, scope):
        """
        Called when __enter__-ing a scoping context manager
        """
        self.scope_stack.append(scope)

    def remove_scope(self, scope):
        """
        Called when __exit__-ing a scoping context manager
        """

        current_scope = self.get_current_scope()
        if current_scope != scope:
            msg = "Refuse to remove scope which is not the topmost on the stack (i.e. the last in the list)"
            raise aux.GeneralPyIRKError(msg)

        self.scope_stack.pop()

    def get_current_scope(self):
        try:
            return self.scope_stack[-1]
        except IndexError:
            msg = "unexpectedly found the scope stack empty"
            raise aux.GeneralPyIRKError(msg)
