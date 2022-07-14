from typing import List, Union

from rdflib import Literal

from .core import (
    create_builtin_relation,
    create_builtin_item,
    Entity,
    Relation,
    Item,
    RelationEdge,
)

# it is OK to access ds here in the builtin module, but this import should not be copied to other knowledge modules
from . import core


__MOD_ID__ = "M1000"


def instance_of(entity, r1: str = None, r2: str = None) -> Item:
    """
    Create an instance (R4) of an item. Try to obtain the label by inspection of the calling context (if r1 is None).

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
            r1 = core.get_key_str_by_inspection()
        # TODO: make this except clause more specific
        except:
            # note this fallback naming can be avoided by explicitly passing r1=...  as kwarg
            r1 = f"{entity.R1} – instance"

    if r2 is None:
        r2 = f'generic instance of {entity.short_key}("{entity.R1}")'

    new_item = core.create_item(
        key_str=core.generate_new_key(prefix="I"), R1__has_label=r1, R2__has_description=r2, R4__instance_of=entity
    )

    return new_item


R1 = create_builtin_relation("R1", R1="has label")
R2 = create_builtin_relation("R2", R1="has description", R2="specifies a natural language description")
R3 = create_builtin_relation("R3", R1="is subclass of")
R4 = create_builtin_relation("R4", R1="is instance of", R22__is_funtional=True)
R5 = create_builtin_relation("R5", R1="is part of")
R6 = create_builtin_relation("R6", R1="has defining equation", R22__is_funtional=True)
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
    R2="specifies that the subject entity has the object-literal as unique local name",
    R22__is_funtional=True,
)

R24 = create_builtin_relation(
    key_str="R24",
    R1="has LaTeX string",
    R2="specifies that the subject is associated with a string of LaTeX source",
    R22__is_funtional=True,
)


# Items

I1 = create_builtin_item("I1", R1="General Item")
I2 = create_builtin_item(
    "I2",
    R1="Metaclass",
    R2__has_description=(
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
    R2__has_description=(
        "Special metaclass. Instances of this class are abstract classes that should not be instantiated, "
        "but subclassed instead."
    ),
)
I11 = create_builtin_item(
    key_str="I11",
    R1="mathematical property",
    R2__has_description="base class for all mathematical properties",
    R4__instance_of=I2("Metaclass"),
    R18__has_usage_hints=(
        "Actual properties are instances of this class (not subclasses). "
        "To create a taxonomy-like structure the relation R17__is_sub_property_of should be used."
    ),
)

I12 = create_builtin_item(
    key_str="I12",
    R1__has_label="mathematical object",
    R2__has_description="base class for any knowledge object of interrest in the field of mathematics",
    R4__instance_of=I2("Metaclass"),
)

I13 = create_builtin_item(
    key_str="I13",
    R1__has_label="mathematical set",
    R2__has_description="mathematical set",
    R3__subclass_of=I12("mathematical object"),
)


I14 = create_builtin_item(
    key_str="I14",
    R1__has_label="mathematical proposition",
    R2__has_description="general mathematical proposition",
    # R3__subclass_of=I7723("general mathematical proposition")
)


I15 = create_builtin_item(
    key_str="I15",
    R1__has_label="implication proposition",
    R2__has_description="proposition, where the premise (if-part) implies the assertion (then-part)",
    R3__subclass_of=I14("mathematical proposition"),
)


I16 = create_builtin_item(
    key_str="I16",
    R1__has_label="Scope",
    R2__has_description="auxiliary class; an instance defines the scope of statements (RelationEdge-objects)",
    R3__instance_of=I2("Metaclass"),
)

###############################################################################
# augment the functionality of `Entity`
###############################################################################

# Once the scope item has been defined it is possible to endow the Entity class with more features


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


Entity.add_method_to_class(_register_scope)


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


def get_scopes(entity: Entity) -> List[Item]:
    """
    Return a list of all scope-items which are associated with this entity like
    [<scope:context>, <scope:premise>, <scope:assertion>] for a proposition-item.

    :param entity:
    :return:
    """
    assert isinstance(entity, Entity)
    # R21__is_scope_of
    scope_relation_edges = core.ds.inv_relation_edges[entity.short_key]["R21"]
    re: RelationEdge
    res = [re.relation_tuple[0] for re in scope_relation_edges]
    return res


def get_items_defined_in_scope(scope: Item) -> List[Entity]:

    assert scope.R4__is_subclass_of == I16("Scope")
    # R20__has_defining_scope
    re_list = core.ds.inv_relation_edges[scope.short_key]["R20"]
    re: RelationEdge
    entities = [re.relation_tuple[0] for re in re_list]
    return entities


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
    R2__has_description="proposition, which establishes the equivalence of two or more statements",
    R3__subclass_of=I14("mathematical proposition"),
)


I18 = create_builtin_item(
    key_str="I18",
    R1__has_label="Formula",
    R2__has_description=(
        "mathematical formula, e.g. represented by a LaTeX-string; this might change in the future to MathMl"
    ),
    R3__instance_of=I2("Metaclass"),
)


def get_ui_short_representation(self) -> str:
    """
    This function returns a string which can be used as a replacement for the label
    :param self:

    :return: mathjax-ready LaTeX source code
    """
    latex_src = self.R24
    assert latex_src.startswith("$")
    assert latex_src.endswith("$")

    # latex make recognizable for mathjax
    res = f"\\({latex_src[1:-1]}\\)"
    return res


I18.add_method(get_ui_short_representation)
del get_ui_short_representation
R24("has LaTeX string").set_relation(R8("has domain of argument 1"), I18("Formula"))
R24("has LaTeX string").set_relation(R11("has range of result"), str)


def create_formula(latex_src: str, r1: str = None, r2: str = None) -> Item:
    if r1 is None:
        r1 = f"generic formula ({latex_src})"

    # TODO: hide such automatically created instances in search results by default (because there will be many)
    formula_item = instance_of(I18("Formula"), r1=r1, r2=r2)

    formula_item.set_relation(R24("has LaTeX string"), latex_src)

    return formula_item


I19 = create_builtin_item(
    key_str="I19",
    R1__has_label="multilingual string literal",
    R2__has_description=("used to encode strings that depend on natural languages"),
    R3__instance_of=I2("Metaclass"),
)


class LangaguageCode:
    # for now we only support a subset of languages with wich the authors are familiar
    # if you miss a language please consider contributing
    valid_tags = ["en", "de"]
    # https://en.wikipedia.org/wiki/IETF_language_tag

    def __init__(self, langtag):
        assert langtag in self.valid_tags

        self.langtag = langtag

    def __rmatmul__(self, arg: str) -> str:
        assert isinstance(arg, str)

        res = Literal(arg, self.langtag)

        return res


en = LangaguageCode("en")
de = LangaguageCode("de")
