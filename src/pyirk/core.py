"""
Core module of pyirk
"""

import os
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass
import inspect
import types
import abc
import random
import functools
from urllib.parse import quote
from enum import Enum, unique
import re as regex
from addict import Dict as attr_dict
from typing import Any, Dict, Union, List, Iterable, Optional
from rdflib import Literal
import pydantic
import re
import json, yaml

from pyirk import auxiliary as aux
from pyirk import settings

# allow convenient access to exceptions in downstream applications
from pyirk.auxiliary import (
    InvalidURIError,
    InvalidPrefixError,
    PyIRKException,
    EmptyURIStackError,
    InvalidShortKeyError,
    UnknownPrefixError,
)

from ipydex import IPS, activate_ips_on_exception, set_trace

if os.environ.get("IPYDEX_AIOE") == "true":
    activate_ips_on_exception()


# Facade re-export of key-/short-key-management migrated to the `_core` subpackage.
# Placed early so that all subsequent code in this module sees the names (e.g. EType,
# ProcessedStmtKey, process_key_str, KeyManager). The submodule only binds the (here
# still partially loaded) `core` module object and reads its globals lazily at call
# time, so importing it here does not cause a circular failure.
from ._core.keymanager import *  # noqa: E402,F401,F403

# Facade re-export of inspection-/context-/module-lifecycle helpers migrated to
# the `_core` subpackage. Placed early (right after keymanager) so that all
# subsequent code in this module sees the names (e.g. uri_context,
# get_active_mod_uri, get_caller_frame, start_mod). The submodule only binds the
# (here still partially loaded) `core` module object and reads its globals
# lazily at call time, so importing it here does not cause a circular failure.
from ._core.context import *  # noqa: E402,F401,F403

# Facade re-export of module-lifecycle / entity-unlinking helpers migrated to
# the `_core` subpackage. The submodule only binds the (here still partially
# loaded) `core` module object and reads its globals lazily at call time, so
# importing it here does not cause a circular failure.
from ._core.mod_management import *  # noqa: E402,F401,F403

# Facade re-export of serialization-/formatting helpers migrated to the `_core`
# subpackage. The submodule only binds the (here still partially loaded) `core`
# module object and reads its globals lazily at call time, so importing it here
# does not cause a circular failure.
from ._core.serialization import *  # noqa: E402,F401,F403

# Facade re-export of query / rule-result helpers migrated to the `_core`
# subpackage. The submodule only binds the (here still partially loaded) `core`
# module object and reads its globals lazily at call time, so importing it here
# does not cause a circular failure.
from ._core.queries import *  # noqa: E402,F401,F403

# Facade re-export of entity-operation helpers migrated to the `_core`
# subpackage. The submodule only binds the (here still partially loaded) `core`
# module object and reads its globals lazily at call time, so importing it here
# does not cause a circular failure.
from ._core.entity_ops import *  # noqa: E402,F401,F403

# Facade re-export of HTML-formatting helpers migrated to the `_core`
# subpackage.
from ._core.html_format import *  # noqa: E402,F401,F403

# Facade re-export of PrefixShortCut migrated to the `_core` subpackage.
from ._core.prefix_shortcut import *  # noqa: E402,F401,F403

# Facade re-export of DataStore migrated to the `_core` subpackage.
# The singleton ``ds = DataStore()`` stays in this module (see below).
from ._core.datastore import DataStore  # noqa: E402,F401


allowed_literal_types = (str, bool, float, int, complex, Literal)

# Relations with R11__has_range_of_result=I19["multilingual string literal"] (due to multilinguality support)
# Here we should automatically identify those relations which have R11__has_range_of_result=I19["multilingual string literal"]
# for now these are hardcoded (which is also faster)
RELKEYS_WITH_LITERAL_RANGE = ("R1", "R2", "R77")


# copied from yamlpyowl project
def check_type(obj, expected_type, strict=True):
    """
    Use the pydantic package to check for (complex) types from the typing module.
    If type checking passes returns `True`. This allows to use `assert check_type(...)` which allows to omit those
    type checks (together with other assertions) for performance reasons, e.g. with `python -O ...` .
    :param obj:             the object to check
    :param expected_type:   primitive or complex type (like typing.List[dict])
    :return:                True (or raise an TypeError)
    """

    class Model(pydantic.BaseModel):
        data: expected_type
        # necessary because https://github.com/samuelcolvin/pydantic/issues/182
        # otherwise check_type raises() an error for types as Dict[str, owl2.Thing]
        # note: this has been converted from class-based config to dict-based config
        # see: https://docs.pydantic.dev/2.4/migration/#changes-to-config
        model_config = {
            "arbitrary_types_allowed": True,
        }

    # convert ValidationError to TypeError if the obj does not match the expected type
    try:
        mod = Model(data=obj)
    except pydantic.ValidationError as ve:
        if not strict:
            return False
        msg = (
            f"Unexpected type. Got: {type(obj)}. Expected: {expected_type}. "
            f"Further Information:\n {str(ve.errors())}"
        )
        raise TypeError(msg)

    if not mod.data == obj:
        if not strict:
            return False
        msg = f"While type-checking: Unexpected inner structure of parsed model. Expected: {expected_type}"
        raise TypeError(msg)
    return True


