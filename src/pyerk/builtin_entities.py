from typing import List, Union, Optional

from ipydex import IPS, activate_ips_on_exception, set_trace

activate_ips_on_exception()

from .core import (
    create_builtin_relation,
    create_builtin_item,
    Entity,
    Relation,
    Item,
    RelationEdge,
    de,
    en,
    QualifierFactory,
)

# it is OK to access ds here in the builtin module, but this import should not be copied to other knowledge modules
from . import core


__MOD_ID__ = "M1000"


def is_instance_of_generalized_metaclass(entity) -> bool:
    """
    Check if `entity` is a metaclass or a subclass of metaclass

    :param entity:
    :return:        bool
    """

    test_entity = entity

    while test_entity is not None:
        if test_entity.R4__is_instance_of == I2["Metaclass"]:
            return True

        test_entity = test_entity.R3__is_subclass_of

    # the loop was finished
    return False


def instance_of(entity, r1: str = None, r2: str = None) -> Item:
    """
    Create an instance (R4) of an item. Try to obtain the label by inspection of the calling context (if r1 is None).

    :param entity:  the type of which an instance is created
    :param r1:      the label; if None use inspection to fetch it from the left hand side of the assingnment
    :param r2:

    :return:        new item
    """

    has_super_class = entity.R3 is not None

    # we have to determine if `entity` is a metaclass or a subclass of metaclass

    is_instance_of_metaclass = is_instance_of_generalized_metaclass(entity)

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


# the bootstrapping of relations is slightly unintuitive because
# a) labels and descriptions are introduced with some delay and
# b) because keys reflect historical development


R32 = create_builtin_relation(key_str="R32")  # will be R32["is functional for each language"]

R1 = create_builtin_relation("R1", R32=True)
R1.set_relation(R1, "has label")
R32.set_relation(R1, "is functional for each language")

R2 = create_builtin_relation("R2", R1="has description", R32=True)
R2.set_relation(R2, "specifies a natural language description")
R1.set_relation(R2, "specifies a short natural language label")
R32.set_relation(
    R2, "specifies that for each subject there is at most one 'R30-RelationEdge' for a given language tag (e.g. en)"
)

R22 = create_builtin_relation(
    key_str="R22",
    R1="is functional",
    R2="specifies that the subject entity is a relation which has at most one value per item",
)

R22["is functional"].set_relation(R22["is functional"], True)
R32["is functional for each language"].set_relation(R22["is functional"], True)

# Note that R1, R22, and R32 are used extensively to control the behavior in pyerk.core

R3 = create_builtin_relation("R3", R1="is subclass of", R22__is_funtional=True)
R4 = create_builtin_relation("R4", R1="is instance of", R22__is_funtional=True)
R5 = create_builtin_relation("R5", R1="is part of")
R6 = create_builtin_relation("R6", R1="has defining equation", R22__is_funtional=True)
R7 = create_builtin_relation("R7", R1="has arity", R22__is_funtional=True)
R8 = create_builtin_relation("R8", R1="has domain of argument 1")
R9 = create_builtin_relation("R9", R1="has domain of argument 2")
R10 = create_builtin_relation("R10", R1="has domain of argument 3")
R11 = create_builtin_relation("R11", R1="has range of result", R2="specifies the range of the result (last arg)")
R12 = create_builtin_relation("R12", R1="is defined by means of")
R13 = create_builtin_relation("R13", R1="has canonical symbol", R22__is_funtional=True)
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
    R1="is scope of",
    R2="specifies that the subject of that relation is a scope-item of the object (statement-item)",
    R18=(
        "This relation is used to bind scope items to its 'semantic parents'. "
        "This is *not* the inverse relation to R20"
    ),
    R22__is_funtional=True,
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

R25 = create_builtin_relation(
    key_str="R25",
    R1="has language specified string",
    R2="...",
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
I6 = create_builtin_item("I6", R1="mathematical operation", R4__instance_of=I2["Metaclass"])
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
    R4__instance_of=I2["Metaclass"],
    R18__has_usage_hints=(
        "Actual properties are instances of this class (not subclasses). "
        "To create a taxonomy-like structure the relation R17__is_sub_property_of should be used."
    ),
)

I12 = create_builtin_item(
    key_str="I12",
    R1__has_label="mathematical object",
    R2__has_description="base class for any knowledge object of interrest in the field of mathematics",
    R4__instance_of=I2["Metaclass"],
)

