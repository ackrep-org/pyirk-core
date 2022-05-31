"""
Core module of pykerl
"""
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, unique
import re
from addict import Dict as attr_dict
from typing import Dict, Union
import yaml
from ipydex import IPS, activate_ips_on_exception


activate_ips_on_exception()


"""
    TODO:
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


class Entity:
    """
    Abstract parent class for both Relations and Items
    """

    pass


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
    etype: EType = None
    stype: SType = None
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
    elif match_rel:
        res.short_key = match_rel.group(1)
        res.etype = EType.RELATION
    else:
        res.short_key = None
        res.etype = EType.LITERAL
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

        self.process_all_creation_stmts()

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

    def process_all_creation_stmts(self):
        """

        :return:
        """

        for stm_key, raw_stm in self.raw_stmts_dict.items():
            if raw_stm.stype is not SType.CREATION:
                continue
            self.process_creation_stmt(raw_stm, stm_key)
            break

    def process_creation_stmt(self, raw_stm: RawStatement, stm_key):
        """

        :param stm_key:
        :param raw_stm:
        :return:
        """

        if raw_stm.processed_key.etype is EType.ITEM:
            processed_inner_obj = self.process_inner_obj(raw_stm.raw_value, stm_key)
            short_key = raw_stm.processed_key.short_key
            item = create_item_from_processed_inner_obj(short_key, processed_inner_obj)
            ds.versioned_entities[short_key].set(stm_key, item)
        elif raw_stm.processed_key.etype is EType.RELATION:
            pass
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
class Item:
    def __init__(self, item_key: str, **kwargs):

        self.item_key = item_key
        self._references = None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        R1 = getattr(self, "R1", "no label").replace(" ", "_")
        return f"<Item {self.item_key}__{R1}>"


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
class Relation:
    def __init__(self, rel_key, **kwargs):

        # set label
        self.rel_key = rel_key
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        R1 = getattr(self, "R1", "no label").replace(" ", "_")
        return f"<Relation {self.rel_key}__{R1}>"


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
    ds.builtin_entities[itm.item_key] = itm
    return itm


def create_builtin_relation(*args, **kwargs) -> Relation:
    rel = create_relation(*args, **kwargs)
    ds.builtin_entities[rel.rel_key] = rel
    return rel


R1 = create_builtin_relation("R1", R1="has label")
R2 = create_builtin_relation("R2", R1="has natural language definition")
R3 = create_builtin_relation("R3", R1="subclass of")
R4 = create_builtin_relation("R4", R1="instance of")
R5 = create_builtin_relation("R5", R1="part of")

I1 = create_builtin_item("I1", R1="General Item")
I2 = create_builtin_item(
    "I2",
    R1="Metaclass",
    R2__has_natural_language_definition=(
        "Parent class for other classes; subclasses of this are also meta classes"
        "instances are ordinary classes",
    ),
    R3__subclass_of=I1,
)

I3 = create_builtin_item("I3", R1="Field of science")
I4 = create_builtin_item("I4", R1="Mathematics", R4__instance_of=I3)
I5 = create_builtin_item("I5", R1="Engineering", R4__instance_of=I3)


def script_main(fpath):
    m = Manager(fpath)
    IPS()