class Entity(abc.ABC):
    """
    Abstract parent class for both Relations and Items.

    Do not forget to call self.__post_init__ at the end of __init__ in subclasses.
    """

    # a "short_key" is something like "I1234" while for usability reasons we also allow keys like
    # I1234__some_explanatory_label (which is a key but not a short key)
    short_key: str = None

    def __init__(self, base_uri):
        # this will hold mappings like "R1234": EntityRelation(..., R1234)
        self._is_initialized = False  # will be True after __post_init__
        self.relation_dict = {}
        self._method_prototypes = []
        self._namespaces = {}
        self.base_uri = base_uri
        self.uri = None  # will be set in __post_init__

        # simplifies debugging, will be set by _unlink_entity()
        self._label_after_unlink = None
        self._unlinked = False

        self.updated = False

    def __call__(self, *args, **kwargs):
        custom_call_method = getattr(self, "_custom_call", None)
        if custom_call_method is None:
            msg = f"entity {self} has not defined a _custom_call-method and thus cannot be called"
            raise TypeError(msg)
        else:
            assert callable(custom_call_method)

            res = custom_call_method(*args, **kwargs)

            if custom_call_post_process := getattr(self, "_custom_call_post_process", None):
                res = custom_call_post_process(res, *args, **kwargs)

            return res

    @property
    def name_labeled_key(self):
        return f"{self.short_key}__{self.R1.replace(' ', '_')}"

    def idoc(self, adhoc_label: str):
        """
        idoc means "inline doc". This function allows to attach a label to entities when using them in code
        because it returns just the Entity-object itself. Thus one can use the following expressions interchangeably:
        `I1234` and `I1234.idoc("human readable item name")`

        Note that there is a shortcut to this function: `I1234["human readable item name"]

        :return:    self
        """

        # check if the used ad hoc label in indexed-key notation matches the stored label
        # note: this also passes for rdflib.term.Literal
        assert isinstance(adhoc_label, str)

        if getattr(self, "_ignore_mismatching_adhoc_label", False):
            # we do not need to test the adhoc label
            return self

        if adhoc_label != self.R1:
            # due to multilinguality there might be multiple labels. As adhoc label we accept any language
            all_labels = self.get_relations("R1", return_obj=True)
            all_labels_dict = dict((str(label.value), None) for label in all_labels)
            adhoc_label_str = str(adhoc_label)

            if adhoc_label_str not in all_labels_dict:
                msg = (
                    f"Mismatching label for Entity {self.short_key}! Got '{adhoc_label}' but valid labels are: "
                    f" {all_labels}.\n\n"
                    f"Note: in index-labeled key notation the language of the labels is ignored for convenience."
                )
                raise ValueError(msg)

        return self

    def __getitem__(self, adhoc_label):
        """
        This magic method overloads the [...]-operator. See docs for `idoc` for more information.

        :param adhoc_label:
        :return:   self
        """
        return self.idoc(adhoc_label)

    def __getattr__(self, attr_name):
        try:
            return self.__dict__[attr_name]
        except KeyError:
            pass
        processed_key: ProcessedStmtKey = self.__process_attribute_name(attr_name)

        try:
            # TODO: introduce prefixes here, which are mapped to uris
            etyrel = self._get_relation_contents(rel_uri=processed_key.uri, lang_indicator=processed_key.lang_indicator)
        except KeyError:
            msg = f"'{type(self)}' object has no attribute '{processed_key.short_key}'"
            raise AttributeError(msg)
        return etyrel

    def __setattr__(self, attr_name: str, attr_value: Any):
        if attr_name.startswith("_") or not self._is_initialized or attr_name in self.__dict__:
            # change of existing "real" attribute
            super().__setattr__(attr_name, attr_value)
            return
        try:
            processed_key = self.__process_attribute_name(attr_name, exception_type=aux.UndefinedRelationError)
        except aux.UndefinedRelationError:
            # attr_name could not be resolved to an defined relation
            super().__setattr__(attr_name, attr_value)
            return
        self.set_relation(ds.get_entity_by_uri(processed_key.uri), attr_value)

    def __process_attribute_name(self, attr_name: str, exception_type=AttributeError) -> "ProcessedStmtKey":
        pass
        active_mod_uri = get_active_mod_uri(strict=False)
        search_uri = _search_uri_stack[-1] if _search_uri_stack else None
        cache_key = (attr_name, active_mod_uri, search_uri)
        cached = _attr_name_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            processed_key = process_key_str(attr_name)
        except aux.ShortKeyNotFoundError as err:
            raise
        except (aux.InvalidGeneralKeyError, aux.InvalidShortKeyError, aux.UnknownURIError) as err:
            # this happens if a syntactically valid key string could not be resolved
            raise exception_type(*err.args)
        if not processed_key.etype == EType.RELATION:
            r3 = getattr(self, "R3", None)
            r4 = getattr(self, "R4", None)
            msg = (
                f"Unexpected attribute name: '{attr_name}' of entity {self}\n",
                f"Type hint: self.R3__is_subclass_of: {r3}\n",
                f"Type hint: self.R4__is_instance_of: {r4}\n",
            )
            raise exception_type(msg)
        _attr_name_cache[cache_key] = processed_key
        return processed_key

    def __eq__(self, other):
        return id(self) == id(other)

    def __post_init__(self):
        # for a solution how to automate this see
        # https://stackoverflow.com/questions/55183333/how-to-use-an-equivalent-to-post-init-method-with-normal-class
        assert self.uri is not None
        self._perform_inheritance()
        self._perform_instantiation()
        self._is_initialized = True

    def _perform_inheritance(self):
        """
        Transfer method prototypes from parent to child classes

        :return:
        """
        # this relates to R3__is_subclass_of defined in builtin_entities
        parent_class: Union[Entity, None]
        try:
            parent_class = self.R3
        except aux.ShortKeyNotFoundError:
            parent_class = None

        if parent_class not in (None, []):
            assert isinstance(parent_class, Item)
            # TODO: assert metaclass-property of `parent_class`
            self._method_prototypes.extend(parent_class._method_prototypes)

            # also propagate _method_prototypes down the line to potential children of self
            def set_method_prototypes_recursively(item: Item):
                for child in item.get_inv_relations("R3", return_subj=True):
                    child._method_prototypes.extend(parent_class._method_prototypes)
                    set_method_prototypes_recursively(child)

            set_method_prototypes_recursively(self)

    def _perform_instantiation(self):
        """
        Convert all method prototypes from class-item into methods of instance-item
        :return:
        """

        # this relates to R4__is_instance_of defined builtin_entities
        parent_class: Union[Entity, None]
        try:
            parent_class = self.R4
        except aux.ShortKeyNotFoundError:
            parent_class = None

        if parent_class not in (None, []):
            for func in parent_class._method_prototypes:
                self.add_method(func)

    def _get_relation_contents(self, rel_uri: str, lang_indicator=None):
        assert aux.ensure_valid_uri(rel_uri)

        statements: List[Statement] = ds.get_statements(self.uri, rel_uri)

        # for each of the relation edges get a list of the result-objects
        # (this assumes the relation tuple to be a triple (sub, rel, obj))
        res = [re.relation_tuple[2] for re in statements if re.role is RelationRole.SUBJECT]

        # the following logic decides whether to e.g. return a list of length 1 or the contained entity itself
        # this depends on whether self is a functional relation (->  R22__is_functional)

        # if rel_uri == "<bi>R22" -> relation is the R22-entity: we are asking whether self is functional;
        # this must be handled separately to avoid infinite recursion:
        # (note that R22 itself is also a functional relation: only one of {True, False} is meaningful, same holds for
        # R32["is functional for each language"]). R32 also must be handled separately

        relation: Relation = ds.relations[rel_uri]
        hardcoded_functional_relations = [
            aux.make_uri(settings.BUILTINS_URI, "R22"),
            aux.make_uri(settings.BUILTINS_URI, "R32"),
        ]

        hardcoded_functional_fnc4elang_relations = [aux.make_uri(settings.BUILTINS_URI, "R1")]

        # in the following or-expression the second operand is only evaluated if the first ist false
        # if rel_uri in ["...#R22", "...#R32"] or relation.R22:
        if rel_uri in hardcoded_functional_relations or relation.R22:
            if len(res) == 0:
                return None
            else:
                assert len(res) == 1
                return res[0]

        #  is a similar situation
        # if rel_key == "R32" this means that self 'is functional for each language'
        elif rel_uri in hardcoded_functional_fnc4elang_relations or relation.R32:
            if lang_indicator is not None and lang_indicator not in settings.SUPPORTED_LANGUAGES:
                msg = f"unsupported language ({lang_indicator}) while accessing {self}.{relation.short_key}."
                raise aux.MultilingualityError(msg)

            if lang_indicator is None:
                lang_indicator = settings.DEFAULT_DATA_LANGUAGE

            filtered_res_explicit_lang = []
            filtered_res_without_lang = []

            # TODO: simplify this since now we can be sure that we have only Literal-instances in res
            for elt in res:
                # if no language is defined (e.g. ordinary string) -> use interpret this as match
                # (but only if no other result with matching language attribute is available)
                lng = getattr(elt, "language", None)
                if lng is None:
                    filtered_res_without_lang.append(elt)
                elif lng == lang_indicator:
                    filtered_res_explicit_lang.append(elt)

            if filtered_res_explicit_lang:
                filtered_res = filtered_res_explicit_lang
            else:
                filtered_res = filtered_res_without_lang

            if len(filtered_res) == 0:
                return None
            elif len(filtered_res) == 1:
                return filtered_res[0]
            else:
                msg = (
                    f"unexpectedly found more then one object for relation {relation.short_key} "
                    f"and language {lang_indicator}."
                )

                raise aux.MultilingualityError(msg)

        else:
            return res

    @classmethod
    def add_method_to_class(cls, func):
        """
        Used to add methods to the class from the builtin_entities module.
        This mechanism (adding the method later) allows to keep the dependency monodirectional
        """
        setattr(cls, func.__name__, func)

    def add_method(self, func: callable, name: Optional[str] = None):
        """
        Add a method to this instance (self). If there are R4 relations pointing from child items to self,
        this method is also inherited to those child items.

        :param func:
        :param name:    the name under which the callable object should be accessed
        :return:
        """
        if name is None:
            name = getattr(func, "given_name", func.__name__)

        caller_frame = get_caller_frame(1)

        # TODO: the mod_uri should be taken from the frame where func is defined and not where add_method is called
        # currently this works because they are usually the same
        if mod_uri := caller_frame.f_locals.get("__URI__"):
            func = wrap_function_with_search_uri_context(func, mod_uri)

        # ensure that the func object has a `.given_name` attribute
        func.given_name = name

        self.__dict__[name] = types.MethodType(func, self)
        self._method_prototypes.append(func)

        # make sure that all already defined subclasses and instances also have this method
        for stm in self.get_inv_relations("R4"):
            stm.subject.add_method(func, name)
        for stm in self.get_inv_relations("R3"):
            stm.subject.add_method(func, name)

    def _set_relations_from_init_kwargs(self, **kwargs):
        """
        This method is called explicitly from the __init__-method of subclasses after preprocessing the kwargs

        :param kwargs:
        :return:
        """

        for key, value in kwargs.items():
            if isinstance(value, (tuple, list)):
                # this conveniently allows to add several relations at once during entity creation
                # this is unpacked to "scalar relations"
                for elt in value:
                    self.set_relation(key, elt)
            else:
                self.set_relation(key, value)

    def set_multiple_relations(
        self, relation: Union["Relation", str], obj_seq: Union[tuple, list], *args, **kwargs
    ) -> List["Statement"]:
        """
        Convenience function to create multiple Statements at once
        """
        res_list = []

        if not isinstance(obj_seq, (tuple, list)):
            raise TypeError(f"obj_seq must be tuple or list, got {type(obj_seq).__name__}")
        for obj in obj_seq:
            res_list.append(self.set_relation(relation, obj, *args, **kwargs))

        return res_list

    def set_relation(
        self,
        relation: Union["Relation", str],
        obj,
        scope: "Entity" = None,
        proxyitem: Optional["Item"] = None,
        qualifiers: Optional[List["RawQualifier"]] = None,
        prevent_duplicate=False,
    ) -> Optional["Statement"]:
        """
        Allows to add a relation after the item was created.

        :param relation:    Relation-Entity (or its short_key)
        :param obj:         target (object) of the relation (where self is the subject)
        :param scope:       Entity for the scope in which the relation is defined
        :param proxyitem:   optional item to which the Statement is associated (e.g. an equation-instance)
        :param qualifiers:  optional list of RawQualifiers (see docstring of this class)
        :param prevent_duplicate
                            bool; prevent the creation of a statement which already exists.
        :return:
        """

        if isinstance(relation, str):
            if aux.ensure_valid_uri(relation, strict=False):
                relation = ds.get_entity_by_uri(relation)
            else:
                # assume we got the short key of the relation
                relation = ds.get_entity_by_key_str(relation)

        if prevent_duplicate:
            existing_objects = self.get_relations(relation.uri, return_obj=True)
            if obj in existing_objects:
                return None

        if not isinstance(relation, Relation):
            msg = f"unexpected type: {type(relation)} of relation object {relation}, with {self} as subject"
            raise TypeError(msg)

        if isinstance(obj, (list, tuple)):
            msg = f"Sequences like ({type(obj)}) are not allowed in `.set_relation`. Use `.set_multiple_relations`."
            raise TypeError(msg)

        # handle R32__is_functional_for_each_language
        enforce_literal_as_type = relation.short_key in RELKEYS_WITH_LITERAL_RANGE or relation.R32

        if enforce_literal_as_type and not isinstance(obj, Literal):
            obj = Literal(obj, lang=settings.DEFAULT_DATA_LANGUAGE)

        if isinstance(obj, (Entity, *allowed_literal_types)) or obj in allowed_literal_types:
            return self._set_relation(relation.uri, obj, scope=scope, qualifiers=qualifiers, proxyitem=proxyitem)
        else:
            msg = f"Unsupported type ({type(obj)}) of {obj}, while setting relation {relation.short_key} of {self}"
            raise TypeError(msg)

    def _set_relation(
        self,
        rel_uri: str,
        rel_content: object,
        scope: Optional["Entity"] = None,
        qualifiers: Optional[list] = None,
        proxyitem: Optional["Item"] = None,
    ) -> "Statement":
        aux.ensure_valid_uri(rel_uri)
        rel = ds.relations[rel_uri]

        # store relation for later usage
        self.relation_dict[rel_uri] = rel

        # store this relation edge in the global store
        if isinstance(rel_content, Entity):
            corresponding_entity = rel_content
            corresponding_literal = None
        elif isinstance(rel_content, allowed_literal_types):
            corresponding_entity = None
            corresponding_literal = rel_content
        else:
            msg = f"unexpected type: {type(rel_content)} for object {rel_content}"
            raise TypeError(msg)

        if qualifiers is None:
            qualifiers = []

        if scope is not None:
            assert scope.R4__is_instance_of == ds.get_entity_by_uri(u("bi__I16__scope"))
            qff_has_defining_scope: QualifierFactory = ds.qff_dict["qff_has_defining_scope"]
            qualifiers.append(qff_has_defining_scope(scope))

        stm = Statement(
            relation=rel,
            relation_tuple=(self, rel, rel_content),
            role=RelationRole.SUBJECT,
            corresponding_entity=corresponding_entity,
            corresponding_literal=corresponding_literal,
            scope=scope,
            qualifiers=qualifiers,
            proxyitem=proxyitem,
        )

        ds.set_statement(stm)

        if scope is not None:
            ds.scope_statements[scope.uri].append(stm)

        # if the object is not a literal then also store the inverse relation
        if isinstance(rel_content, Entity):
            inv_stm = Statement(
                relation=rel,
                relation_tuple=(self, rel, rel_content),
                role=RelationRole.OBJECT,
                corresponding_entity=self,
                scope=scope,
                qualifiers=stm.qualifiers,
                proxyitem=proxyitem,
            )

            # interconnect the primal Statement with the inverse one:
            stm.dual_statement = inv_stm
            inv_stm.dual_statement = stm

            # ds.set_statement(rel_content.short_key, rel.short_key, inv_stm)
            tmp_list = ds.inv_statements[rel_content.uri][rel.uri]

            # TODO: maybe check length here for inverse functional
            tmp_list.append(inv_stm)
        return stm

    def get_relations(
        self, key_str_or_uri: Optional[str] = None, return_subj: bool = False, return_obj: bool = False
    ) -> Union[Dict[str, list], list]:
        """
        Return all Statement instance where this item is subject

        :param key_str_or_uri:      optional; either a verbose key_str (of a builtin entity) or a full uri;
                                    if passed only return the result for this key
        :param return_subj:         default False; if True only return the subject(s) of the relation edges,
                                    not the whole statement

        :return:            either the whole dict or just one value (of type list)
        """

        if key_str_or_uri is not None and not isinstance(key_str_or_uri, (str)):
            msg = f"unexpected type for key_str_or_uri: {type(key_str_or_uri)}. Expected a str or None."
            raise TypeError(msg)

        rel_dict = ds.statements[self.uri]
        return self._return_relations(rel_dict, key_str_or_uri, return_subj, return_obj)

    def get_inv_relations(
        self, key_str_or_uri: Optional[str] = None, return_subj: bool = False, return_obj: bool = False
    ) -> Union[Dict[str, list], list]:
        """
        Return all Statement instance where this item is object

        :param key_str_or_uri:      optional; either a verbose key_str (of a builtin entity) or a full uri;
                                    if passed only return the result for this key
        :param return_subj:         default False; if True only return the subject(s) of the relation edge(s),
                                    not the whole statement
        :param return_obj:          default False; if True only return the object(s) of the relation edge(s),
                                    not the whole statement

        :return:            either the whole dict or just one value (of type list)
        """

        inv_rel_dict = ds.inv_statements[self.uri]

        return self._return_relations(inv_rel_dict, key_str_or_uri, return_subj, return_obj)

    @staticmethod
    def _return_relations(
        base_dict,
        key_str_or_uri: str,
        return_subj: bool = False,
        return_obj: bool = False,
    ) -> Union[Dict[str, list], list]:
        """

        :param base_dict:           either ds.statements or ds.inv_statements
        :param key_str_or_uri:      optional; either a verbose key_str (of a builtin entity) or a full uri;
                                    if passed only return the result for this key
        :param return_subj:         default False; if True only return the subject(s) of the relation edge(s),
                                    not the whole statement
        :param return_obj:          default False; if True only return the object(s) of the relation edge(s),
                                    not the whole statement
        :return:
        """
        if key_str_or_uri is None:
            return base_dict

        # the caller wants only results for this key (e.g. "R4")
        if aux.ensure_valid_uri(key_str_or_uri, strict=False):
            uri = key_str_or_uri
        else:
            # we try to resolve a prefix and use the active module and finally builtins as fallback
            key_str = key_str_or_uri
            try:
                pr_key = process_key_str(key_str)
            except aux.ShortKeyNotFoundError:
                # during the construction of builtins we might ask for keys which do not exist
                return []
            uri = pr_key.uri

        stm_res: Union[Statement, List[Statement]] = base_dict.get(uri, [])
        if return_subj:
            # do not return the Statement instance(s) but only the subject(s)
            if isinstance(stm_res, list):
                stm_res: List[Statement]
                res = [re.subject for re in stm_res]
            else:
                assert isinstance(stm_res, Statement)
                res = stm_res.subject
        elif return_obj:
            # do not return the Statement instance(s) but only the object(s)
            if isinstance(stm_res, list):
                stm_res: List[Statement]
                res = [re.object for re in stm_res]
            else:
                assert isinstance(stm_res, Statement)
                res = stm_res.object

        else:
            # neither return_subj nor return_obj -> return full statements
            res = stm_res
        return res

    def overwrite_statement(self, rel_key_str_or_uri: str, new_obj: "Entity", qualifiers=None) -> "Statement":
        # the caller wants only results for this key (e.g. "R4")

        if not isinstance(rel_key_str_or_uri, str):
            raise TypeError(f"rel_key_str_or_uri must be str, got {type(rel_key_str_or_uri).__name__}")

        if aux.ensure_valid_uri(rel_key_str_or_uri, strict=False):
            rel_uri = rel_key_str_or_uri
        else:
            # we try to resolve a prefix and use the active module and finally builtins as fallback
            key_str = rel_key_str_or_uri
            pr_key = process_key_str(key_str)
            rel_uri = pr_key.uri

        rel = ds.get_entity_by_uri(rel_uri)

        stm = self.get_relations(rel_uri)

        if isinstance(stm, list):
            if len(stm) == 0:
                msg = f"Unexpectedly found empty statement list for entity {self} and relation {rel}"
                raise aux.GeneralPyIRKError(msg)
            if len(stm) > 1:
                msg = f"Unexpectedly found length-{len(stm)} statement list for entity {self} and relation {rel}"
                raise aux.GeneralPyIRKError(msg)
            stm = stm[0]

        assert isinstance(stm, Statement)

        if stm.qualifiers:
            raise NotImplementedError("Processing old qualifiers is not yet implemented while overwriting statements")

        stm.unlink()
        return self.set_relation(rel, new_obj, qualifiers=qualifiers)

    def finalize(self):
        """
        Method which is intended to be explicitly called if an (automatically created) entity is finished.

        Background: some entities like evaluated mappings are manipulated after creation.
        Hooks like consistency-checking have to be executed afterwards.
        """

        run_hooks(self, phase="post-finalize")

    def __hash__(self):
        """
        Defining a hash method allows to use Entities as keys in dicts, or create sets of them.
        """

        return hash(self.uri)

    def update_relations(self, **kwargs):
        if not (self.updated == False):
            raise AssertionError("This function can be called only once for each object, this is the second time.")

        item_key = self.short_key

        new_kwargs, lang_related_kwargs = process_kwargs_for_entity_creation(item_key, kwargs)

        for dict_key, value in new_kwargs.items():
            if type(value) == list:
                self.set_multiple_relations(dict_key, value)
            else:
                self.set_relation(dict_key, value)

        process_lang_related_kwargs_for_entity_creation(self, item_key, lang_related_kwargs)

        # update inheritance and instantiation
        self.__post_init__()

        self.updated = True


