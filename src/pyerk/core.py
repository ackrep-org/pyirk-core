"""
Core module of pyerk
"""
import os
import sys
from collections import defaultdict
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
from typing import Dict, Union, List, Iterable, Optional
from rdflib import Literal
import pydantic
import re

from pyerk import auxiliary as aux
from pyerk import settings
from pyerk.auxiliary import (
    InvalidURIError,
    InvalidPrefixError,
    PyERKError,
    EmptyURIStackError,
    InvalidShortKeyError,
    UnknownPrefixError,
)

from ipydex import IPS, activate_ips_on_exception, set_trace

if os.environ.get("IPYDEX_AIOE") == "true":
    activate_ips_on_exception()


"""
    TODO:

    report should link entities to django

    model sets as type? and elements as instances?
    manually trigger reload in gui

    Caylay-Hamilton-Theorem
    qualifier relations, e.g. for universal quantification

    Lyapunov stability theorem
    visualizing the results
    has implementation (application to actual instances)


    multiple assignments via list
    natural language representation of ordered atomic statements
    Labels (als Listeneinträge)
    DOMAIN und RANGE

    unittests ✓
    Sanity-check: `R1__part_of` muss einen Fehler werfen

    content: dynamical_system can_be_represented_by mathematical_model
    → Herausforderung: in OWL sind relationen nur zwischen Instanzen zulässig.
    Damit ist die Angabe von DOMAIN und RANGE, relativ klar. Wenn die Grenze zwischen Klasse und Instanz verschwimmt
    ist das nicht mehr so klar: Jede Instanz der Klasse <dynamical_system> ???

    anders: <can_be_represented_by> ist eine n:m Zuordnung von Instanzen der Klasse
    <dynamical_system> zu Instanzen der Klasse <mathematical_model>

    komplexere Aussagen:
    alle steuerbaren linearen ODE-systeme sind flach

"""

