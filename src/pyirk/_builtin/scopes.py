"""
Scope-machinery extracted from :mod:`pyirk.builtin_entities`.

Like :mod:`pyirk._builtin.taxonomy`, this module only binds the (partially
loaded) ``builtin_entities`` module object as ``_be``. All accesses to its
module-globals (items like ``I16``, relations like ``R20``, and already
migrated helpers like ``instance_of``) happen module-qualified and exclusively
at *call* time inside function/method bodies — never at import time.
"""

from typing import List, Union

from collections import defaultdict

from pyirk import core
from pyirk.core import Entity, Relation, Item, Statement, ds, RawQualifier, QualifierFactory

# Note: this import only binds the (already loaded) module object; its attributes
# are accessed lazily inside the function/method bodies (i.e. at call time, not import time).
from pyirk import builtin_entities as _be


__all__ = [
    "_register_scope",
    "add_relations_to_scope",
    "get_scopes",
    "get_items_defined_in_scope",
    "ScopingCM",
    "AbstractMathRelatedScopeCM",
    "ConditionSubScopeCM",
    "QuantifiedSubScopeCM",
    "_get_subscopes",
    "_get_subscope",
]


def _register_scope(self, name: str, scope_type: str = None) -> tuple[dict, "Item"]:
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
        scope = _be.instance_of(_be.I16["scope"], r1=scope_name, r2=f"scope of {self.R1}")
        scope.set_relation(_be.R21["is scope of"], self)

    # prevent accidental overwriting
    msg = f"Entity {self} already has a scope with name '{name}'.\nPossible reason: copy-paste-error."
    if scope_name in self.__dict__:
        raise core.aux.InvalidScopeNameError(msg)
    self.__dict__[scope_name] = scope

    assert isinstance(ns, dict)
    assert isinstance(scope, Item) and (scope.R21__is_scope_of == self)

    if scope_type is None:
        scope_type = name.upper()

    scope.set_relation(_be.R64["has scope type"], scope_type)

    return ns, scope


def add_relations_to_scope(relation_tuples: Union[list, tuple], scope: Entity):
    """
    Add relations defined by 3-tuples (sub, rel, obj) to the respective scope.

    :param relation_tuples:
    :param scope:
    :return:
    """

    assert scope.R21__is_scope_of is not None
    assert scope.R4__is_instance_of is _be.I16["scope"]

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
    [<scope:setting>, <scope:premise>, <scope:assertion>] for a proposition-item.

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
    assert scope.R4__is_instance_of == _be.I16["scope"]
    # R20__has_defining_scope
    re_list = core.ds.inv_statements[scope.short_key]["R20"]
    re: Statement
    entities = [re.relation_tuple[0] for re in re_list]
    return entities


