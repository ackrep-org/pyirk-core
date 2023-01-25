from typing import List, Union, Optional, Any

from ipydex import IPS  # noqa

from .core import (
    create_builtin_relation,
    create_builtin_item,
    Entity,
    Relation,
    Item,
    Statement,
    de,
    en,
    QualifierFactory,
    RawQualifier,
    ds,
    RuleResult,
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
    R2, "specifies that for each subject there is at most one 'R30-Statement' for a given language tag (e.g. en)"
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

# The short key R61 was choosen for historical and/or pragmatic reasons
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


I40 = create_builtin_item(
    key_str="I40",
    R1__has_label="general relation",
    R2__has_description="proxy item for a relation",
    R18__has_usage_hint=(
        "This item (which is in no relation to I1__general_item) can be used as a placeholder for any relation. "
        "In other words: this can be interpreted as the common superclass for all relations"
    ),
)


R68 = create_builtin_relation(
    key_str="R68",
    R1="is inverse of",
    R2="specifies that the subject is the inverse relation of the object",
    R8__has_domain_of_argument_1=I40["general relation"],
    R11__has_range_of_result=I40["general relation"],
    R22__is_functional=True,
)


R20 = create_builtin_relation(
    key_str="R20",
    R1="has defining scope",
    R2="specifies the scope *in* which an entity or relation edge is defined (e.g. the premise of a theorem)",
    R18=(
        "Notes: This relation is functional. But an Entity (e.g. a theorem) can be parent (via R21) of multiple "
        "scopes, (e.g. 'setting', 'premise', 'assertion'). Each of these items can 'contain' other items in the sense, "
        "that these other items are R20_has_defining_scope-related to the scope item. Thus, R20 and R21__is_scope_of "
        "are *not* inverse to each other."
    ),
    R22__is_functional=True,
)

qff_has_defining_scope = QualifierFactory(R20["has defining scope"], registry_name="qff_has_defining_scope")


R21 = create_builtin_relation(
    key_str="R21",
    R1="is scope of",
    R2="specifies that the subject of that relation is a (sub) scope-item of the object (statement-item)",
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
    R2__has_description="auxiliary class; an instance defines the scope of statements (Statement-objects)",
    R4__is_instance_of=I2["Metaclass"],
)

###############################################################################
# augment the functionality of `Entity`
###############################################################################

# Once the scope item has been defined it is possible to endow the Entity class with more features


def _register_scope(self, name: str, scope_type: str = None) -> (dict, "Item"):
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
    msg = f"Entity {self} already has a scope with name '{name}'.\nPossible reason: copy-paste-error."
    if scope_name in self.__dict__:
        raise core.aux.InvalidScopeNameError(msg)
    self.__dict__[scope_name] = scope

    assert isinstance(ns, dict)
    assert isinstance(scope, Item) and (scope.R21__is_scope_of == self)

    if scope_type is None:
        scope_type = name.upper()

        # TODO: remove this after renaming has taken place:
        new_types = {"CONTEXT": "SETTING", "PREMISES": "PREMISE", "ASSERTIONS": "ASSERTION"}
        scope_type = new_types.get(scope_type, scope_type)
    scope.set_relation(R64["has scope type"], scope_type)

    return ns, scope


# every entity can have scopes
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
    scope_statements = core.ds.inv_statements[entity.short_key]["R21"]
    re: Statement
    res = [re.relation_tuple[0] for re in scope_statements]
    return res


def get_items_defined_in_scope(scope: Item) -> List[Entity]:

    assert scope.R4__is_instance_of == I16["scope"]
    # R20__has_defining_scope
    re_list = core.ds.inv_statements[scope.short_key]["R20"]
    re: Statement
    entities = [re.relation_tuple[0] for re in re_list]
    return entities


def add_scope_to_defining_statement(ent: Entity, scope: Item) -> None:
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
    assert isinstance(re, Statement)
    re.scope = scope


class ScopingCM:
    """
    Context manager to for creating ("atomic") statements in the scope of other (bigger statements).
    E.g. establishing a relationship between two items as part of the assertions of a theorem-item
    """

    valid_subscope_types = None

    def __init__(self, itm: Item, namespace: dict, scope: Item, parent_scope_cm=None):

        # prevent the accidental instantiation of abstract subclasses
        assert not __class__.__name__.lower().startswith("abstract")

        self.item = itm
        self.namespace = namespace
        self.scope = scope
        self.parent_scope_cm = parent_scope_cm

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

        msg = "the `new_var` method of a scope-context accepts exactly one keyword argument"
        assert len(kwargs) == 1, msg

        variable_name, variable_object = list(kwargs.items())[0]

        return self._new_var(variable_name, variable_object)

    def _new_var(self, variable_name: str, variable_object: Entity) -> Entity:
        self._check_scope()
        variable_object: Entity

        add_scope_to_defining_statement(variable_object, self.scope)

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

    # TODO: this should be renamed to new_statement
    def new_rel(self, sub: Entity, pred: Relation, obj: Entity, qualifiers=None, overwrite=False) -> Statement:
        """
        Create a new statement ("relation edge") in the current scope

        :param sub:         subject
        :param pred:        predicate (Relation-Instance)
        :param obj:         object
        :param qualifiers:  List of RawQualifiers
        :param overwrite:   boolean flag that the new statement should replace the old one

        :return: the newly created Statement

        """
        self._check_scope()
        assert isinstance(sub, Entity)
        assert isinstance(pred, Relation)
        if isinstance(qualifiers, RawQualifier):
            qualifiers = [qualifiers]
        elif qualifiers is None:
            qualifiers = []

        if overwrite:

            qff_has_defining_scope: QualifierFactory = ds.qff_dict["qff_has_defining_scope"]
            qualifiers.append(qff_has_defining_scope(self.scope))
            return sub.overwrite_statement(pred.uri, obj, qualifiers=qualifiers)
        else:
            # Note: As qualifiers is a list, it will be changed by the next call (the R20-scope qlf is appended).
            res = sub.set_relation(pred, obj, scope=self.scope, qualifiers=qualifiers)

            return res

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

    def _check_scope(self):
        active_scope = ds.scope_stack[-1]

        if not active_scope == self.scope:
            msg = f"Unexpected active scope: ({active_scope}). Expected: {self.scope}"
            raise core.aux.InvalidScopeNameError(msg)

    def _create_subscope_cm(self, scope_type: str, cls: type):
        """
        :param scope_type:     a str like "AND" or "OR"
        :param cls:            the class to instantiate, e.g. RulePremiseSubScopeCM

        """

        if isinstance(self.valid_subscope_types, dict):
            # assume that this is a dict mapping types to maximum number of such subscopes
            try:
                max_subscopes_of_this_type = self.valid_subscope_types[scope_type]
            except KeyError:
                msg = f"subscope of {scope_type} is not allowed in scope {self.scope}"
                raise core.aux.InvalidScopeTypeError(msg)

        all_sub_scopes = self.scope.get_inv_relations("R21__is_scope_of", return_subj=True)
        matching_type_sub_scopes = [scp for scp in all_sub_scopes if scp.R64__has_scope_type == scope_type]

        n = len(matching_type_sub_scopes)
        if n >= max_subscopes_of_this_type:
            msg = (
                f"There already exists {n} subscope(s) of type {scope_type} for scope {self.scope}. "
                "More are not allowed."
            )
            raise core.aux.InvalidScopeTypeError(msg)


        if max_subscopes_of_this_type == 1:
            name = scope_type
        else:
            # e.g. we allow multiple AND-subscopes
            name = f"{scope_type}{n}"

        namespace, scope = self.scope._register_scope(name, scope_type)

        cm = cls(itm=self.item, namespace=namespace, scope=scope, parent_scope_cm=self)
        return cm


class AbstractMathRelatedScopeCM(ScopingCM):
    """
    Context manager containing methods which are math-related
    """

    def new_equation(self, lhs: Item, rhs: Item) -> Item:
        """
        convenience method to create a equation-related Statement

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
        convenience method to create a math_relation-related StatementObject (aka "Statement")

        :param lhs:   left hand side
        :param rsgn:  relation sign
        :param rhs:   rght hand sign

        :return:      new instance of
        """

        # prevent accidental identity of both sides of the equation
        assert lhs is not rhs

        rel = new_mathematical_relation(lhs, rsgn, rhs, scope=self.scope)
        return rel


class _proposition__CM(AbstractMathRelatedScopeCM):
    """
    Context manager taylored for mathematical theorems and definitions
    """

    valid_subscope_types = {"UNIV_QUANT": float("inf"), "EXIS_QUANT": float("inf")}

    def universally_quantified(self) -> ScopingCM:
        """
        Create a new subscope of type "UNIV_QUANT", which can hold arbitrary statements. That subscope will contain
        another subscope ("CONDITIONS") whose statements are considered as universally quantified condition-statements.
        """

        # create a new context manager (which implicitly creates a new scope-item), where the user can add statements
        # note: this also creates an internal "CONDITION" subscope
        cm = self._create_subscope_cm(scope_type="UNIV_QUANT", cls=QuantifiedSubScopeCM)
        return cm

    def existentially_quantified(self) -> ScopingCM:
        """
        Create a new subscope of type "EXIS_QUANT", which can hold arbitrary statements. That subscope will contain
        another subscope ("CONDITIONS") whose statements are considered as existentially quantified condition-statements.
        """

        # create a new context manager (which implicitly creates a new scope-item), where the user can add statements
        # note: this also creates an internal "CONDITION" subscope
        cm = self._create_subscope_cm(scope_type="EXIS_QUANT", cls=QuantifiedSubScopeCM)
        return cm


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


class QuantifiedSubScopeCM(AbstractMathRelatedScopeCM):
    """
    A scoping context manager for universally or existentially quantified statements
    """
    valid_subscope_types = {"CONDITION": 1}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.condition_cm = self._create_subscope_cm("CONDITION", SubScopeConditionCM)

    def add_condition_statement(self, subj, pred, obj, qualifiers=None):

        with self.condition_cm:
            self.condition_cm.new_rel(subj, pred, obj, qualifiers=qualifiers)

    def add_condition_math_relation(self, *args, **kwargs):

        with self.condition_cm:
            self.condition_cm.new_math_relation(*args, **kwargs)

    def new_condition_var(self, **kwargs):
        with self.condition_cm:
            return self.condition_cm.new_var(**kwargs)

class SubScopeConditionCM(AbstractMathRelatedScopeCM):
    """
    A scoping context manager to specify the condition of another scope
    """
    valid_subscope_types = {}


class _rule__CM(ScopingCM):

    valid_subscope_types = {"AND": float("inf"), "OR": 1}

    def __init__(self, *args, **kwargs):

        self._anchor_item_counter = 0
        super().__init__(*args, **kwargs)

    @property
    def anchor_item_counter(self):
        """
        For subscopes we want to use the counter of the parent scope
        """
        if self.parent_scope_cm:
            # using property here to support nesting
            return self.parent_scope_cm.anchor_item_counter
        else:
            # using attribute here
            return self._anchor_item_counter

    @anchor_item_counter.setter
    def anchor_item_counter(self, value):
        """
        For subscopes we want to use the counter of the parent scope
        """
        if self.parent_scope_cm:
            # using property here to support nesting
            self.parent_scope_cm.anchor_item_counter = value
        else:
            # using attribute here
            self._anchor_item_counter = value

    def uses_external_entities(self, *args):
        """
        Specifies that some external entities will be used inside the rule (to which this scope belongs)
        """
        for arg in args:
            self.scope.set_relation(R55["uses as external entity"], arg)

    def set_sparql(self, sparql_src: str):
        """
        Define the `WHERE`-part of a sparql SELECT-query
        """
        # TODO check sparql syntax
        assert isinstance(sparql_src, str)

        self.scope.set_relation(R63["has SPARQL source"], sparql_src)

    def new_variable_literal(self, name):
        """
        Create an instance of I44["variable literal"] to represent a literal.inside a rule. Variable means that
        the literal can have a different value for each match.
        Because this item takes a special role it is marked with a qualifier.
        """

        variable_object = instance_of(I44["variable literal"], r1=f"{name} (I44__variable_literal)")

        variable_object.set_relation(R59["has rule-prototype-graph-mode"], 3)

        return self._new_var(name, variable_object)

    def new_rel_var(self, name):
        """
        Create an instance of I40["general relation"] to represent a relation inside a rule.
        Because this item takes a special role it is marked with a qualifier.
        """

        variable_object = instance_of(
            I40["general relation"], r1=f"{name} (I40__general_relation)", qualifiers=[qff_has_rule_ptg_mode(1)]
        )

        return self._new_var(name, variable_object)

    def new_rel(self, sub: Entity, pred: Entity, obj: Entity, qualifiers=None, overwrite=False) -> Statement:

        if qualifiers is None:
            qualifiers = []

        if isinstance(pred, Item):

            if not pred.R4__is_instance_of == I40["general relation"]:
                msg = f"Expected relation but got {pred}"
                raise TypeError(msg)

            # this mechanism allows to match relations in rules (see unittests for zebra02.py)
            qualifiers.append(proxy_item(pred))
            pred = R58["wildcard relation"]

        return super().new_rel(sub, pred, obj, qualifiers, overwrite)

    def _get_new_anchor_item(self, name):

        # note `anchor_item_counter` is a property

        name = f"{name}{self.anchor_item_counter}"
        self.anchor_item_counter += 1

        itm = instance_of(I43["anchor item"], r1=name)
        self.new_var(**{name: itm})
        return itm

    def new_condition_func(self, func: callable, *args, anchor_item=None):
        """
        Add an existing function that will be called to a graph-match. Only if it evaluates True, the premise is
        considered to be fulfilled. This helps to model conditions on literals
        """

        if self.scope.R64__has_scope_type == "OR":
            # This is not allowed. Reason: this call might create multiple R29__has_argument statements.
            # However every statement inside an OR-subscope is considered to be an alternative condition on its own
            msg = (
                "The creation of condition functions is not allowed in an OR-subscope. Wrap it in a nested "
                "AND-subscope."
            )
            raise core.aux.SemanticRuleError(msg)

        if anchor_item is None:
            anchor_item = self._get_new_anchor_item(name="condition_anchor_item")
        else:
            assert isinstance(anchor_item, Item)

        anchor_item.add_method(func, "condition_func")

        for arg in args:
            # args are supposed to be variables created in the "setting"-scope
            self.new_rel(anchor_item, R29["has argument"], arg)

    def new_consequent_func(self, func: callable, *args, anchor_item=None):
        """
        Add an existing function that should be called in the assertion-part of a semantic rule
        """

        if anchor_item is None:
            factory_anchor = self._get_new_anchor_item(name="fiat_factory_item")
        else:
            assert isinstance(anchor_item, Item)
            factory_anchor = anchor_item

        # this method (identified by its name) will be called by the RuleApplicator during .apply()
        factory_anchor.add_method(func, "fiat_factory")

        for arg in args:
            # args are supposed to be variables created in the "setting"-scope
            self.new_rel(factory_anchor, R29["has argument"], arg, qualifiers=[qff_has_rule_ptg_mode(4)])

    def OR(self):
        """
        Register a subscope for OR-connected statements
        """

        if self.scope.R64__has_scope_type not in ("PREMISE", "AND"):
            msg = "logical OR subscope is only allowed inside 'premise'-scope and AND-subscope"
            raise core.aux.SemanticRuleError(msg)

        return self._create_subscope_cm(scope_type="OR", cls=RulePremiseSubScopeCM)

    def AND(self):
        msg = "AND-logical subscope is only allowed inside a subscope of a 'premise'-scope"
        raise core.aux.SemanticRuleError(msg)


class RulePremiseSubScopeCM(_rule__CM):
    """
    Context Manager for logical subscopes (like OR and AND) in premises
    """

    def AND(self):
        """
        Register a subscope for AND-connected statements
        """

        if self.scope.R64__has_scope_type not in ("OR",):
            msg = "logical AND-subscope is only allowed inside OR-subscope"
            raise core.aux.SemanticRuleError(msg)

        return self._create_subscope_cm(scope_type="AND", cls=RulePremiseSubScopeCM)


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


def _get_subscopes(self):
    """
    Convenience method for items which usually have scopes: allow easy access to subscopes
    """
    return self.get_inv_relations("R21__is_scope_of", return_subj=True)

I15["implication proposition"].add_method(_get_subscopes, name="get_subscopes")
I16["scope"].add_method(_get_subscopes, name="get_subscopes")

def _get_statements_for_scope(self):
    """
    Convenience method for scope items to allow easy access to the statements made in that scope
    """
    subjects = self.get_inv_relations("R20__has_defining_scope", return_subj=True)

    # return all statements where which have self as R20 qualifier
    return [s for s in subjects if isinstance(s, Statement)]

I16["scope"].add_method(_get_statements_for_scope, name="get_statements_for_scope")

def _get_items_for_scope(self):
    """
    Convenience method for scope items to allow easy access to the items created in that scope
    """
    subjects = self.get_inv_relations("R20__has_defining_scope", return_subj=True)

    # return all items where which have self as R20 qualifier
    return [s for s in subjects if isinstance(s, Item)]

I16["scope"].add_method(_get_items_for_scope, name="get_items_for_scope")


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

# TODO: add these methods via inheritance
I20["mathematical definition"].add_method(_proposition__scope, name="scope")
I20["mathematical definition"].add_method(_get_subscopes, name="get_subscopes")


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

    target_class = mapping.R11__has_range_of_result
    # TODO: this should be ensured by consistency check: for operatators R11 should be functional
    if target_class:
        assert len(target_class) == 1
        target_class = target_class[0]
    else:
        target_class = I32["evaluated mapping"]

    # achieve determinism: if this mapping-item was already evaluated with the same args we want to return
    # the same evaluated-mapping-item again

    target_class_instance_stms = target_class.get_inv_relations("R4__is_instance_of")

    # Note: this could be speed up by caching, however it is unclear where the cache should live
    # and how it relates to RDF representation
    # thus we iterate over all instances of I32["evaluated mapping"]

    for tci_stm in target_class_instance_stms:
        assert isinstance(tci_stm, Statement)
        tci = tci_stm.subject

        if tci.R35__is_applied_mapping_of == mapping:
            old_arg_tup = tci.R36__has_argument_tuple
            if tuple(old_arg_tup.R39__has_element) == args:
                return tci

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
        "corresponding Statement."
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
    R2__has_description="specifies an item which represents an Statement",
    R18__has_usage_hint=(
        "This relation is intended to be used as qualifier, e.g. on R31__is_in_mathematical_relation_with, "
        "where the proxy item is an instance of I23__equation."
    ),
)

