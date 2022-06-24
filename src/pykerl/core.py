"""
Core module of pykerl
"""
from collections import defaultdict
from dataclasses import dataclass
import abc
import copy
from enum import Enum, unique
import re
from addict import Dict as attr_dict
from typing import Dict, Union
import yaml
from ipydex import IPS, activate_ips_on_exception


activate_ips_on_exception()


"""
    TODO:
    create statements ✓
    extend statements [ ]
    rename kerl → ERK (easy representation of knowledge)
    SSD (sequential semantic documents)
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
    Abstract parent class for both Relations and Items
    """

    short_key: str = None

    @abc.abstractmethod
    def __init__(self): ...


class PatchyPseudoDict:
    """
    Assumes keys to be numeric.

    Setting value for key K:
        like normal dict + additionally save K in an ordered list L of keys.
    Getting value for key K: return self[Q] where Q is the largest element of L with Q <= K.
    """

    def __init__(self):
        # do not allow initialization with data in the constructor
        self.key_list = []
        self.store = {}

    def set(self, key: int, value: object) -> None:
        if not isinstance(key, int):
            msg = f"Expected int but got {type(key)}"
            raise TypeError(msg)
        if not self.key_list:
            self.key_list.append(key)
            self.store[key] = value
            return

        last_key = self.key_list[-1]
        if key == last_key:
            self.store[key] = value
            return

        # ensure ordering
        # (this is for simplicity and could be extended in the future)
        if not key > last_key:
            msg = f"new key ({key}) must be bigger than last_ley ({last_key})."
            raise ValueError(msg)
        self.key_list.append(key)
        self.store[key] = value

    def get(self, key):
        if not isinstance(key, int):
            msg = f"Expected int but got {type(key)}"
            raise TypeError(msg)
        if not self.key_list:
            raise KeyError(key)

        # there is no data for such a small key
        if key < self.key_list[0]:
            msg = f"The smallest available key is {self.key_list[0]} but {key} was provided."
            raise KeyError(msg)

        # iterate from behind
        # this probably could be speed up by some clever tricks
        for q in reversed(self.key_list):
            if q <= key:
                return self.store[q]

        # if this is reached something unexpected happened
        msg = f"Could not find matching internal key for provided key {key}. This is unexpected."
        raise ValueError(msg)


class DataStore:
    """
    Provides objects to store all data that would be global otherwise
    """

    def __init__(self):
        self.items = attr_dict()
        self.relations = attr_dict()
        self.statements = attr_dict()

        # this dict contains everything which is predefined by hardcoding
        self.builtin_entities = attr_dict()

        # this dict contains a PatchyPseudoDict for every short key to store different versions of the same object
        self.versioned_entities = defaultdict(PatchyPseudoDict)

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