class ScopingCM:
    """
    Context manager to for creating ("atomic") statements in the scope of other (bigger statements).
    E.g. establishing a relationship between two items as part of the assertions of a theorem-item
    """

    _all_instances = []
    _instances = defaultdict(list)

    valid_subscope_types = None

    def __init__(self, itm: Item, namespace: dict, scope: Item, parent_scope_cm=None):
        # prevent the accidental instantiation of abstract subclasses
        assert not __class__.__name__.lower().startswith("abstract")

        # the item to which the scope refers e.g. <Item I9223["definition of zero matrix"]>,
        self.item: Item = itm
        self.namespace: dict = namespace
        # the associated scope-item (which has a R64__has_scope_type relation)
        self.scope: Item = scope
        self.parent_scope_cm: ScopingCM | None = parent_scope_cm

        # introduced to facilitate debugging and experimentation
        self._instances[type(self)].append(self)
        self._all_instances.append(self)

    def __enter__(self):
        """
        implicitly called in the head of the with statement
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

        _be.add_scope_to_defining_statement(variable_object, self.scope)

        # this reflects a design assumption which might be generalized later
        assert isinstance(variable_object, Entity)

        # allow simple access to the variables → put them into dict (after checking that the name is still free)
        msg = f"The name '{variable_name}' is already occupied in the scope `{self.scope}` of item `{self.item}`."
        assert variable_name not in self.item.__dict__ and variable_name not in self.__dict__, msg
        self.item.__dict__[variable_name] = variable_object

        # keep track of added context vars
        self.namespace[variable_name] = variable_object

        # indicate that the variable object is defined in the context of `self`
        assert getattr(variable_object, "R20", None) is None
        variable_object.set_relation(_be.R20["has defining scope"], self.scope)

        # todo: evaluate if this makes the namespaces obsolete
        variable_object.set_relation(_be.R23["has name in scope"], variable_name)

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

    def _check_scope(self):
        active_scope = ds.scope_stack[-1]

        if not active_scope == self.scope:
            msg = f"Unexpected active scope: ({active_scope}). Expected: {self.scope}"
            raise core.aux.InvalidScopeNameError(msg)

    def _create_subscope_cm(self, scope_type: str, cls: type):
        """
        :param scope_type:     a str like "AND", "OR", "NOT"
        :param cls:            the class to instantiate, e.g. RulePremiseSubScopeCM

        """

        assert issubclass(cls, ScopingCM) or (cls == ScopingCM)

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
        cm.scope_type = scope_type
        return cm

    def copy_from(self, other_obj: Item, scope_name: str = None):
        assert isinstance(other_obj, Item)
        if scope_name is None:
            other_scope = other_obj
            assert other_scope.R4 is _be.I16["scope"]
        else:
            assert isinstance(scope_name, str)
            other_scope = other_obj.get_subscope(scope_name)

        statements = other_scope.get_inv_relations("R20__has_defining_scope")
        var_definitions = []
        relation_stms = []

        for stm in statements:
            if isinstance(stm, core.QualifierStatement):
                assert isinstance(stm.subject, core.Statement)
                relation_stms.append(stm.subject)
            elif isinstance(stm, core.Statement):
                var_definitions.append(stm.subject)

        if other_scope.R64__has_scope_type in ("PREMISE", "ASSERTION"):
            pass

        # create variables
        for var_item in var_definitions:
            name = var_item.R23__has_name_in_scope
            class_item = var_item.R4__is_instance_of

            # ensure that this variable was created with instance_of
            assert _be.is_generic_instance(var_item)

            if var_item.R35__is_applied_mapping_of:
                new_var_item = self._copy_mapping(var_item)
            else:
                new_var_item = self._new_var(variable_name=name, variable_object=_be.instance_of(class_item, r1=name))

            # to keep track of which old variables correspond to which new ones
            ds.scope_var_mappings[(self.scope.uri, var_item.uri)] = new_var_item

        # create relations
        stm: core.Statement
        for stm in relation_stms:
            subj, pred, obj = stm.relation_tuple
            new_subj = self._get_new_var_from_old(subj)
            new_obj = self._get_new_var_from_old(obj)

            # TODO: handle qualifiers and overwrite flag
            try:
                self.new_rel(new_subj, pred, new_obj)
            except core.aux.FunctionalRelationError:
                if new_subj.R35__is_applied_mapping_of is not None:
                    res = new_subj.overwrite_statement(pred.uri, obj)
                else:
                    raise
            except:
                raise

        # TODO: handle ImplicationStatement (see test_c07c__scope_copying)

    def _get_new_var_from_old(self, old_var: Item, strict=False) -> Item:

        if isinstance(old_var, core.allowed_literal_types):
            return old_var

        assert isinstance(old_var, Item)

        # 1st try: vars created in this scope
        new_var = ds.scope_var_mappings.get((self.scope.uri, old_var.uri))

        if new_var is not None:
            return new_var

        # 2nd try: vars created in the setting scope
        this_scope_parent = self.scope.R21__is_scope_of
        all_scopes = this_scope_parent.get_inv_relations("R21__is_scope_of", return_subj=True)

        setting_scopes = [scp for scp in all_scopes if scp.R64__has_scope_type == "SETTING"]
        assert len(setting_scopes) == 1
        setting_scope = setting_scopes[0]

        new_var = ds.scope_var_mappings.get((setting_scope.uri, old_var.uri))

        if new_var is not None:
            return new_var

        # TODO: look in the premise scope?

        if strict:
            msg = f"Unexpected: Could not find a copied item associated to {old_var}"
            raise core.aux.GeneralPyIRKError(msg)

        # last resort return the original variable (because it was an external var)
        return old_var

    def _copy_mapping(self, mapping_item: Item) -> Item:
        mapping_type = mapping_item.R35__is_applied_mapping_of
        assert mapping_type is not None

        name = mapping_item.R23__has_name_in_scope
        assert name is not None

        try:
            args = mapping_item.get_arguments()
        except AttributeError:
            args = ()
        new_args = (self._get_new_var_from_old(arg, strict=True) for arg in args)

        new_mapping_item = mapping_type(*new_args)
        # TODO: add R20__has_defining_scope and R23__has_name_in_scope

        self._new_var(variable_name=name, variable_object=new_mapping_item)

        return new_mapping_item

    def _get_premise_vars(self) -> dict:
        """
        return a dict of all items that were defined in the associated setting scope.

        key: variable names (via R23__has_name_in_scope)
        value: item objects
        """
        this_scope_parent = self.scope.R21__is_scope_of

        all_scopes = this_scope_parent.get_inv_relations("R21__is_scope_of", return_subj=True)

        setting_scopes = [scp for scp in all_scopes if scp.R64__has_scope_type == "SETTING"]
        assert len(setting_scopes) == 1
        setting_scope = setting_scopes[0]
        defined_items = setting_scope.get_inv_relations("R20__has_defining_scope")

        settings_vars_mapping = dict((stm.subject.R23__has_name_in_scope, stm.subject) for stm in defined_items)
        return settings_vars_mapping


class AbstractMathRelatedScopeCM(ScopingCM):
    """
    Context manager containing methods which are math-related
    """

    def new_equation(self, lhs: Item, rhs: Item, force_key: str = None) -> Item:
        """
        convenience method to create a equation-related Statement

        :param lhs:
        :param rhs:
        :return:
        """

        # prevent accidental identity of both sides of the equation
        assert lhs is not rhs

        eq = _be.new_equation(lhs, rhs, scope=self.scope, force_key=force_key)
        return eq

    # TODO: this makes  self.new_equation obsolete, doesn't it?
    def new_math_relation(
        self, lhs: Item, rsgn: str, rhs: Item, add_relations: dict = {}, force_key: str = None, name: str = None
    ) -> Item:
        """
        convenience method to create a math_relation-related StatementObject (aka "Statement")

        :param lhs:   left hand side
        :param rsgn:  relation sign
        :param rhs:   right hand sign

        :return:      new instance of
        """

        # prevent accidental identity of both sides of the equation
        assert lhs is not rhs

        rel = _be.new_mathematical_relation(
            lhs, rsgn, rhs, scope=self.scope, add_relations=add_relations, force_key=force_key
        )
        if name:
            # add name of equation to available names in context for explicit referencing
            # TODO unsure if this is the cleanest way
            msg = f"The name '{name}' is already occupied in the scope `{self.scope}` of item `{self.item}`."
            assert name not in self.item.__dict__ and name not in self.__dict__, msg
            self.item.__dict__[name] = rel

            # keep track of added context vars
            self.namespace[name] = rel

        return rel

    def AND(self) -> "ConditionSubScopeCM":
        """
        Create a new subscope of type "AND", which can hold arbitrary statements.
        These statements are considered to be AND-related in a boolean sense.
        """

        # This is forbidden because it likely means a modeling error
        self.check_scope_type(forbidden="AND")

        cm = self._create_subscope_cm(scope_type="AND", cls=ConditionSubScopeCM)
        return cm

    def OR(self) -> "ConditionSubScopeCM":
        """
        Create a new subscope of type "OR", which can hold arbitrary statements.
        These statements are considered to be OR-related in a boolean sense.
        """
        # This is forbidden because it likely means a modeling error
        self.check_scope_type(forbidden="OR")

        cm = self._create_subscope_cm(scope_type="OR", cls=ConditionSubScopeCM)
        return cm

    def NOT(self) -> "ConditionSubScopeCM":
        """
        Create a new subscope of type "NOT", which can hold arbitrary statements.
        These statements are considered to be negated in a boolean sense.
        """

        # This is forbidden because it likely means a modeling error
        self.check_scope_type(forbidden="AND")

        cm = self._create_subscope_cm(scope_type="NOT", cls=ConditionSubScopeCM)
        return cm

    def check_scope_type(self, *args, **kwargs):
        """
        This method might raise an exception in subclasses
        """
        pass


class ConditionSubScopeCM(AbstractMathRelatedScopeCM):
    """
    A scoping context manager to handle conditions
    """

    valid_subscope_types = {
        "UNIV_QUANT": float("inf"),
        "EXIS_QUANT": float("inf"),
        "OR": float("inf"),
        "AND": float("inf"),
        "NOT": float("inf"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # this will be set from outside (in `_create_subscope_cm()`) after instance-creation
        self.scope_type = None

    def add_condition_statement(self, subj, pred, obj, qualifiers=None):
        self.new_rel(subj, pred, obj, qualifiers=qualifiers)

    def add_condition_math_relation(self, *args, **kwargs):
        self.new_math_relation(*args, **kwargs)

    def new_condition_var(self, **kwargs):
        return self.new_var(**kwargs)

    def check_scope_type(self, forbidden):
        if self.scope_type == forbidden:
            msg = f"{forbidden}-scope inside {self.scope_type}-scope is not allowed"
            raise core.aux.InvalidScopeTypeError(msg)


class QuantifiedSubScopeCM(ConditionSubScopeCM):
    """
    A scoping context manager for universally or existentially quantified statements.

    Created by methods universally_quantified() and existentially_quantified() of _proposition__CM
    """

    pass


def _get_subscopes(self):
    """
    Convenience method for items which usually have scopes: allow easy access to subscopes
    """
    scope_rels: list = self.get_inv_relations("R21__is_scope_of", return_subj=True)
    return scope_rels


def _get_subscope(self, name: str):
    assert isinstance(name, str)
    scope_rels: list = self.get_inv_relations("R21__is_scope_of", return_subj=True)

    res = []
    for rel in scope_rels:
        assert isinstance(rel.R1, core.Literal)
        r1 = rel.R1.value
        if r1 == name or r1 == f"scp__{name}":
            res.append(rel)

    if len(res) == 0:
        msg = f"no scope with name {name} could be found"
        raise core.aux.InvalidScopeNameError(msg)
    elif len(res) > 1:
        msg = f"unexpected: scope name {name} is not unique"
        raise core.aux.InvalidScopeNameError(msg)
    else:
        return res[0]
