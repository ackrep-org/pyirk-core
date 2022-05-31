"""
Core module of pykerl
"""
# from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import re
from addict import Dict as attr_dict
from typing import Dict
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
        self.items = {}
        self.relations = {}
        self.statements = {}
        self.versioned_entities = {}


ds = DataStore()


class EType(Enum):
    """
    Entity types.
    """

    ITEM = 0
    RELATION = 1
    LITERAL = 2


class SType(Enum):
    """
    Statement types.
    """

    CREATION = 0
    EXTENTION = 1


@dataclass
class ProcessedStmtKey:
    """
    Container for processed statement key
    """

    short_key: str = None
    etype: EType = None
    stype: SType = None
    content: object = None


class RawStatement:
    """
    Class representing an (quite) unprocessed statement (except the key).
    """
    def __init__(self, raw_statement: dict, label=None):
        assert isinstance(raw_statement, dict)

        self.label = label
        self.raw_statement = raw_statement
        self.raw_key, self.raw_value = unpack_l1d(raw_statement)

        self.processed_key = process_key_str(self.raw_key)

        self.stype = self.processed_key.stype

    def __repr__(self):
        res = f"<S {self.processed_key.short_key}: {self.stype.name}"
        return res


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


class Manager(object):
    """
    Omniscient Master object controlling knowledge representation.
    Will probably be refactored in the future.
    """

    def __init__(self, fpath: str):

        self.name_mapping = dict(**ds.items, **ds.relations)

        self.ignore_list = [
            "meta",
        ]

        self.raw_data = self.load_yaml(fpath)

        # fill dict of all statements
        self.raw_stmts_dict: Dict[int, RawStatement] = dict()
        self.process_statements_stage1(self.raw_data)

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

    def process_creation_stmt(self, raw_stm: RawStatement, stm_key):
        """

        :param stm_key:
        :param raw_stm:
        :return:
        """

        if raw_stm.processed_key.etype is EType.ITEM:
            processed_inner_obj = self.process_inner_obj(raw_stm.raw_value)
            # create_item(raw_stm.processed_key.short_key)
        elif raw_stm.processed_key.etype is EType.RELATION:
            pass
        else:
            msg = f"unexpected key type: {raw_stm.processed_key.etype} during processing of statement {raw_stm}."
            raise ValueError(msg)

    def process_inner_obj(self, raw_inner_obj: dict) -> None:
        """

        :param raw_inner_obj:   dict like {"R1__has_label": "dynamical system"}
        :return:
        """
        assert isinstance(raw_inner_obj, dict)
        for key, value in raw_inner_obj.items():
            processed_key = process_key_str(self.key)
            assert processed_key.etype is EType.RELATION
            assert processed_key.stype is not SType.CREATION

            relation = self

    def get_obj(self, short_key, stm_key):
        """
        Returns the object corresponding to the pair (short_key, stm_key). If it does not exist return a FutureEntity.

        :param short_key:
        :param stm_key:
        :return:
        """




class FutureEntity:
    """
    Objects of this class serve as placeholder to reference Entities which will be defined later in the sequence of
    statements.
    """
    def __init__(self, short_key, stm_key):
        self.short_key = short_key
        self.stm_key = stm_key


class Item:
    def __init__(self, item_key: str, **kwargs):

        self.item_key = item_key
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        R1 = getattr(self, "R1", "no label").replace(" ", "_")
        return f"<Item {self.item_key}__{R1}>"


# noinspection PyShadowingNames
def create_item(item_key: str, **kwargs):
    """

    :param item_key:    unique key of this item (something like `I1234`)
    :param kwargs:      further relations

    :return:        newly created item
    """

    new_kwargs = {}
    for dict_key, value in kwargs.items():
        attr_short_key, typ = process_key_str(dict_key)

        if typ != "relation":
            msg = f"unexpected key: {dict_key} during creation of item {item_key}."
            raise ValueError(msg)

        new_kwargs[attr_short_key] = value

    n = Item(item_key, **new_kwargs)
    assert item_key not in RegistryMeta.ITEM_REGISTRY
    RegistryMeta.ITEM_REGISTRY[item_key] = n
    return n

def script_main(fpath):
    m = Manager(fpath)
    IPS()