def wrap_function_with_search_uri_context(func, uri=None):
    if uri is None:
        # assume that this function is used as decorator in a module which defines __URI__ globally
        import inspect

        frame = inspect.currentframe()
        uri = frame.f_back.f_globals.get("__URI__")
        if uri is None:
            fi = inspect.getframeinfo(frame.f_back)
            msg = f"could not find `__URI__` in module {fi.filename}"
            raise aux.GeneralPyIRKError(msg)

    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        with search_uri_context(uri=uri):
            return func(*args, **kwargs)

    return wrapped_func


# NOTE: PrefixShortCut moved to _core/prefix_shortcut.py

pf = PrefixShortCut()


# NOTE: DataStore moved to _core/datastore.py

ds = DataStore()

YAML_VALUE = Union[str, list, dict]


def get_label_to_item_dict(known_duplicates: list = None):
    """
    Returns a map from labels to items.
    If a label occurs multiple times the last occurrence is decisive.
    If this is not declared as expected via `known_duplicates` a warning is generated.

    :param known_duplicates:    sequence of labels which are known to occur multiple times
    """

    if known_duplicates is None:
        known_duplicates = []

    d = {}
    for uri, item in ds.items.items():
        if "a" in item.short_key:
            continue
        label = item.R1.value
        if label in d.keys() and label not in known_duplicates:
            msg = f"items with same label ('{label}'): {item.uri}, {d[label].uri}"
            if settings.STRICT:
                raise Warning(msg)
            else:
                print(aux.byellow(f"Warning: {msg}"))
        d[label] = item
    return d


