"""
Core module of pyerk
"""
import os
from collections import defaultdict
from dataclasses import dataclass
import inspect
import types
import abc
import random
from enum import Enum, unique
import re as regex
from addict import Dict as attr_dict
from typing import Dict, Union, List, Iterable, Optional
from rdflib import Literal


from . import auxiliary as aux
from . import settings

from ipydex import IPS, activate_ips_on_exception, set_trace


activate_ips_on_exception()


"""
    TODO:
    
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


class Entity(abc.ABC):
    """
    Abstract parent class for both Relations and Items.

    Do not forget to call self.__post_init__ at the end of __init__ in subclasses.
    """

    # a "short_key" is something like "I1234" while for usability reasons we also allow keys like
    # I1234__some_explanatory_label (which is a key but not a short key)
    short_key: str = None

    def __init__(self):
        # this will hold mappings like "R1234": EntityRelation(..., R1234)
        self.relation_dict = {}
        self._method_prototypes = []
        self._namespaces = {}

    def __call__(self, *args, **kwargs):
        # returning self allows to use I1234 and I1234("human readable item name") interchageably
        # (once the object is created)

        custom_call_method = getattr(self, "_custom_call", None)
        if custom_call_method is None:
            msg = f"entity {self} has not defined a _custom_call-method and thus cannot be called"
            raise TypeError(msg)
        else:
            assert callable(custom_call_method)
            return custom_call_method(*args, **kwargs)

    def idoc(self, adhoc_label: str):
        """
        idoc means "inline doc". This function allows to attach a label to entities when using them in code
        because it returns just the Entity-object itself. Thus one can use the following expressions interchageably:
        `I1234` and `I1234.idoc("human readable item name")`

        Note that there is a shortcut to this function: `I1234["human readable item name"]

        :return:    self
        """

        # check if the used label matches the description
        assert isinstance(adhoc_label, str)
        if adhoc_label != self.R1 and not getattr(self, "_ignore_mismatching_adhoc_label", False):
            msg = f"got mismatiching label for Entity {self}: '{adhoc_label}'"
            raise ValueError(msg)

        # TODO: check consistency between adhoc_label and self.label
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
        res = process_key_str(attr_name)
        if not res.etype == EType.RELATION:
            r3 = getattr(self, "R3", None)
            r4 = getattr(self, "R4", None)
            msg = (
                f"Unexpected attribute name: '{attr_name}' of entity {self}\n",
                f'Type hint: self.R3("is_subclass_of"): {r3}\n',
                f'Type hint: self.R4("is_instance_of"): {r4}\n',
            )
            raise AttributeError(msg)

        try:
            etyrel = self._get_relation_contents(res.short_key)
        except KeyError:
            msg = f"'{type(self)}' object has no attribute '{res.short_key}'"
            raise AttributeError(msg)
            # general_relation = ds.relations[res.short_key]
            # etyrel = EntityRelation(entity=self, relation=general_relation)
        return etyrel

    def __eq__(self, other):
        return id(self) == id(other)

    def __post_init__(self):
        # for a solution how to automate this see
        # https://stackoverflow.com/questions/55183333/how-to-use-an-equivalent-to-post-init-method-with-normal-class
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

    def _get_relation_contents(self, rel_key: str):

        relation_edges: List[RelationEdge] = ds.get_relation_edges(self.short_key, rel_key)

        # for each of the relation edges get a list of the result-objects
        # (this assumes the relation tuple to be a triple (sub, rel, obj))
        res = [re.relation_tuple[2] for re in relation_edges if re.role is RelationRole.SUBJECT]

        # the following logic decides whether to e.g. return a list of length 1 or the contained entity itself
        # this depends on whether self is a functional relation (->  R22__is_functional)

        # if rel_key == "R22" -> relation is the R22-entity: we are asking whether self is functional;
        # this must be handled separately to avoid infinite recursion:
        # (note that R22 itself is also a functional relation: only one of {True, False} is meaningful, same holds for
        # R32["is functional for each language"]). R32 also must be handled separately

        relation = ds.relations[rel_key]
        hardcode_functional_relations = ["R22", "R32"]
        hardcode_functional_fnc4elang_relations = ["R1"]

        # in the following or-expression the second operand is only evaluated if the first ist false
        # if rel_key in ["R22", "R32"] or relation.R22:
        if rel_key in hardcode_functional_relations or relation.R22:
            if len(res) == 0:
                return None
            else:
                assert len(res) == 1
                return res[0]

        #  is a similar situation
        # if rel_key == "R32" this means that self 'is functional for each language'

        elif rel_key in hardcode_functional_fnc4elang_relations or relation.R32:
            # TODO: handle multilingual situations more flexible

            # todo: specify currently relevant language here (influences the return value); for now: using default
            language = settings.DEFAULT_DATA_LANGUAGE

            filtered_res = []
            for elt in res:

                # if no language is defined (e.g. ordinary string) -> use default
                lng = getattr(elt, "language", settings.DEFAULT_DATA_LANGUAGE)
                if lng == language:
                    filtered_res.append(elt)

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

    def set_relation(
        self,
        relation: Union["Relation", str],
        obj,
        scope: "Entity" = None,
        proxyitem: Optional["Item"] = None,
        qualifiers: Optional[List["RawQualifier"]] = None,
    ) -> "RelationEdge":
        """
        Allows to add a relation after the item was created.

        :param relation:    Relation-Entity (or its short_key)
        :param obj:         target (object) of the relation (where self is the subject)
        :param scope:       Entity for the scope in which the relation is defined
        :param proxyitem:   optional item to which the RelationEdge is associated (e.g. an equation-instance)
        :param qualifiers:  optional list of RawQualifiers (see docstring of this class)
        :return:
        """

        if isinstance(relation, str):
            # assume we got the short key of the relation
            relation = ds.get_entity(relation)

        allowed_types = (str, bool, float, int, complex)
        if isinstance(relation, Relation):

            if isinstance(obj, (Entity, *allowed_types)) or obj in allowed_types:
                return self._set_relation(
                    relation.short_key, obj, scope=scope, qualifiers=qualifiers, proxyitem=proxyitem
                )
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
        rel_key: str,
        rel_content: object,
        scope: Optional["Entity"] = None,
        qualifiers: Optional[list] = None,
        proxyitem: Optional["Item"] = None,
    ) -> "RelationEdge":

        rel = ds.relations[rel_key]

        # store relation for later usage
        self.relation_dict[rel_key] = rel

        # store this relation edge in the global store
        if isinstance(rel_content, Entity):
            corresponding_entity = rel_content
            corresponding_literal = None
        else:
            corresponding_entity = None
            corresponding_literal = repr(rel_content)

        rledg = RelationEdge(
            relation=rel,
            relation_tuple=(self, rel, rel_content),
            role=RelationRole.SUBJECT,
            corresponding_entity=corresponding_entity,
            corresponding_literal=corresponding_literal,
            scope=scope,
            qualifiers=qualifiers,
            proxyitem=proxyitem,
        )

        ds.set_relation_edge(self.short_key, rel.short_key, rledg)

        if scope is not None:
            ds.scope_relation_edges[scope.short_key].append(rledg)

        # if the object is not a literal then also store the inverse relation
        if isinstance(rel_content, Entity):

            inv_rledg = RelationEdge(
                relation=rel,
                relation_tuple=(self, rel, rel_content),
                role=RelationRole.OBJECT,
                corresponding_entity=self,
                scope=scope,
                qualifiers=qualifiers,
                proxyitem=proxyitem,
            )

            # interconnect the primal RE with the inverse one:
            rledg.dual_relation_edge = inv_rledg
            inv_rledg.dual_relation_edge = rledg

            # ds.set_relation_edge(rel_content.short_key, rel.short_key, inv_rledg)
            tmp_list = ds.inv_relation_edges[rel_content.short_key][rel.short_key]

            # TODO: maybe check length here for inverse functional
            tmp_list.append(inv_rledg)
        return rledg

    def get_relations(self, key_str: Optional[str] = None) -> Union[Dict[str, list], list]:
        """
        Return all RelationEdge instance where this item is subject

        :param key_str:     if passed return only the result for this key
        :return:            either the whole dict or just one value (of type list)
        """

        rel_dict = ds.relation_edges[self.short_key]
        if key_str is None:
            return rel_dict
        else:
            processed_key = pk(key_str)
            return rel_dict.get(processed_key, [])

    def get_inv_relations(self, key_str: Optional[str] = None) -> Union[Dict[str, list], list]:
        """
        Return all RelationEdge instance where this item is object

        :param key_str:     if passed return only the result for this key
        :return:            either the whole dict or just one value (of type list)
        """

        inv_rel_dict = ds.inv_relation_edges[self.short_key]
        if key_str is None:
            return inv_rel_dict
        else:
            processed_key = pk(key_str)
            return inv_rel_dict.get(processed_key, [])


class DataStore:
    """
    Provides objects to store all data that would be global otherwise
    """

    def __init__(self):
        self.items = attr_dict()
        self.relations = attr_dict()
        self.statements = attr_dict()

        # dict of lists store keys of the entities (not the entities itself, to simplify deletion)
        self.entities_created_in_mod = defaultdict(list)

        # mappings like .a = {"M1234": "/path/to/mod.py"} and .b = {"/path/to/mod.py": "M1234"}
        self.mod_path_mapping = aux.OneToOneMapping()

        # this dict contains everything which is predefined by hardcoding
        self.builtin_entities = attr_dict()

        # for every entity key store a dict that maps relation keys to lists of corresponding relation-edges
        self.relation_edges = defaultdict(dict)

        # also do this for the inverse relations (for easy querying)
        self.inv_relation_edges = defaultdict(lambda: defaultdict(list))

        # for every scope-item key store the relevant relation-edges
        self.scope_relation_edges = defaultdict(list)

        # for every relation key store the relevant relation-edges
        self.relation_relation_edges = defaultdict(list)

        # store a list of all relation edges (to maintain the order)
        self.relation_edge_list = []

        # this will be set on demand
        self.rdfgraph = None

    def get_entity(self, key_str) -> Entity:
        """
        :param key_str:     str like I1234 or I1234__some_label

        :return:            corresponding entity
        """

        processed_key = process_key_str(key_str)
        if res := self.relations.get(processed_key.short_key):
            return res
        if res := self.items.get(processed_key.short_key):
            return res
        else:
            msg = f"Could not find entity with key {processed_key.short_key}; Entity type: {processed_key.etype}"
            raise KeyError(msg)

    def get_relation_edges(self, entity_key: str, relation_key: str) -> List["RelationEdge"]:
        """
        self.relation_edges maps an entity_key to an inner_dict.
        The inner_dict maps an relation_key to a RelationEdge or List[RelationEdge].

        :param entity_key:
        :param relation_key:
        :return:
        """

        # We return an empty list if the entity has no such relation.
        # TODO: model this as defaultdict?
        return self.relation_edges[entity_key].get(relation_key, list())

    def set_relation_edge(self, entity_key: str, relation_key: str, re_object: "RelationEdge") -> None:

        self.relation_relation_edges[relation_key].append(re_object)
        self.relation_edge_list.append(re_object)

        relation = self.relations[relation_key]

        # inner_obj will be either a list of relation_edges or None
        inner_obj = self.relation_edges[entity_key].get(relation_key, None)

        if inner_obj is None:
            self.relation_edges[entity_key][relation_key] = [re_object]

        elif isinstance(inner_obj, list):
            # R22__is_functional, this means there can only be one value for this relation and this item
            if relation.R22:
                msg = (
                    f"for entity {entity_key} there already exists a RelationEdge for functional relation "
                    f"with key {relation_key}. Another one is not allowed."
                )
                raise ValueError(msg)
            elif relation.R32:
                # TODO: handle multiple laguages here !!qa
                pass
            inner_obj.append(re_object)

        else:
            msg = (
                f"unexpected type ({type(inner_obj)}) of dict content for entity {entity_key} and "
                f"relation {relation_key}. Expected list or None"
            )
            raise TypeError(msg)


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


def unpack_l1d(l1d: Dict[str, object]):
    """
    unpack a dict of length 1
    :param l1d:
    :return:
    """
    assert len(l1d) == 1
    return tuple(*l1d.items())


def process_key_str(key_str: str) -> ProcessedStmtKey:

    res = ProcessedStmtKey()

    # prepare regular expressions
    # second character is an optional "a" for "autogenerated"
    re_itm = regex.compile(r"^(Ia?\d+)_?_?.*$")
    re_rel = regex.compile(r"^(Ra?\d+)_?_?.*$")

    # determine statement type
    if key_str.startswith("new "):
        res.stype = SType.CREATION
        key_str = key_str[4:]
    else:
        res.stype = SType.EXTENTION

    # determine entity type
    match_itm = re_itm.match(key_str)
    match_rel = re_rel.match(key_str)

    if match_itm:
        res.short_key = match_itm.group(1)
        res.etype = EType.ITEM
        res.vtype = VType.ENTITY
    elif match_rel:
        res.short_key = match_rel.group(1)
        res.etype = EType.RELATION
        res.vtype = VType.ENTITY
    else:
        res.short_key = None
        res.etype = EType.LITERAL
        res.vtype = VType.LITERAL
        res.content = key_str

    return res


def pk(key_str: str) -> str:
    """
    Convenience function converting "I1234__my_label"  to "I1234". Intended for usage in unittests

    :param key_str:
    :return:
    """

    processed_key = process_key_str(key_str)
    assert processed_key.short_key is not None
    return processed_key.short_key


# noinspection PyShadowingNames
class Item(Entity):
    def __init__(self, key_str: str, **kwargs):
        super().__init__()

        res = process_key_str(key_str)
        assert res.etype == EType.ITEM

        self.short_key = res.short_key
        self._set_relations_from_init_kwargs(**kwargs)

        self.__post_init__()

    def __repr__(self):
        try:
            R1 = getattr(self, "R1", "no label")
        except ValueError:
            R1 = "<<ValueError while retrieving R1>>"
        return f'<Item {self.short_key}["{R1}"]>'


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

    mod_id_list = get_mod_id_list_by_inspection()

    # get the uppermost __MOD_ID__
    mod_id = mod_id_list.pop()

    new_kwargs = {}
    # prepare the kwargs to set relations
    for dict_key, value in kwargs.items():
        processed_key = process_key_str(dict_key)

        if processed_key.etype != EType.RELATION:
            msg = f"unexpected key: {dict_key} during creation of item {item_key}."
            raise ValueError(msg)

        new_kwargs[processed_key.short_key] = value

    itm = Item(item_key, **new_kwargs)
    assert item_key not in ds.items, f"Problematic (duplicated) key: {item_key}"
    ds.items[item_key] = itm

    # acces the defaultdict(list)
    ds.entities_created_in_mod[mod_id].append(item_key)
    return itm


# noinspection PyShadowingNames
class Relation(Entity):
    def __init__(self, rel_key, **kwargs):
        super().__init__()

        # set label
        self.short_key = rel_key
        self._set_relations_from_init_kwargs(**kwargs)

        self.__post_init__()

    def __repr__(self):
        R1 = getattr(self, "R1", "no label")
        return f'<Relation {self.short_key}["{R1}"]>'


@unique
class RelationRole(Enum):
    """
    Statement types.
    """

    SUBJECT = 0
    PREDICATE = 1
    OBJECT = 2


# for now we want unique numbers for keys for relations and items etc (although this is not necessary)


def generate_key_numbers() -> list:
    """
    Creates a reaservoir of keynumbers, e.g. for automatically created entities. Due to the hardcoded seed value
    these numbers are stable between runs of the software, which simplifies development and debugging.

    This function is also called after unloading a module because the respective keys are "free" again

    :return:    list of integers
    """
    # passing seed (arg `x`) ensures "reproducible randomness" accross runs
    random_ng = random.Random(x=1750)
    _available_key_numbers = list(range(1000, 9999))
    random_ng.shuffle(_available_key_numbers)

    return _available_key_numbers


available_key_numbers = generate_key_numbers()


class RawQualifier:
    """
    Precursor to a real Qualifier (which is a RelationEdge) where the subject is yet unspecified
    (will be the qualified RelationEdge). Instances of this class are produced by QualifierFactory
    """

    def __init__(self, rel: Relation, obj: Union[Literal, Entity]):
        self.rel = rel
        self.obj = obj


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

    def __init__(self, relation: Relation):
        self.relation = relation

    def __call__(self, obj):
        return RawQualifier(self.relation, obj)


class RelationEdge:
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
        qualifiers: Optional[List[RawQualifier]] = None,
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

        self.key_str = f"RE{available_key_numbers.pop()}"
        self.relation = relation
        self.relation_tuple = relation_tuple
        self.role = role
        self.scope = scope
        self.corresponding_entity = corresponding_entity
        self.corresponding_literal = corresponding_literal
        self.qualifiers = []
        self._process_qualifiers(qualifiers)
        self.dual_relation_edge = None
        self.unlinked = None

        # TODO: replace this by qualifier
        self.proxyitem = proxyitem

    def __repr__(self):

        # fixme: this breaks if self.role is not a valid enum-value in (0, 2)

        res = f"RE[{self.role.name[0]}]{self.relation_tuple}"
        return res

    def _process_qualifiers(self, qlist: List[RawQualifier], scope: Optional["Entity"] = None) -> None:

        if qlist is None:
            # nothing to do
            return

        for qf in qlist:

            if isinstance(qf.obj, Entity):
                corresponding_entity = qf.obj
                corresponding_literal = None
            else:
                corresponding_entity = None
                corresponding_literal = repr(qf.obj)

            rledg = RelationEdge(
                relation=qf.rel,
                relation_tuple=(self, qf.rel, qf.obj),
                role=RelationRole.SUBJECT,
                corresponding_entity=corresponding_entity,
                corresponding_literal=corresponding_literal,
                scope=scope,
                qualifiers=None,
                proxyitem=None,
            )
            self.qualifiers.append(rledg)

    def unlink(self, *args) -> None:
        """
        Remove this RelationEdge instance from all data structures in the global data storage
        :return:
        """

        if not len(self.relation_tuple) == 3:
            raise NotImplementedError

        if self.unlinked:
            return

        subj, pred, obj = self.relation_tuple

        if self.role == RelationRole.SUBJECT:
            # ds.relation_edge_list: store a list of all (primal/subject) relation edges (to maintain the order)

            tolerant_removal(ds.relation_edge_list, self)

            subj_rel_edges: Dict[str : List[RelationEdge]] = ds.relation_edges[subj.short_key]
            tolerant_removal(subj_rel_edges.get(pred.short_key, []), self)

            # ds.relation_relation_edges: for every relation key stores a list of relevant relation-edges
            # (check before accessing the *defaultdict* to avoid to create a key just by looking)
            if pred.short_key in ds.relation_relation_edges:
                tolerant_removal(ds.relation_relation_edges.get(pred.short_key, []), self)

        elif self.role == RelationRole.OBJECT:
            assert isinstance(obj, Entity)
            obj_rel_edges: Dict[str : List[RelationEdge]] = ds.inv_relation_edges[obj.short_key]
            # (check before accessing, see above)
            if pred.short_key in obj_rel_edges:
                tolerant_removal(obj_rel_edges[pred.short_key], self)
        else:
            msg = f"Unexpected .role attribute: {self.role}"
            raise ValueError(msg)

        # this prevents from infinite recursion
        self.unlinked = True
        if self.dual_relation_edge is not None:
            self.dual_relation_edge.unlink()


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

    # get uppermost __MOD_ID__ from frame stack
    mod_id = get_mod_id_list_by_inspection().pop()

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

    rel = Relation(rel_key, **new_kwargs)
    assert rel_key not in ds.relations
    ds.relations[rel_key] = rel
    ds.entities_created_in_mod[mod_id].append(rel_key)
    return rel


def create_builtin_item(*args, **kwargs) -> Item:
    itm = create_item(*args, **kwargs)
    ds.builtin_entities[itm.short_key] = itm
    return itm


def create_builtin_relation(*args, **kwargs) -> Relation:
    rel = create_relation(*args, **kwargs)
    ds.builtin_entities[rel.short_key] = rel
    return rel


def generate_new_key(prefix, prefix2=""):

    assert prefix in ("I", "R")

    while True:
        key = f"{prefix}{prefix2}{available_key_numbers.pop()}"
        try:
            ds.get_entity(key)
        except KeyError:
            # the key was new -> now problem
            return key
        else:
            continue


def print_new_key():
    """
    print random integer keys from the pregenerated list.

    :return:
    """

    for i in range(30):
        k = generate_new_key("I")[1:]

        print(f"supposed key:    I{k}      R{k}")


# ------------------


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
        mod_id = frame.f_globals.get("__MOD_ID__")
        if mod_id is not None:
            res.append(mod_id)
        frame = frame.f_back
        if frame is None:
            break

    return res


class Context:
    """
    Container class for context definitions
    """

    def __init__(self, *args, **kwargs):
        pass


def unload_mod(mod_id: str, strict=True) -> None:
    """
    Delete all references to entities comming from a module with `mod_id`

    :param mod_id:  str; key string like "M1234"
    :param strict:  boolean; raise Exception if module seems be not loaded

    :return:        None
    """

    # TODO: This might to check dependencies in the future

    entity_keys: List[str] = ds.entities_created_in_mod.pop(mod_id)

    if not entity_keys and strict:
        msg = f"Seems like no entities from {mod_id} have been loaded. This is unexpected."
        raise KeyError(msg)

    for ek in entity_keys:
        _unlink_entity(ek)
        assert ek not in ds.relation_relation_edges.keys()

    intersection_set = set(entity_keys).intersection(ds.relation_relation_edges.keys())

    msg = "Unexpectedly some of the entity keys are still present"
    assert len(intersection_set) == 0, msg

    ds.mod_path_mapping.remove_pair(key_a=mod_id)


def _unlink_entity(ek: str) -> None:
    """
    Remove the occurrence of this the respective entitiy from all relevant data structures

    :param ek:     entity key
    :return:        None
    """

    entity: Entity = ds.get_entity(ek)
    res1 = ds.items.pop(ek, None)
    res2 = ds.relations.pop(ek, None)

    if res1 is None and res2 is None:
        msg = f"No entity with key {ek} could be found. This is unexpected."
        raise KeyError(msg)

    # now delete the relation edges from the data structures
    re_dict = ds.relation_edges.pop(entity.short_key, {})
    inv_re_dict = ds.inv_relation_edges.pop(entity.short_key, {})

    # in case res1 is a scope-item we delete all corressponding relation edges, otherwise nothing happens
    ds.scope_relation_edges.pop(ek, None)

    # create a item-list of all RelationEdges instances where `ek` is involved either as subject or object
    re_item_list = list(re_dict.items()) + list(inv_re_dict.items())

    for rel_key, re_list in re_item_list:
        # rel_key: key of the relation (like "R1234")
        # re_list: list of RelationEdge instances
        for re in re_list:
            re: RelationEdge
            re.unlink(ek)

    ds.relation_relation_edges.pop(ek, None)

    # during unlinking of the RelationEdges the default dicts might have been recreating some keys -> pop again
    ds.relation_edges.pop(entity.short_key, None)
    ds.inv_relation_edges.pop(entity.short_key, None)


def register_mod(mod_id):
    frame = get_caller_frame(upcount=1)
    path = os.path.abspath(frame.f_globals["__file__"])
    assert frame.f_globals.get("__MOD_ID__", None) == mod_id
    ds.mod_path_mapping.add_pair(key_a=mod_id, key_b=path)


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


def script_main(fpath):
    IPS()
