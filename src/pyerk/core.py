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
import copy
from enum import Enum, unique
import re as regex
from addict import Dict as attr_dict
from typing import Dict, Union, List, Iterable
import yaml

from . import auxiliary as aux

from ipydex import IPS, activate_ips_on_exception


activate_ips_on_exception()


"""
    TODO:
    
    model sets as type? and elements as instances?
    manually trigger reload in gui

    Caylay-Hamilton-Theorem
    qualifier rleations, e.g. for universal quantification
         
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

    def _perform_inheritance(self):

        # this relates to R4__instance_of defined below
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

        relation = ds.relations[rel_key]

        # this assumes the relation tuple to be a triple (sub, rel, obj)
        res = [re.relation_tuple[2] for re in relation_edges if re.role is RelationRole.SUBJECT]

        # R22__is_functional
        if relation.R22:
            if len(res) == 0:
                return None
            else:
                assert len(res) == 1
                return res[0]
        else:
            return res

    @classmethod
    def add_method_to_class(cls, func):
        setattr(cls, func.__name__, func)

    def add_method(self, func):
        """
        Add a method to this instance (self). If there are R4 relations pointing from child items to self,
        this method is also inherited to those child items.

        :param func:
        :return:
        """
        self.__dict__[func.__name__] = types.MethodType(func, self)
        self._method_prototypes.append(func)

    def set_relation(self, relation: Union["Relation", str], *args, scope: "Entity" = None) -> None:
        """
        Allows to add a relation after the item was created.

        :param relation:    Relation-Entity (or its short_key)
        :param args:        target (object) of the relation
        :param scope:       Entity for the scope in which the relation is defined
        :return:
        """

        if isinstance(relation, str):
            # assume we got the short key of the relation
            relation = ds.get_entity(relation)

        if isinstance(relation, Relation):
            if not len(args) == 1:
                raise NotImplementedError
            arg0 = args[0]
            if isinstance(arg0, (tuple, list)):
                for elt in arg0:
                    self._set_relation(relation.short_key, elt, scope=scope)
            elif isinstance(arg0, str):
                self._set_relation(relation.short_key, arg0, scope=scope)
            elif isinstance(arg0, Iterable):
                msg = f"Unsupported iterable type ({type(arg0)}) of {arg0}, while setting relation {relation.short_key}"
                raise TypeError(msg)
            else:
                self._set_relation(relation.short_key, *args, scope=scope)
        else:
            raise NotImplementedError

    def _set_relation(self, rel_key: str, rel_content: object, scope: "Entity" = None) -> None:

        rel = ds.relations[rel_key]
        prk = process_key_str(rel_key)

        # set the relation to the object
        setattr(self, rel_key, rel_content)

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
            )
            # ds.set_relation_edge(rel_content.short_key, rel.short_key, inv_rledg)
            tmp_list = ds.inv_relation_edges[rel_content.short_key][rel.short_key]

            # TODO: maybe check length here for inverse functional
            tmp_list.append(inv_rledg)


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

    def get_entity(self, short_key) -> Entity:
        if res := self.relations.get(short_key):
            return res
        if res := self.items.get(short_key):
            return res
        else:
            msg = f"Could not find entity with key {short_key}"
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
            assert not relation.R22
            inner_obj.append(re_object)

        else:
            msg = (
                f"unexpected type ({type(inner_obj)}) of dict content for entity {entity_key} and "
                f"relation {relation_key}. Expected list or None"
            )


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
    re_itm = regex.compile(r"^(I\d+)_?_?.*$")
    re_rel = regex.compile(r"^(R\d+)_?_?.*$")

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


# noinspection PyShadowingNames
class Item(Entity):
    def __init__(self, key_str: str, **kwargs):
        super().__init__()

        res = process_key_str(key_str)
        assert res.etype == EType.ITEM

        self.short_key = res.short_key
        self._references = None

        for key, value in kwargs.items():
            self.set_relation(key, value)

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
    # prepare the kwargs to set relations
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

    def __call__(self, adhoc_label):
        # we have to redefine this method to let PyCharm recognize the correct type
        res = super().__call__(adhoc_label)

        assert isinstance(res, Relation)
        return res


@unique
class RelationRole(Enum):
    """
    Statement types.
    """

    SUBJECT = 0
    PREDICATE = 1
    OBJECT = 2


# for now we want unique numbers for keys for relations and items etc (although this is not necessary)

# passing seed (arg `x`) ensures "reproducible randomness" accross runs
random_ng = random.Random(x=1750)
available_key_numbers = list(range(1000, 9999))
random_ng.shuffle(available_key_numbers)


class RelationEdge:
    """
    Models a conrete (instatiated) relation between entities. This is basically a dict.
    """

    def __init__(
        self,
        relation: Relation = None,
        relation_tuple: tuple = None,
        role: RelationRole = None,
        corresponding_entity: Entity = None,
        corresponding_literal=None,
        scope=None,
        qualifiers=None,
    ) -> None:
        """

        :param relation:
        :param relation_tuple:
        :param role:                    RelationRole.SUBJECT for normal and RelationRole.OBJECT for inverse edges
        :param corresponding_entity:
        :param corresponding_literal:
        :param scope:
        :param qualifiers:              list of relation edges, that describe `self` more precisely
                                        (cf. wikidata qualifiers)
        """

        self.key_str = f"RE{available_key_numbers.pop()}"
        self.relation = relation
        self.relation_tuple = relation_tuple
        self.role = role
        self.scope = scope
        self.corresponding_entity = corresponding_entity
        self.corresponding_literal = corresponding_literal
        if qualifiers is None:
            qualifiers = []
        assert isinstance(qualifiers, list)
        self.qualifiers = qualifiers

    def __repr__(self):

        # fixme: this breaks if self.role is not a valid enum-value in (0, 2)

        res = f"RE[{self.role.name[0]}]{self.relation_tuple}"
        return res


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

    default_relations = {
        "R22": None,  # R22__is_functional
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


def generate_new_key(prefix):

    assert prefix in ("I", "R")

    while True:
        key = f"{prefix}{available_key_numbers.pop()}"
        try:
            ds.get_entity(key)
        except KeyError:
            # the key was new -> now problem
            return key
        else:
            continue


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

        # for every entity key it stores a dict that maps relation keys to lists of corresponding relation-edges
        re_dict = ds.relation_edges.pop(ek, {})
        inv_re_dict = ds.inv_relation_edges.pop(ek, {})

        # in case res1 is a scope-item we delete all corressponding relation edges, otherwise nothing happens
        ds.scope_relation_edges.pop(ek, None)

        for rel_key, re_list in list(re_dict.items()) + list(inv_re_dict.items()):
            for re in re_list:
                try:
                    # ds.relation_relation_edges: for every relation key stores a list of relevant relation-edges
                    ds.relation_relation_edges[rel_key].remove(re)
                except ValueError:
                    # this happens if there was no entity in the list
                    pass

                try:
                    # ds.store a list of all relation edges (to maintain the order)
                    ds.relation_edge_list.remove(re)
                except ValueError:
                    # this happens if there was no entity in the list
                    pass

    ds.mod_path_mapping.remove_pair(key_a=mod_id)


def register_mod(mod_id):
    frame = get_caller_frame(upcount=1)
    path = os.path.abspath(frame.f_globals["__file__"])
    assert frame.f_globals.get("__MOD_ID__", None) == mod_id
    ds.mod_path_mapping.add_pair(key_a=mod_id, key_b=path)


def script_main(fpath):
    IPS()


# ------------------

# !! defining that stuff on module level makes the script slow:
# todo: move this to a separate module