def get_label_to_relation_dict(known_duplicates: list = None):
    """
    Returns a map from labels to relations.
    If a label occurs multiple times the last occurrence is decisive.
    If this is not declared as expected via `known_duplicates` a warning is generated.

    :param known_duplicates:    sequence of labels which are known to occur multiple times
    """

    if known_duplicates is None:
        known_duplicates = []

    d = {}
    for uri, rel in ds.relations.items():
        if "a" in rel.short_key:
            continue
        label = rel.R1.value
        if label in d.keys() and label not in known_duplicates:
            msg = f"items with same label ('{label}'): {rel.uri}, {d[label].uri}"
            if settings.STRICT:
                raise Warning(msg)
            else:
                print(aux.byellow(f"Warning: {msg}"))
        d[label] = rel
    return d


# NOTE: EType moved to _core/keymanager.py
# NOTE: SType moved to _core/keymanager.py
# NOTE: VType moved to _core/keymanager.py
# NOTE: ProcessedStmtKey moved to _core/keymanager.py
# NOTE: unpack_l1d moved to _core/keymanager.py


# define regular expressions outside of the function (they have to be compiled only once)
# use https://pythex.org/ with fixture e. g `some_prefix__S000['test label']` to understand these
re_prefix_shortkey_suffix = re.compile(r"^((.+?)__)?((Ia?)|(Ra?)|(S))(\d+)(.*)$")
re_suffix_underscore = re.compile(r"^__([\w\-]+)$")  # \w means alphanumeric (including `_`);
re_suffix_square_brackets = re.compile(r"""^\[["'](.+)["']\]""")


