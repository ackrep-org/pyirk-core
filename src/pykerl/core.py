"""
Core module of pykerl
"""
from collections import defaultdict
import re
from addict import Dict as attr_dict
from typing import Dict
import yaml
from ipydex import IPS, activate_ips_on_exception
activate_ips_on_exception()


"""
1/0 TODO:
    relations als Instanzen modellieren
    innere dicts sind in Listen gekapselt -> auflösen
    natural language representation
    Sanity-check: `R1__part_of` muss einen Fehler werfen
    content: dynamical_system can_be_represented_by mathematical_model
"""


class Entity:
    """
    Abstract parent class for both Relations and Items
    """
    pass



class RegistryMeta(type):

    # TODO: rename to RELATION_REGISTRY
    _REGISTRY = {}
    ITEM_REGISTRY = {}

    def __new__(cls, name, bases, dct):
        """
        This method controls how new classes (inheriting from this one) are created
        """

        # this is the standard behavior
        new = super().__new__(cls, name, bases, dct)

        # register
        skip_registration = getattr(new, "__skip_registration", False)
        if not skip_registration:
            RegistryMeta._REGISTRY[name] =  new

        # this is standard again
        return new


def unpack_l1d(l1d: Dict[str, object]):
    assert len(l1d) == 1
    return tuple(*l1d.items())


def process_key_str(key_str: str):
    """
    Takex something like "R1023__some_relation" and returns ("R1023", "relation").
    """

    re_itm = re.compile(r"^(I\d+)_?_?.*$")
    re_rel = re.compile(r"^(R\d+)_?_?.*$")

    match_itm = re_itm.match(key_str)
    match_rel = re_rel.match(key_str)

    if match_itm:
        res = match_itm.group(1)
        typ = "item"
    elif match_rel:
        res = match_rel.group(1)
        typ = "relation"
    else:
        res = key_str
        typ = "literal"

    return res, typ


class Manager(object):
    """
    Omniscient Master object controlling knowledge representation.
    Will probably be refactored in the future.
    """
    def __init__(self, fpath: str):


        self.name_mapping = dict(**RegistryMeta._REGISTRY, **RegistryMeta.ITEM_REGISTRY)


        self.ignore_list = "meta"

        self.items = defaultdict(dict)
        self.relations = defaultdict(dict)

        self.raw_data = self.load_yaml(fpath)
        self.process_all_data()

    @staticmethod
    def load_yaml(fpath):
        with open(fpath, "r") as myfile:
            raw_data = yaml.safe_load(myfile)

        return raw_data

    def register_name(self, name: str, obj: object):

        assert name not in self.name_mapping
        self.name_mapping[name] = object

    def process_all_data(self):

        # iterate over statements (represented as top level dict)

        # stage 1: create the complete dictionaries
        for tld in self.raw_data:
            key, value = unpack_l1d(tld)
            if key in self.ignore_list:
                continue

            res, typ = self.process_key_str(key)

            if typ == "item":
                self.process_item(res, value)
            elif typ == "relation":
                self.process_relation(res, value)
                self.process_relation(res, value)
            elif typ == "literal":
                msg = f"unexpected key in yaml file: {key}"
                raise ValueError(msg)
            else:
                msg = f"unexpected result type: {typ}"
                raise ValueError(msg)

        # stage 2: create all objects

        for name in self.items.keys():
            1/0
            new_class = type(name, (Item,), {})
            self.name_mapping[name] = new_class

        for name in self.relations.keys():
            new_class = type(name, (Relation,), {})
            self.name_mapping[name] = new_class

        # now all keys exists

        # stage 3: fill internals

        # for simplicity we assume everything which does not match an object or relation
        # to be a literar value
        # TODO: introduce DOMAIN and RANGE, to make this more robust.

        for name, inner_dict in self.items.items():
            new_obj = self.name_mapping[name]
            pass

        for name, inner_dict in self.relations.items():
            new_obj = self.name_mapping[name]
            pass

    def process_inner_dict(self, data_dict: dict, referent: Entity = None):

        for key, value in data_dict.items():
            key_res, key_typ = process_key_str(key)
            value_res, value_typ = process_key_str(value)

            if key_typ == "literal":
                msg = f"unexpected key in yaml file: {key}"
                raise ValueError(msg)

            key_obj = self.name_mapping[key_res]

            # currently only relations make sense here
            assert isinstance(key_obj, Relation)


    def process_item(self, short_key, value):
        assert isinstance(value, dict)

        # TODO: assert that nothing gets overwritten
        self.items[short_key].update(**value)


    def process_relation(self, short_key, value):
        assert isinstance(value, dict)

        # TODO: assert that nothing gets overwritten
        self.relations[short_key].update(**value)



class Relation(metaclass=RegistryMeta):
    # private class variable
    __skip_registration = True


class R1(Relation):
    label = "has label"


class R2(Relation):
    label = "has natural language definition"


class R3(Relation):
    label = "subclass of"


class R4(Relation):
    label = "instance of"


class R5(Relation):
    label = "part of"


#class AbstractItem(metaclass=RegistryMeta):
    ## private class variable
    #__skip_registration = True

class Item:
    def __init__(self, R1, **kwargs):

        # set label
        self.R1 = R1
        for key, value in kwargs.items:
            setattr(self, key, value)


def new_item(name, **kwargs):

    new_kwargs = {}
    for key, value in kwargs.items():
        short_key, typ = process_key_str(key)

        if typ != "relation":
            msg = f"unexpected key: {key} during creation of item {name}."
            raise ValueError(msg)

        new_kwargs[short_key] = value

    n = Item(**new_kwargs)
    RegistryMeta.ITEM_REGISTRY[name] = n


I1 = new_item("I1", R1="General Item")
I2 = new_item("I2",
         R1="Metaclass",
         R2__has_natural_language_definition="Parent class for other classes; subclasses of this are also meta classes, instances are ordinary classes",
         R3__subclass_of=I1
         )
I3 = new_item("I3", R1="Field of science")
I4 = new_item("I4", R1="Mathematics", R4__instance_of=I3)
I5 = new_item("I5", R1="Engineering")


def script_main(fpath):

    m = Manager(fpath)

    IPS()

    print("Script successfully executed")