class Manager(object):
    """
    Omniscient Master object controlling knowledge representation.
    Will probably be refactored in the future.
    """

    def __init__(self, fpath: str):

        self.name_mapping = dict(**ds.items, **ds.relations)

        self.ignore_list = [
            "meta",
            "iri",
        ]

        self.raw_data = self.load_yaml(fpath)

        # fill dict of all statements
        self.raw_stmts_dict: Dict[int, RawStatement] = dict()
        self.process_statements_stage1(self.raw_data)

        self.process_all_stmts()

        # simplify access
        self.n = attr_dict(self.name_mapping)

    @staticmethod
    def load_yaml(fpath):
        with open(fpath, "r") as myfile:
            raw_data = yaml.safe_load(myfile)

        return raw_data

    def process_statements_stage1(self, raw_data: dict) -> None:
        """
        Iterare over the the statement list, preprocess the keys and fill the raw_stmts_dict with content like
        `{0: <RawStatment0>, ...}
        :param raw_data:
        :return:
        """

        # iterate over statements, represented as list of length_1_dicts (`stmd`)
        # Every stmd is of the form {stm_key: stm_value}

        next_label = None
        stmt_counter = 0
        for stmd in raw_data:
            key, value = unpack_l1d(stmd)
            if key in self.ignore_list:
                continue
            if key == "LABEL":
                next_label = value
                continue

            raw_stm = RawStatement(stmd, next_label)
            self.raw_stmts_dict[stmt_counter] = raw_stm
            stmt_counter += 1

    def process_all_stmts(self) -> None:
        """

        :return:
        """

        for stm_key, raw_stm in self.raw_stmts_dict.items():
            if raw_stm.stype is SType.CREATION:
                self.process_creation_stm(raw_stm, stm_key)
            elif raw_stm.stype is SType.EXTENTION:
                self.process_extension_stm(raw_stm, stm_key)
                break
            else:
                msg = f"unexpected type of raw statement with key {stm_key} ({raw_stm}): {raw_stm.stype}"
                raise ValueError(msg)

    def process_extension_stm(self, raw_stm: RawStatement, stm_key):
        """

        :param stm_key:
        :param raw_stm:
        :return:
        """

        if raw_stm.processed_key.etype is EType.ITEM:
            short_key = raw_stm.processed_key.short_key
            item = ds.items[short_key]
            processed_inner_obj = self.process_inner_obj(raw_stm.raw_value, stm_key)
            item.apply_extension_statement(processed_inner_obj)

    def process_creation_stm(self, raw_stm: RawStatement, stm_key):
        """

        :param stm_key:
        :param raw_stm:
        :return:
        """

        if raw_stm.processed_key.etype is EType.ITEM:
            processed_inner_obj = self.process_inner_obj(raw_stm.raw_value, stm_key)
            short_key = raw_stm.processed_key.short_key
            item = create_item_from_processed_inner_obj(short_key, processed_inner_obj)
            ds.save_entity_snapshot(item, stm_key)
        elif raw_stm.processed_key.etype is EType.RELATION:
            raise NotImplementedError
        else:
            msg = f"unexpected key type: {raw_stm.processed_key.etype} during processing of statement {raw_stm}."
            raise ValueError(msg)

    def process_inner_obj(self, raw_inner_obj: dict, stm_key: int) -> ProcessedInnerDict:
        """

        :param raw_inner_obj:   dict like {"R1__has_label": "dynamical system"}
        :param stm_key:

        :return:                ProcessedInnerDict
        """
        assert isinstance(raw_inner_obj, dict)

        res = ProcessedInnerDict()

        # stores the versioned state of the relation object
        res.relation_dict = {}

        # stores the versioned (if not literal) state of the relation target of the triple
        # (<subject> <relation> <reltarget>) (Note: we are avoiding the ambiguous term 'object' here)
        res.reltarget_dict = {}

        for key, value in raw_inner_obj.items():
            processed_key = process_key_str(key)
            assert processed_key.etype is EType.RELATION
            assert processed_key.stype is not SType.CREATION

            # get versioned relation
            relation_object = get_entity(processed_key.short_key, stm_key)
            res.relation_dict[processed_key.short_key] = relation_object

            # process the relation target
            processed_value = process_raw_value(value, stm_key)
            res.reltarget_dict[processed_key.short_key] = processed_value

        assert len(res.relation_dict) == len(res.relation_dict)
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


class FutureEntity:
    """
    Objects of this class serve as placeholder to reference Entities which will be defined later in the sequence of
    statements.
    """
    def __init__(self, short_key, stm_key):
        self.short_key = short_key
        self.stm_key = stm_key


# noinspection PyShadowingNames
class Item(Entity):
    def __init__(self, item_key: str, **kwargs):
        super().__init__()

        self.short_key = item_key
        self._references = None
        self.relation_dict = {}
        self.reltarget_dict = {}
        for key, value in kwargs.items():
            self._set_relation(key, value)

    def __repr__(self):
        R1 = getattr(self, "R1", "no label").replace(" ", "_")
        return f"<Item {self.short_key} ({R1})>"

    def _set_relation(self, rel_key, rel_content):

        rel = ds.relations[rel_key]
        prk = process_key_str(rel_key)

        # set the relation to the object
        setattr(self, rel_key, rel_content)

        # store relation for later usage
        self.relation_dict[rel_key] = rel
        self.reltarget_dict[rel_key] = ProcessedDictValue(vtype=prk.vtype, content=rel_content)

    def create_copy(self):
        NotImplementedError



    def apply_extension_statement(self, processed_inner_obj: ProcessedInnerDict):

        for rel_key, rel in processed_inner_obj.relation_dict.items():
            rel_target = processed_inner_obj.reltarget_dict[rel_key]

            # TODO: decide whether to support overwriting of relations
            # make sure that the attribute is new
            attr = getattr(self, rel_key, None)
            assert attr is None
            setattr(self, rel_key, rel_target.content)

            IPS()