# NOTE: process_key_str moved to _core/keymanager.py


# NOTE: _resolve_prefix moved to _core/keymanager.py


# regex pattern which represents a language indicator
langcode_end_pattern = re.compile("__[a-z]{2}$")


# NOTE: check_processed_key_label moved to _core/keymanager.py


# NOTE: ilk2nlk moved to _core/keymanager.py


# NOTE: u moved to _core/keymanager.py


# noinspection PyShadowingNames
class Item(Entity):
    def __init__(self, base_uri: str, key_str: str, **kwargs):
        super().__init__(base_uri=base_uri)

        res = process_key_str(key_str, check=False, resolve_prefix=False)
        msg = f"invalid entity type deduced from key string: {key_str}: expected {EType.ITEM} but got {res.etype}."
        if res.etype != EType.ITEM:
            raise AssertionError(msg)

        self.short_key = res.short_key
        self.uri = aux.make_uri(self.base_uri, self.short_key)

        if self.uri in ds.items:
            raise AssertionError(f"{self.uri} is already occupied. Cannot create new item.")

        self._set_relations_from_init_kwargs(**kwargs)

        self.__post_init__()

    def __repr__(self):
        if not self._unlinked:
            try:
                r1 = getattr(self, "R1", "no label")
            except ValueError:
                r1 = "<<ValueError while retrieving R1>>"
        else:
            r1 = getattr(self, "_label_after_unlink", "no label")
        return f'<Item {self.short_key}["{r1}"]>'


# NOTE: get_active_mod_uri moved to _core/context.py


def process_kwargs_for_entity_creation(entity_key: str, kwargs: dict) -> tuple[dict, dict]:
    """
    :return:    return new_kwargs, lang_related_kwargs
    """
    return KWArgManager(entity_key, kwargs).process()


class KWArgManager:
    """
    This class processes all keyword args for entity creation
    """

    def __init__(self, entity_key: str, kwargs: dict):
        self.entity_key: str = entity_key
        self.kwargs: dict = kwargs
        self.mod_uri = get_active_mod_uri()
        self.new_kwargs = {}
        self.lang_related_kwargs = defaultdict(list)

    def process(self):
        for kwarg_name, kwarg_value in self.kwargs.items():
            skwap = SingleKWArgProcessor(kwam=self, kwarg_name=kwarg_name, kwarg_value=kwarg_value)
            skwap.handle_kwarg_stage1()

            try:
                skwap.handle_kwarg_stage2()
            except aux.ContinueOuterLoop:
                # in cases where we already have assigned a value but we get another one
                # for a different language (which would have the same `new_key`-attribute)
                # we omit it for the `self.new_kwargs[skwap.new_key]` mechanism

                # it will be contained in `self.lang_related_kwargs` and handled later
                assert skwap.new_value is None
                continue

            # for non-functional (R32) relations there might be several kwargs like R77 and R77__de
            # which result in the same `skwap.new_key` -> in this case we create a list

            existing_value = self.new_kwargs.get(skwap.new_key)
            if existing_value is None:
                self.new_kwargs[skwap.new_key] = skwap.new_value
            else:
                if not isinstance(existing_value, list):
                    existing_value = [existing_value]
                if not isinstance(skwap.new_value, list):
                    skwap.new_value = [skwap.new_value]
                self.new_kwargs[skwap.new_key] = [*existing_value, *skwap.new_value]

        return self.new_kwargs, self.lang_related_kwargs


