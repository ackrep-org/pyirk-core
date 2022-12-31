from typing import List, Union, Optional

from ipydex import IPS  # noqa

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
    RawQualifier,
    ds,
)

from .settings import BUILTINS_URI

# it is OK to access ds here in the builtin module, but this import should not be copied to other knowledge modules
from . import core


__URI__ = BUILTINS_URI
keymanager = core.KeyManager()
core.register_mod(__URI__, keymanager)


def allows_instantiation(itm: Item) -> bool:
    """
    Check if `itm` is an instance of metaclass or a subclass of it. If true, this entity is considered
    a class by itself and is thus allowed to have instances and subclasses

    Possibilities:

        I2 = itm -> True (by our definition)
        I2 -R4-> itm -> True (trivial, itm is an ordinary class)
        I2 -R4-> I100 -R4-> itm -> False (I100 is ordinary class → itm is ordinary instance)

        I2 -R3-> itm -> True (subclasses of I2 are also metaclasses)
        I2 -R3-> I100 -R4-> itm -> True (I100 is subclass of metaclass → itm is metaclass instance)
        I2 -R3-> I100 -R3-> I101 -R3-> I102 -R4-> itm -> True (same)

        # multiple times R4: false
        I2 -R4-> I100 -R3-> I101 -R3-> I102 -R4-> itm -> False
                                (I100 is ordinary class → itm is ordinary instance of its sub-sub-class)
        I2 -R3-> I100 -R4-> I101 -R3-> I102 -R4-> itm -> False (same)

        I2 -R3-> I100 -R3-> I101 -R3-> I102 -R4-> itm -> True (same)
        I2 -R4-> I100 -R3-> I101 -R3-> I102 -R3-> itm -> True (itm is an ordinary sub-sub-sub-subclass)
        I2 -R3-> I100 -R4-> I101 -R3-> I102 -R3-> itm -> True
                                (itm is an sub-sub-subclass of I101 which is an instance of a subclass of I2)

    :param itm:     item to test
    :return:        bool
    """

    taxtree = get_taxonomy_tree(itm)

    # This is a list of 2-tuples like the following:
    # [(None, <Item I4239["monovariate polynomial"]>),
    #  ('R3', <Item I4237["monovariate rational function"]>),
    #  ('R3', <Item I4236["mathematical expression"]>),
    #  ('R3', <Item I4235["mathematical object"]>),
    #  ('R4', <Item I2["Metaclass"]>),
    #  ('R3', <Item I1["general item"]>)]

    if len(taxtree) < 2:
        return False

    relation_keys, items = zip(*taxtree)
    if items[-2] is not I2["Metaclass"]:
        return False

    if relation_keys.count("R4") > 1:
        return False

    return True


def get_taxonomy_tree(itm, add_self=True) -> list:
    """
    Recursively iterate over super and parent classes and

    :param imt: DESCRIPTION
    :raises NotImplementedError: DESCRIPTION


    :return:  list of 2-tuples like [(None, I456), ("R3", I123), ("R4", I2)]
    :rtype: dict

    """

    res = []

    if add_self:
        res.append((None, itm))

    # Note:
    # parent_class refers to R4__is_instance, super_class refers to R3__is_subclass_of
    super_class = itm.R3__is_subclass_of
    parent_class = itm.R4__is_instance_of

    if (super_class is not None) and (parent_class is not None):
        msg = f"currently not allowed together: R3__is_subclass_of and R4__is_instnace_of (Entity: {itm}"
        raise NotImplementedError(msg)

    if super_class:
        res.append(("R3", super_class))
        res.extend(get_taxonomy_tree(super_class, add_self=False))
    elif parent_class:
        res.append(("R4", parent_class))
        res.extend(get_taxonomy_tree(parent_class, add_self=False))

    return res


def instance_of(cls_entity, r1: str = None, r2: str = None, qualifiers: List[Item] = None) -> Item:
    """
    Create an instance (R4) of an item. Try to obtain the label by inspection of the calling context (if r1 is None).

    :param cls_entity:      the type of which an instance is created
    :param r1:          the label; if None use inspection to fetch it from the left hand side of the assingnment
    :param r2:          the description (optional)
    :param qualifiers:  list of RawQualifiers (optional); will be passed to the R4__is_instance_of relation
            
    if `cls_entity` has a defining scope and `qualifiers` is None, then an appropriate R20__has_defining_scope-
    qualifier will be added to the R4__is_instance_of-relation of the new item.            
    
    :return:        new item
    """

    has_super_class = cls_entity.R3 is not None
    
    class_scope = cls_entity.R20__has_defining_scope

    # we have to determine if `cls_entity` is an instnace of I2_metaclass or a subclass of it

    is_instance_of_metaclass = allows_instantiation(cls_entity)
    
    cls_exceptions = (I1["general item"], I40["general relation"]) 

    if (not has_super_class) and (not is_instance_of_metaclass) and (cls_entity not in cls_exceptions):
        msg = f"the entity '{cls_entity}' is not a class, and thus could not be instantiated"
        raise TypeError(msg)

    if r1 is None:
        try:
            r1 = core.get_key_str_by_inspection()
        # TODO: make this except clause more specific
        except:
            # note this fallback naming can be avoided by explicitly passing r1=...  as kwarg
            r1 = f"{cls_entity.R1} – instance"

    if r2 is None:
        r2 = f'generic instance of {cls_entity.short_key}("{cls_entity.R1}")'

    new_item = core.create_item(
        # add prefix2 "a" for "autogenerated"
        key_str=core.pop_uri_based_key(prefix="I", prefix2="a"),
        R1__has_label=r1,
        R2__has_description=r2,
    )
    
    if not qualifiers and class_scope is not None:
        qualifiers = [qff_has_defining_scope(class_scope)]
    new_item.set_relation(R4["is instance of"], cls_entity, qualifiers=qualifiers)

    # TODO: solve this more elegantly    
    # this has to be run again after setting R4
    new_item.__post_init__()

    return new_item


