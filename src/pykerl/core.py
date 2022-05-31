"""
Core module of pykerl
"""
from collections import defaultdict
import re
from addict import Dict as attr_dict
from typing import Dict
import yaml
from ipydex import IPS, activate_ips_on_exception, Container

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


class RegistryMeta(type):

    # TODO: rename to RELATION_REGISTRY
    RELATION_REGISTRY = {}
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
            RegistryMeta.RELATION_REGISTRY[name] = new

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

        self.name_mapping = dict(**RegistryMeta.RELATION_REGISTRY, **RegistryMeta.ITEM_REGISTRY)

        self.ignore_list = "meta"

        self.item_dict = defaultdict(dict)
        self.relation_dict = defaultdict(dict)

        self.raw_data = self.load_yaml(fpath)
        self.process_all_data()

        # simplify access
        self.n = attr_dict(self.name_mapping)

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

        # to store the yet unprocessed raw_data-values along with the already processed keys
        tmp_map = defaultdict(dict)
        # stage 1: create the complete dictionaries
        # raw_data is a list of length_1_dicts (top_level_dicts, `tld`).
        # Every tld has a dict as (only) value (`inner_object`).
        for tld in self.raw_data:

            key, inner_object = unpack_l1d(tld)
            if key in self.ignore_list:
                continue

            short_key, typ = process_key_str(key)

            if typ == "item":
                self.process_item(short_key, inner_object)
            elif typ == "relation":
                self.process_relation(short_key, inner_object)
                self.process_relation(short_key, inner_object)
            elif typ == "literal":
                msg = f"unexpected key in yaml file: {key}"
                raise ValueError(msg)
            else:
                msg = f"unexpected result type: {typ}"
                raise ValueError(msg)

            assert isinstance(inner_object, dict)
            tmp_map[short_key].update(**inner_object)

        # stage 2: create all objects

        for short_key in self.item_dict.keys():
            new_item = create_item(item_key=short_key)
            self.name_mapping[short_key] = new_item

        for short_key in self.relation_dict.keys():
            new_relation = create_relation(short_key)
            self.name_mapping[short_key] = new_relation

        # now all keys exists

        # stage 3: fill internals

        # for simplicity we assume everything which does not match an object or relation
        # to be a literal value
        # TODO: introduce DOMAIN and RANGE, to make this more robust.

        for short_key, inner_dict in list(self.item_dict.items()) + list(self.relation_dict.items()):
            new_obj = self.name_mapping[short_key]
            c_list = self.process_inner_dict(inner_dict)
            for c in c_list:
                if isinstance(c.key_obj, Relation):
                    setattr(new_obj, c.key_res, c.value_obj)

    def process_inner_dict(self, data_dict: dict, enforce_key_typ_in=("relation",)):
        """

        :param data_dict:
        :param enforce_key_typ_in:

        :return:      list of Containers
        """

        res = []

        for key, value in data_dict.items():
            c = Container()

            # make key canonical
            c.key_res, c.key_typ = process_key_str(key)

            # the value migt contain: a literal, a keys, or a complex object
            if isinstance(value, str):
                # key or literal
                c.value_res, c.value_typ = process_key_str(value)
            elif isinstance(value, list):
                # currently only support lists of keys
                c.value_typ = "list"
            else:
                msg = f"unexpected type of value: {type(value)}"
                raise TypeError(msg)

            if c.key_typ not in enforce_key_typ_in:
                msg = f"unexpected type of {key}: `{c.key_typ}` but expected one of {enforce_key_typ_in}"
                raise ValueError(msg)

            c.key_obj = self.name_mapping[c.key_res]

            if c.value_typ == "literal":
                # take the literal value directly
                c.value_obj = value
            elif c.value_typ == "list":
                c.value_obj = [self.name_mapping[process_key_str(elt)[0]] for elt in value]
            elif c.value_typ in ("item", "relation"):
                c.value_obj = self.name_mapping[c.value_res]

            res.append(c)

        return res


    def process_item(self, short_key, inner_object):
        assert isinstance(inner_object, dict)

        # TODO: assert that nothing gets overwritten
        self.item_dict[short_key].update(**inner_object)

    def process_relation(self, short_key, inner_object):
        assert isinstance(inner_object, dict)

        # TODO: assert that nothing gets overwritten
        self.relation_dict[short_key].update(**inner_object)


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


def create_relation(rel_key, **kwargs):

    new_kwargs = {}
    for key, value in kwargs.items():
        short_key, typ = process_key_str(key)

        if typ != "relation":
            msg = f"unexpected key: {key} during creation of item {rel_key}."
            raise ValueError(msg)

        new_kwargs[short_key] = value

    n = Relation(rel_key, **new_kwargs)
    assert rel_key not in RegistryMeta.RELATION_REGISTRY
    RegistryMeta.RELATION_REGISTRY[rel_key] = n
    return n


R1 = create_relation("R1", R1="has label")
R2 = create_relation("R2", R1="has natural language definition")
R3 = create_relation("R3", R1="subclass of")
R4 = create_relation("R4", R1="instance of")
R5 = create_relation("R5", R1="part of")


# noinspection PyShadowingNames
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


I1 = create_item("I1", R1="General Item")
I2 = create_item(
    "I2",
    R1="Metaclass",
    R2__has_natural_language_definition=(
        "Parent class for other classes; subclasses of this are also meta classes"
        "instances are ordinary classes",
    ),
    R3__subclass_of=I1,
)

I3 = create_item("I3", R1="Field of science")
I4 = create_item("I4", R1="Mathematics", R4__instance_of=I3)
I5 = create_item("I5", R1="Engineering", R4__instance_of=I3)


def script_main(fpath):

    m = Manager(fpath)

    IPS()

    print("Script successfully executed")