class SingleKWArgProcessor:
    """
    This class processes a single keyword arg for entity creation
    """

    def __init__(self, kwam: KWArgManager, kwarg_name: str, kwarg_value: str):
        self.kwam = kwam
        self.kwarg_name: str = kwarg_name
        self.kwarg_value: str = kwarg_value
        self.processed_rel_key = process_key_str(self.kwarg_name)
        self.new_key: str = None
        self.new_value = None
        self.rel_is_functional = None  # (R22)
        self.rel_is_functional_fel = None  # ... for each language (R32)

    def handle_kwarg_stage1(self):
        """
        Determine new_key
        """
        if self.processed_rel_key.etype != EType.RELATION:
            msg = f"unexpected key: {self.kwarg_name} during creation of item {self.entity_key}."
            raise ValueError(msg)

        if self.processed_rel_key.prefix:
            self.new_key = f"{self.processed_rel_key.prefix}__{self.processed_rel_key.short_key}"
        else:
            self.new_key = self.processed_rel_key.short_key

    def handle_kwarg_stage2(self):

        rel_obj = ds.get_entity_by_uri(self.processed_rel_key.uri)

        try:
            self.rel_is_functional = rel_obj.R22__is_functional != None
        except aux.ShortKeyNotFoundError:
            # this happens at the beginning if R22/R32 is not yet defined
            self.rel_is_functional = False

        try:
            self.rel_is_functional_fel = rel_obj.R32__is_functional_for_each_language != None
        except aux.ShortKeyNotFoundError:
            # this happens at the beginning if R22/R32 is not yet defined
            self.rel_is_functional_fel = False

        # handle those relations which might come with multiple languages
        if self.new_key in RELKEYS_WITH_LITERAL_RANGE:
            self.new_value = self.dispatch_value_multiplicity_for_rk_with_lr()
        else:
            self.new_value = self.kwarg_value

    def dispatch_value_multiplicity_for_rk_with_lr(self):
        """
        Situation for relkeys with literal range:
        self.kwarg_value might be a 'scalar' value or list of 'scalar' values.
        This method handles the difference and then calls the actual processing
        """

        if isinstance(self.kwarg_value, list):

            if self.rel_is_functional:
                msg = f"List argument for functional relation {self.kwarg_name} is not allowed."
                raise aux.GeneralPyIRKError(msg)
            if self.rel_is_functional_fel:
                msg = f"List argument for lang-functional (R32) relation {self.kwarg_name} is not allowed."
                raise aux.GeneralPyIRKError(msg)

            self.new_value = []
            for scalar_kwarg_value in self.kwarg_value:
                new_scalar_value = self.handle_rk_with_lr(scalar_kwarg_value=scalar_kwarg_value)

                self.new_value.append(new_scalar_value)
            return self.new_value
        else:
            return self.handle_rk_with_lr(scalar_kwarg_value=self.kwarg_value)

    def handle_rk_with_lr(self, scalar_kwarg_value):
        """
        'rk' means relkeys
        'lr' means literal range

        Background:
        Relation keys like R1, R2 and R77 are used in triples where the object is a Literal.
        R1__has_label, R2__has_description are functional (R32__is_functional_for_each_language).
        R77__has_alternative_label is not functional (neither R22__is_functional nor R32).

        This function handles the different cases
        """
        if self.rel_is_functional_fel:
            new_kwarg_value = self._handle_kwarg_for_functional_rel(scalar_kwarg_value)
        else:
            # handle the non-functional case here:
            self._check_for_valid_language(scalar_kwarg_value)
            new_kwarg_value = self._handle_value(scalar_kwarg_value)
        return new_kwarg_value

    def _handle_kwarg_for_functional_rel(self, scalar_kwarg_value):

        lang_related_value_list = self.kwam.lang_related_kwargs[self.new_key]
        # lang_related_value_list is supposed to be a list of 2-tuples: (lang_indicator, Literal-inst.)
        # this list might be updated here as a side effect. It does not need to be returned

        if len(lang_related_value_list) == 0:
            # this is the first value for this kwarg. Maybe more will come later for other languages.
            # They will be handled in the else branch
            self._check_for_valid_language(scalar_kwarg_value, first_value=True)
            new_kwarg_value = self._handle_value(scalar_kwarg_value, lang_related_value_list)
        else:
            lang_related_value_list.append((self.processed_rel_key.lang_indicator, scalar_kwarg_value))
            # do not process the current key-value-pair to the Item-constructor
            # it will be handled later
            self.new_value = None
            raise aux.ContinueOuterLoop()

        return new_kwarg_value

    def _check_for_valid_language(self, scalar_kwarg_value, first_value=False):
        valid_languages = (None, settings.DEFAULT_DATA_LANGUAGE)

        # note: this is to handle thins like `R1__has_label__de="deutsches label" @ p.de`
        if first_value and self.processed_rel_key.lang_indicator not in valid_languages:
            msg = (
                f"while creating {self.kwam.entity_key}: the first {self.new_key}-argument must be "
                " with lang_indicator `None` or explicitly using the default language. "
                f"Got {self.processed_rel_key.lang_indicator} instead."
            )
            raise aux.MultilingualityError(msg)
        value_lang = getattr(scalar_kwarg_value, "language", None)
        if value_lang not in valid_languages:
            msg = (
                f"while creating {self.kwam.entity_key}: the first {self.new_key}-argument must be "
                f"a flat string or a literal with the default language "
                f"({settings.DEFAULT_DATA_LANGUAGE}). Got {value_lang} instead."
            )
            raise aux.MultilingualityError(msg)

    def _handle_value(self, kwarg_value, lang_related_value_list=None) -> Literal:
        if not isinstance(kwarg_value, Literal):
            if not isinstance(kwarg_value, str):
                item_uri = aux.make_uri(self.kwam.mod_uri, self.kwam.entity_key)
                msg = (
                    f"While creating {item_uri}: the {self.new_key}-argument must be a string. "
                    f"Got {type(kwarg_value)} instead."
                )
                raise TypeError(msg)
            lang = self.processed_rel_key.lang_indicator
            if lang is None:
                lang = settings.DEFAULT_DATA_LANGUAGE
            new_kwarg_value = Literal(kwarg_value, lang=lang)
        else:
            # we already have a literal object
            new_kwarg_value = kwarg_value
        if lang_related_value_list is not None:
            # this is important for the functional_for_each_language case
            assert self.rel_is_functional_fel
            assert isinstance(lang_related_value_list, list)
            lang_related_value_list.append((self.processed_rel_key.lang_indicator, new_kwarg_value))
        return new_kwarg_value


def process_lang_related_kwargs_for_entity_creation(entity: Entity, short_key: str, lang_related_kwargs: dict) -> None:
    """
    This function processes language related keyword args for relations which have
    R32__is_functional_for_each_language=True
    """
    for rel_key, value_list in lang_related_kwargs.items():
        # omit the first argument as it was already passed to the Item-constructor
        for lang_indicator, value in value_list[1:]:
            if isinstance(value, Literal):
                if value.language != lang_indicator:
                    msg = (
                        f"while creating {short_key} ({rel_key}-argument) got inconsistent language indicators: "
                        f"in argument_name: {lang_indicator} but in value (Literal-instance) {value.language}"
                    )
                    raise aux.MultilingualityError(msg)
            elif isinstance(value, str):
                value = Literal(value, lang=lang_indicator)
            else:
                msg = f"unexpected type ({type(value)}) while creating {short_key} ({rel_key}-argument)"
                raise TypeError(msg)

            entity.set_relation(rel_key, value)


def create_item(key_str: str = "", **kwargs) -> Item:
    """

    :param key_str:     "" or unique key of this item (something like `I1234`)
    :param kwargs:      further relations

    :return:        newly created item
    """

    if key_str == "":
        item_key = get_key_str_by_inspection()
    else:
        item_key = key_str

    mod_uri = get_active_mod_uri()

    new_kwargs, lang_related_kwargs = process_kwargs_for_entity_creation(item_key, kwargs)

    itm = Item(base_uri=mod_uri, key_str=item_key, **new_kwargs)
    assert itm.uri not in ds.items, f"Problematic (duplicated) uri: {itm.uri}"
    ds.items[itm.uri] = itm

    # access the defaultdict(list)
    ds.entities_created_in_mod[mod_uri].append(itm.uri)

    process_lang_related_kwargs_for_entity_creation(itm, item_key, lang_related_kwargs)

    run_hooks(itm, phase="post-create")

    return itm


