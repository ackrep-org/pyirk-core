import os
import re as regex
import yaml
from yaml.parser import ParserError
from ipydex import IPS
from typing import Union

from .core import Item, Relation, Entity
from . import core
from . import aux
from .builtin_entities import instance_of
from .erkloader import load_mod_from_path
from . import builtin_entities
from .auxiliary import *

__URI__ = "erk:/models"
keymanager = core.KeyManager()


ERK_ROOT_DIR = aux.get_erk_root_dir()

entity_pattern = regex.compile(r"^(I|Ra?\d+)(\[(.*)\])$")
item_pattern = regex.compile(r"^(Ia?\d+)(\[(.*)\])$")
relation_pattern = regex.compile(r"^(Ra?\d+)(\[(.*)\])$")
function_pattern = regex.compile(r"^(.+)(\(.*\))$")


def parse_ackrep(base_path: str = None) -> int:
    """parse ackrep entities. if no base path is given, entire ackrep_data repo is parsed. if path is given
    only this path is parsed.

    Args:
        base_path (str, optional): optional target path to parse. Defaults to None.

    Returns:
        int: sum of returncodes
    """
    # default path
    if base_path is None:
        base_path = os.path.join(ERK_ROOT_DIR, settings.ACKREP_DATA_REL_PATH)

    if os.path.isabs(base_path):
        ackrep_path = base_path
    else:
        ackrep_path = os.path.join(os.getcwd(), base_path)

    TEST_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "control-theory", "control_theory1.py")
    TEST_MOD_NAME = "control_theory1"

    global mod
    mod = load_mod_from_path(TEST_DATA_PATH, TEST_MOD_NAME)

    retcodes = []
    # parse entire repo
    if "ackrep_data" in os.path.split(ackrep_path)[1]:
        retcodes.append(parse_all_system_models(ackrep_path))
        retcodes.append(parse_all_problems_and_solutions(ackrep_path))

    # assume path leads to entity folder
    else:
        if "system_models" in ackrep_path:
            retcode = parse_system_model(ackrep_path)
        elif "problem_specifications" in ackrep_path or "problem_solutions" in ackrep_path:
            retcode = parse_problem_or_solution(ackrep_path)
        retcodes.append(retcode)

    return sum(retcodes)


def parse_all_problems_and_solutions(ackrep_path):
    retcodes = []
    for n in ["problem_specifications", "problem_solutions"]:
        path = os.path.join(ackrep_path, n)
        folders = os.listdir(path)
        for folder in folders:
            # skip template folder
            if folder[0] == "_":
                continue
            if not os.path.isdir(os.path.join(path, folder)):
                continue

            retcode = parse_problem_or_solution(os.path.join(path, folder))
            retcodes.append(retcode)

    # if sum(retcodes) == 0:
        # print(bgreen("All entities successfully parsed."))
    # else:
        # print(bred("Not all entities parsed, see above."))

    return sum(retcodes)


def parse_all_system_models(ackrep_path):
    retcodes = []
    system_models_path = os.path.join(ackrep_path, "system_models")
    model_folders = os.listdir(system_models_path)
    for folder in model_folders:
        # skip template folder
        if folder[0] == "_":
            continue

        retcode = parse_system_model(os.path.join(system_models_path, folder))
        retcodes.append(retcode)

    # if sum(retcodes) == 0:
    #     print(bgreen("All entities successfully parsed."))
    # else:
    #     print(bred("Not all entities parsed, see above."))

    return sum(retcodes)


def parse_problem_or_solution(entity_path: str):
    """very basic to incorporate already existing ocse tags"""
    metadata_path = os.path.join(entity_path, "metadata.yml")

    if "problem_specifications" in entity_path:
        e_type = "pspec"
        erk_class = mod.I5919["problem specification"]
    elif "problem_solutions" in entity_path:
        e_type = "psol"
        erk_class = mod.I4635["problem solution"]
    else:
        raise TypeError(f"path {entity_path} doesnt lead to prob spec or prob sol.")

    with open(metadata_path, "r") as metadata_file:
        try:
            md = yaml.safe_load(metadata_file)
        except ParserError as e:
            msg = f"Metadata file of '{os.path.split(entity_path)[1]}' has yaml syntax error, see message above."
            raise SyntaxError(msg) from e
    core.register_mod(__URI__, keymanager)
    core.start_mod(__URI__)

    entity = instance_of(erk_class, r1=md["name"], r2=md["short_description"])
    entity.set_relation(mod.R2950["has corresponding ackrep key"], md["key"])

    tags = md["tag_list"]
    # assume this is just a simple list
    for tag in tags:
        if "ocse:" in tag:
            t = instance_of(mod.I1161["old tag"], r1=tag)
            entity.set_relation(mod.R1070["has old tag"], t)
    # IPS()
    # print(entity.get_relations())
    core.end_mod()
    return 0