########################################################################################################################
#
#            Creattion of entities
#
########################################################################################################################


core.start_mod(__URI__)

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

R3 = create_builtin_relation("R3", R1="is subclass of", R22__is_functional=True)
R4 = create_builtin_relation("R4", R1="is instance of", R22__is_functional=True)
R5 = create_builtin_relation("R5", R1="is part of")
R6 = create_builtin_relation("R6", R1="has defining mathematical relation", R22__is_functional=True)
R7 = create_builtin_relation("R7", R1="has arity", R22__is_functional=True)
R8 = create_builtin_relation("R8", R1="has domain of argument 1")
R9 = create_builtin_relation("R9", R1="has domain of argument 2")
R10 = create_builtin_relation("R10", R1="has domain of argument 3")
R11 = create_builtin_relation("R11", R1="has range of result", R2="specifies the range of the result (last arg)")
R12 = create_builtin_relation("R12", R1="is defined by means of")
R13 = create_builtin_relation("R13", R1="has canonical symbol", R22__is_functional=True)
R14 = create_builtin_relation("R14", R1="is subset of")
R15 = create_builtin_relation("R15", R1="is element of", R2="states that arg1 is an element of arg2")
R16 = create_builtin_relation(
    key_str="R16",
    R1="has property",
    R2="relates an entity with a mathematical property",
    # R8__has_domain_of_argument_1=I4235("mathematical object"),
    # R10__has_range_of_result=...
)
R61 = create_builtin_relation(
    key_str="R61",
    R1="does not have property",
    R2="relates an entity with a mathematical property that it specifically does not have",
    # R8__has_domain_of_argument_1=I4235("mathematical object"),
    # R10__has_range_of_result=...
)
# TODO: rule: consistency of R16 and R61
R17 = create_builtin_relation(
    key_str="R17", R1="is subproperty of", R2="specifies that arg1 (subj) is a subproperty of arg2 (obj)"
)
R18 = create_builtin_relation(
    "R18", R1="has usage hint", R2="specifies a hint (str) on how this relation should be used"
)

R16.set_relation(R18["has usage hint"], "this relation should be used on conrete instances, not on generic types")
R61.set_relation(R18["has usage hint"], "this relation should be used on conrete instances, not on generic types")

R19 = create_builtin_relation(
    key_str="R19",
    R1="defines method",
    R2="specifies that an entity has a special method (defined by executeable code)"
    # R10__has_range_of_result=callable !!
)

R20 = create_builtin_relation(
    key_str="R20",
    R1="has defining scope",
    R2="specifies the scope in which an entity or relation edge is defined (e.g. the premise of a theorem)",
    R18="Note: one Entity can be parent of multiple scopes, (e.g. a theorem has 'context', 'premises', 'assertions')",
    R22__is_functional=True,
    # R43__is_opposite_of=R21["is scope of"],  # defined later for dependency reasons
)

qff_has_defining_scope = QualifierFactory(R20["has defining scope"], registry_name="qff_has_defining_scope")

R21 = create_builtin_relation(
    key_str="R21",
    R1="is scope of",
    R2="specifies that the subject of that relation is a scope-item of the object (statement-item)",
    R18=(
        "This relation is used to bind scope items to its 'semantic parents'. "
        "This is *not* the inverse relation to R20. "
        "This is not to be confused with R45__has_subscope."
    ),
    R22__is_functional=True,
)


R23 = create_builtin_relation(
    key_str="R23",
    R1="has name in scope",
    R2="specifies that the subject entity has the object-literal as unique local name",
    R22__is_functional=True,
)

R24 = create_builtin_relation(
    key_str="R24",
    R1="has LaTeX string",
    R2="specifies that the subject is associated with a string of LaTeX source",
    R22__is_functional=True,
)

R25 = create_builtin_relation(
    key_str="R25",
    R1="has language specified string",
    R2="...",
)


# Items

I1 = create_builtin_item("I1", R1="general item")
I2 = create_builtin_item(
    "I2",
    R1="Metaclass",
    R2__has_description=(
        "Parent class for other classes; subclasses of this are also metaclasses " "instances are ordinary classes"
    ),
    R3__is_subclass_of=I1,
)

I3 = create_builtin_item("I3", R1="Field of science", R4__is_instance_of=I2)
I4 = create_builtin_item("I4", R1="Mathematics", R4__is_instance_of=I3)
I5 = create_builtin_item("I5", R1="Engineering", R4__is_instance_of=I3)
I6 = create_builtin_item("I6", R1="mathematical operation", R4__is_instance_of=I2["Metaclass"])

# TODO: model this with a relation instead of subclassing
I7 = create_builtin_item("I7", R1="mathematical operation with arity 1", R3__is_subclass_of=I6, R7=1)
I8 = create_builtin_item("I8", R1="mathematical operation with arity 2", R3__is_subclass_of=I6, R7=2)
I9 = create_builtin_item("I9", R1="mathematical operation with arity 3", R3__is_subclass_of=I6, R7=3)
I10 = create_builtin_item(
    "I10",
    R1="abstract metaclass",
    R3__is_subclass_of=I2,
    R2__has_description=(
        "Special metaclass. Instances of this class are abstract classes that should not be instantiated, "
        "but subclassed instead."
    ),
)
I11 = create_builtin_item(
    key_str="I11",
    R1="mathematical property",
    R2__has_description="base class for all mathematical properties",
    R4__is_instance_of=I2["Metaclass"],
    R18__has_usage_hint=(
        "Actual properties are instances of this class (not subclasses). "
        "To create a taxonomy-like structure the relation R17__is_sub_property_of should be used."
    ),
)

