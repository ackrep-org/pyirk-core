import os
import re as regex
import yaml
from yaml.parser import ParserError
from ipydex import IPS
from typing import Union

from .core import Item, Relation, Entity
from . import aux
from .builtin_entities import instance_of
from .erkloader import load_mod_from_path
from . import builtin_entities

ERK_ROOT_DIR = aux.get_erk_root_dir()
TEST_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "control-theory", "control_theory1.py")
TEST_MOD_NAME = "control_theory1"

mod = load_mod_from_path(TEST_DATA_PATH, TEST_MOD_NAME)

entity_pattern = regex.compile(r"^(I|Ra?\d+)(\[(.*)\])$")
item_pattern = regex.compile(r"^(Ia?\d+)(\[(.*)\])$")
relation_pattern = regex.compile(r"^(Ra?\d+)(\[(.*)\])$")


def parse_ackrep(path: str):

    if os.path.isabs(path):
        ackrep_path = path
    else:
        ackrep_path = os.path.join(os.getcwd(), path)

    # TODO: implement walk
    # for all system models ----------------------------------------------------
    system_models_path = os.path.join(ackrep_path, "system_models")
    model_folders = os.listdir(system_models_path)
    for folder in model_folders:
        # skip template folder
        if folder[0] == "_":
            continue

        metadata_path = os.path.join(system_models_path, folder, "metadata.yml")

        with open(metadata_path, "r") as metadata_file:
            try:
                md = yaml.safe_load(metadata_file)
            except ParserError as e:
                msg = f"Metadata file of '{folder}' has yaml syntax error, see message above."
                raise SyntaxError(msg) from e

        model = instance_of(mod.I7641["general system model"], r1=md["name"], r2=md["short_description"])
        model.set_relation(mod.R2950["has corresponding ackrep key"], md["key"])

        try:
            ed = md["erk_data"]
            parse_recursive(model, ed)
            print(model.get_relations())
        except KeyError:
            print(f"{md['key']}({md['name']}) has no erk_data yet.")

    return 0


def parse_recursive(parent: Item, d: dict):
    """recursively parse ackrep metadata
    create items and set appropriate relations"""

    for k, v in d.items():
        assert relation_pattern.match(k) is not None, f"This key ({k}) has to be a relation."
        relation = get_entity_from_string(k)
        # value is literal (number)
        if isinstance(v, (str, int, float)):
            item = handle_literal(obj=v)
            parent.set_relation(relation, item)
        # value is list
        elif isinstance(v, list):
            for entry in v:
                if isinstance(entry, (str, int, float)):
                    item = handle_literal(obj=entry)
                elif isinstance(entry, dict):
                    item = handle_dict(entry)
                elif isinstance(entry, list):
                    msg = f"the result of a relation can be a list. Though the list entries (here {entry}) \
                        have to be literals or dicts, not lists."
                    raise TypeError(msg)
                else:
                    raise NotImplementedError
                parent.set_relation(relation, item)
        # value is dict
        elif isinstance(v, dict):
            item = handle_dict(v)
            parent.set_relation(relation, item)
        else:
            raise TypeError(f"value {v} has unrecognized type {type(v)}.")


def handle_literal(obj: Union[int, float, str]) -> Union[int, float, str, Item]:
    """handle yaml literal and return appropriate object (int, float, str, Item)"""

    # literal is number
    if isinstance(obj, (int, float)):
        item = obj
    # literal is string or item
    elif isinstance(obj, str):
        # TODO: how to differentiate between bad entity and regular string
        # see if this is an item by examining pattern
        if item_pattern.match(obj):
            item = get_entity_from_string(obj)
        elif relation_pattern.match(obj):
            raise TypeError(f"relation result {obj} should not be another relation.")
        # else its a normal string
        else:
            item = obj
    else:
        raise NotImplementedError

    return item


def handle_dict(d: dict) -> Item:
    """handle yaml dict, create new item and recusively add all its relations
    return created Item"""

    assert len(d.keys()) == 1, f"Item dictionary {d} has to have exacly one key"
    k, v = list(d.items())[0]
    assert item_pattern.match(k) is not None, f"This key ({k}) has to be an item."
    item = get_entity_from_string(k)
    parse_recursive(item, v)

    return item


def get_entity_from_string(string: str) -> Entity:
    """search mod and builtin_entities for attribute s and return this entity

    Args:
        mod (_type_): external module
        s (str): entity string

    Returns:
        Entity:
    """
    s = string.split("[")[0]
    entity = None
    # try builtin entities first
    try:
        entity = getattr(builtin_entities, s)
    except AttributeError:
        pass

    # try imported modules (e.g. erk-data/control_theory1.py)
    try:
        entity = getattr(mod, s)
    except AttributeError:
        pass

    if entity is None:
        raise AttributeError(f"Attribute {s} not found.")

    # consitency check of string ["something"] and fetched entity
    entity.idoc(string.split("[")[1].split("]")[0][1:-1])

    if isinstance(entity, Relation):
        res = entity
    elif isinstance(entity, Item):
        # if entity is class
        try:
            return builtin_entities.instance_of(entity)
        # if entity is already instance
        except TypeError:
            res = entity
    else:
        raise TypeError

    return res


"""
usefull commands
pyerk -pad ../../ackrep/ackrep_data

"""