def parse_system_model(entity_path: str):

    metadata_path = os.path.join(entity_path, "metadata.yml")

    with open(metadata_path, "r") as metadata_file:
        try:
            md = yaml.safe_load(metadata_file)
        except ParserError as e:
            msg = f"Metadata file of '{os.path.split(entity_path)[1]}' has yaml syntax error, see message above."
            raise SyntaxError(msg) from e
    core.register_mod(__URI__, keymanager, check_uri=False)
    core.ds.uri_prefix_mapping.add_pair(__URI__, "mod")
    core.start_mod(__URI__)
    model = instance_of(mod.I7641["general system model"], r1=md["name"], r2=md["short_description"])
    model.set_relation(mod.R2950["has corresponding ackrep key"], md["key"])

    try:
        ed = md["erk_data"]
    except KeyError:
        # print(byellow(f"{md['key']}({md['name']}) has no erk_data yet."))
        core.end_mod()
        return 2

    parse_recursive(model, ed)
    # print(model.get_relations())
    # print(bgreen(f"{md['key']}({md['name']}) successfully parsed."))

    core.end_mod()
    return 0


def parse_recursive(parent: Item, d: dict):
    """recursively parse ackrep metadata
    create items and set appropriate relations"""

    for k, v in d.items():
        assert relation_pattern.match(k) is not None, f"This key ({k}) has to be a relation."
        relation = get_entity_from_string(k)
        # value is literal (number)
        if isinstance(v, (str, int, float)):
            item = handle_literal(literal=v)
            parent.set_relation(relation, item)
        # value is list
        elif isinstance(v, list):
            for entry in v:
                if isinstance(entry, (str, int, float)):
                    item = handle_literal(literal=entry)
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


def handle_literal(literal: Union[int, float, str]) -> Union[int, float, str, Item]:
    """handle yaml literal and return appropriate object (int, float, str, Item)"""

    # literal is number
    if isinstance(literal, (int, float)):
        item = literal
    # literal is string or item
    elif isinstance(literal, str):
        # TODO: how to differentiate between bad entity and regular string and function?
        # see if this is an item by examining pattern
        if item_pattern.match(literal):
            item = get_entity_from_string(literal)
        elif relation_pattern.match(literal):
            raise TypeError(f"relation result {literal} should not be another relation.")
        elif function_pattern.match(literal):
            func = getattr(builtin_entities, literal.split("(")[0])
            item = func(literal.split("(")[1].split(")")[0])
        # else its a normal string
        else:
            item = literal
    else:
        raise NotImplementedError

    return item


def handle_dict(d: dict) -> Item:
    """handle yaml dict, create new item and recusively add all its relations
    return created Item"""

    assert len(d.keys()) == 1, f"Item dictionary {d} has to have exacly one key"
    k, v = list(d.items())[0]
    assert item_pattern.match(k) is not None, f"This key ({k}) has to be an item."
    item = get_entity_from_string(k, enforce_class=True)
    msg = f"value {v} of dictionary {d} has to be another dict with relations as keys and items as values"
    assert isinstance(v, dict), msg
    parse_recursive(item, v)

    return item


def get_entity_from_string(string: str, enforce_class=False) -> Entity:
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
        raise AttributeError(f"Attribute {s} not found. Maybe there is a typo?")

    # consitency check of string ["something"] and fetched entity
    entity.idoc(string.split("[")[1].split("]")[0][1:-1])

    if isinstance(entity, Relation):
        res = entity
    elif isinstance(entity, Item):
        if enforce_class:
            # we have to determine if `entity` is a metaclass or a subclass of metaclass
            # this is relevant for entities, that have to be specified by additional relations
            has_super_class = entity.R3 is not None
            is_instance_of_metaclass = builtin_entities.is_instance_of_generalized_metaclass(entity)
            assert has_super_class or is_instance_of_metaclass, f"The item {entity} has to be a class, not an instance."

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
pyerk -pad ../../ackrep/ackrep_data/system_models/lorenz_system

"""