allowed_literal_types = (str, bool, float, int, complex)


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

        class Config:
            # necessary because https://github.com/samuelcolvin/pydantic/issues/182
            # otherwise check_type raises() an error for types as Dict[str, owl2.Thing]
            arbitrary_types_allowed = True
            smart_union=True  # seems to be necessary to respect the ordering of types inside a unioin

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
        msg = (
            f"While type-checking: Unexpected inner structure of parsed model. Expected: {expected_type}"
        )
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
        self.relation_dict = {}
        self._method_prototypes = []
        self._namespaces = {}
        self.base_uri = base_uri
        self.uri = None  # will be set in __post_init__

        # simplifies debugging, will be set by _unlink_entity()
        self._label_after_unlink = None
        self._unlinked = False

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

    def idoc(self, adhoc_label: str):
        """
        idoc means "inline doc". This function allows to attach a label to entities when using them in code
        because it returns just the Entity-object itself. Thus one can use the following expressions interchageably:
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
            all_labels_dict = dict((str(label), None) for label in all_labels)
            adhoc_label_str = str(adhoc_label)

            if adhoc_label_str not in all_labels_dict:
                msg = (
                    f"Mismatiching label for Entity {self.short_key}!\nGot '{adhoc_label}' but valid labels are: "
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
        try:
            res = process_key_str(attr_name)
        except (KeyError, aux.UnknownURIError) as err:
            # this happens if a syntactically valid key string could not be resolved
            raise AttributeError(*err.args)
        if not res.etype == EType.RELATION:
            r3 = getattr(self, "R3", None)
            r4 = getattr(self, "R4", None)
            msg = (
                f"Unexpected attribute name: '{attr_name}' of entity {self}\n",
                f"Type hint: self.R3__is_subclass_of: {r3}\n",
                f"Type hint: self.R4__is_instance_of: {r4}\n",
            )
            raise AttributeError(msg)

        try:
            # TODO: introduce prefixes here, which are mapped to uris
            etyrel = self._get_relation_contents(rel_uri=res.uri)
        except KeyError:
            msg = f"'{type(self)}' object has no attribute '{res.short_key}'"
            raise AttributeError(msg)
        return etyrel

    def __eq__(self, other):
        return id(self) == id(other)

    def __post_init__(self):
        # for a solution how to automate this see
        # https://stackoverflow.com/questions/55183333/how-to-use-an-equivalent-to-post-init-method-with-normal-class
        assert self.uri is not None
        self._perform_inheritance()
        self._perform_instantiation()

    def _perform_inheritance(self):
        """
        Transfer method prototypes from parent to child classes

        :return:
        """
        # this relates to R3__is_subclass_of defined in builtin_entities
        parent_class: Union[Entity, None]
        try:
            parent_class = self.R3
        except AttributeError:
            parent_class = None

        if parent_class not in (None, []):
            assert isinstance(parent_class, Item)
            # TODO: assert metaclass-property of `parent_class`
            self._method_prototypes.extend(parent_class._method_prototypes)

    def _perform_instantiation(self):
        """
        Convert all method prototypes from class-item into methods of instance-item
        :return:
        """

        # this relates to R4__is_instance_of defined builtin_entities
        parent_class: Union[Entity, None]
        try:
            parent_class = self.R4
        except AttributeError:
            parent_class = None

        if parent_class not in (None, []):
            for func in parent_class._method_prototypes:
                self.add_method(func)

    def _get_relation_contents(self, rel_uri: str):

        aux.ensure_valid_uri(rel_uri)

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

        relation = ds.relations[rel_uri]
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
            # TODO: handle multilingual situations more flexible

            # todo: specify currently relevant language here (influences the return value); for now: using default
            language = settings.DEFAULT_DATA_LANGUAGE

            filtered_res_explicit_lang = []
            filtered_res_without_lang = []
            for elt in res:

                # if no language is defined (e.g. ordinary string) -> use interpret this as match
                # (but only if no other result with matching language attribute is available)
                lng = getattr(elt, "language", None)
                if lng is None:
                    filtered_res_without_lang.append(elt)
                elif lng == language:
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
                    f"and language {language}."
                )

                raise ValueError(msg)

        else:
            return res

    @classmethod
    def add_method_to_class(cls, func):
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

    def set_mutliple_relations(
        self, relation: Union["Relation", str], obj_seq: Union[tuple, list], *args, **kwargs
    ) -> List["Statement"]:
        """
        Convenience function to create multiple Statements at once
        """
        res_list = []

        assert isinstance(obj_seq, (tuple, list))
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

        if isinstance(relation, Relation):

            if isinstance(obj, (Entity, *allowed_literal_types)) or obj in allowed_literal_types:
                return self._set_relation(relation.uri, obj, scope=scope, qualifiers=qualifiers, proxyitem=proxyitem)
            # Todo: remove obsolete code:
            # elif isinstance(obj, Iterable):
            #     msg = f"Unsupported iterable type ({type(obj)}) of {obj}, while setting relation {relation.short_key}"
            #     raise TypeError(msg)
            # elif isinstance(obj, (Entity, str, bool, float, int, complex)):
            #     # obj is eithter an entity or a literal
            #     return self._set_relation(relation.short_key, obj, scope=scope, proxyitem=proxyitem)
            else:
                msg = f"Unsupported type ({type(obj)}) of {obj}, while setting relation {relation.short_key} of {self}"
                raise TypeError(msg)
        else:
            msg = f"unexpected type: {type(relation)} of relation object {relation}, with {self} as subject"
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
        else:
            corresponding_entity = None

            if not isinstance(rel_content, (str, int, float, complex)):
                rel_content = repr(rel_content)
            corresponding_literal = rel_content

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
            pr_key = process_key_str(key_str)
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
            res = stm_res
        return res

    def overwrite_statement(self, rel_key_str_or_uri: str, new_obj: "Entity", qualifiers=None) -> "Statement":
        # the caller wants only results for this key (e.g. "R4")

        assert isinstance(rel_key_str_or_uri, str)

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
                raise aux.PyERKError(msg)
            if len(stm) > 1:
                msg = f"Unexpectedly found length-{len(stm)} statement list for entity {self} and relation {rel}"
                raise aux.PyERKError(msg)
            stm = stm[0]

        assert isinstance(stm, Statement)

        if stm.qualifiers:
            raise NotImplementedError("Processing old qualifiers is not yet implemented while overwriting statements")

        stm.unlink()
        return self.set_relation(rel, new_obj, qualifiers=qualifiers)


def wrap_function_with_search_uri_context(func, uri):
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        with search_uri_context(uri=uri):
            return func(*args, **kwargs)

    return wrapped_func


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

        # TODO: obsolete!
        # list of keys which are released, when unloading a module
        self.released_keys = []

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

        # this list serves to keep track of nested scopes
        self.scope_stack = []

        # store unlinked entities
        self.unlinked_entities = {}

    def get_item_by_label(self, label) -> Entity:
        """
        Search over all item and return the first item which has the provided label.
        Useful during interactive debugging. Not useful for production!
        """
        for uri, itm in self.items.items():
            if itm.R1 == label:
                return itm

    def get_entity_by_key_str(self, key_str, mod_uri=None) -> Entity:
        """
        :param key_str:     str like I1234 or I1234__some_label
        :param mod_uri:     optional uri of the module; if None the active module is assumed

        :return:            corresponding entity
        """

        processed_key = process_key_str(key_str, mod_uri=mod_uri)
        assert processed_key.etype in (EType.ITEM, EType.RELATION)

        if mod_uri is None:
            uri = processed_key.uri
        else:
            uri = aux.make_uri(mod_uri, processed_key.short_key)

        res = self.get_entity_by_uri(uri, processed_key.etype, strict=False)
        if res is None:
            mod_uri = get_active_mod_uri(strict=False)
            msg = (
                f"Could not find entity with key '{processed_key.short_key}'; Entity type: '{processed_key.etype}'; "
                f"Active mod: '{mod_uri}'"
            )
            raise KeyError(msg)

        return res

    def get_entity_by_uri(self, uri: str, etype=None, strict=True) -> Union[Entity, None]:

        if etype is not None:
            # only one lookup is needed
            if etype == EType.ITEM:
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

        stm_list: List[Statement] = self.relation_statements[rel_uri]

        res = []
        if isinstance(filter, allowed_literal_types) or isinstance(filter, Entity):
            cond_func = lambda obj: obj == filter
        else:
            cond_func = lambda obj: True
        for stm in stm_list:
            if cond_func(stm.object) and self._default_subject_filter(stm.subject):
                res.append(stm.subject)

        return res

    def get_statements(self, entity_uri: str, rel_uri: str) -> List["Statement"]:
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

    def set_statement(self, stm: "Statement") -> None:
        """
        Insert a Statement into the relevant data structures of the DataStorage (self)

        This method does not handle the dual realtion. It must be created and stored separately.

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
                lang_list = [get_language_of_str_literal(s.object) for s in stm_list]
                new_lang = get_language_of_str_literal(stm.object)
                if new_lang in lang_list:
                    msg = (
                        f"for subject {subj_uri} ({subj_label}) there already exists statements for relation "
                        f"{stm.predicate} with the object languages {lang_list}. This relation is functional for "
                        f"each language (R32). Thus another statement with language `{new_lang}` is not allowed."
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

    def preprocess_query(self, query):
        if "__" in query:
            prefixes = re.findall(r"[\w]*:[ ]*<.*?>", query)
            prefix_dict = {}
            for prefix in prefixes:
                parts = prefix.split(" ")
                key = parts[0]
                value = parts[-1].replace("<", "").replace(">", "")
                prefix_dict[key] = value
            # print(prefix_dict)

            entities = re.findall(r"[\w]*:[\w]+__[\w]+(?:–_instance)?", query)
            for e in entities:
                # check sanity
                prefix, rest = e.split(":")
                prefix = prefix + ":"
                erk_key, description = rest.split("__")

                entity_uri = prefix_dict.get(prefix) + erk_key
                entity = self.get_entity_by_uri(entity_uri)

                label = description.replace("_", " ")

                msg = f"Entity label '{entity.R1}' for entity '{e}' and given label '{label}' do not match!"
                assert entity.R1 == label, msg

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
            raise PyERKError(msg)

        self.scope_stack.pop()

    def get_current_scope(self):
        try:
            return self.scope_stack[-1]
        except IndexError:
            msg = "unexepectedly found the scope stack empty"
            raise PyERKError(msg)


ds = DataStore()

YAML_VALUE = Union[str, list, dict]


@unique
class EType(Enum):
    """
    Entity types.
    """

    ITEM = 0
    RELATION = 1
    LITERAL = 2


@unique
class SType(Enum):
    """
    Statement types.
    """

    CREATION = 0
    EXTENTION = 1
    UNDEFINED = 2


@unique
class VType(Enum):
    """
    Dict value types.
    """

    LITERAL = 0
    ENTITY = 1
    LIST = 2
    DICT = 3


@dataclass
class ProcessedStmtKey:
    """
    Container for processed statement key
    """

    short_key: str = None
    # entity type (enum)
    etype: EType = None
    # statement type (enum)
    stype: SType = None
    # value type (enum)
    vtype: VType = None

    content: object = None
    delimiter: str = None
    label: str = None
    prefix: str = None
    uri: str = None

    original_key_str: str = None


def unpack_l1d(l1d: Dict[str, object]):
    """
    unpack a dict of length 1
    :param l1d:
    :return:
    """
    assert len(l1d) == 1
    return tuple(*l1d.items())


# define regular expressions outside of the function (they have to be compiled only once)
# use https://pythex.org/ with fixture e. g `some_prefix__S000['test label']` to understand these
re_prefix_shortkey_suffix = re.compile(r"^((.+?)__)?((Ia?)|(Ra?)|(S))(\d+)(.*)$")
re_suffix_underscore = re.compile(r"^__([\w\-]+)$")  # \w means alphanumeric (including `_`);
re_suffix_square_brackets = re.compile(r"""^\[["'](.+)["']\]""")


def process_key_str(
    key_str: str,
    check: bool = True,
    resolve_prefix: bool = True,
    mod_uri: str = None,
) -> ProcessedStmtKey:
    """
    In ERK there are the following kinds of keys:
        - a) short_key like `R1234`
        - b) name-labeled key like `R1234__my_relation` (consisting of a short_key, a delimiter (`__`) and a label)
        - c) prefixed short_key like `bi__R1234`
        - d) prefixed name-labeled key like `bi__R1234__my_relation`

        - e) index-labeld key like  `R1234["my relation"]`
        - f) prefixed index-labeld key like  `bi__R1234["my relation"]`

    See also: userdoc/overview.html#keys-in-pyerk

    Also, the leading character indicates the entity type (EType).

    This function expects any of these cases.
    :param key_str:     a string like "R1234__my_relation" or "R1234" or "bi__R1234__my_relation"
    :param check:       boolean flag; determines if the label part should be checked wrt its consistency to
    :param resolve_prefix:
                        boolean flag; determines if
    :param mod_uri:     optional uri of the module


    :return:            a data structure which allows to access short_key, type and label separately
    """

    res = ProcessedStmtKey()
    res.original_key_str = key_str

    match1 = re_prefix_shortkey_suffix.match(key_str)

    errmsg = f"unxexpected key_str: `{key_str}` (maybe a literal or syntax error)"
    if not match1:
        raise KeyError(errmsg)

    if match1.group(3) is None or match1.group(7) is None:
        raise KeyError(errmsg)

    res.prefix = match1.group(2)  # this might be None
    res.short_key = match1.group(3) + match1.group(7)

    suffix = match1.group(8) or ""

    match2 = re_suffix_underscore.match(suffix)
    match3 = re_suffix_square_brackets.match(suffix)

    errmsg = f"invalid suffix of key_str `{key_str}` (probably syntax error)"
    if match2 and match3:
        # key seems to mix underscores and square brackets
        raise KeyError(errmsg)

    if suffix and (not match2) and (not match3):
        # syntax of suffix seems to be wrong (e., g. missing bracket)
        raise KeyError(errmsg)

    if match2:
        res.label = match2.group(1)
    elif match3:
        res.label = match3.group(1)
    else:
        res.label = None

    if res.short_key.startswith("I"):
        res.etype = EType.ITEM
        res.vtype = VType.ENTITY
    elif res.short_key.startswith("R"):
        res.etype = EType.RELATION
        res.vtype = VType.ENTITY
    else:
        msg = f"unxexpected shortkey: '{res.short_key}' (maybe a literal)"
        raise KeyError(msg)

    if resolve_prefix:
        _resolve_prefix(res, passed_mod_uri=mod_uri)

    if check:
        aux.ensure_valid_short_key(res.short_key)
        check_processed_key_label(res)

    return res


def _resolve_prefix(pr_key: ProcessedStmtKey, passed_mod_uri: str = None) -> None:
    """
    get uri from prefix or from passed argument or from active module
    """
    active_mod_uri = get_active_mod_uri(strict=False)
    if _search_uri_stack:
        search_uri = _search_uri_stack[-1]
    else:
        search_uri = None

    if pr_key.prefix is None:
        if active_mod_uri is None and search_uri is None:
            if passed_mod_uri:
                mod_uri = passed_mod_uri
            else:
                # assume that `builtin_entities` is meant
                mod_uri = settings.BUILTINS_URI
        else:
            # Situation: create_item(..., R321="some value") within an active module
            # (no prefix). short_key R321 could refer to
            # a) the module where the function is defined which performs this call (search_uri)),
            # b) the active module or c) builtin_entities -> search in this order

            # 1. check that passed_mod_uri does not contradict
            if passed_mod_uri and (passed_mod_uri not in (active_mod_uri, search_uri)):
                msg = (
                    f"Encountered inconsistent uris for object with key_str {pr_key.original_key_str}. "
                    f"Explicitly passed: '{passed_mod_uri}'."
                    f"expected one of: '{active_mod_uri}' (active mod) or '{search_uri}' (search_uri)."
                )
                raise aux.InvalidURIError(msg)

            # 2a) check search_uri context
            if search_uri:

                candidate_uri = aux.make_uri(search_uri, pr_key.short_key)
                res_entity = ds.get_entity_by_uri(candidate_uri, strict=False)

                if res_entity is not None:
                    pr_key.uri = candidate_uri
                    return

            # 2b) check active mod
            if active_mod_uri:
                candidate_uri = aux.make_uri(active_mod_uri, pr_key.short_key)
                res_entity = ds.get_entity_by_uri(candidate_uri, strict=False)

                if res_entity is not None:
                    pr_key.uri = candidate_uri
                    return

            # 2c) try builtin_entities as fallback
            candidate_uri = aux.make_uri(settings.BUILTINS_URI, pr_key.short_key)
            res_entity = ds.get_entity_by_uri(candidate_uri, strict=False)

            if res_entity is not None:
                pr_key.uri = candidate_uri
                return
            else:
                # if res_entity is still None no entity could be found
                msg = (
                    f"No entity could be found for short_key {pr_key.short_key}, neither in active module "
                    f"({active_mod_uri}) nor in builin_entities ({settings.BUILTINS_URI})"
                )
                raise KeyError(msg)
    else:
        # prefix was not not None
        mod_uri = ds.get_uri_for_prefix(pr_key.prefix)

        if passed_mod_uri and (passed_mod_uri != active_mod_uri):
            msg = (
                f"encountered inconsistent uris for object with key_str {pr_key.original_key_str}. "
                f"from prefix mod: '{mod_uri}' vs explicitly passed: '{passed_mod_uri}'."
            )
            raise aux.InvalidURIError(msg)

    pr_key.uri = aux.make_uri(mod_uri, pr_key.short_key)


def check_processed_key_label(pkey: ProcessedStmtKey) -> None:
    """
    Check if the used label of a key_str matches the actual label (R1) of that entity

    :param pkey:
    :return:
    """

    # TODO: check prefix

    if not pkey.label:
        return

    try:
        entity = ds.get_entity_by_uri(pkey.uri)
    except KeyError:
        # entity does not exist -> no label to compare with
        return
    label_compare_str1 = entity.R1
    label_compare_str2 = entity.R1.replace(" ", "_").replace("-", "_")

    if pkey.label.lower() not in (label_compare_str1.lower(), label_compare_str2.lower()):
        msg = (
            f"check of label consistency failed for key {pkey.original_key_str}. Expected:  one of "
            f'("{label_compare_str1}", "{label_compare_str2}") but got  "{pkey.label}". '
            "Note: this test is *not* case-sensitive."
        )
        raise ValueError(msg)


def u(key_str: str) -> str:
    """
    Convenience function converting "[prefix__]I1234__my_label"  to "[moduri#]I1234".
    If no prefix is given the active module and `builtin_entities` are searched for (in this order).

    :param key_str:
    :return:
    """

    processed_key = process_key_str(key_str)
    assert processed_key.short_key is not None
    return processed_key.uri


# noinspection PyShadowingNames
class Item(Entity):
    def __init__(self, base_uri: str, key_str: str, **kwargs):
        super().__init__(base_uri=base_uri)

        res = process_key_str(key_str, check=False, resolve_prefix=False)
        msg = f"invalid entity type deduced from key string: {key_str}: expected {EType.ITEM} but got {res.etype}."
        assert res.etype == EType.ITEM, msg

        self.short_key = res.short_key
        self.uri = aux.make_uri(self.base_uri, self.short_key)

        assert self.uri not in ds.items, f"{self.uri} is already occupied. Cannot create new item."

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


def get_active_mod_uri(strict: bool = True) -> Union[str, None]:
    try:
        res = _uri_stack[-1]
    except IndexError:
        msg = (
            "Unexpected: empty uri_stack. Be sure to use uri_contex manager or similar technique "
            "when creating entities"
        )
        if strict:
            raise EmptyURIStackError(msg)
        else:
            return None
    return res


# noinspection PyShadowingNames
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

    new_kwargs = {}
    # prepare the kwargs to set relations
    for dict_key, value in kwargs.items():
        processed_key = process_key_str(dict_key)

        if processed_key.etype != EType.RELATION:
            msg = f"unexpected key: {dict_key} during creation of item {item_key}."
            raise ValueError(msg)

        if processed_key.prefix:
            new_key = f"{processed_key.prefix}__{processed_key.short_key}"
        else:
            new_key = processed_key.short_key
        new_kwargs[new_key] = value

    itm = Item(base_uri=mod_uri, key_str=item_key, **new_kwargs)
    assert itm.uri not in ds.items, f"Problematic (duplicated) uri: {itm.uri}"
    ds.items[itm.uri] = itm

    # acces the defaultdict(list)
    ds.entities_created_in_mod[mod_uri].append(itm.uri)
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


# for now we want unique numbers for keys for relations and items etc (although this is not necessary)
class KeyManager:
    """
    Class for a flexible and comprehensible key management. Every pyerk module must have its own (passed via)
    """

    # TODO: the term "maxval" is misleading because it will be used in range where the upper bound is exclusive
    # however, using range(minval, maxval+1) would results in different shuffling and thus will probably need some
    # refactoring of existing modules
    def __init__(self, minval=1000, maxval=9999, keyseed=None):
        """

        :param minval:  int
        :param maxval:  int
        :param keyseed: int; This allows a module to create its own random key order
        """

        self.instance = self
        self.minval = minval
        self.maxval = maxval
        self.keyseed = keyseed

        self.key_reservoir = None

        self._generate_key_numbers()

    def pop(self, index: int = -1) -> int:

        key = self.key_reservoir.pop(index)
        return key

    def _generate_key_numbers(self) -> None:
        """
        Creates a reaservoir of keynumbers, e.g. for automatically created entities. Due to the hardcoded seed value
        these numbers are stable between runs of the software, which simplifies development and debugging.

        This function is also called after unloading a module because the respective keys are "free" again

        Rationale behind random keys: During creation of knowledge bases it frees the mind of thinking too much
        about a meaningful order in which to create entities.

        :return:    list of integers
        """

        assert self.key_reservoir is None

        # passing seed (arg `x`) ensures "reproducible randomness" accross runs
        if not self.keyseed:
            # use hardcoded fallback
            self.keyseed = 1750
        random_ng = random.Random(x=self.keyseed)
        self.key_reservoir = list(range(self.minval, self.maxval))
        random_ng.shuffle(self.key_reservoir)


def pop_uri_based_key(prefix: Optional[str] = None, prefix2: str = "") -> Union[int, str]:
    """
    Create a short key (int or str) (optionally with prefixes) from the reservoir.

    :param prefix:
    :param prefix2:
    :return:
    """

    active_mod_uri = get_active_mod_uri()
    km: KeyManager = ds.uri_keymanager_dict[active_mod_uri]
    num_key = km.pop()
    if prefix is None:
        assert not prefix2
        return num_key

    assert prefix in ("I", "R")

    short_key = f"{prefix}{prefix2}{num_key}"
    return short_key


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
        assert isinstance(relation, Relation)
        self.relation = relation

        # TODO: maybe this 'registry name should be uri-based?'
        if registry_name is not None:
            assert isinstance(registry_name, str) and registry_name not in ds.qff_dict
            ds.qff_dict[registry_name] = self

    def __call__(self, obj):
        return RawQualifier(self.relation, obj)


class Statement:
    """
    Models a conrete (instantiated/applied) relation between entities. This is basically a dict.
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
        :param role:                    RelationRole.SUBJECT for normal and RelationRole.OBJECT for inverse edges
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
        self.rsk = relation.short_key  # to conviniently access this attribute in visualization
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
        assert [key, uri].count(None) == 1, "exactly one of the arguments must be provided, not 0 not 2"

        if key:
            try:
                uri = process_key_str(key).uri
            except KeyError:
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

        # TODO: remove obsolete key-recycling
        ds.released_keys.append(self.short_key)


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

    assert rel_key.startswith("R")

    mod_uri = get_active_mod_uri()

    default_relations = {
        # "R22": None,  # R22__is_functional
    }

    new_kwargs = {**default_relations}
    for key, value in kwargs.items():
        processed_key = process_key_str(key)

        if processed_key.etype != EType.RELATION:
            msg = f"unexpected key: {key} during creation of item {rel_key}."
            raise ValueError(msg)

        new_kwargs[processed_key.short_key] = value

    rel = Relation(mod_uri, rel_key, **new_kwargs)
    if rel.uri in ds.relations:
        msg = f"URI '{rel.uri}' has already been used."
        raise aux.InvalidURIError(msg)
    ds.relations[rel.uri] = rel
    ds.entities_created_in_mod[mod_uri].append(rel.uri)
    return rel


def create_builtin_item(*args, **kwargs) -> Item:
    with uri_context(uri=settings.BUILTINS_URI):
        itm = create_item(*args, **kwargs)
    return itm


def create_builtin_relation(*args, **kwargs) -> Relation:
    with uri_context(uri=settings.BUILTINS_URI):
        rel = create_relation(*args, **kwargs)
    return rel


def generate_new_key(prefix, prefix2="", mod_uri=None):
    """
    Utility function for the command line.

    :param prefix:
    :param prefix2:
    :param mod_uri:
    :return:
    """

    assert prefix in ("I", "R")

    if mod_uri is None:
        mod_uri = settings.BUILTINS_URI
        print(aux.byellow(f"Warning: creating key based on module {mod_uri}, which is probably unintended"))

    with uri_context(mod_uri):
        while True:
            key = f"{prefix}{prefix2}{pop_uri_based_key()}"
            uri = aux.make_uri(mod_uri, key)
            try:
                ds.get_entity_by_uri(uri)
            except aux.UnknownURIError:
                # the key was new -> no problem
                return key
            else:
                continue


def print_new_keys(n=30, loaded_mod=None):
    """
    print n random integer keys from the pregenerated list.

    :return:
    """

    if loaded_mod:
        # this ensures that the new keys are created wrt the loaded module (see also: script.py)
        mod_uri = loaded_mod.__URI__
    else:
        mod_uri = None
    if n > 0:
        print(aux.bcyan("supposed keys:    "))
    for i in range(n):
        k = generate_new_key("I", mod_uri=mod_uri)[1:]

        print(f"I{k}      R{k}")


def get_caller_frame(upcount: int) -> types.FrameType:
    # get the topmost frame
    frame = inspect.currentframe()
    # + 1 because the we have to leave this frame first
    i = upcount + 1
    while True:
        if frame.f_back is None:
            break
        frame = frame.f_back
        i -= 1
        if i == 0:
            break

    return frame


def get_key_str_by_inspection(upcount=1) -> str:
    """
    Retrieve the name of an entity from a code line like
      `cm.new_var(M=p.instance_of(I9904["matrix"]))`

    :param upcount:     int; how many frames to go up
    :return:
    """

    # get the topmost frame
    frame = get_caller_frame(upcount=upcount + 1)

    # this is strongly inspired by sympy.var
    try:
        fi = inspect.getframeinfo(frame)
        code_context = fi.code_context
    finally:
        # we should explicitly break cyclic dependencies as stated in inspect
        # doc
        del frame

    # !! TODO: parsing the assignment should be more robust (correct parsing of logical lines)
    # assume that there is at least one `=` in the line
    lhs, rhs = code_context[0].split("=")[:2]
    res: str = lhs.split("(")[-1].strip()
    assert res.isidentifier()
    return res


# TODO: remove obsolete this obsolete function
def get_mod_name_by_inspection(upcount=1):
    """
    :param upcount:     int; how many frames to go up
    :return:
    """

    frame = get_caller_frame(upcount=upcount + 1)

    mod_id = frame.f_globals.get("__MOD_ID__")
    return mod_id


def get_mod_id_list_by_inspection(upcount=2) -> list:
    """
    :param upcount:     int; how many frames to go up at beginning
                        upcount=2 (default) means: start int the caller frame. Example: fnc1()->fnc2()->fnc3()
                        where fnc3 is this function, called by fnc2, which itself is called by fnc1 (the caller)
    :return:            list of mod_id-objects (type str)
    """

    # get start frame
    frame = inspect.currentframe()
    i = upcount
    while True:
        assert frame.f_back is not None
        frame = frame.f_back
        i -= 1
        if i == 0:
            break

    # now `frame` is our start frame where we begin to look for __MOD_ID__
    res = [None]
    while True:
        mod_id = frame.f_globals.get("__URI__")
        if mod_id is not None:
            res.append(mod_id)
        frame = frame.f_back
        if frame is None:
            break

    return res


# TODO: obsolete?
class Context:
    """
    Container class for context definitions
    """

    def __init__(self, *args, **kwargs):
        pass


_uri_stack = []
_search_uri_stack = []


class abstract_uri_context:
    def __init__(self, uri_stack: list, uri: str, prefix: str = None):
        self.uri_stack = uri_stack
        self.uri = uri
        self.prefix = prefix

    def __enter__(self):
        """
        implicitly called in the head of the with statemet
        :return:
        """
        self.uri_stack.append(self.uri)

        if self.prefix:
            ds.uri_prefix_mapping.add_pair(self.uri, self.prefix)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is the place to handle exceptions

        res = self.uri_stack.pop()
        assert res == self.uri
        if self.prefix:
            ds.uri_prefix_mapping.remove_pair(self.uri, self.prefix)


class uri_context(abstract_uri_context):
    """
    Context manager for creating entities with a given uri
    """
    def __init__(self, uri: str, prefix: str = None):
        super().__init__(_uri_stack, uri, prefix)


class search_uri_context(abstract_uri_context):
    """
    uri Context manager for searching for entities with a given key
    """
    def __init__(self, uri: str, prefix: str = None):
        super().__init__(_search_uri_stack, uri, prefix)


def unload_mod(mod_uri: str, strict=True) -> None:
    """
    Delete all references to entities comming from a module with `mod_id`

    :param mod_uri: str; uri of the module, see its __URI__ attribute
    :param strict:  boolean; raise Exception if module seems be not loaded

    :return:        list of released keys
    """

    # prepare the list to store the released keys
    ds.released_keys.clear()

    # TODO: This might to check dependencies in the future

    entity_uris: List[str] = ds.entities_created_in_mod.pop(mod_uri, [])
    stm_dict = ds.stms_created_in_mod.pop(mod_uri, {})

    if strict and (not entity_uris and not stm_dict):
        msg = f"Seems like neither entities nor statements from {mod_uri} have been loaded. This is unexpected."
        raise KeyError(msg)

    for uri in entity_uris:
        _unlink_entity(uri)
        assert uri not in ds.relation_statements.keys()

    intersection_set = set(entity_uris).intersection(ds.relation_statements.keys())

    msg = "Unexpectedly some of the entity keys are still present"
    assert len(intersection_set) == 0, msg

    for uri, stm in stm_dict.items():
        stm: Statement
        assert isinstance(stm, Statement)
        stm.unlink()

    try:
        ds.mod_path_mapping.remove_pair(key_a=mod_uri)
    except KeyError:
        if strict:
            raise
        else:
            pass

    aux.clean_dict(ds.statements)
    aux.clean_dict(ds.inv_statements)

    # TODO: obsolete
    res = list(ds.released_keys)

    try:
        ds.uri_keymanager_dict.pop(mod_uri)
    except KeyError:
        if strict:
            raise

    try:
        ds.uri_mod_dict.pop(mod_uri)
    except KeyError:
        if strict:
            raise

    ds.uri_prefix_mapping.remove_pair(mod_uri, strict=strict)

    if modname := ds.modnames.get(mod_uri):
        sys.modules.pop(modname)

    # empty the list again to avoid confusion in future uses
    ds.released_keys.clear()


def _unlink_entity(uri: str, remove_from_mod=False) -> None:
    """
    Remove the occurrence of this the respective entitiy from all relevant data structures

    :param uri:     entity uri
    :return:        None
    """
    assert isinstance(uri, str)
    aux.ensure_valid_uri(uri)
    entity: Entity = ds.get_entity_by_uri(uri)
    r1 = getattr(entity, "R1", "<unknown entity>")
    entity._label_after_unlink = f"!!unlinked: {r1}"
    entity._unlinked = True
    ds.unlinked_entities[uri] = entity

    if remove_from_mod:
        mod_uri = uri.split("#")[0]
        mod_entities = ds.entities_created_in_mod[mod_uri]

        # TODO: this could be speed up by using a dict instead of a list for mod_entities
        mod_entities.remove(uri)

    res1 = ds.items.pop(uri, None)
    res2 = ds.relations.pop(uri, None)

    if res1 is None and res2 is None:
        msg = f"No entity with key {uri} could be found. This is unexpected."
        raise KeyError(msg)

    # now delete the relation edges from the data structures
    re_dict = ds.statements.pop(entity.uri, {})
    inv_re_dict = ds.inv_statements.pop(entity.uri, {})

    # in case res1 is a scope-item we delete all corressponding relation edges, otherwise nothing happens
    scope_rels = ds.scope_statements.pop(uri, [])

    re_list = list(scope_rels)

    # create a item-list of all Statements instances where `ek` is involved either as subject or object
    re_item_list = list(re_dict.items()) + list(inv_re_dict.items())

    for rel_uri, local_re_list in re_item_list:
        # rel_uri: uri of the relation (like "pyerk/foo#R1234")
        # re_list: list of Statement instances
        re_list.extend(local_re_list)

    if isinstance(entity, Relation):

        tmp = ds.relation_statements.pop(uri, [])
        re_list.extend(tmp)

    # now iterate over all Statement instances
    for stm in re_list:
        stm: Statement
        stm.unlink(uri)

    # during unlinking of the Statements the default dicts might have been recreating some keys -> pop again
    # TODO: obsolete because we clean up the defaultdicts anyway
    ds.statements.pop(entity.uri, None)
    ds.inv_statements.pop(entity.uri, None)

    ds.released_keys.append(uri)


def replace_and_unlink_entity(old_entity: Entity, new_entity: Entity):
    """
    Replace all statements where `old_entity` is subject or object with new relations where `new_entity` is sub or obj.
    For the "subject-case" only process those statements for which `new_entity` does not yet have any relations.
    Thus do not replace e.g. the R4__is_instance_of statement of `new_entity`.

    Then unlink `old_entity`.
    """

    res = RuleResult()

    from pyerk import builtin_entities as bi

    # these predicates should not be replaced
    omit_uris = aux.uri_set(
        bi.R1["has label"], bi.R2["has description"], bi.R4["is instance of"], bi.R57["is placeholder"]
    )

    # ensure both entities exist (raise UnknownURIError otherwise):
    ds.get_entity_by_uri(old_entity.uri)
    ds.get_entity_by_uri(new_entity.uri)

    stm_dict1 = old_entity.get_inv_relations()  # where it is obj
    stm_dict2 = old_entity.get_relations()  # where it is subj

    _unlink_entity(old_entity.uri, remove_from_mod=True)
    res.unlinked_entities.append(old_entity)
    res.replacements.append((old_entity, new_entity))

    for relation_uri, stm_list in list(stm_dict1.items()) + list(stm_dict2.items()):
        for stm in stm_list:
            new_stm = None
            stm: Statement
            subject, predicate, obj = stm.relation_tuple
            if predicate.uri in omit_uris:
                continue
            subject: Item
            qlf = stm.qualifiers
            if obj == old_entity:
                # case1: old_entity was object, subject stays the same
                new_stm = subject.set_relation(predicate, new_entity, qualifiers=qlf, prevent_duplicate=True)
                res.add_statement(new_stm)
                continue
            else:
                # case2: old_entity was subject, subject must be new_entity
                assert subject == old_entity

                # prevent the creation of a duplicated statement
                existing_objs = new_entity.get_relations(predicate.uri, return_obj=True)
                if not obj in existing_objs:

                    # it is possible that predicate is functional and new_entitiy.predicate has a value
                    # different from obj. this is OK if one of them is a placeholder
                    if len(existing_objs) == 1 and predicate.R22__is_functional:
                        existing_obj = existing_objs[0]
                        if obj.R57__is_placeholder:
                            # ignore it -> continue with next statement
                            continue
                        elif not existing_obj.R57__is_placeholder and not obj.R57__is_placeholder:
                            msg = (
                                f"confilicting statement for functional predicate {predicate} and non-placeholder "
                                f"objects: {obj} (of old_entity)  and {existing_obj} of new_entity, while replacing"
                                f"{old_entity} (old) with {new_entity} (new)."
                            )
                            raise aux.FunctionalRelationError(msg)
                        else:
                            assert existing_obj.R57__is_placeholder and not obj.R57__is_placeholder
                            # replace the placeholder with the non-placeholder information
                            chgd_stm = new_entity.overwrite_statement(predicate.uri, obj, qualifiers=qlf)
                            res.changed_statements.append(chgd_stm)
                            continue
                    else:
                        # no replacement has to be made
                        new_stm = new_entity.set_relation(predicate, obj, qualifiers=qlf)
                        res.add_statement(new_stm)
                        continue
                else:
                    assert obj in existing_objs
                    # no new information available -> continue with next statement
                    continue

    return res


def register_mod(uri: str, keymanager: KeyManager, check_uri=True):
    frame = get_caller_frame(upcount=1)
    path = os.path.abspath(frame.f_globals["__file__"])
    if check_uri:
        assert frame.f_globals.get("__URI__", None) == uri
    if uri != settings.BUILTINS_URI:
        # the builtin module is an exception because it should not be unloaded

        if uri in ds.mod_path_mapping.a:
            msg = f"URI '{uri}' was already registered by {ds.mod_path_mapping.a[uri]}."
            raise aux.InvalidURIError(msg)

        ds.mod_path_mapping.add_pair(key_a=uri, key_b=path)

    # all modules should have their own key manager
    ds.uri_keymanager_dict[uri] = keymanager


def start_mod(uri):
    """
    Register the uri for the _uri_stack.

    Note: between start_mod and end_mod no it is not allowed to load other erk modules

    :param uri:
    :return:
    """
    assert len(_uri_stack) == 0, f"Non-empty uri_stack: {_uri_stack}"
    _uri_stack.append(uri)


def end_mod():
    _uri_stack.pop()
    assert len(_uri_stack) == 0


def get_language_of_str_literal(obj: Union[str, Literal]):
    if isinstance(obj, Literal):
        return obj.language

    return None


class LangaguageCode:
    def __init__(self, langtag):
        assert langtag in settings.SUPPORTED_LANGUAGES

        self.langtag = langtag

    def __rmatmul__(self, arg: str) -> Literal:
        """
        This enables syntax like `"test string" @ en` (where `en` is a LanguageCode instance)

        :param arg:     the string for which the language ist to be specified

        :return:        Literal instance with `.lang` attribute set
        """
        assert isinstance(arg, str)

        res = Literal(arg, lang=self.langtag)

        return res


en = LangaguageCode("en")
de = LangaguageCode("de")


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

    def add_statement(self, stm: Statement):
        if stm is None:
            return
        assert stm not in self.new_statements
        self.new_statements.append(stm)
        self.rel_map[stm.predicate.uri].append(stm)

    def add_statements(self, stms: List[Statement]):
        for stm in stms:
            self.add_statement(stm)

    def add_entity(self, entity: Entity):
        self.new_entities.append(entity)

    def extend(self, part: "RuleResult"):
        assert isinstance(part, RuleResult)
        self.add_statements(part.new_statements)
        self.new_entities.extend(part.new_entities)
        self.unlinked_entities.extend(part.unlinked_entities)
        self.replacements.extend(part.replacements)
        if part.exception:
            self.exception = part.exception

    def add_partial(self, part: "RuleResult"):
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


def format_entity_html(e: Entity):

    short_txt = f'<span class="entity">{e.R1}</span>'
    detailed_txt = f'<span class="entity">{e.short_key}["{e.R1}"]</span>'

    return f'<span class="js-toggle" data-short-txt="{quote(short_txt)}" data-detailed-txt="{quote(detailed_txt)}">{short_txt}</span>'


def format_literal_html(obj):
    return f'<span class="literal">{repr(obj)}</span>'


def script_main(fpath):
    IPS()
