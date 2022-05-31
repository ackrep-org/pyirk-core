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
    multiple assignments via list ✓
    natural language representation of ordered atomic statements
    SSD (sequential semantic documents)
    Labels (als Listeneinträge)
    DOMAIN und RANGE
    
    unittests 
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


class DataStore:
    """
    Provides objects to store all data that would be global otherwise
    """

    def __init__(self):
        self.items = {}
        self.relations = {}
        self.statements = {}


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


class Statement:
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
        self.stmts_dict = dict()
        self.process_statements(self.raw_data)

        # simplify access
        self.n = attr_dict(self.name_mapping)

    @staticmethod
    def load_yaml(fpath):
        with open(fpath, "r") as myfile:
            raw_data = yaml.safe_load(myfile)

        return raw_data

    def process_statements(self, raw_data: dict) -> None:

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

            stm = Statement(stmd, next_label)
            self.stmts_dict[stmt_counter] = stm
            stmt_counter += 1


def script_main(fpath):
    m = Manager(fpath)
    IPS()