I13 = create_builtin_item(
    key_str="I13",
    R1__has_label="mathematical set",
    R2__has_description="mathematical set",
    R3__subclass_of=I12["mathematical object"],
)


I14 = create_builtin_item(
    key_str="I14",
    R1__has_label="mathematical proposition",
    R2__has_description="general mathematical proposition",
    # R3__subclass_of=I7723["general mathematical proposition"]
)


I15 = create_builtin_item(
    key_str="I15",
    R1__has_label="implication proposition",
    R2__has_description="proposition, where the premise (if-part) implies the assertion (then-part)",
    R3__subclass_of=I14["mathematical proposition"],
)


I16 = create_builtin_item(
    key_str="I16",
    R1__has_label="scope",
    R2__has_description="auxiliary class; an instance defines the scope of statements (RelationEdge-objects)",
    R3__instance_of=I2["Metaclass"],
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
        scope = instance_of(I16["scope"], r1=scope_name, r2=f"scope of {self.R1}")
        scope.set_relation(R21["is scope of"], self)

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
    assert scope.R4__is_instance_of is I16["scope"]

    for rel_tup in relation_tuples:
        assert isinstance(rel_tup, tuple)
        # this might become >= 3 in the future, if we support multivalued relations
        assert len(rel_tup) == 3

        sub, rel, obj = rel_tup
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

    assert scope.R4__is_instance_of == I16["scope"]
    # R20__has_defining_scope
    re_list = core.ds.inv_relation_edges[scope.short_key]["R20"]
    re: RelationEdge
    entities = [re.relation_tuple[0] for re in re_list]
    return entities


def add_scope_to_defining_relation_edge(ent: Entity, scope: Item) -> None:
    """

    :param ent:
    :param scope:
    :return:        None

    The motivation for this function is a usage pattern like:
    ```
    with I3007.scope("context") as cm:
        cm.new_var(sys=p.instance_of(I5948["dynamical system"]))
    )
    ```

    ideally the `instance_of` function would notice that it was called from within a python-context which defines a
    scope item. But this seems hardly achievable in a clean way. Thus, this function is called after p.instance_of,
    inside cm.new_var(...).
    """

    assert isinstance(ent, Entity)
    assert isinstance(scope, Item)
    assert scope.R4__is_instance_of == I16["scope"]

    # for every entity key this dict stores a dict that maps relation keys to lists of corresponding relation-edges
    re_dict = core.ds.relation_edges[ent.short_key]

    # for now all defining_relations are R4-relations (R4__is_instance_of) (there should be exactly 1)
    r4_list = re_dict["R4"]
    assert len(r4_list) == 1

    re = r4_list[0]
    assert isinstance(re, RelationEdge)
    re.scope = scope


class _proposition__CM:
    """
    Context manager to for creating ("atomic") statements in the scope of other (bigger statements).
    E.g. establishing a relationship between two items as part of the assertions of a theorem-item
    """

    def __init__(self, itm: Item, namespace: dict, scope: Item):
        self.item = itm
        self.namespace = namespace
        self.scope = scope

    def __enter__(self):
        """
        implicitly called in the head of the with statemet
        :return:
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is the place to handle exceptions
        pass

    def new_var(self, **kwargs) -> None:
        """
        create and register a new variable to the respective scope

        :param kwargs:      dict of len == 1 (to allow (almost) arbitrary variable names)

        :return:
        """

        assert self.namespace is not None
        assert self.scope is not None

        # for now we only accept on kwarg per call
        assert len(kwargs) == 1

        variable_name, variable_object = list(kwargs.items())[0]
        variable_object: Entity

        add_scope_to_defining_relation_edge(variable_object, self.scope)

        # this reflects a dessign assumption which might be generalized later
        assert isinstance(variable_object, Entity)

        # allow simple access to the variables → put them into dict (after checking that the name is still free)
        assert variable_name not in self.__dict__
        self.item.__dict__[variable_name] = variable_object

        # keep track of added context vars
        self.namespace[variable_name] = variable_object

        # indicate that the variable object is defined in the context of `self`
        assert getattr(variable_object, "R20", None) is None
        variable_object.set_relation(R20["has defining scope"], self.scope)

        # todo: evaluate if this makes the namespaces obsolete
        variable_object.set_relation(R23["has name in scope"], variable_name)

    def new_rel(self, sub, pred, obj) -> None:
        assert isinstance(sub, Entity)
        assert isinstance(pred, Relation)
        sub.set_relation(pred, obj, scope=self.scope)

    def new_equation(self, lhs: Item, rhs: Item) -> Item:
        """
        convenience method to create a equation-related RelationEdge

        :param lhs:
        :param rhs:
        :return:
        """

        # prevent accidental identity of both sides of the equation
        assert lhs is not rhs

        eq = new_equation(lhs, rhs, scope=self.scope)
        return eq


def _proposition__scope(self: Item, scope_name: str):
    """
    This function will be used as a method for proposition-Items. It will return a __proposition__CM instance.
    (see above). For details see examples

    :param self:
    :param scope_name:
    :return:
    """
    namespace, scope = self._register_scope(scope_name)

    cm = _proposition__CM(itm=self, namespace=namespace, scope=scope)

    return cm


I15["implication proposition"].add_method(_proposition__scope, name="scope")


I17 = create_builtin_item(
    key_str="I17",
    R1__has_label="equivalence proposition",
    R2__has_description="proposition, which establishes the equivalence of two or more statements",
    R3__subclass_of=I14["mathematical proposition"],
)


I18 = create_builtin_item(
    key_str="I18",
    R1__has_label="mathematical expression",
    R2__has_description=(
        "mathematical expression, e.g. represented by a LaTeX-string; this might change in the future to MathMl"
    ),
    R3__instance_of=I2["Metaclass"],
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
R24["has LaTeX string"].set_relation(R8["has domain of argument 1"], I18["mathematical expression"])
R24["has LaTeX string"].set_relation(R11["has range of result"], str)


# TODO: how does this relate to I23["equation"]?
def create_expression(latex_src: str, r1: str = None, r2: str = None) -> Item:
    if r1 is None:
        r1 = f"generic expression ({latex_src})"

    # TODO: hide such automatically created instances in search results by default (because there will be many)
    expression = instance_of(I18["mathematical expression"], r1=r1, r2=r2)

    expression.set_relation(R24["has LaTeX string"], latex_src)

    return expression


# todo: docs: currently ordinary strings can be used where such an Item is expected
# they are interpreted as in the default language
# todo: this entity is obsolete, we use a construction with RDF-Literals instead
I19 = create_builtin_item(
    key_str="I19",
    R1__has_label="multilingual string literal",
    R2__has_description="used to encode strings that depend on natural languages",
    R3__is_instance_of=I2["Metaclass"],
)


I20 = create_builtin_item(
    key_str="I20",
    R1__has_label="mathematical definition",
    R2__has_description="mathematical definition statement (structurally similar to other propositions)",
    R3__is_subclass_of=I14["mathematical proposition"],
    # TODO: ensure this restriction via quality checks
    R18__has_usage_hint=(
        "We model a definition in the same way as an implication proposition; However the assertion must only contain "
        'R3["is_instance_of relations"].'
    ),
)

I20["mathematical definition"].add_method(_proposition__scope, name="scope")

I21 = create_builtin_item(
    key_str="I21",
    R1__has_label="mathematical relation",
    R2__has_description="establishes that two mathematical expressions (I18) are in a relation, e.g. equalness",
)


R26 = create_builtin_relation(
    key_str="R26",
    R1__has_label="has lhs",
    R2__has_description="specifies the left hand side of an relation",
    R22__is_funtional=True,
)

R27 = create_builtin_relation(
    key_str="R27",
    R1__has_label="has rhs",
    R2__has_description="specifies the right hand side of an relation",
    R22__is_funtional=True,
)

R26["has lhs"].set_relation(R8["has domain of argument 1"], I21["mathematical relation"])
R27["has rhs"].set_relation(R8["has domain of argument 1"], I21["mathematical relation"])

I22 = create_builtin_item(
    key_str="I22",
    R1__has_label="mathematical knowledge artifact",
    R2__has_description="(class for) something like an equation or a theorem",
    R3__is_subclass_of=I2["Metaclass"],
)


I14["mathematical proposition"].set_relation(R3["is subclass of"], I22["mathematical knowledge artifact"])
I21["mathematical relation"].set_relation(R3["is subclass of"], I22["mathematical knowledge artifact"])


I23 = create_builtin_item(
    key_str="I23",
    R1__has_label="equation",
    R2__has_description="mathematical relation that specifies that lhs and rhs are equal",
    R3__is_subclass_of=I21["mathematical relation"],
)

# inequalities are based on: https://en.wikipedia.org/wiki/Inequality_(mathematics)

I24 = create_builtin_item(
    key_str="I24",
    R1__has_label="inequation",
    R2__has_description="mathematical relation that specifies that lhs is unequal to rhs",
    R3__is_subclass_of=I21["mathematical relation"],
    R18__has_usage_hints=(
        "This item is different from inquality (I25): lhs and rhs need to be members of the same ordered set."
    ),
)

I25 = create_builtin_item(
    key_str="I25",
    R1__has_label="general inequality",
    R2__has_description="superclass for strict and non-strict inequality",
    R3__is_subclass_of=I21["mathematical relation"],
)

I26 = create_builtin_item(
    key_str="I26",
    R1__has_label="strict inequality",
    R2__has_description=(
        "mathematical relation that specifies that lhs is either strictly greater or strictly less than rhs"
    ),
    R3__is_subclass_of=I25["general inequality"],
)

I27 = create_builtin_item(
    key_str="I27",
    R1__has_label="non-strict inequality",
    R2__has_description=("super class for greater-than-or-equal-to and less-than-or-equal-to"),
    R3__is_subclass_of=I25["general inequality"],
)

I28 = create_builtin_item(
    key_str="I28",
    R1__has_label="greater-than-relation",
    R2__has_description="mathematical relation that specifies that lhs is strictly greater than rhs",
    R3__is_subclass_of=I26["strict inequality"],
)

I29 = create_builtin_item(
    key_str="I29",
    R1__has_label="less-than-relation",
    R2__has_description="mathematical relation that specifies that lhs is strictly less than rhs",
    R3__is_subclass_of=I26["strict inequality"],
)

I30 = create_builtin_item(
    key_str="I30",
    R1__has_label="greater-than-relation",
    R2__has_description="mathematical relation that specifies that lhs is strictly greater than rhs",
    R3__is_subclass_of=I27["non-strict inequality"],
)

I31 = create_builtin_item(
    key_str="I31",
    R1__has_label="less-than-relation",
    R2__has_description="mathematical relation that specifies that lhs is strictly less than rhs",
    R3__is_subclass_of=I27["non-strict inequality"],
)

I32 = create_builtin_item(
    key_str="I32",
    R1__has_label="evaluated mapping",
    R2__has_description="this item type symbolically represents arbitrary evaluated mappings",
    R3__is_subclass_of=I2["Metaclass"],
)

R28 = create_builtin_relation(
    key_str="R28",
    R1__has_label="has mapping item",
    R2__has_description='specifies the concrete mapping item of an I32["evaluated mapping"] item',
    R22_is_functional=True,
)

R29 = create_builtin_relation(
    key_str="R29",
    R1__has_label="has argument",
    R2__has_description='specifies the concrete argument item of an I32["evaluated mapping"] item',
    # todo: currently we only need univariate mappings. However, once we have multivariate mappings
    #  this needs be reflected here (maybe use qualifiers or a seperate relation for each argument)
)


def create_evaluated_mapping(mapping: Item, arg: Entity) -> Item:

    r1 = f"mapping '{mapping}' applied to '{arg}'"

    # achieve determinism: if this mapping-item was already evaluated with this arg-item we want to return
    # the same evaluated-mapping-item again

    i32_instance_rels = I32["evaluated mapping"].get_inv_relations("R4__is_instance_of")

    # Note: this could be speed up by caching, however it is unclear where the cache should live
    # and how it relates to RDF representation

    for i32_inst_rel in i32_instance_rels:
        i32_instance = i32_inst_rel.relation_tuple[0]

        # TODO: adapt this for multivariant mappings
        if i32_instance.R35__is_applied_mapping_of == mapping and i32_instance.R36__has_argument[0] == arg:
            return i32_instance

    # for loop finished regularly -> the application `mapping(arg)` has not been created before -> create new item
    ev_mapping = instance_of(I32["evaluated mapping"], r1=r1)
    ev_mapping.set_relation(R35["is applied mapping of"], mapping)
    ev_mapping.set_relation(R36["has argument"], arg)

    return ev_mapping


# TODO: doc: this mechanism needs documentation
# this function can be added to mapping objects as needed
def custom_call__create_evaluated_mapping(self, arg):
    return create_evaluated_mapping(mapping=self, arg=arg)


R30 = create_builtin_relation(
    key_str="R30",
    R1__has_label="is secondary instance of",
    R2__has_description=(
        "specifies that the subject is an instance of a class-item,in addtioin to its unambiguous parent class."
    ),
    R18__has_usage_hints=(
        "Note that this relation is not functional. This construction allows to combine single (R4) "
        "and multiple inheritance."
    ),
)


R31 = create_builtin_relation(
    key_str="R31",
    R1__has_label="is in mathematical relation with",
    R2__has_description=(
        'specifies that the subject is related to the object via an instance of I25["mathematical relation"].'
    ),
    R18__has_usage_hints=(
        "The actual type of the relation can be tretrieved by the .proxyitem attribute of the "
        "corresponding RelationEdge."
    ),
)


def new_equation(lhs: Item, rhs: Item, doc=None, scope: Optional[Item] = None) -> Item:

    if doc is not None:
        assert isinstance(doc, str)
    eq = instance_of(I23["equation"])

    # TODO: perform type checking
    # assert check_is_instance_of(lhs, I23("mathematical term"))

    eq.set_relation(R26["has lhs"], lhs)
    eq.set_relation(R27["has rhs"], rhs)

    # TODO: proxyitem should be specified by a qualifier
    re = lhs.set_relation(R31["is in mathematical relation with"], rhs, scope=scope, qualifiers=[proxy_item(eq)])

    return eq


# annoying: pycharm does not recognize that "str"@some_LangaguageCode_obj is valid because str does not
# implement __matmul__
# noinspection PyUnresolvedReferences
I900 = create_builtin_item(
    key_str="I900",
    R1__has_label="test item mit label auf deutsch" @ de,
    R2__has_description="used for testing during development",
    R3__is_instance_of=I2["Metaclass"],
    R18__has_usage_hints="This item serves only for unittesting labels in different languages",
)


# reminder that R32["is functional for each language"] already is defined
assert R32 is not None

R33 = create_builtin_relation(
    key_str="R33",
    R1__has_label="has corresponding wikidata entity",
    R2__has_description="specifies the corresponding wikidata item or relation",
    R22_is_functional=True,
)

R34 = create_builtin_relation(
    key_str="R34",
    R1__has_label="has proxy item",
    R2__has_description="specifies an item which represents an RelationEdge",
    R18__has_usage_hints=(
        "This relation is intended to be used as qualifier, e.g. on R31__is_in_mathematical_relation_with, "
        "where the proxy item is an instance of I23__equation."
    ),
)

proxy_item = QualifierFactory(R34["has proxy item"])


R35 = create_builtin_relation(
    key_str="R35",
    R1__has_label="is applied mapping of",
    R2__has_description="specifies the mapping entitiy for which the subject is an application",
    R8__has_domain_of_argument_1=I32["evaluated mapping"],
    R22__is_functional=True,
    R18__has_usage_hints=(
        "Example: if subj = P(A) then we have: subj.R4__is_instance_of = I32; subj.R35 = P; subj.R36 = A"
    ),
)

R36 = create_builtin_relation(
    key_str="R36",
    R1__has_label="has argument",
    R2__has_description="specifies the/an argument entitiy of the subject",
    R8__has_domain_of_argument_1=I32["evaluated mapping"],
    R18__has_usage_hints=(
        "Example: if subj = P(A) then we have: subj.R4__is_instance_of = I32; subj.R35 = P; subj.R36 = A"
    ),
)

R37 = create_builtin_relation(
    key_str="R37",
    R1__has_label="has definition",
    R2__has_description="specifies a formal definition of the item",
    # R8__has_domain_of_argument_1= <mathematical object> (will be defined in other module)
    R11__has_range_of_result=I20["mathematical definition"],
)


# noinspection PyUnresolvedReferences
I900.set_relation(R1["has label"], "test item with english label" @ en)


I000 = create_builtin_item(
    key_str="I000",
    R1__has_label="dummy item",
    R2__has_description="used during development as placeholder for items which will be defined later",
    R4__instance_of=I2["Metaclass"],  # this means: this Item is an ordinary class
)

R000 = create_builtin_relation(
    key_str="R000",
    R1__has_label="dummy relation",
    R2__has_description="used during development as placeholder for relations which will be defined later",
)

# this allows to use I000("with any label") witout triggering an exception in I000.idoc
I000._ignore_mismatching_adhoc_label = True
# ... same for R000
R000._ignore_mismatching_adhoc_label = True


# TODO: evaluate the necessity of this class
class Sequence:
    r"""
    Models a sequence like y, `\dot y, ..., y^(k)`
    """

    def __init__(self, base, prop, link_op, start, stop):
        # Sequence item with the respective relations and conveniently create all necessary auxiliary items
        # runnig index of `prop` and running index of the sequence object have to be connected
        self.base = base
        self.prop = prop
        self.link_op = link_op
        self.start = start
        self.stop = stop
