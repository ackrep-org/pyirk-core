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
from typing import Dict, Union, List
import yaml

from . import auxiliary as aux

from ipydex import IPS, activate_ips_on_exception


activate_ips_on_exception()


"""
    TODO:
    clean up and removal of obsolete code
    rename R2__has_definition to R2__has_description  
    autocompletion assistent (web based, with full text search in labels and description)
        - basic interface ✓
        - simple data actualization
        - text search in description ✓
    entity detail page:
        - display scopes
        - create href for Relation objects
        
         
    Lyapunov stability theorem
    visualizing the results
    has implementation (application to actual instances)
    SPARQL interface
    
    
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

    def _register_scope(self, name: str) -> (dict, "Item"):
        """
        Create a namespace-object (dict) and a Scope-Item
        :param name:    the name of the scope
        :return:
        """

        # TODO: obsolete assert?
        assert not name.startswith("_ns_") and not name.startswith("_scope_")
        ns_name = f"_ns_{name}"
        scope_name = f"scope:{name}"
        scope = getattr(self, scope_name, None)

        if (ns := getattr(self, ns_name, None)) is None:
            # namespace is yet unknown -> assume that scope is also unknown
            assert scope is None

            # create namespace
            ns = dict()
            setattr(self, ns_name, ns)
            self._namespaces[ns_name] = ns

            # create scope
            scope = instance_of(I16("Scope"), r1=scope_name, r2=f"scope of {self.R1}")
            scope.set_relation(R21("is scope of"), self)

            # prevent accidental overwriting
            assert scope_name not in self.__dict__
            self.__dict__[scope_name] = scope

        assert isinstance(ns, dict)
        assert isinstance(scope, Item) and (scope.R21__is_scope_of == self)

        return ns, scope

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

    def add_method(self, func):
        """
        Add a method to this instance (self). If there are R4 relations pointing from child items to self,
        this method is also inherited to those child items.

        :param func:
        :return:
        """
        self.__dict__[func.__name__] = types.MethodType(func, self)
        self._method_prototypes.append(func)

    def set_relation(self, relation: "Relation", *args, scope: "Entity" = None):
        """
        Allows to add a relation after the item was created.

        :param relation:    Relation-Entity
        :param args:        target (object) of the relation
        :param scope:       Entity for the scope in which the relation is defined
        :return:
        """

        if isinstance(relation, Relation):
            if not len(args) == 1:
                raise NotImplementedError
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
        inner_obj = self.relation_edges[entity_key].get(relation_key, None)

        if inner_obj is None:
            self.relation_edges[entity_key][relation_key] = [re_object]

        elif isinstance(inner_obj, list):
            # R22__is_functional
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


def instance_of(entity, r1: str = None, r2: str = None) -> Item:
    """
    Create an instance of an item. Try to obtain the label by inspection of the calling context (if r1 is None).

    :param entity:
    :param r1:      the label; if None use inspection to fetch it from the left hand side of the assingnment
    :param r2:
    :return:
    """

    has_super_class = getattr(entity, "R3", None) is not None
    is_instance_of_metaclass = getattr(entity, "R4", None) == I2("Metaclass")

    if (not has_super_class) and (not is_instance_of_metaclass):
        msg = f"the entity '{entity}' is not a class, and thus could not be instantiated"
        raise TypeError(msg)

    if r1 is None:
        try:
            r1 = get_key_str_by_inspection()
        # TODO: make this except clause more specific
        except:
            # note this fallback naming can be avoided by explicitly passing r1=...  as kwarg
            r1 = f"{entity.R1} – instance"

    if r2 is None:
        r2 = f'generic instance of {entity.short_key}("{entity.R1}")'

    new_item = create_item(
        key_str=generate_new_key(prefix="I"), R1__has_label=r1, R2__has_definition=r2, R4__instance_of=entity
    )

    return new_item


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


def add_relations_to_scope(relation_tuples: Union[list, tuple], scope: Entity):
    """
    Add relations defined by 3-tuples (sub, rel, obj) to the respective scope.

    :param relation_tuples:
    :param scope:
    :return:
    """

    assert scope.R21__is_scope_of is not None
    assert scope.R4__is_instance_of is I16("Scope")

    for arg in relation_tuples:
        assert isinstance(arg, tuple)
        # this might become >= 3 in the future, if we support multivalued relations
        assert len(arg) == 3

        sub, rel, obj = arg
        assert isinstance(sub, Entity)
        assert isinstance(rel, Relation)
        sub.set_relation(rel, obj, scope=scope)


###############################################################################
# auxiliary functions based on core
###############################################################################

# These function will be moved to an auxiliary module in the future. However, this will depend on core and thus
# circular imports have to be avoided


def get_scopes(entity: Entity) -> List[Item]:
    """
    Return a list of all scope-items which are associated with this entity like
    [<scope:context>, <scope:premise>, <scope:assertion>] for a proposition-item.

    :param entity:
    :return:
    """
    assert isinstance(entity, Entity)
    # R21__is_scope_of
    scope_relation_edges = ds.inv_relation_edges[entity.short_key]["R21"]
    re: RelationEdge
    res = [re.relation_tuple[0] for re in scope_relation_edges]
    return res


def get_items_defined_in_scope(scope: Item) -> List[Entity]:

    assert scope.R4__is_subclass_of == I16("Scope")
    # R20__has_defining_scope
    re_list = ds.inv_relation_edges[scope.short_key]["R20"]
    re: RelationEdge
    entities = [re.relation_tuple[0] for re in re_list]
    return entities


def script_main(fpath):
    IPS()


# ------------------

# !! defining that stuff on module level makes the script slow:
# todo: move this to a separate module


__MOD_ID__ = "M1000"

R1 = create_builtin_relation("R1", R1="has label")
R2 = create_builtin_relation("R2", R1="has natural language definition")
R3 = create_builtin_relation("R3", R1="is subclass of")
R4 = create_builtin_relation("R4", R1="is instance of", R22__is_funtional=True)
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
    key_str="R17", R1="is subproperty of", R2="specifies that arg1 (subj) is a subproperty of arg2 (obj)"
)
R18 = create_builtin_relation("R18", R1="has usage hints", R2="specifies hints on how this relation should be used")

R19 = create_builtin_relation(
    key_str="R19",
    R1="defines method",
    R2="specifies that an entity has a special method (defined by executeable code)"
    # R10__has_range_of_result=callable !!
)

R20 = create_builtin_relation(
    key_str="R20",
    R1="has defining scope",
    R2="specifies the scope in which an entity is defined (e.g. the premise of a theorem)",
    R18="Note: one Entity can be parent of multiple scopes, (e.g. a theorem has 'context', 'premises', 'assertions')",
    R22__is_funtional=True,
)

R21 = create_builtin_relation(
    key_str="R21",
    R1="is scope of statement",
    R2="specifies that the subject of that relation is a scope-item of the object (complex-statement-item)",
    R18=(
        "This relation is used to bind scope items to its 'semantic parents'. "
        "This is *not* the inverse relation to R20",
    ),
    R22__is_funtional=True,
)


# TODO: apply this to all relations where it belongs
R22 = create_builtin_relation(
    key_str="R22",
    R1="is functional",
    R2="specifies that the subject entity is a relation which has at most one value per item",
)

R23 = create_builtin_relation(
    key_str="R23",
    R1="has name in scope",
    R2="specifies that the subject entity has the object-literal as local name",
    R22__is_funtional=True,
)


# Items

I1 = create_builtin_item("I1", R1="General Item")
I2 = create_builtin_item(
    "I2",
    R1="Metaclass",
    R2__has_natural_language_definition=(
        "Parent class for other classes; subclasses of this are also metaclasses " "instances are ordinary classes"
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
    "I10",
    R1="abstract metaclass",
    R3__subclass_of=I2,
    R2__has_natural_language_definition=(
        "Special metaclass. Instances of this class are abstract classes that should not be instantiated, "
        "but subclassed instead."
    ),
)
I11 = create_builtin_item(
    key_str="I11",
    R1="mathematical property",
    R2__has_definition="base class for all mathematical properties",
    R4__instance_of=I2("Metaclass"),
    R18__has_usage_hints=(
        "Actual properties are instances of this class (not subclasses). "
        "To create a taxonomy-like structure the relation R17__is_sub_property_of should be used."
    ),
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
    R3__subclass_of=I14("mathematical proposition"),
)


I16 = create_builtin_item(
    key_str="I16",
    R1__has_label="Scope",
    R2__has_definition="auxiliary class; an instance defines the scope of statements (RelationEdge-objects)",
    R3__instance_of=I2("Metaclass"),
)


def ensure_existence(thedict, key, default):
    """
    Ensures the existence of a key-value pair in a dictionary.

    :param thedict:
    :param key:
    :param default:
    :return:
    """

    if value := thedict.get(key) is None:
        value = thedict[key] = default
    return value


def define_context_variables(self, **kwargs):
    self: Entity
    context_ns, context_scope = self._register_scope("context")

    for variable_name, variable_object in kwargs.items():
        variable_object: Entity

        # this reflects a dessign assumption which might be generalized later
        assert isinstance(variable_object, Entity)

        # allow simple access to the variables → put them into dict (after checking that the name is still free)
        assert variable_name not in self.__dict__
        self.__dict__[variable_name] = variable_object

        # keep track of added context vars
        context_ns[variable_name] = variable_object

        # indicate that the variable object is defined in the context of `self`
        assert getattr(variable_object, "R20", None) is None
        variable_object.set_relation(R20("has_defining_scope"), context_scope)

        # todo: evaluate if this makes the namespaces obsolete
        variable_object.set_relation(R23("has_name_in_scope"), variable_name)


I15.add_method(define_context_variables)
del define_context_variables


def set_context_relations(self, *args, **kwargs):
    """

    :param self:    the entity to which this method will be bound
    :param args:    tuple like (subj, rel, obj)
    :param kwargs:  yet unused
    :return:
    """
    self: Entity

    _, context_scope = self._register_scope("context")
    # context_relations = ensure_existence(context, "_relations", [])

    add_relations_to_scope(args, context_scope)


I15.add_method(set_context_relations)
del set_context_relations


def set_premises(self, *args):
    self: Entity
    _, premises_scope = self._register_scope("premises")
    add_relations_to_scope(args, premises_scope)


I15.add_method(set_premises)
del set_premises


def set_assertions(self, *args):
    self: Entity
    _, assertions_scope = self._register_scope("assertions")
    add_relations_to_scope(args, assertions_scope)


I15.add_method(set_assertions)
del set_assertions


I17 = create_builtin_item(
    key_str="I17",
    R1__has_label="equivalence proposition",
    R2__has_definition="proposition, which establishes the equivalence of two or more statements",
    R3__subclass_of=I14("mathematical proposition"),
)
