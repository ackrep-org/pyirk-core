"""
Core module of pyerk
"""
import os
from collections import defaultdict
from dataclasses import dataclass
import inspect
import types
import abc
import copy
from enum import Enum, unique
import re
from addict import Dict as attr_dict
from typing import Dict, Union
import yaml

from . import auxiliary as aux

from ipydex import IPS, activate_ips_on_exception


activate_ips_on_exception()


"""
    TODO:
    create statements ✓
    rename kerl → ERK (easy representation of knowledge) ✓ 
    clean up and removal of obsolete code
    rename R2__has_definition to R2__has_description  
    autocompletion assistent (web based, with full text search in labels and definitions)
        - basic interface ✓
        - simple data actualization 
    Lyapunov stability theorem
    visualizing the results
    has implementation (application to actual instances)
    SPARQL interface
    
    
    SSD (sequential semantic documents) (stalled)
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


class EntityRelation:
    """
    This class models the application of a relation to an entity.
    """

    def __init__(self, entity, relation):
        """

        :param entity:          The entity to which self is assigned
        :param relation:        The actual relation object
        """
        self.entity = entity
        self.relation = relation
        self.store = []

    def __call__(self, arg) -> None:
        """
        Interpret a call as an assingment to store.

        :param arg:
        :return:
        """
        self.store.append(arg)


class Entity(abc.ABC):
    """
    Abstract parent class for both Relations and Items.

    Do not forget to call self.__post_init__ at the end of __init__ in subclasses.
    """

    short_key: str = None

    def __init__(self):
        # this will hold mappings like "R1234": EntityRelation(..., R1234)
        self._rel_dict = {}
        self._method_prototypes = []
        self.relation_dict = {}
        self.reltarget_dict = {}

    def __call__(self, adhoc_label):
        # returning self allows to use I1234 and I1234("human readable item name") interchageably
        # (once the object is created)

        # TODO: check consistency between adhoc_label and self.label
        return self

    def __getattr__(self, attr_name):
        try:
            return self.__dict__[attr_name]
        except KeyError:
            pass
        res = process_key_str(attr_name)
        if not res.etype == EType.RELATION:
            msg = f"Unexpected attribute name: '{attr_name}'"
            raise AttributeError(msg)

        try:
            etyrel = self._rel_dict[res.short_key]
        except KeyError:
            msg = f"'{type(self)}' object has no attribute '{res.short_key}'"
            raise AttributeError(msg)
            # general_relation = ds.relations[res.short_key]
            # etyrel = EntityRelation(entity=self, relation=general_relation)
            # self._rel_dict[res.short_key] = etyrel
        return etyrel

    def __post_init__(self):
        # for a solution how to automate this see
        # https://stackoverflow.com/questions/55183333/how-to-use-an-equivalent-to-post-init-method-with-normal-class
        self._perform_inheritance()

    def _perform_inheritance(self):

        # this relates to R4__instance_of defined below
        parent_class: Entity
        try:
            parent_class = self.R4
        except AttributeError:
            parent_class = None

        if parent_class is not None:
            for func in parent_class._method_prototypes:
                self.add_method(func)

    def add_method(self, func):
        """
        Add a method to this instance (self). If there are R4 relations pointing from child items to self,
        this method is also inherited to those child items.

        :param func:
        :return:
        """
        self.__dict__[func.__name__] = types.MethodType(func, self)
        self._method_prototypes.append(func)

    def set_relation(self, relation, *args):
        """
        Allows to add a relation after the item was created.

        :param relation:   Relation
        :param args:
        :return:
        """

        if isinstance(relation, Relation):
            if not len(args) == 1:
                raise NotImplementedError
            self._set_relation(relation.short_key, *args)
        else:
            raise NotImplementedError

    def _set_relation(self, rel_key: str, rel_content: object) -> None:

        rel = ds.relations[rel_key]
        prk = process_key_str(rel_key)

        # set the relation to the object
        setattr(self, rel_key, rel_content)

        # store relation for later usage
        self.relation_dict[rel_key] = rel
        self.reltarget_dict[rel_key] = ProcessedDictValue(vtype=prk.vtype, content=rel_content)


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

        # for every entity key store a list of its relation-edges
        self.relation_edges = defaultdict(list)

    def save_entity_snapshot(self, entity: Entity, stm_key: int):
        """
        Saves a copy of the entity to the versioned_entities store.

        :param entity:
        :param stm_key:
        :return:
        """

        copied_entity = copy.copy(entity)
        self.versioned_entities[copied_entity.short_key].set(stm_key, copied_entity)


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


@dataclass
class ProcessedDictValue:
    """
    Container for processed statement key
    """

    vtype: VType = None
    content: object = None


@dataclass
class ProcessedInnerDict:
    """
    Container for processed inner dict of a statement dict
    """

    relation_dict: Dict[str, "Relation"] = None
    reltarget_dict: Dict[str, ProcessedDictValue] = None


class AbstractStatement:
    """
    Common ancestor of all statements
    """
    def __init__(self, label):
        self.label = label
        self.processed_key = None

        # short key of the subject
        self.short_key = None

        # key of the statement
        self.stm_key = None
        self.stype = SType.UNDEFINED

    def __repr__(self):
        res = f"<{type(self)} {self.short_key}: {self.stype.name}"
        return res


class RawStatement(AbstractStatement):
    """
    Class representing an (quite) unprocessed statement (except the key).
    """
    def __init__(self, raw_stm_dict: dict, label=None):
        super().__init__(label=label)
        assert isinstance(raw_stm_dict, dict)

        self.label = label
        self.raw_statement = raw_stm_dict
        self.raw_key, self.raw_value = unpack_l1d(raw_stm_dict)

        self.processed_key = process_key_str(self.raw_key)
        self.short_key = self.processed_key.short_key

        self.stype = self.processed_key.stype


class SemanticStatement(AbstractStatement):
    """
    Class representing a processed statement.
    """

    def __init__(self, raw_statement: RawStatement, label=None):
        super().__init__(label=label)
        assert isinstance(raw_statement, RawStatement)

    # TODO: implement something like qualifiers: https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial#Qualifiers


def unpack_l1d(l1d: Dict[str, object]):
    assert len(l1d) == 1
    return tuple(*l1d.items())


def process_key_str(key_str: str) -> ProcessedStmtKey:

    res = ProcessedStmtKey()

    # prepare regular expressions
    re_itm = re.compile(r"^(I\d+)_?_?.*$")
    re_rel = re.compile(r"^(R\d+)_?_?.*$")

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


def process_raw_value(raw_value: YAML_VALUE, stm_key) -> ProcessedDictValue:

    res = ProcessedDictValue()
    if isinstance(raw_value, str):
        # it might be a key -> check
        processed_key = process_key_str(raw_value)
        if processed_key.etype is not EType.LITERAL:
            res.vtype = VType.ENTITY
            res.content = get_entity(processed_key.short_key, stm_key)

        else:
            res.vtype = VType.LITERAL
            res.content = raw_value
    else:
        msg = "List, dict etc not yet implemented."
        raise NotImplementedError(msg)

    return res


def get_entity(short_key, stm_key):
    """
    Returns the object corresponding to the pair (short_key, stm_key). If it does not exist return a FutureEntity.

    :param short_key:
    :param stm_key:
    :return:
    """

    res = ds.builtin_entities.get(short_key, None)
    if res is not None:
        return res

    raise NotImplementedError



# noinspection PyShadowingNames
class Item(Entity):
    def __init__(self, key_str: str, **kwargs):
        super().__init__()

        res = process_key_str(key_str)
        assert res.etype == EType.ITEM

        self.short_key = res.short_key
        self._references = None

        for key, value in kwargs.items():
            self._set_relation(key, value)

        self.__post_init__()

    def __repr__(self):
        R1 = getattr(self, "R1", "no label")
        return f'<Item {self.short_key}("{R1}")>'

    def get_relations(self):
        """
        Return all relations where this item is either subject (argument) or object (result)
        :return:
        """
        pass


# noinspection PyShadowingNames
def create_item(key_str: str = "", **kwargs) -> Item:
    """

    :param key_str:     "" or unique key of this item (something like `I1234`)
    :param _references: versioned references of relations
    :param kwargs:      further relations

    :return:        newly created item
    """

    if key_str == "":
        item_key = get_key_str_by_inspection()
    else:
        item_key = key_str

    mod_id = get_mod_name_by_inspection()

    new_kwargs = {}
    for dict_key, value in kwargs.items():
        processed_key = process_key_str(dict_key)

        if processed_key.etype != EType.RELATION:
            msg = f"unexpected key: {dict_key} during creation of item {item_key}."
            raise ValueError(msg)

        new_kwargs[processed_key.short_key] = value

    itm = Item(item_key, **new_kwargs)
    assert item_key not in ds.items, f"Problematic key: {item_key}"
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
        for key, value in kwargs.items():
            setattr(self, key, value)

        self.__post_init__()

    def __repr__(self):
        R1 = getattr(self, "R1", "no label").replace(" ", "_")
        return f"<Relation {self.short_key}__{R1}>"


def create_relation(key_str: str = "", **kwargs) -> Relation:
    """

    :param key_str:     "" or unique key of this item (something like `I1234`)
    :param kwargs:      further relations

    :return:        newly created relation
    """

    if key_str == "":
        rel_key = get_key_str_by_inspection()
    else:
        rel_key = key_str

    mod_id = get_mod_name_by_inspection()

    new_kwargs = {}
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


def print_new_key(fname):
    """
    generate a new random integer and print it. Optionally check if it is already present in a file
    and generate a new one, if necessary

    :param fname:
    :return:
    """
    import random

    if fname:
        with open(fname, "r") as myfile:
            txt_data = myfile.read()
    else:
        txt_data = ""

    for i in range(30):
        while True:
            k = str(random.randint(1000, 9999))
            if k in txt_data:
                # print("collision detected -> regenerate key")
                continue
            break

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
    return lhs.strip()


def get_mod_name_by_inspection(upcount=1):
    """
    :param upcount:     int; how many frames to go up
    :return:
    """

    frame = get_caller_frame(upcount=upcount + 1)

    mod_id = frame.f_globals.get("__MOD_ID__")
    return mod_id


class Context:
    """
    Container class for context definitions
    """

    def __init__(self, *args, **kwargs):
        pass


def generic_instance(*args):
    raise NotImplementedError


def create_item_from_namespace():
    frame = inspect.currentframe()

    upcount = 1
    i = upcount
    while True:
        if frame.f_back is None:
            break
        frame = frame.f_back
        i -= 1
        if i <= 0:
            break

    fi = inspect.getframeinfo(frame)
    part1, key_str = fi.function.split("_")[:2]
    assert part1 == "create"

    key_res = process_key_str(key_str)
    assert key_res.etype in [EType.ITEM, EType.RELATION]

    try:
        res = create_item(key_str=key_res.short_key, **frame.f_locals)
    finally:
        # we should explicitly break cyclic dependencies as stated in inspect doc
        del frame

    return res


class GenericInstance:
    def __init__(self, cls):
        self.cls = cls


def instance_of(entity):
    has_super_class = getattr(entity, "R3", None) is not None
    is_instance_of_metaclass = getattr(entity, "R4", None) == I2("Metaclass")

    if (not has_super_class) and (not is_instance_of_metaclass):
        msg = f"the entity '{entity}' is not a class, and thus could not be instantiated"
        raise TypeError(msg)

    return GenericInstance(entity)


class AndOperation:
    def __init__(self, *args):
        self.args = args


def AND(*args):
    return AndOperation(*args)


class OrOperation:
    def __init__(self, *args):
        self.args = args


def OR(*args):
    return OrOperation(*args)


def unload_mod(mod_id: str, strict=True) -> None:
    """
    Delete all references to entities comming from a module with `mod_id`

    :param mod_id:  str; key string like "M1234"
    :param strict:  boolean; raise Exception if module seems be not loaded

    :return:        None
    """

    # TODO: This might to check dependencies in the future

    entity_keys = ds.entities_created_in_mod.pop(mod_id)

    if not entity_keys and strict:
        msg = f"Seems like no entities from {mod_id} have been loaded. This is unexpected."
        raise KeyError(msg)

    for ek in entity_keys:
        res1 = ds.items.pop(ek, None)
        res2 = ds.relations.pop(ek, None)

        if res1 is None and res2 is None:
            msg = f"No entity with key {ek} could be found. This is unexpected."
            raise msg

    ds.mod_path_mapping.remove_pair(key_a=mod_id)


def register_mod(mod_id):
    frame = get_caller_frame(upcount=1)
    path = os.path.abspath(frame.f_globals["__file__"])
    assert frame.f_globals.get("__MOD_ID__", None) == mod_id
    ds.mod_path_mapping.add_pair(key_a=mod_id, key_b=path)


def script_main(fpath):
    m = Manager(fpath)
    IPS()

# ------------------

# !! defining that stuff on module level makes the script slow:
# todo: move this to a separate module


__MOD_ID__ = "M1000"

R1 = create_builtin_relation("R1", R1="has label")
R2 = create_builtin_relation("R2", R1="has natural language definition")
R3 = create_builtin_relation("R3", R1="is subclass of")
R4 = create_builtin_relation("R4", R1="is instance of")
R5 = create_builtin_relation("R5", R1="is part of")
R6 = create_builtin_relation("R6", R1="has defining equation")
R7 = create_builtin_relation("R7", R1="has arity")
R8 = create_builtin_relation("R8", R1="has domain of argument 1")
R9 = create_builtin_relation("R9", R1="has domain of argument 2")
R10 = create_builtin_relation("R10", R1="has domain of argument 3")
R11 = create_builtin_relation("R11", R1="has range of result", R2="specifies the range of the result (last arg)")
R12 = create_builtin_relation("R12", R1="is defined by means of")
R13 = create_builtin_relation("R13", R1="has canonical symbol")
R14 = create_builtin_relation("R14", R1="is subset of")
R15 = create_builtin_relation("R15", R1="is element of", R2="states that arg1 is an element of arg2")
R16 = create_builtin_relation(
    key_str="R16",
    R1="has property",
    R2="relates an entity with a mathematical property",
    # R8__has_domain_of_argument_1=I4235("mathematical object"),
    # R10__has_range_of_result=...

)
R17 = create_builtin_relation(
    key_str="R17",
    R1="is subproperty of",
    R2="specifies that arg1 is a sub property of arg2"
)
R18 = create_builtin_relation("R18", R1="has usage hints", R2="specifies hints on how this relation should be used")

R19 = create_builtin_relation(
    key_str="R19",
    R1="defines method",
    R2="specifies that an entity has a special method (defined by executeable code)"
    # R10__has_range_of_result=callable !!
)


# Items

I1 = create_builtin_item("I1", R1="General Item")
I2 = create_builtin_item(
    "I2",
    R1="Metaclass",
    R2__has_natural_language_definition=(
        "Parent class for other classes; subclasses of this are also metaclasses "
        "instances are ordinary classes"
    ),
    R3__subclass_of=I1,
)

I3 = create_builtin_item("I3", R1="Field of science")
I4 = create_builtin_item("I4", R1="Mathematics", R4__instance_of=I3)
I5 = create_builtin_item("I5", R1="Engineering", R4__instance_of=I3)
I6 = create_builtin_item("I6", R1="mathematical operation", R4__instance_of=I2("Metaclass"))
I7 = create_builtin_item("I7", R1="mathematical operation with arity 1", R3__subclass_of=I6, R7=1)
I8 = create_builtin_item("I8", R1="mathematical operation with arity 2", R3__subclass_of=I6, R7=2)
I9 = create_builtin_item("I9", R1="mathematical operation with arity 3", R3__subclass_of=I6, R7=3)
I10 = create_builtin_item(
    "I10", R1="abstract metaclass",
    R3__subclass_of=I2,
    R2__has_natural_language_definition=(
        "Special metaclass. Instances of this class are abstract classes that should not be instantiated, "
        "but subclassed instead."
    )
)
I11 = create_builtin_item(
    key_str="I11",
    R1="mathematical property",
    R2__has_definition="base class for all mathematical properties",
    R4__instance_of=I2("Metaclass"),
    R18__has_usage_hints=(
        "Actual properties are instances of this class (not subclasses). "
        "To create a taxonomy-like structure the relation R17__is_sub_property_of should be used."
   )
)

I12 = create_builtin_item(
    key_str="I12",
    R1__has_label="mathematical object",
    R2__has_definition="base class for any knowledge object of interrest in the field of mathematics",
    R4__instance_of=I2("Metaclass"),
)

I13 = create_builtin_item(
    key_str="I13",
    R1__has_label="mathematical set",
    R2__has_definition="mathematical set",
    R3__subclass_of=I12("mathematical object"),
)


I14 = create_builtin_item(
    key_str="I14",
    R1__has_label="mathematical proposition",
    R2__has_definition="general mathematical proposition",
    # R3__subclass_of=I7723("general mathematical proposition")
)


I15 = create_builtin_item(
    key_str="I15",
    R1__has_label="implication proposition",
    R2__has_definition="proposition, where the premise (if-part) implies the assertion (then-part)",
    R3__subclass_of=I14("mathematical proposition")
)


def set_context_vars(self, **kwargs):
    for key, value in kwargs.items():
        self.__dict__[key] = value


I15.add_method(set_context_vars)
del set_context_vars


def set_context_relations(self, *args, **kwargs):
    context_relations = getattr(self, "_context_relations", [])

    # todo: check nested types of args; should be tuple of tuples, where inner tuples have len > 2
    context_relations.extend(args)
    self._context_relations = context_relations


I15.add_method(set_context_relations)
del set_context_relations


def set_premise(self, arg):
    self._premise = arg


I15.add_method(set_premise)
del set_premise


def set_assertion(self, arg):
    self._assertion = arg


I15.add_method(set_assertion)
del set_assertion


def set_assertions(self, *args):
    self._assertion = AND(*args)


I15.add_method(set_assertions)
del set_assertions


I16 = create_builtin_item(
    key_str="I16",
    R1__has_label="equivalence proposition",
    R2__has_definition="proposition, which establishes the equivalence of two or more statements",
    R3__subclass_of=I14("mathematical proposition")
)