# noinspection PyShadowingNames
def create_item(item_key: str, **kwargs) -> Item:
    """

    :param item_key:    unique key of this item (something like `I1234`)
    :param _references: versioned references of relations
    :param kwargs:      further relations

    :return:        newly created item
    """

    new_kwargs = {}
    for dict_key, value in kwargs.items():
        processed_key = process_key_str(dict_key)

        if processed_key.etype != EType.RELATION:
            msg = f"unexpected key: {dict_key} during creation of item {item_key}."
            raise ValueError(msg)

        new_kwargs[processed_key.short_key] = value

    itm = Item(item_key, **new_kwargs)
    assert item_key not in ds.items
    ds.items[item_key] = itm
    return itm


def create_item_from_processed_inner_obj(item_key: str, pio: ProcessedInnerDict) -> Item:

    new_kwargs = {}
    for key, processed_value in pio.reltarget_dict.items():
        new_kwargs[key] = processed_value.content

    itm = Item(item_key, **new_kwargs)

    itm._relations = pio
    assert item_key not in ds.items
    ds.items[item_key] = itm

    return itm


# noinspection PyShadowingNames
class Relation(Entity):
    def __init__(self, rel_key, **kwargs):
        super().__init__()

        # set label
        self.short_key = rel_key
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        R1 = getattr(self, "R1", "no label").replace(" ", "_")
        return f"<Relation {self.short_key}__{R1}>"


def create_relation(rel_key, **kwargs) -> Relation:

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


# !! defining that stuff on module level makes the script slow:


R1 = create_builtin_relation("R1", R1="has label")
R2 = create_builtin_relation("R2", R1="has natural language definition")
R3 = create_builtin_relation("R3", R1="subclass of")
R4 = create_builtin_relation("R4", R1="instance of")
R5 = create_builtin_relation("R5", R1="part of")
R6 = create_builtin_relation("R6", R1="has defining equation")
R7 = create_builtin_relation("R7", R1="has arity")
R8 = create_builtin_relation("R8", R1="has domain of argument 1")
R9 = create_builtin_relation("R9", R1="has domain of argument 2")
R10 = create_builtin_relation("R10", R1="has domain of argument 3")
R11 = create_builtin_relation("R11", R1="has range of result")
R12 = create_builtin_relation("R12", R1="is defined by means of")

I1 = create_builtin_item("I1", R1="General Item")
I2 = create_builtin_item(
    "I2",
    R1="Metaclass",
    R2__has_natural_language_definition=(
        "Parent class for other classes; subclasses of this are also metaclasses"
        "instances are ordinary classes",
    ),
    R3__subclass_of=I1,
)

I3 = create_builtin_item("I3", R1="Field of science")
I4 = create_builtin_item("I4", R1="Mathematics", R4__instance_of=I3)
I5 = create_builtin_item("I5", R1="Engineering", R4__instance_of=I3)
I6 = create_builtin_item("I6", R1="mathematical operation", R4__instance_of=I2)
I7 = create_builtin_item("I7", R1="mathematical operation with arity 1", R3__subclass_of=I6, R7=1)
I8 = create_builtin_item("I8", R1="mathematical operation with arity 2", R3__subclass_of=I6, R7=2)
I9 = create_builtin_item("I9", R1="mathematical operation with arity 3", R3__subclass_of=I6, R7=3)
I10 = create_builtin_item(
    "I10", R1="abstract metaclass",
    R3__subclass_of=I2,
    R2__has_natural_language_definition=(
        "Special metaclass. Instances of this class are abstract classes that should not be instantiated, ",
        "but subclassed instead."
    )
)


def script_main(fpath):
    m = Manager(fpath)
    IPS()