# TODO: clearify the difference between the I12 and I18
I12 = create_builtin_item(
    key_str="I12",
    R1__has_label="mathematical object",
    R2__has_description="base class for any knowledge object of interrest in the field of mathematics",
    R4__is_instance_of=I2["Metaclass"],
)

I13 = create_builtin_item(
    key_str="I13",
    R1__has_label="mathematical set",
    R2__has_description="mathematical set",
    R3__is_subclass_of=I12["mathematical object"],
)


I14 = create_builtin_item(
    key_str="I14",
    R1__has_label="mathematical proposition",
    R2__has_description="general mathematical proposition",
    # R3__is_subclass_of=I7723["general mathematical proposition"]
)


I15 = create_builtin_item(
    key_str="I15",
    R1__has_label="implication proposition",
    R2__has_description="proposition, where the premise (if-part) implies the assertion (then-part)",
    R3__is_subclass_of=I14["mathematical proposition"],
)


I16 = create_builtin_item(
    key_str="I16",
    R1__has_label="scope",
    R2__has_description="auxiliary class; an instance defines the scope of statements (RelationEdge-objects)",
    R4__is_instance_of=I2["Metaclass"],
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

    assert isinstance(self, Entity)
    # TODO: obsolete assert?
    assert not name.startswith("_ns_") and not name.startswith("_scope_")
    ns_name = f"_ns_{name}"
    scope_name = f"scp__{name}"
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

    # for now all defining_relations are R4-relations (R4__is_instance_of) (there should be exactly 1)
    r4_list = ent.get_relations(R4.uri)
    assert len(r4_list) == 1

    re = r4_list[0]
    assert isinstance(re, RelationEdge)
    re.scope = scope


class ScopingCM:
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
        ds.append_scope(self.scope)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is the place to handle exceptions
        ds.remove_scope(self.scope)

    def __getattr__(self, name: str):
        """
        This function allows to use `cm.<local variable> instead of I2345.<local variable> where I2345 is the
        parent object of the scope.

        :param name:
        :return:
        """

        if name in self.__dict__:
            return self.dict__[name]

        return getattr(self.item, name)

    def new_var(self, **kwargs) -> Entity:
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
        
        return self._new_var(variable_name, variable_object)
        
    def _new_var(self, variable_name: str, variable_object: Entity) -> Entity:
        variable_object: Entity

        add_scope_to_defining_relation_edge(variable_object, self.scope)

        # this reflects a dessign assumption which might be generalized later
        assert isinstance(variable_object, Entity)

        # allow simple access to the variables → put them into dict (after checking that the name is still free)
        msg = f"The name '{variable_name}' is already occupied in the scope `{self.scope}` of item `{self.item}`."
        assert variable_name not in self.item.__dict__ and variable_name not in self.__dict__, msg
        self.item.__dict__[variable_name] = variable_object

        # keep track of added context vars
        self.namespace[variable_name] = variable_object

        # indicate that the variable object is defined in the context of `self`
        assert getattr(variable_object, "R20", None) is None
        variable_object.set_relation(R20["has defining scope"], self.scope)

        # todo: evaluate if this makes the namespaces obsolete
        variable_object.set_relation(R23["has name in scope"], variable_name)

        return variable_object

    def new_rel(self, sub: Entity, pred: Relation, obj: Entity, qualifiers=None) -> RelationEdge:
        """
        Create a new statement ("relation edge") in the current scope

        :param sub:         subject
        :param pred:        predicate (Relation-Instance)
        :param obj:         object
        :param qualifiers:  List of RawQualifiers

        :return: statement (relation edge)

        """

        assert isinstance(sub, Entity)
        assert isinstance(pred, Relation)
        if isinstance(qualifiers, RawQualifier):
            qualifiers = [qualifiers]
        assert isinstance(qualifiers, (type(None), list))

        return sub.set_relation(pred, obj, scope=self.scope, qualifiers=qualifiers)

    @classmethod
    def create_scopingcm_factory(cls):

        def scopingcm_factory(self: Item, scope_name: str) -> ScopingCM:
            """
            This function will be used as a method for Items which can create a scoping context manager.
            It will return a `cls`-instance, where `cls` is either `ScopingCM` or a subclass of it.
            For details see examples

            :param self:        Item; the item to which the scope should be associated
            :param scope_name:  str; the name of the scope

            :return:            an instance of ScopingCM
            """
            namespace, scope = self._register_scope(scope_name)

            cm = cls(itm=self, namespace=namespace, scope=scope)

            return cm

        # return that function object
        return scopingcm_factory


class _proposition__CM (ScopingCM):
    """
    Context manager taylored for mathematical theorems and definitions
    """

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

    # TODO: this makes  self.new_equation obsolete, doesnt it?
    def new_math_relation(self, lhs: Item, rsgn: str, rhs: Item) -> Item:
        """
        convenience method to create a math_relation-related StatementObject (aka "RelationEdge")

        :param lhs:   left hand side
        :param rsgn:  relation sign
        :param rhs:   rght hand sign

        :return:      new instance of
        """

        # prevent accidental identity of both sides of the equation
        assert lhs is not rhs

        rel = new_mathematical_relation(lhs, rsgn, rhs, scope=self.scope)
        return rel


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


class _rule__CM (ScopingCM):
    def uses_external_entities(self, *args):
        """
        Specifies that some external entities will be used inside the rule (to which this scope belongs)
        """
        for arg in args:
            self.scope.set_relation(R55["uses as external entity"], arg)
            
    def new_rel_var(self, name):
        """
        Create an instance of I40["general relation"] to represent a relation inside a rule.
        Because this item takes a special role it is marked with a qualifier.
        """
        
        variable_object = instance_of(
            I40["general relation"], r1='instance of I40["general relation"]', qualifiers=[qff_ignore_in_rule_ptg(True)]
        )
        
        self._new_var(name, variable_object)
        
    def new_rel(self, sub: Entity, pred: Entity, obj: Entity, qualifiers=None) -> RelationEdge:
        
        if qualifiers is None:
            qualifiers = []
        
        if isinstance(pred, Item):
            
            if not pred.R4__is_instance_of == I40["general relation"]:
                msg = f"Expected relation but got {pred}"
                raise TypeError(msg)
            
            # this mechanism allows to match relations in rules (see unittests for zebra02.py)
            qualifiers.append(proxy_item(pred))
            pred = R58["wildcard relation"]
        
        return super().new_rel(sub, pred, obj, qualifiers)


def _rule__scope(self: Item, scope_name: str):
    """
    This function will be used as a method for semantic-rule-Items. It will return a __rule__CM instance.
    (see above). For details see examples and tests.

    :param self:
    :param scope_name:
    :return:
    """
    namespace, scope = self._register_scope(scope_name)

    cm = _rule__CM(itm=self, namespace=namespace, scope=scope)

    return cm


I15["implication proposition"].add_method(_proposition__scope, name="scope")


I17 = create_builtin_item(
    key_str="I17",
    R1__has_label="equivalence proposition",
    R2__has_description="proposition, which establishes the equivalence of two or more statements",
    R3__is_subclass_of=I14["mathematical proposition"],
)


I18 = create_builtin_item(
    key_str="I18",
    R1__has_label="mathematical expression",
    R2__has_description=(
        "mathematical expression, e.g. represented by a LaTeX-string; this might change in the future to MathMl"
    ),
    R4__is_instance_of=I2["Metaclass"],
)


def get_ui_short_representation(self) -> str:
    """
    This function returns a string which can be used as a replacement for the label
    :param self:

    :return: mathjax-ready LaTeX source code
    """
    latex_src = self.R24
    assert latex_src.startswith("$"), f"{latex_src} of {self} does not start with $"
    assert latex_src.endswith("$"), f"{latex_src} of {self} does not end with $"

    # latex make recognizable for mathjax
    res = f"\\({latex_src[1:-1]}\\)"
    return res


I18.add_method(get_ui_short_representation)
del get_ui_short_representation
R24["has LaTeX string"].set_relation(R8["has domain of argument 1"], I18["mathematical expression"])
R24["has LaTeX string"].set_relation(R11["has range of result"], str)


# TODO: how does this relate to I21["mathmatical relation"]?
# -> Latex expressions are for human readable representation
# they should be used only as an addendum to semantic representations
# TODO: Fix ocse_ct.I6091["control affinity"]
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
    R4__is_instance_of=I2["Metaclass"],
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
    R22__is_functional=True,
)