# noinspection PyShadowingNames
class Relation(Entity):
    def __init__(self, base_uri: str, short_key: str, **kwargs):
        super().__init__(base_uri=base_uri)

        self.short_key = short_key
        self.uri = aux.make_uri(self.base_uri, self.short_key)

        # set label
        self._set_relations_from_init_kwargs(**kwargs)

        self.__post_init__()

    def __repr__(self):
        if not self._unlinked:
            r1 = getattr(self, "R1", "no label")
        else:
            r1 = getattr(self, "_label_after_unlink", "no label")
        return f'<Relation {self.short_key}["{r1}"]>'


@unique
class RelationRole(Enum):
    """
    Statement types.
    """

    SUBJECT = 0
    PREDICATE = 1
    OBJECT = 2


VALID_HOOK_PHASES = ["post-create", "post-finalize"]
VALID_HOOK_TYPES = [
    "post-create-entity",
    "post-create-item",
    "post-create-relation",
    "post-finalize-entity",
    "post-finalize-item",
    "post-finalize-relation",
]


def run_hooks(entity: Entity, phase: str) -> None:
    """
    Run (previously registered) hooks after the creation of entities.
    This can be used for sanity checking etc.
    """

    assert phase in VALID_HOOK_PHASES

    for hook_func in ds.hooks[f"{phase}-entity"]:
        hook_func(entity)

    if isinstance(entity, Item):
        for hook_func in ds.hooks[f"{phase}-item"]:
            hook_func(entity)

    if isinstance(entity, Relation):
        for hook_func in ds.hooks[f"{phase}-relation"]:
            hook_func(entity)


def register_hook(type_str: str, func: callable) -> None:
    if not type_str in VALID_HOOK_TYPES:
        raise AssertionError()
    if not callable(func):
        raise AssertionError()

    ds.hooks[type_str].append(func)


# for now we want unique numbers for keys for relations and items etc (although this is not necessary)
# NOTE: KeyManager moved to _core/keymanager.py


# NOTE: pop_uri_based_key moved to _core/keymanager.py


def repl_spc_by_udsc(txt: str) -> str:
    return txt.replace(" ", "_")


class RawQualifier:
    """
    Precursor to a real Qualifier (which is a Statement) where the subject is yet unspecified
    (will be the qualified Statement). Instances of this class are produced by QualifierFactory
    """

    def __init__(self, rel: Relation, obj: Union[Literal, Entity]):
        self.rel = rel
        self.obj = obj

    def __repr__(self):
        if isinstance(self.obj, Entity):
            obj_label = f"{self.obj.short_key}__{repl_spc_by_udsc(self.obj.R1)}"
        else:
            obj_label = str(self.obj)
        return f"<RawQualifier (...) ({self.rel.short_key}__{repl_spc_by_udsc(self.rel.R1)}) ({obj_label})>"


class QualifierFactory:
    """
    Convenience class to create an RawQualifier.
    This allows syntax like:

    ```
    start_date = QualifierFactory(R1234["start date"])
    # ...
    I2746["Rudolf Kalman"].set_relation(R1833["has employer"], I7301["ETH Zürich"], qualifiers=[start_date(1973)])
    ```
    """

    # TODO: rename this class

    def __init__(self, relation: Relation, registry_name: Optional[str] = None):
        """

        :param relation:
        :param registry_name:   optional str; if not None this is the key under which this QF is stored in ds.qff_dict.
        """
        if not isinstance(relation, Relation):
            raise AssertionError()
        self.relation = relation

        # TODO: maybe this 'registry name should be uri-based?'
        if registry_name is not None:
            if not (isinstance(registry_name, str) and registry_name not in ds.qff_dict):
                raise AssertionError()
            ds.qff_dict[registry_name] = self

    def __call__(self, obj):
        return RawQualifier(self.relation, obj)


class Statement:
    # Note: in earlier versions this class was called "RelationEdge";
    # some old comments might refer to this
    """
    Models a concrete (instantiated/applied) relation between entities. This is basically a dict.
    """

    def __init__(
        self,
        relation: Relation = None,
        relation_tuple: tuple = None,
        role: RelationRole = None,
        corresponding_entity: Entity = None,
        corresponding_literal=None,
        scope=None,
        qualifiers: Optional[Union[List[RawQualifier], List["QualifierStatement"]]] = None,
        proxyitem: Optional[Item] = None,
    ) -> None:
        """

        :param relation:
        :param relation_tuple:
        :param role:                    RelationRole.SUBJECT for normal and RelationRole.OBJECT for inverse statements
        :param corresponding_entity:    This is the entity on the "other side" of the relation (depending of `role`) or
                                        None in case that other side is a literal
        :param corresponding_literal:   This is the literal on the "other side" of the relation (depending of `role`) or
        :param scope:                   None in case that other side is an Entity
        :param qualifiers:              list of relation edges, that describe `self` more precisely
                                        (cf. wikidata qualifiers)
        :param proxyitem:               associated item; e.g. a equation-item
        """

        # S means "statement" (successor of earlier RE for "relation edge")
        self.short_key = f"S{pop_uri_based_key()}"
        mod_uri = get_active_mod_uri()
        self.base_uri = mod_uri
        self.uri = f"{aux.make_uri(self.base_uri, self.short_key)}"
        self.relation = relation
        self.rsk = relation.short_key  # to conveniently access this attribute in visualization
        self.relation_tuple = relation_tuple
        self.subject = relation_tuple[0]
        self.predicate = relation_tuple[1]
        self.object = relation_tuple[2]
        self.role = role
        self.scope = scope
        self.corresponding_entity = corresponding_entity
        self.corresponding_literal = corresponding_literal
        self.dual_statement = None
        self.unlinked = None
        self.qualifiers = []
        self._process_qualifiers(qualifiers)

        ds.stms_created_in_mod[mod_uri][self.uri] = self

        assert self.uri not in ds.statement_uri_map
        ds.statement_uri_map[self.uri] = self

        # TODO: replace this by qualifier
        self.proxyitem = proxyitem

    @property
    def key_str(self):
        # TODO: the "attribute" `.key_str` for Statement is deprecated; use `.short_key` instead
        return self.short_key

    def __repr__(self):
        res = f"{self.short_key}{self.relation_tuple}"
        return res

    def _process_qualifiers(
        self, qlist: Union[List[RawQualifier], List["QualifierStatement"]], scope: Optional["Entity"] = None
    ) -> None:
        if not qlist:
            # nothing to do
            return

        if isinstance(qlist[0], QualifierStatement):
            # this is the case when an inverse statement is created
            self.qualifiers = [*qlist]
            return

        for qf in qlist:
            if isinstance(qf.obj, Entity):
                corresponding_entity = qf.obj
                corresponding_literal = None
            else:
                corresponding_entity = None
                corresponding_literal = repr(qf.obj)

            qf_stm = QualifierStatement(
                relation=qf.rel,
                relation_tuple=(self, qf.rel, qf.obj),
                role=RelationRole.SUBJECT,
                corresponding_entity=corresponding_entity,
                corresponding_literal=corresponding_literal,
                scope=scope,
                qualifiers=None,
                proxyitem=None,
            )
            self.qualifiers.append(qf_stm)

            # save the qualifier statement in the appropriate data structures
            ds.set_statement(stm=qf_stm)

            if isinstance(qf.obj, Entity):
                ds.inv_statements[qf.obj.uri][qf.rel.uri].append(qf_stm)

    def is_qualifier(self):
        # TODO: replace this by isinstance(stm, QualifierStatement)
        return isinstance(self.subject, Statement)

    def get_first_qualifier_obj_with_rel(self, key=None, uri=None, tolerate_key_error=False):
        if [key, uri].count(None) != 1:
            raise ValueError("exactly one of the arguments must be provided, not 0 not 2")

        if key:
            try:
                uri = process_key_str(key, check=False).uri
            except aux.ShortKeyNotFoundError:
                if tolerate_key_error:
                    # this allows to ask for qualifiers before they are created
                    return None
                else:
                    raise

        for qstm in self.qualifiers:
            if qstm.predicate.uri == uri:
                return qstm.object

        return None

    def unlink(self, *args) -> None:
        """
        Remove this Statement instance from all data structures in the global data storage
        :return:
        """

        if not len(self.relation_tuple) == 3:
            raise NotImplementedError

        if self.unlinked:
            return

        subj, pred, obj = self.relation_tuple

        if isinstance(self, QualifierStatement):
            ds.statements.pop(subj.uri, None)

            assert isinstance(subj, Statement)

            # seems like during unloading of modules the qualifiers might already have been removed
            # -> do nothing
            try:
                subj.qualifiers.remove(self)
            except ValueError:
                pass
            try:
                subj.dual_statement.qualifiers.remove(self)
            except (ValueError, AttributeError):
                # AttributeError means that dual_statement was None
                pass

        if self.role == RelationRole.SUBJECT:
            subj_rel_edges: Dict[str : List[Statement]] = ds.statements[subj.uri]
            tolerant_removal(subj_rel_edges.get(pred.uri, []), self)

            # ds.relation_statements: for every relation key stores a list of relevant relation-edges
            # (check before accessing the *defaultdict* to avoid to create a key just by looking)
            if pred.uri in ds.relation_statements:
                tolerant_removal(ds.relation_statements.get(pred.uri, []), self)

        elif self.role == RelationRole.OBJECT:
            assert isinstance(obj, Entity)
            obj_rel_edges: Dict[str : List[Statement]] = ds.inv_statements[obj.uri]
            # (check before accessing, see above)
            if pred.uri in obj_rel_edges:
                tolerant_removal(obj_rel_edges[pred.uri], self)
        else:
            msg = f"Unexpected .role attribute: {self.role}"
            raise ValueError(msg)

        # this prevents from infinite recursion
        self.unlinked = True
        if self.dual_statement is not None:
            self.dual_statement.unlink()

        for qf in self.qualifiers:
            qf: Statement
            qf.unlink()

        ds.statement_uri_map.pop(self.uri)