proxy_item = QualifierFactory(R34["has proxy item"])


def get_proxy_item(stm: Statement, strict=True) -> Item:
    assert isinstance(stm, Statement)

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

    res: Statement = relevant_qualifiers[0]

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
        "subj.R36__has_argument_tuple -> A",
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
    R8__has_domain_of_argument_1=I12["mathematical object"],
    R11__has_range_of_result=I20["mathematical definition"],
    R22__is_functional=True,
)

R67 = create_builtin_relation(
    key_str="R67",
    R1__has_label="is definition of",
    R2__has_description="specifies that the subject is the formal definition of the object",
    R8__has_domain_of_argument_1=I20["mathematical definition"],
    R11__has_range_of_result=I12["mathematical object"],
    R22__is_functional=True,
    R68__is_inverse_of=R37["has definition"],
)

R37["has definition"].set_relation("R68__is_inverse_of", R67["is definition of"])


R38 = create_builtin_relation(
    key_str="R38",
    R1__has_label="has length",
    R2__has_description="specifies the length of a finite sequence",
    R8__has_domain_of_argument_1=I12["mathematical object"],
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

# TODO: should be functional
R40 = create_builtin_relation(
    key_str="R40",
    R1__has_label="has index",
    R2__has_description="qualifier; specifies the index (starting at 0) of an R39__has_element relation edge of a tuple",
    # R8__has_domain_of_argument_1= <Statement> # TODO: specify
    R9__has_domain_of_argument_2=I38["non-negative integer"],
    R18__has_usage_hint="This relation should be used as qualifier for R39__has_element",
)

has_index = QualifierFactory(R40["has index"])


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


R68["is inverse of"].set_relation(R42["is symmetrical"], True)


R43 = create_builtin_relation(
    key_str="R43",
    R1__has_label="is opposite of",
    R2__has_description="specifies that the subject is the oposite of the object.",
    R42__is_symmetrical=True,
    R8__has_domain_of_argument_1=I1["general item"],
    R9__has_domain_of_argument_2=I1["general item"],
)


# I40 defined above

I41 = create_builtin_item(
    key_str="I41",
    R1__has_label="semantic rule",
    R2__has_description="...",
    R4__is_instance_of=I2["Metaclass"],
)

I41["semantic rule"].add_method(_rule__scope, name="scope")

# I42 is already used above

I43 = create_builtin_item(
    key_str="I43",
    R1__has_label="anchor item",
    R2__has_description="base class for items whose with the main purpose to host some functions as item-methods",
    R4__is_instance_of=I2["Metaclass"],
    R18__has_usage_hint="used in the class _rule__CM",
)

R44 = create_builtin_relation(
    key_str="R44",
    R1__has_label="is universally quantified",
    R2__has_description=(
        "specifies that the subject represents an universally quantified variable (usually denoted by '∀')"
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=bool,
    R18__has_usage_hint=(
        "should be used as qualifier to specify the free variables in theorems and similar statements; "
        "See also R66__is_existantially_quantified"
    ),
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

# placed here for its obvious relation to universal quantification
R66 = create_builtin_relation(
    key_str="R66",
    R1__has_label="is existantially quantified",
    R2__has_description=(
        "specifies that the subject represents an existentially quantified variable (usually denoted by '∃')"
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=bool,
    R18__has_usage_hint=(
        "should be used as qualifier to specify the free variables in theorems and similar statements; "
        "See also R44__is_universally_quantified"
    ),
)

exis_quant = QualifierFactory(R66["is existantially quantified"])


R45 = create_builtin_relation(
    key_str="R45",
    R1__has_label="is subscope of",
    R2__has_description=("..."),
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
    R2__has_description=("specifies that subject and object are identical"),
    R42__is_symmetrical=True,
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
    R2__has_description=("specifies that subject and object are different"),
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
    R2__has_description=("specifies that every instance of the subject (class) is one of the elements of the object"),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"]
    # TODO: model that this is (probably) equivalent to "owl:oneOf"
)


def is_relevant_item(itm):
    return not itm.R57__is_placeholder and not itm.R20__has_defining_scope


def get_instances_of(cls_item: Item, filter=None) -> List[Item]:
    assert allows_instantiation(cls_item)

    if filter is None:
        filter = lambda obj: True
    assert callable(filter)

    all_instances = cls_item.get_inv_relations("R4__is_instance_of", return_subj=True)
    res = [elt for elt in all_instances if filter(elt)]
    return res


def close_class_with_R51(cls_item: Item):
    """
    Set R51__instances_are_from for all current instances of a class.

    Note: this does not prevent the creation of further instances (because they can be related via R47__is_same_as to
    the exising instances).

    :returns:   tuple-item containing all instances
    """

    instances = get_instances_of(cls_item)
    tpl = new_tuple(*instances)

    cls_item.set_relation("R51__instances_are_from", tpl)

    return tpl

def set_multiple_statements(subjects: Union[list, tuple], predicate: Relation, object: Any, qualifiers=None):
    """
    For every element of subjects, create a statement with predicate and object
    """

    res = []
    for sub in subjects:
        assert isinstance(sub, Entity)
        stm = sub.set_relation(predicate, object, qualifiers=qualifiers)
        res.append(stm)

    return res



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
    R2__has_description=("specifies that the inverse relation of the subject is functional"),
    # R8__has_domain_of_argument_1=I1["general item"],  # unsure here
    R11__has_range_of_result=bool,
    # TODO: model that this is (probably) equivalent to "owl:InverseFunctionalProperty"
)

R54 = create_builtin_relation(
    key_str="R54",
    R1__has_label="is matched by rule",
    R2__has_description=("specifies that subject entitiy is matched by a semantic rule"),
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
    R2__has_description=("specifies that the subject is equivalent to one of the elements of the object"),
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
    R1__has_label="has rule-prototype-graph-mode",
    R2__has_description=(
        "specifies that the subject should be threated according to the mode (int number) when constructing the "
        "prototype graph of an I41__semantic_rule; Modes: 0 -> normal; 1 -> ignore node, 2 -> relation statement, "
        "3 -> variable literal, 4 -> function-anchor; 5 -> create_asserted_statement_only_if_new; "
        "currently '2' is not implemented.",
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=int,
    R18__has_usage_hint="used to adjust the meaning of a statement in the scopes of a I41__semantinc_rule",
)

qff_has_rule_ptg_mode = QualifierFactory(R59["has rule-prototype-graph-mode"])

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

# R61["does not have property"] already defined above

R62 = create_builtin_relation(
    key_str="R62",
    R1__has_label="is relation property",
    R2__has_description=(
        "specifies that a relation is a 'relation property' (like R22_is_functional) and thus threated specially "
        "by edge matching."
    ),
    R8__has_domain_of_argument_1=I40["general relation"],
    R11__has_range_of_result=bool,
    R22__is_functional=True,
)

R22["is functional"].set_relation(R62["is relation property"], True)
R32["is functional for each language"].set_relation(R62["is relation property"], True)
R53["is inverse functional"].set_relation(R62["is relation property"], True)
R42["is symmetrical"].set_relation(R62["is relation property"], True)
R60["is transitive"].set_relation(R62["is relation property"], True)
R62["is relation property"].set_relation(R62["is relation property"], True)


def get_relation_properties_uris():

    stms: List[Statement] = ds.relation_statements[R62.uri]
    uris = []
    for stm in stms:
        # stm is like: RE3064(<Relation R22["is functional"]>, <Relation R62["is relation property"]>, True)
        if stm.object == True:
            uris.append(stm.subject.uri)

    return uris


# TODO: this could be speed up by caching
def get_relation_properties(rel_entity: Entity) -> List[str]:
    """
    return a sorted list of URIs, corrosponding to the relation properties corresponding to `rel_entity`.
    """

    assert isinstance(rel_entity, Relation) or rel_entity.R4__is_instance_of == I40["general relation"]

    relation_properties_uris = get_relation_properties_uris()
    rel_props = []
    for rp_uri in relation_properties_uris:
        res = rel_entity.get_relations(rp_uri, return_obj=True)
        assert len(res) <= 1, "unexpectedly got multiple relation properties"
        if res == [True]:
            rel_props.append(rp_uri)
    rel_props.sort()
    return rel_props


R63 = create_builtin_relation(
    key_str="R63",
    R1__has_label="has SPARQL source",
    R2__has_description=("specifies that the subject (a scope) is featured by some unique SPARQL source code"),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=str,
    R22__is_functional=True,
)


I44 = create_builtin_item(
    key_str="I44",
    R1__has_label="variable literal",
    R2__has_description="base class for items which represent variable literal values inside semantic rules",
    R4__is_instance_of=I2["Metaclass"],
    R18__has_usage_hint="used in the class _rule__CM",
)


R64 = create_builtin_relation(
    key_str="R64",
    R1__has_label="has scope type",
    R2__has_description=("specifies the subject (a scope) has a certain type (currently 'OR', 'AND')"),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=str,
    R22__is_functional=True,
)


R65 = create_builtin_relation(
    key_str="R65",
    R1__has_label="allows alternative functional value",
    R2__has_description=(
        "qualifier that specifies that the subject (a statement) might add an additional statement for a functional "
        "relation."
    ),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=str,
    R22__is_functional=True,
    R18__has_usage_hint="used inside OR-subscopes of semantic rules",
)

qff_allows_alt_functional_value = QualifierFactory(R65["allows alternative functional value"])


# R66 - R68 are defined above to keep dependencies simple


R69 = create_builtin_relation(
    key_str="R69",
    R1__has_label="has explanation text template",
    R2__has_description=(
        "associates a template text to the subject (a rule), which can be processed by the ruleengine."
    ),
    R8__has_domain_of_argument_1=I41["semantic rule"],
    R11__has_range_of_result=str,
    R32__is_functional_for_each_language=True,
    R18__has_usage_hint="used to generate explaining reports of rule results",
)


R70 = create_builtin_relation(
    key_str="R70",
    R1__has_label="has number of prototype-graph-components",
    R2__has_description=(
        "specifies the number of weakly connected 'main components' of the prototype graph of a semantic rule"
    ),
    R8__has_domain_of_argument_1=I41["semantic rule"],
    R11__has_range_of_result=int,
    R22__is_functional=True,
)

R71 = create_builtin_relation(
    key_str="R71",
    R1__has_label="enforce matching result type",
    R2__has_description=(
        "specifies that the subject (a relation) should be used in a statement where the object is an instance (R4) "
        "of the subjects (first) R11-value; to be used in rules"
    ),
    R8__has_domain_of_argument_1=I40["general relation"],
    R11__has_range_of_result=bool,
    R18__has_usage_hint="used to to control the behavior of rules with subjectivized predicates",
    R22__is_functional=True,
)


# next keys: I45, R72

# ######################################################################################################################
# condition functions (to be used in the premise scope of a rule)
# ######################################################################################################################


def label_compare_method(self, item1, item2) -> bool:
    """
    Condition function for rules. Returns True if label of item 1 is alphabetically smaller then that of item2
    """

    if item2.R1 is None:
        # item2 is (probably) undefined
        return True

    if item1.R1 is None:
        return False

    return item1.R1 < item2.R1


def does_not_have_relation(self, item: Item, rel: Relation) -> bool:
    """
    Condition function for rules. Returns True if item does not have any statement where rel is the predicate
    """

    res = item.get_relations(rel.uri)
    return not res


# ######################################################################################################################
# consequent functions (to be used in the assertion scope of a rule)
# ######################################################################################################################


def replacer_method(self, old_item, new_item):
    """
    replace old_item with new_item in every statement, unlink the old item
    """

    try:
        res = core.replace_and_unlink_entity(old_item, new_item)
    except core.aux.UnknownURIError:
        # if one of the two does not exist -> do nothing
        res = RuleResult()

    return res


def copy_statements(self, rel1: Relation, rel2: Relation):
    """
    For every statement like (i1, rel1, i2) create a new statement with rel2 as predicate.
    """
    res = RuleResult()
    for stm in ds.relation_statements[rel1.uri]:
        stm: Statement
    #    TODO: handle qualifiers
        new_stm = stm.subject.set_relation(rel2, stm.object, prevent_duplicate=True)
        res.add_statement(new_stm)

    # this function intentially does not return a new item; only called for its side-effects
    return res


def reverse_statements(self, rel: Relation):
    """
    For every statement like (i1, rel1, i2) create a new statement (i2, rel, i1) (if it does not yet exist).
    """
    res = RuleResult()
    for stm in ds.relation_statements[rel.uri]:
        stm: Statement
        # TODO: handle qualifiers
        assert isinstance(stm.object, Entity)
        existing_reverse_statement_objs = stm.object.get_relations(rel.uri, return_obj=True)
        if stm.subject in existing_reverse_statement_objs:
            # the symmetrically associated statement does already exist -> do nothing
            continue

        # do not process statements which are made inside of a rule (recognizable via qualifier)
        continue_flag = False
        for qf in stm.qualifiers:
            if qf.predicate == R20["has defining scope"]:
                anchor_obj = qf.object.R21__is_scope_of
                if anchor_obj.R4__is_instance_of == I41["semantic rule"]:
                    continue_flag = True
                    # end iterating over qualifiers
                    break

        if continue_flag:
            continue

        new_stm = stm.object.set_relation(rel, stm.subject, prevent_duplicate=True)
        res.add_statement(new_stm)

    return res


def new_instance_as_object(self, subj, pred, obj_type, placeholder=False, name_prefix=None):
    """
    Create a new instance of obj_type and then use this as the object in a new statement.
    """

    res = RuleResult()

    if name_prefix is None:
        name_prefix = f"{obj_type.R1} of "

    name = f"{name_prefix}{subj.R1}"

    new_obj = instance_of(obj_type, r1=name)

    new_stm = subj.set_relation(pred, new_obj)
    res.add_statement(new_stm)
    res.add_entity(new_obj)

    if placeholder:
        new_stm2 = new_obj.set_relation(R57["is placeholder"], True)
        res.add_statement(new_stm2)
    return res


def raise_contradiction(self, msg_template, *args):
    msg = msg_template.format(*args)
    raise core.aux.LogicalContradiction(msg)


def raise_reasoning_goal_reached(self, msg_template, *args):
    msg = msg_template.format(*args)
    raise core.aux.ReasoningGoalReached(msg)


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