R27 = create_builtin_relation(
    key_str="R27",
    R1__has_label="has rhs",
    R2__has_description="specifies the right hand side of an relation",
    R22__is_functional=True,
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
    R18__has_usage_hint=(
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
    R2__has_description="super class for greater-than-or-equal-to and less-than-or-equal-to",
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
    R1__has_label="greater-or-equal-than-relation",
    R2__has_description="mathematical relation that specifies that lhs is strictly greater than rhs",
    R3__is_subclass_of=I27["non-strict inequality"],
)

I31 = create_builtin_item(
    key_str="I31",
    R1__has_label="less-or-equal-than-relation",
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
    R22__is_functional=True,
)

R29 = create_builtin_relation(
    key_str="R29",
    R1__has_label="has argument",
    R2__has_description='specifies the concrete argument item of an I32["evaluated mapping"] item',
    # todo: currently we only need univariate mappings. However, once we have multivariate mappings
    #  this needs be reflected here (maybe use qualifiers or a seperate relation for each argument)
)


# TODO: doc: this mechanism needs documentation
# this function can be added to mapping objects as needed
def create_evaluated_mapping(mapping: Item, *args) -> Item:
    """

    :param mapping:
    :param arg:
    :return:
    """

    arg_repr_list = []
    for arg in args:
        try:
            arg_repr_list.append(arg.R1)
        except AttributeError:
            arg_repr_list.append(str(arg))

    args_repr = ", ".join(arg_repr_list)

    # achieve determinism: if this mapping-item was already evaluated with the same args we want to return
    # the same evaluated-mapping-item again

    i32_instance_rels = I32["evaluated mapping"].get_inv_relations("R4__is_instance_of")

    # Note: this could be speed up by caching, however it is unclear where the cache should live
    # and how it relates to RDF representation
    # thus we iterate over all instances of I32["evaluated mapping"]

    for i32_inst_rel in i32_instance_rels:
        assert isinstance(i32_inst_rel, RelationEdge)
        i32_instance = i32_inst_rel.relation_tuple[0]

        if i32_instance.R35__is_applied_mapping_of == mapping:
            old_arg_tup = i32_instance.R36__has_argument_tuple
            if tuple(old_arg_tup.R39__has_element) == args:
                return i32_instance

    target_class = mapping.R11__has_range_of_result
    
    # TODO: this should be ensured by consistency check: for operatators R11 should be functional
    if target_class:
        assert len(target_class) == 1
        target_class = target_class[0]
    else:
        target_class = I32["evaluated mapping"]
    
    r1 = f"{target_class.R1}: {mapping.R1}({args_repr})"
    # for loop finished regularly -> the application `mapping(arg)` has not been created before -> create new item
    ev_mapping = instance_of(target_class, r1=r1)
    ev_mapping.set_relation(R35["is applied mapping of"], mapping)

    arg_tup = new_tuple(*args)
    ev_mapping.set_relation(R36["has argument tuple"], arg_tup)

    return ev_mapping


# todo: maybe the differece between asserted inheritance and inferred inheritance should be encoded via qualifiers
R30 = create_builtin_relation(
    key_str="R30",
    R1__has_label="is secondary instance of",
    R2__has_description=(
        "specifies that the subject is an instance of a class-item,in addtioin to its unambiguous parent class."
    ),
    R18__has_usage_hint=(
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
    # TODO: update or delete:
    R18__has_usage_hint=(
        "The actual type of the relation can be tretrieved by the .proxyitem attribute of the "
        "corresponding RelationEdge."
    ),
)


def new_equation(lhs: Item, rhs: Item, doc=None, scope: Optional[Item] = None) -> Item:
    """common speacial case of mathematical relation, also ensures backwards compatibility"""

    eq = new_mathematical_relation(lhs, "==", rhs, doc, scope)

    return eq


def new_mathematical_relation(lhs: Item, rsgn: str, rhs: Item, doc=None, scope: Optional[Item] = None) -> Item:

    rsgn_dict = {
        "==": I23["equation"],
        "<": I29["less-than-relation"],
        ">": I28["greater-than-relation"],
        "<=": I31["less-or-equal-than-relation"],
        ">=": I30["greater-or-equal-than-relation"],
        "!=": I26["strict inequality"],
    }
    if doc is not None:
        assert isinstance(doc, str)
    mr = instance_of(rsgn_dict[rsgn])

    if scope is not None:
        mr.set_relation(R20["has defining scope"], scope)

    # TODO: perform type checking
    # assert check_is_instance_of(lhs, I23("mathematical term"))

    mr.set_relation(R26["has lhs"], lhs)
    mr.set_relation(R27["has rhs"], rhs)

    re = lhs.set_relation(R31["is in mathematical relation with"], rhs, scope=scope, qualifiers=[proxy_item(mr)])

    return mr


# annoying: pycharm does not recognize that "str"@some_LangaguageCode_obj is valid because str does not
# implement __matmul__
# noinspection PyUnresolvedReferences
I900 = create_builtin_item(
    key_str="I900",
    R1__has_label="test item mit label auf deutsch" @ de,
    R2__has_description="used for testing during development",
    R4__is_instance_of=I2["Metaclass"],
    R18__has_usage_hint="This item serves only for unittesting labels in different languages",
)


# reminder that R32["is functional for each language"] already is defined
assert R32 is not None

R33 = create_builtin_relation(
    key_str="R33",
    R1__has_label="has corresponding wikidata entity",
    R2__has_description="specifies the corresponding wikidata item or relation",
    R22__is_functional=True,
)

R34 = create_builtin_relation(
    key_str="R34",
    R1__has_label="has proxy item",
    R2__has_description="specifies an item which represents an RelationEdge",
    R18__has_usage_hint=(
        "This relation is intended to be used as qualifier, e.g. on R31__is_in_mathematical_relation_with, "
        "where the proxy item is an instance of I23__equation."
    ),
)

proxy_item = QualifierFactory(R34["has proxy item"])

def get_proxy_item(stm: RelationEdge, strict=True) -> Item:
    assert isinstance(stm, RelationEdge)
    
    if not stm.qualifiers:
        if strict:
            msg = f"No qualifiers found while searching for proxy-item-qualifier for {stm}."
            raise core.aux.MissingQualifierError(msg)
        else:
            return None
    
    relevant_qualifiers = [q for q in stm.qualifiers if q.predicate == R34["has proxy item"]]
    
    if not relevant_qualifiers:
        if strict:
            msg = f"No R34__has_proxy_item-qualifier found while searching for proxy-item-qualifier for {stm}."
            raise core.aux.MissingQualifierError(msg)
        else:
            return None
    if len(relevant_qualifiers) > 1:
        msg = f"Multiple R34__has_proxy_item-qualifiers not (yet) supported (while processing {stm})."
        raise core.aux.AmbiguousQualifierError(msg)
        
    res: RelationEdge = relevant_qualifiers[0]
    
    return res.object


R35 = create_builtin_relation(
    key_str="R35",
    R1__has_label="is applied mapping of",
    R2__has_description="specifies the mapping entitiy for which the subject is an application",
    R8__has_domain_of_argument_1=I32["evaluated mapping"],
    R22__is_functional=True,
    R18__has_usage_hint=(
        "Example: if subj = P(A) then we have: subj.R4__is_instance_of = I32; subj.R35 = P; subj.R36 = A"
    ),
)


I33 = create_builtin_item(
    key_str="I33",
    R1__has_label="tuple",
    R2__has_description="data type for specific ordered sequences of entities and/or literals",
    R3__is_subclass_of=I2["Metaclass"],
    R18__has_usage_hint="positions of the elements are specified via qualifiers",
)


def new_tuple(*args, **kwargs) -> Item:
    """
    Create a new tuple entitiy
    :param args:
    :return:
    """

    # ensure this function is called with an active erk module (to define URIs of new instances )
    _ = core.get_active_mod_uri()

    scope = kwargs.pop("scope", None)
    assert len(kwargs) == 0, f"Unexpected keyword argument(s): {kwargs}"

    length = len(args)

    # TODO generate a useful label for the tuple instance
    args_str = str(args)
    if len(args_str) > 15:
        args_str = f"{args_str[:12]}..."
    tup = instance_of(I33["tuple"], r1=f"{length}-tuple: {args_str}")

    if scope is not None:
        tup.set_relation(R20["has defining scope"], scope)

    tup.set_relation(R38["has length"], len(args))

    for idx, arg in enumerate(args):
        tup.set_relation(R39["has element"], arg, qualifiers=[has_index(idx)])

    return tup


# different number types (complex, real, rational, integer, ...)


R46 = create_builtin_relation(
    key_str="R46",
    R1__has_label="is secondary subclass of",
    R2__has_description=(
        "specifies that the subject is an subclass of a class-item, in addtion to its unambiguous parent class."
    ),
    R18__has_usage_hint=(
        "Note that this relation is not functional. This construction allows to combine single (R3) "
        "and multiple inheritance."
    ),
)


I42 = create_builtin_item(
    key_str="I42",
    R1__has_label="mathematical type (metaclass)",
    R2__has_description="base class of mathematical data types",
    R3__is_subclass_of=I2["Metaclass"],  # because its instances are metaclasses
)


I34 = create_builtin_item(
    key_str="I34",
    R1__has_label="complex number",
    R2__has_description="mathematical type representing all complex numbers",
    R4__is_instance_of=I42["mathematical type (metaclass)"],
    R46__is_secondary_subclass_of=I12["mathematical object"],
)

I35 = create_builtin_item(
    key_str="I35",
    R1__has_label="real number",
    R2__has_description="mathematical type representing all real numbers",
    R3__is_subclass_of=I34["complex number"],
)

I36 = create_builtin_item(
    key_str="I36",
    R1__has_label="rational number",
    R2__has_description="mathematical type representing all rational numbers",
    R3__is_subclass_of=I35["real number"],
)

I37 = create_builtin_item(
    key_str="I37",
    R1__has_label="integer number",
    R2__has_description="mathematical type representing all integer numbers, e.g. ..., -2, -1, 0, 1, ...",
    R3__is_subclass_of=I36["rational number"],
)

I38 = create_builtin_item(
    key_str="I38",
    R1__has_label="non-negative integer",
    R2__has_description="mathematical type equivalent to Nat (from type theory): non-negative integer number",
    R3__is_subclass_of=I37["integer number"],
)

I39 = create_builtin_item(
    key_str="I39",
    R1__has_label="positive integer",
    R2__has_description="mathematical type equivalent to Nat+ (from type theory): positive integer number",
    R3__is_subclass_of=I38["non-negative integer"],
)


R36 = create_builtin_relation(
    key_str="R36",
    R1__has_label="has argument tuple",
    R2__has_description="specifies the tuple of arguments of the subject",
    R8__has_domain_of_argument_1=I32["evaluated mapping"],
    R9__has_domain_of_argument_2=I33["tuple"],
    R18__has_usage_hint=(
        "Example: if subj = P(A) then we have: subj.R4__is_instance_of -> I32__evaluated_mapping; ",
        "subj.R35__is_applied_mapping_of -> P; ",
        "subj.R36__has_argument_tuple -> A"
    ),
    R22__is_functional=True,
)


# TODO: it would be more convenient to have the inverse relation because this could be stated when creating
# the definition; In contrast, the current R37 has to be stated after the creation of both entities
# also this relation should be 1:1
R37 = create_builtin_relation(
    key_str="R37",
    R1__has_label="has definition",
    R2__has_description="specifies a formal definition of the item",
    # R8__has_domain_of_argument_1= <mathematical object> (will be defined in other module)
    R11__has_range_of_result=I20["mathematical definition"],
)

R38 = create_builtin_relation(
    key_str="R38",
    R1__has_label="has length",
    R2__has_description="specifies the length of a finite sequence",
    # R8__has_domain_of_argument_1= <mathematical object> (will be defined in other module)
    R11__has_range_of_result=I38["non-negative integer"],
    R22__is_functional=True,
)

R39 = create_builtin_relation(
    key_str="R39",
    R1__has_label="has element",
    R2__has_description="specifies that the object is an element of the subject; inverse of R15_is_element_of",
    R8__has_domain_of_argument_1=I33["tuple"],
    R18__has_usage_hint="This relation should be used with the qualifier R40__has_index"
    # TODO specify inverse relation R15
)

R40 = create_builtin_relation(
    key_str="R40",
    R1__has_label="has index",
    R2__has_description="qualifier; specifies the index (starting at 0) of an R39__has_element relation edge of a tuple",
    # R8__has_domain_of_argument_1= <Relation Edge> # TODO: specify
    R9__has_domain_of_argument_2=I38["non-negative integer"],
    R18__has_usage_hint="This relation should be used as qualifier for R39__has_element",
)

has_index = QualifierFactory(R40["has index"])

I40 = create_builtin_item(
    key_str="I40",
    R1__has_label="general relation",
    R2__has_description="proxy item for a relation",
    R18__has_usage_hint=(
        "This item (which is in no relation to I1__general_item) can be used as a placeholder for any relation. "
        "In other words: this can be interpreted as the common superclass for all relations"
    ),
)

R41 = create_builtin_relation(
    key_str="R41",
    R1__has_label="has required instance relation",
    R2__has_description=(
        "specifies relations which must be set for an instance of the subject to be valid; "
        "subject is assumed to be a type, i.e. an instance of I2__metaclass"
    ),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R9__has_domain_of_argument_2=I40["general relation"],
)

R42 = create_builtin_relation(
    key_str="R42",
    R1__has_label="is symmetrical",
    R2__has_description=(
        "specifies that the subject ('rel') is a symmetrical relation, i.e. that the statement `subj rel obj` also "
        "implies the statement `obj rel subj`"
    ),
    R8__has_domain_of_argument_1=I40["general relation"],
    R9__has_domain_of_argument_2=bool,
    R22__is_functional=True,
)

R43 = create_builtin_relation(
    key_str="R43",
    R1__has_label="is opposite of",
    R2__has_description="specifies that the subject is the oposite of the object.",
    R42__is_symmetrical=True,
    R8__has_domain_of_argument_1=I1["general item"],
    R9__has_domain_of_argument_2=I1["general item"],
)

R20["has defining scope"].set_relation("R43__is_opposite_of", R21["is scope of"])

I41 = create_builtin_item(
    key_str="I41",
    R1__has_label="semantic rule",
    R2__has_description="...",
    R4__is_instance_of=I2["Metaclass"],
)

I41["semantic rule"].add_method(_rule__scope, name="scope")

R44 = create_builtin_relation(
    key_str="R44",
    R1__has_label="is universally quantified",
    R2__has_description=(
        "specifies that the subject represents an universally quantified variable (usually denoted by '∀')"
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=bool,
    R18__has_usage_hint="should be used as qualifier to specify the free variables in theorems and similar statements",
)


# this qualifier is can be used to express universal quatification (mathematically expressed with ∀) of a relation
# e.g. `some_item.set_relation(p.R15["is element of"], other_item, qualifiers=univ_quant(True))`
# means that the statements where `some_item` is used claim to hold for all elements of `other_item` (which should be
# a set)
# see docs for more general information about qualifiers
univ_quant = QualifierFactory(R44["is universally quantified"])

# TODO: obsolete
def uq_instance_of(type_entity: Item, r1: str = None, r2: str = None) -> Item:
    """
    Shortcut to create an instance and set the relation R44["is universally quantified"] to True in one step
    to allow compact notation.

    :param type_entity:     the type of which an instance is created
    :param r1:              the label (tried to extract from calling context)
    :param r2:              optional description

    :return:                new item
    """

    if r1 is None:
        try:
            r1 = core.get_key_str_by_inspection(upcount=1)
        # TODO: make this except clause more specific
        except:
            # note this fallback naming can be avoided by explicitly passing r1=...  as kwarg
            r1 = f"{type_entity.R1} – instance"

    instance = instance_of(type_entity, r1, r2)
    # TODO: This should be used as a qualifier
    instance.set_relation(R44["is universally quantified"], True)
    return instance


R45 = create_builtin_relation(
    key_str="R45",
    R1__has_label="is subscope of",
    R2__has_description=(
        "..."
    ),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=I16["scope"],
    R18__has_usage_hint="used to specify that the subject (a scope instance is a subscope of another scope instance",
    R22__is_functional=True,
)


class ImplicationStatement:
    """
    Context manager to model conditional statements.

    Example from erk:/math/0.2#I7169["definition of identity matrix"]

    ```
    with p.ImplicationStatement() as imp1:
        imp1.antecedent_relation(lhs=cm.i, rsgn="!=", rhs=cm.j)
        imp1.consequent_relation(lhs=M_ij, rhs=I5000["scalar zero"])
    ```

    """

    def __init__(self):

        parent_scope = ds.get_current_scope()

        scope_name_a = f"imp_stmt_antcdt in {parent_scope}"
        scope_name_c = f"imp_stmt_cnsqt in {parent_scope}"

        r2a = f"antecedent scope of implication statement in {parent_scope}"
        r2c = f"consequent scope of implication statement in {parent_scope}"

        self.antecedent_scope = instance_of(I16["scope"], r1=scope_name_a, r2=r2a)
        self.antecedent_scope.set_relation(R45["is subscope of"], parent_scope)

        self.consequent_scope = instance_of(I16["scope"], r1=scope_name_c, r2=r2c)
        self.consequent_scope.set_relation(R45["is subscope of"], parent_scope)

    def __enter__(self):
        """
        implicitly called in the head of the with-statemet
        """

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is the place to handle exceptions
        pass

    def antecedent_relation(self, **kwargs):
        assert "scope" not in kwargs
        kwargs.update(scope=self.antecedent_scope)
        rel = new_mathematical_relation(**kwargs)
        return rel

    def consequent_relation(self, **kwargs):
        assert "scope" not in kwargs
        kwargs.update(scope=self.consequent_scope)
        rel = new_mathematical_relation(**kwargs)
        return rel


# R46 is used above


R47 = create_builtin_relation(
    key_str="R47",
    R1__has_label="is same as",
    R2__has_description=(
        "specifies that subject and object are identical"
    ),
    # TODO: model that this is (probably)  equivalent to "owl:sameAs"
)

R48 = create_builtin_relation(
    key_str="R48",
    R1__has_label="has start time",
    R2__has_description="specifies when a statement becomes true",
    R18__has_usage_hint="to be used as a qualifier",
    R33__has_corresponding_wikidata_entity="P580",
)

R49 = create_builtin_relation(
    key_str="R49",
    R1__has_label="has end time",
    R2__has_description="specifies when a statement ends to be true",
    R18__has_usage_hint="to be used as a qualifier",
    R33__has_corresponding_wikidata_entity="P582",
)


R50 = create_builtin_relation(
    key_str="R50",
    R1__has_label="is different from",
    R2__has_description=(
        "specifies that subject and object are different"
    ),
    R42__is_symmetrical=True,
    R18__has_usage_hint=(
        "this might be used in two situations: a) to prevent accidental confusion during modeling; "
        "b) to express a nontrivial fact of inequality, e.g. that a person has two childs and not just one with "
        "two names."
    ),
)

R51 = create_builtin_relation(
    key_str="R51",
    R1__has_label="instances are from",
    R2__has_description=(
        "specifies that every instance of the subject (class) is one of the elements of the object"
    ),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"]
    # TODO: model that this is (probably) equivalent to "owl:oneOf"
)


def close_class_with_R51(cls_item: Item):
    """
    Set R51__instances_are_from for all current instances of a class.
    
    Note: this does not prevent the creation of further instances (because they can be related via R47__is_same_as to
    the exising instances).
    
    :returns:   tuple-item containing all instances
    """
        
    assert allows_instantiation(cls_item)
    
    instances = cls_item.get_inv_relations("R4__is_instance_of", return_subj=True)
    tpl = new_tuple(*instances)
    
    cls_item.set_relation("R51__instances_are_from", tpl)
    
    return tpl


R52 = create_builtin_relation(
    key_str="R52",
    R1__has_label="is none of",
    R2__has_description=(
        "specifies that every instance of the subject (class) is different from each of the elements of the object"
    ),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"]
    # TODO: find out whether there is an owl equivalent for this relation
)
# http://www.w3.org/2002/07/owl#distinctMembers, http://www.w3.org/2002/07/owl#AllDifferent

R53 = create_builtin_relation(
    key_str="R53",
    R1__has_label="is inverse functional",
    R2__has_description=(
        "specifies that the inverse relation of the subject is functional"
    ),
    # R8__has_domain_of_argument_1=I1["general item"],  # unsure here
    R11__has_range_of_result=bool,
    # TODO: model that this is (probably) equivalent to "owl:InverseFunctionalProperty"
)

R54 = create_builtin_relation(
    key_str="R54",
    R1__has_label="is matched by rule",
    R2__has_description=(
        "specifies that subject entitiy is matched by a semantic rule"
    ),
    # R8__has_domain_of_argument_1=I1["general item"],  # unsure here
    R11__has_range_of_result=I41["semantic rule"],
    R18__has_usage_hint="useful for debugging and testing semantic rules"
    # TODO: model that this is (probably) equivalent to "owl:InverseFunctionalProperty"
)

R55 = create_builtin_relation(
    key_str="R55",
    R1__has_label="uses as external entity",
    R2__has_description=(
        "specifies that the subject (a setting-scope) uses the object entitiy as an external variable in its graph"
    ),
    R8__has_domain_of_argument_1=I16["scope"],  
    R11__has_range_of_result=I1["general item"],
    R18__has_usage_hint="useful for inside semantic rules"
    # TODO: model that this is (probably) equivalent to "owl:InverseFunctionalProperty"
)


R56 = create_builtin_relation(
    key_str="R56",
    R1__has_label="is one of",
    R2__has_description=(
        "specifies that the subject is equivalent to one of the elements of the object"
    ),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"]
    # TODO: model that this is (probably) NOT equivalent to "owl:oneOf" (see R51 above)
    # TODO: decide whether this is the inverse of R52__is_none_of
)

R57 = create_builtin_relation(
    key_str="R57",
    R1__has_label="is placeholder",
    R2__has_description="specifies that the subject is a placeholder and might be replaced by other itmes",
    # TODO: 
    # R8__has_domain_of_argument_1=<any ordinary instance>,
    R11__has_range_of_result=bool,
    R22__is_functional=True,
)

R58 = create_builtin_relation(
    key_str="R58",
    R1__has_label="wildcard relation",
    R2__has_description="specifies that the subject related to the object by any relation (used in rules)",
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=I1["general item"],
)

R59 = create_builtin_relation(
    key_str="R59",
    R1__has_label="ignore in rule prototype graph",
    R2__has_description=(
        "specifies that the subject should be ignored when constructing the prototype graph of an I41__semantic_rule",
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=bool,
)

qff_ignore_in_rule_ptg = QualifierFactory(R59["ignore in rule prototype graph"])

R60 = create_builtin_relation(
    key_str="R60",
    R1__has_label="is transitive",
    R2__has_description=(
        "specifies that the subject ('rel') is a transitive relation, i.e. that the statements `A rel B` and "
        "`B rel C` also implies the statement `A rel C`"
    ),
    R8__has_domain_of_argument_1=I40["general relation"],
    R9__has_domain_of_argument_2=bool,
    R22__is_functional=True,
)


relation_properties = (
    R22["is functional"],
    R32["is functional for each language"],
    R53["is inverse functional"],
    R42["is symmetrical"],
    R60["is transitive"],
)

relation_properties_uris = tuple(rel.uri for rel in relation_properties)

# TODO: this could be speed up by caching
def get_relation_properties(rel_entity: Entity) -> List[str]:
    """
    return a sorted list of URIs, corrosponding to the relation properties corresponding to `rel_entity`.
    """
    
    assert isinstance(rel_entity, Relation) or rel_entity.R4__is_instance_of == I40["general relation"]

    rel_props = []
    for rp_uri in relation_properties_uris:
        res = rel_entity.get_relations(rp_uri, return_obj=True)
        assert len(res) <= 1, "unexpectedly got multiple relation properties"
        if res == [True]:
            rel_props.append(rp_uri)
    rel_props.sort()
    
    return rel_props

# testing


# ######################################################################################################################
# Testing and debugging entities

# I041 = create_builtin_item(
#     key_str="I041",
#     R1__has_label="subproperty rule 1",
#     R2__has_description=(
#         # "specifies the 'transitivity' of I11_mathematical_property-instances via R17_issubproperty_of"
#         "specifies the 'transitivity' of R17_issubproperty_of"
#     ),
#     R4__is_instance_of=I41["semantic rule"],
# )
#
#
# with I041["subproperty rule 1"].scope("context") as cm:
#
#     cm.new_var(P1=instance_of(I11["mathematical property"]))
#     cm.new_var(P2=instance_of(I11["mathematical property"]))
#     cm.new_var(P3=instance_of(I11["mathematical property"]))
# #     # A = cm.new_var(sys=instance_of(I1["general item"]))
# #
# with I041["subproperty rule 1"].scope("premises") as cm:
#     cm.new_rel(cm.P2, R17["is subproperty of"], cm.P1)
#     cm.new_rel(cm.P3, R17["is subproperty of"], cm.P2)
#     # todo: state that all variables are different from each other
#
# with I041["subproperty rule 1"].scope("assertions") as cm:
#     cm.new_rel(cm.P3, R17["is subproperty of"], cm.P1)

# noinspection PyUnresolvedReferences
I900.set_relation(R1["has label"], "test item with english label" @ en)


I000 = create_builtin_item(
    key_str="I000",
    R1__has_label="dummy item",
    R2__has_description="used during development as placeholder for items which will be defined later",
    R4__is_instance_of=I2["Metaclass"],  # this means: this Item is an ordinary class
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


# TODO: evaluate the necessity of this class (especially in face of IntegerRangeElement (ocse.ma))
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


# this is the inverse operation to `core.start_mod(__URI__)` (see above)
core.end_mod()