class QualifierStatement(Statement):
    def __init__(self, *args, **kwargs):
        # self.dual_qualifier = None
        super().__init__(*args, **kwargs)
        self.short_key = f"Q{self.short_key}"


def tolerant_removal(sequence, element):
    """
    call sequence.remove(element) but tolerate KeyError and ValueError
    :param sequence:
    :param element:
    :return:
    """

    try:
        sequence.remove(element)
    except (KeyError, ValueError):
        pass


def create_relation(key_str: str = "", **kwargs) -> Relation:
    """

    :param key_str:     "" or unique key of this relation (something like `R1234`); if empty key will be retrieved
                        via inspection of the caller code

    :param kwargs:      further relations (e.g. R1__has_label etc.)

    :return:        newly created relation
    """

    if key_str == "":
        rel_key = get_key_str_by_inspection()
    else:
        rel_key = key_str

    if not rel_key.startswith("R"):
        raise AssertionError

    mod_uri = get_active_mod_uri()

    # TODO: obsolete?
    default_relations = {
        # "R22": None,  # R22__is_functional
    }

    new_kwargs, lang_related_kwargs = process_kwargs_for_entity_creation(rel_key, kwargs)
    if "R4" not in new_kwargs.keys() and "irk:/builtins#R4" in ds.relations.keys():
        try:
            new_kwargs["R4"] = ds.items["irk:/builtins#I40"]
        except KeyError:
            pass

    rel = Relation(mod_uri, rel_key, **new_kwargs)
    if rel.uri in ds.relations:
        msg = f"URI '{rel.uri}' has already been used."
        raise aux.InvalidURIError(msg)
    ds.relations[rel.uri] = rel
    ds.entities_created_in_mod[mod_uri].append(rel.uri)

    process_lang_related_kwargs_for_entity_creation(rel, rel_key, lang_related_kwargs)

    run_hooks(rel, phase="post-create")

    _attr_name_cache.clear()
    return rel


def create_builtin_item(*args, **kwargs) -> Item:
    with uri_context(uri=settings.BUILTINS_URI):
        itm = create_item(*args, **kwargs)
    return itm


def create_builtin_relation(*args, **kwargs) -> Relation:
    with uri_context(uri=settings.BUILTINS_URI):
        rel = create_relation(*args, **kwargs)
    return rel


# NOTE: generate_new_key moved to _core/keymanager.py


# NOTE: print_new_keys moved to _core/keymanager.py


# NOTE: get_caller_frame moved to _core/context.py
# NOTE: get_key_str_by_inspection moved to _core/context.py
# NOTE: get_mod_name_by_inspection moved to _core/context.py
# NOTE: get_mod_id_list_by_inspection moved to _core/context.py
# NOTE: Context moved to _core/context.py


_uri_stack = []
_search_uri_stack = []

# Cache for __process_attribute_name. Key: (attr_name, active_mod_uri, search_uri).
# Only successful RELATION resolutions are stored. Cleared in create_relation to stay
# correct when a new relation is registered that could shadow a previously resolved URI.
_attr_name_cache: dict = {}


# NOTE: abstract_uri_context moved to _core/context.py
# NOTE: uri_context moved to _core/context.py
# NOTE: search_uri_context moved to _core/context.py


# NOTE: unload_mod moved to _core/mod_management.py
# NOTE: _unlink_entity moved to _core/mod_management.py


# NOTE: replace_and_unlink_entity moved to _core/entity_ops.py


# NOTE: register_mod moved to _core/context.py
# NOTE: start_mod moved to _core/context.py
# NOTE: end_mod moved to _core/context.py


# NOTE: get_language_of_str_literal moved to _core/serialization.py
# NOTE: LanguageCode moved to _core/serialization.py (instances below stay in the facade)


df = LanguageCode(settings.DEFAULT_DATA_LANGUAGE)
en = LanguageCode("en")
de = LanguageCode("de")
fr = LanguageCode("fr")
it = LanguageCode("it")
es = LanguageCode("es")


# NOTE: RuleResult moved to _core/queries.py
# NOTE: is_true moved to _core/queries.py


# NOTE: format_entity_html moved to _core/html_format.py


# NOTE: format_literal_html moved to _core/serialization.py


# NOTE: script_main moved to _core/serialization.py


# NOTE: is_subclass moved to _core/queries.py
# NOTE: is_instance moved to _core/queries.py
# NOTE: is_subproperty moved to _core/queries.py


# NOTE: export_entities moved to _core/serialization.py
