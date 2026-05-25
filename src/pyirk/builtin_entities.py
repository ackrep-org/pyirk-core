from typing import List, Union, Optional, Any, Tuple
from collections import defaultdict

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


# Facade re-export of implementation migrated to the `_builtin` subpackage.
# NOTE: this must be imported *before* the bootstrapping block below, because that
# block calls e.g. `instance_of` at import time (via `I64.scope(...)`). The submodule
# only binds the (partially loaded) `builtin_entities` module object and reads its
# globals lazily at call time, so importing it here does not cause a circular failure.
from ._builtin.taxonomy import *  # noqa: E402,F401,F403
from ._builtin.scopes import *  # noqa: E402,F401,F403
from ._builtin.math_expressions import *  # noqa: E402,F401,F403
from ._builtin.operators import *  # noqa: E402,F401,F403
from ._builtin.statement_utils import *  # noqa: E402,F401,F403


########################################################################################################################
#
#            Creation of entities
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
    R2,
    "specifies that for each subject there is at most one 'R30-Statement' for a given language tag (e.g. en)",
)
R18 = create_builtin_relation(
    "R18", R1="has usage hint", R2="specifies a hint (str) on how this relation should be used"
)

R22 = create_builtin_relation(
    key_str="R22",
    R1="is functional",
    R2="specifies that the subject entity is a relation which has at most one value per item",
)

I40 = create_builtin_item(
    key_str="I40",
    R1__has_label="general relation",
    R2__has_description="proxy item for a relation",
    R18__has_usage_hint=(
        "This item (which is in no direct relation to I1__general_item) can be used as a placeholder for any relation. "
        "In other words: this can be interpreted as the common superclass for all relations"
    ),
)

R22["is functional"].set_relation(R22["is functional"], True)
R32["is functional for each language"].set_relation(R22["is functional"], True)

# Note that R1, R22, and R32 are used extensively to control the behavior in pyirk.core

R3 = create_builtin_relation("R3", R1="is subclass of", R22__is_functional=True)
R4 = create_builtin_relation("R4", R1="is instance of", R22__is_functional=True)

# update type of relations before automatic was possible (in create_relation())
R32.set_relation(R4["is instance of"], I40["general relation"])
R1.set_relation(R4["is instance of"], I40["general relation"])
R2.set_relation(R4["is instance of"], I40["general relation"])
R18.set_relation(R4["is instance of"], I40["general relation"])
R22.set_relation(R4["is instance of"], I40["general relation"])
R3.set_relation(R4["is instance of"], I40["general relation"])
R4.set_relation(R4["is instance of"], I40["general relation"])

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

# The short key R61 was chosen for historical and/or pragmatic reasons
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


R16.set_relation(R18["has usage hint"], "this relation should be used on concrete instances, not on generic types")
R61.set_relation(R18["has usage hint"], "this relation should be used on concrete instances, not on generic types")

R19 = create_builtin_relation(
    key_str="R19",
    R1="defines method",
    R2="specifies that an entity has a special method (defined by executable code)",
    # R10__has_range_of_result=callable !!
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
    R2="specifies the scope *in* which an entity or statement is defined (e.g. the premise of a theorem)",
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
    R1="general property",
    R2__has_description="base class for all properties",
    R4__is_instance_of=I2["Metaclass"],
    R18__has_usage_hint=(
        "Actual properties are instances of this class (not subclasses). "
        "To create a taxonomy-like structure the relation R17__is_sub_property_of should be used."
    ),
)

# TODO: clarify the difference between the I12 and I18
I12 = create_builtin_item(
    key_str="I12",
    R1__has_label="mathematical object",
    R2__has_description="base class for any knowledge object of interest in the field of mathematics",
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
    # R3__is_subclass_off will be set below to I22__mathematical_knowledge_artifact
)


# I15 is defined below


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


# NOTE: `_register_scope`, `add_relations_to_scope`, `get_scopes` and
# `get_items_defined_in_scope` have been moved to `._builtin.scopes` and are
# re-exported above. The method-binding for `_register_scope` stays here on
# purpose (only `def`/`class` definitions were moved).

# every entity can have scopes
Entity.add_method_to_class(_register_scope)


def add_scope_to_defining_statement(ent: Entity, scope: Item) -> None:
    """

    :param ent:
    :param scope:
    :return:        None

    The motivation for this function is a usage pattern like:
    ```
    with I3007.scope("setting") as cm:
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


# NOTE: `ScopingCM`, `AbstractMathRelatedScopeCM`, `ConditionSubScopeCM` and
# `QuantifiedSubScopeCM` have been moved to `._builtin.scopes` and are re-exported above.


# class SubScopeConditionCM(AbstractMathRelatedScopeCM):
#     """
#     A scoping context manager to specify the condition of another scope
#     """

#     valid_subscope_types = {}


class _proposition__CM(AbstractMathRelatedScopeCM):
    """
    Context manager tailored for mathematical theorems and definitions
    """

    valid_subscope_types = {
        "UNIV_QUANT": float("inf"),
        "EXIS_QUANT": float("inf"),
        "OR": float("inf"),
        "AND": float("inf"),
        "NOT": float("inf"),
    }

    def universally_quantified(self) -> ScopingCM:
        """
        Create a new subscope of type "UNIV_QUANT", which can hold arbitrary statements. That subscope will contain
        another subscope ("CONDITION") whose statements are considered as universally quantified condition-statements.
        """

        # create a new context manager (which implicitly creates a new scope-item), where the user can add statements
        # note: this also creates an internal "CONDITION" subscope
        cm = self._create_subscope_cm(scope_type="UNIV_QUANT", cls=QuantifiedSubScopeCM)
        return cm

    def existentially_quantified(self) -> ScopingCM:
        """
        Create a new subscope of type "EXIS_QUANT", which can hold arbitrary statements. That subscope will contain
        another subscope ("CONDITION") whose statements are considered as existentially quantified condition-statements.
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


class _rule__CM(AbstractMathRelatedScopeCM):
    valid_subscope_types = {"AND": float("inf"), "OR": 1}

    def __init__(self, *args, **kwargs):
        self._anchor_item_counter = 0
        super().__init__(*args, **kwargs)
        r21_parent_of_scope = self.scope.R21__is_scope_of
        while True:
            # take care of nested scopes
            tmp = r21_parent_of_scope.R21__is_scope_of
            if tmp:
                r21_parent_of_scope = tmp
            else:
                break
        self.rule = r21_parent_of_scope
        assert is_instance_of(self.rule, I41["semantic rule"])

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
            I40["general relation"],
            r1=f"{name} (I40__general_relation)",
            qualifiers=[qff_has_rule_ptg_mode(1)],
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

    # TODO unify these logical rules with the logical rules for theorems etc.
    def NOT(self):
        msg = "implementing this is planned for the future"
        raise NotImplementedError

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


I14["mathematical proposition"].add_method(_proposition__scope, name="scope")


# NOTE: `_get_subscopes` and `_get_subscope` have been moved to `._builtin.scopes`
# and are re-exported above; only their method-bindings stay here.
I14["mathematical proposition"].add_method(_get_subscopes, name="get_subscopes")
I16["scope"].add_method(_get_subscopes, name="get_subscopes")


I14["mathematical proposition"].add_method(_get_subscope, name="get_subscope")
I16["scope"].add_method(_get_subscope, name="get_subscope")


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


I15 = create_builtin_item(
    key_str="I15",
    R1__has_label="implication proposition",
    R2__has_description="proposition, where the premise (if-part) implies the assertion (then-part)",
    R3__is_subclass_of=I14["mathematical proposition"],
)


I17 = create_builtin_item(
    key_str="I17",
    R1__has_label="equivalence proposition",
    R2__has_description="proposition, which establishes the equivalence of two sets of statements (premise and assertion)",
    R3__is_subclass_of=I14["mathematical proposition"],
    R18__has_usage_hint=(
        "While for I15__implication_proposition the border between scopes 'setting' and premise is somewhat arbitrary "
        "this is not the case for I17__equivalence_proposition because assertion and premise here are interchangeable. "
        "The implication must be true in the other direction as well."
    ),
)


I51 = create_builtin_item(
    key_str="I51",
    R1__has_label="data type",
    R2__has_description="subclasses of this item model data types such as string",
    R4__is_instance_of=I2["Metaclass"],
    R18__has_usage_hint="This class is meant to be 'abstract': it is not intended to be instantiated itself",
)


I52 = create_builtin_item(
    key_str="I52",
    R1__has_label="string",
    R2__has_description="equivalent entity of the python datatype `str`",
    R3__is_subclass_of=I51["data type"],
)


I53 = create_builtin_item(
    key_str="I53",
    R1__has_label="bool",
    R2__has_description="equivalent entity of the python datatype `bool`",
    R3__is_subclass_of=I51["data type"],
)


I18 = create_builtin_item(
    key_str="I18",
    R1__has_label="mathematical expression",  # = math. term
    R2__has_description=(
        "mathematical expression, e.g. represented by a LaTeX-string; this might change in the future to MathMl"
    ),
    R3__is_subclass_of=I12["mathematical object"],
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
R24["has LaTeX string"].set_relation(R11["has range of result"], I52["string"])


# NOTE: create_expression moved to _builtin/math_expressions.py


I19 = create_builtin_item(
    key_str="I19",
    R1__has_label="language-specified string literal",
    R2__has_description="used to encode strings that depend on natural languages",
    R4__is_instance_of=I2["Metaclass"],
)

R1.set_relation(R11, I19["language-specified string literal"])
R2.set_relation(R11, I19["language-specified string literal"])


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
I20["mathematical definition"].add_method(_get_subscope, name="get_subscope")


I21 = create_builtin_item(
    key_str="I21",
    R1__has_label="mathematical relation",
    R2__has_description="establishes that two mathematical expressions (I18) are in a relation, e.g. equality",
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

I46 = create_builtin_item(
    key_str="I46",
    R1__has_label="knowledge artifact",
    R2__has_description="general type for things like a theory, quote, equation ...",
    R4__is_instance_of=I2["Metaclass"],
)

I22 = create_builtin_item(
    key_str="I22",
    R1__has_label="mathematical knowledge artifact",
    R2__has_description="(class for) something like an equation or a theorem",
    R3__is_subclass_of=I46["knowledge artifact"],
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
        "This item is different from inequality (I25): There, lhs and rhs need to be members of the same ordered set."
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
    #  this needs be reflected here (maybe use qualifiers or a separate relation for each argument)
)


# NOTE: get_arguments and create_evaluated_mapping moved to _builtin/math_expressions.py
# (the add_method bindings below still reference create_evaluated_mapping via the facade re-export)


I6["mathematical operation"].add_method(create_evaluated_mapping, "_custom_call")
I7["mathematical operation with arity 1"].add_method(create_evaluated_mapping, "_custom_call")
I8["mathematical operation with arity 2"].add_method(create_evaluated_mapping, "_custom_call")
I9["mathematical operation with arity 3"].add_method(create_evaluated_mapping, "_custom_call")

# todo: maybe the difference between asserted inheritance and inferred inheritance should be encoded via qualifiers
R30 = create_builtin_relation(
    key_str="R30",
    R1__has_label="is secondary instance of",
    R2__has_description=(
        "specifies that the subject is an instance of a class-item, in addition to its unambiguous parent class."
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
        'specifies that the subject is related to the object via an instance of I21["mathematical relation"].'
    ),
    # TODO: update or delete:
    R18__has_usage_hint=(
        "The actual type of the relation can be retrieved by the .proxyitem attribute of the "
        "corresponding Statement."
    ),
)


# NOTE: new_equation and new_mathematical_relation moved to _builtin/math_expressions.py


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


# NOTE: get_proxy_item moved to _builtin/math_expressions.py


R35 = create_builtin_relation(
    key_str="R35",
    R1__has_label="is applied mapping of",
    R2__has_description="specifies the mapping entity for which the subject is an application",
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


# NOTE: new_tuple moved to _builtin/math_expressions.py


# different number types (complex, real, rational, integer, ...)


R46 = create_builtin_relation(
    key_str="R46",
    R1__has_label="is secondary subclass of",
    R2__has_description=(
        "specifies that the subject is an subclass of a class-item, in addition to its unambiguous parent class."
    ),
    R18__has_usage_hint=(
        "Note that this relation is not functional. This construction allows to combine single (R3) "
        "and multiple inheritance."
    ),
)


I42 = create_builtin_item(
    key_str="I42",
    R1__has_label="scalar mathematical expression",
    R2__has_description="base class of mathematical data types",
    R3__is_subclass_of=I18["mathematical expression"],
)


I34 = create_builtin_item(
    key_str="I34",
    R1__has_label="complex number",
    R2__has_description="mathematical type representing all complex numbers",
    R3__is_subclass_of=I42["scalar mathematical expression"],
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

I39["positive integer"].R1__has_label = "positive Ganzzahl" @ de


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
    R18__has_usage_hint="This relation should be used with the qualifier R40__has_index",
    R68__is_inverse_of=R15["is element of"],
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
    R9__has_domain_of_argument_2=I53["bool"],
    R22__is_functional=True,
)


R68["is inverse of"].set_relation(R42["is symmetrical"], True)


R43 = create_builtin_relation(
    key_str="R43",
    R1__has_label="is opposite of",
    R2__has_description="specifies that the subject is the opposite of the object.",
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
I41["semantic rule"].add_method(_get_subscopes, name="get_subscopes")
I41["semantic rule"].add_method(_get_subscope, name="get_subscope")

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
    R11__has_range_of_result=I53["bool"],
    R18__has_usage_hint=(
        "should be used as qualifier to specify the free variables in theorems and similar statements; "
        "See also R66__is_existentially_quantified"
    ),
)


# this qualifier is can be used to express universal quantification (mathematically expressed with ∀) of a relation
# e.g. `some_item.set_relation(p.R15["is element of"], other_item, qualifiers=univ_quant(True))`
# means that the statements where `some_item` is used claim to hold for all elements of `other_item` (which should be
# a set)
# see docs for more general information about qualifiers
univ_quant = QualifierFactory(R44["is universally quantified"])


# TODO: this should use qualifier approach
# NOTE: uq_instance_of moved to _builtin/math_expressions.py


# placed here for its obvious relation to universal quantification
R66 = create_builtin_relation(
    key_str="R66",
    R1__has_label="is existentially quantified",
    R2__has_description=(
        "specifies that the subject represents an existentially quantified variable (usually denoted by '∃')"
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=I53["bool"],
    R18__has_usage_hint=(
        "should be used as qualifier to specify the free variables in theorems and similar statements; "
        "See also R44__is_universally_quantified"
    ),
)

exis_quant = QualifierFactory(R66["is existentially quantified"])


R45 = create_builtin_relation(
    key_str="R45",
    R1__has_label="is subscope of",
    R2__has_description=("..."),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=I16["scope"],
    R18__has_usage_hint="used to specify that the subject (a scope instance is a subscope of another scope instance",
    R22__is_functional=True,
)


# NOTE: ImplicationStatement moved to _builtin/math_expressions.py


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
        "b) to express a nontrivial fact of inequality, e.g. that a person has two children and not just one with "
        "two names."
    ),
)

R51 = create_builtin_relation(
    key_str="R51",
    R1__has_label="instances are from",
    R2__has_description=("specifies that every instance of the subject (class) is one of the elements of the object"),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"],
    # TODO: model that this is (probably) equivalent to "owl:oneOf"
)


# NOTE: set_multiple_statements moved to _builtin/statement_utils.py


R52 = create_builtin_relation(
    key_str="R52",
    R1__has_label="is none of",
    R2__has_description=(
        "specifies that every instance of the subject (class) is different from each of the elements of the object"
    ),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"],
    # TODO: find out whether there is an owl equivalent for this relation
)
# http://www.w3.org/2002/07/owl#distinctMembers, http://www.w3.org/2002/07/owl#AllDifferent

R53 = create_builtin_relation(
    key_str="R53",
    R1__has_label="is inverse functional",
    R2__has_description=("specifies that the inverse relation of the subject is functional"),
    # R8__has_domain_of_argument_1=I1["general item"],  # unsure here
    R11__has_range_of_result=I53["bool"],
    # TODO: model that this is (probably) equivalent to "owl:InverseFunctionalProperty"
)

R54 = create_builtin_relation(
    key_str="R54",
    R1__has_label="is matched by rule",
    R2__has_description=("specifies that subject entity is matched by a semantic rule"),
    # R8__has_domain_of_argument_1=I1["general item"],  # unsure here
    R11__has_range_of_result=I41["semantic rule"],
    R18__has_usage_hint="useful for debugging and testing semantic rules",
)

R55 = create_builtin_relation(
    key_str="R55",
    R1__has_label="uses as external entity",
    R2__has_description=(
        "specifies that the subject (a setting-scope) uses the object entity as an external variable in its graph"
    ),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=I1["general item"],
    R18__has_usage_hint="useful for inside semantic rules",
)


R56 = create_builtin_relation(
    key_str="R56",
    R1__has_label="is one of",
    R2__has_description=("specifies that the subject is equivalent to one of the elements of the object"),
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I33["tuple"],
    # TODO: model that this is (probably) NOT equivalent to "owl:oneOf" (see R51 above)
    # TODO: decide whether this is the inverse of R52__is_none_of
)

R57 = create_builtin_relation(
    key_str="R57",
    R1__has_label="is placeholder",
    R2__has_description="specifies that the subject is a placeholder and might be replaced by other items",
    # TODO:
    # R8__has_domain_of_argument_1=<any ordinary instance>,
    R11__has_range_of_result=I53["bool"],
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
        "currently '2' is not implemented."
    ),
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=I37["integer number"],
    R18__has_usage_hint="used to adjust the meaning of a statement in the scopes of a I41__semantic_rule",
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
    R9__has_domain_of_argument_2=I53["bool"],
    R22__is_functional=True,
)

R17["is subproperty of"].set_relation(R60["is transitive"], True)

# R61["does not have property"] already defined above

R62 = create_builtin_relation(
    key_str="R62",
    R1__has_label="is relation property",
    R2__has_description=(
        "specifies that a relation is a 'relation property' (like R22_is_functional) and thus threated specially "
        "by edge matching."
    ),
    R8__has_domain_of_argument_1=I40["general relation"],
    R11__has_range_of_result=I53["bool"],
    R22__is_functional=True,
)

R22["is functional"].set_relation(R62["is relation property"], True)
R32["is functional for each language"].set_relation(R62["is relation property"], True)
R53["is inverse functional"].set_relation(R62["is relation property"], True)
R42["is symmetrical"].set_relation(R62["is relation property"], True)
R60["is transitive"].set_relation(R62["is relation property"], True)
R62["is relation property"].set_relation(R62["is relation property"], True)


# NOTE: get_relation_properties_uris moved to _builtin/statement_utils.py
# NOTE: get_relation_properties moved to _builtin/statement_utils.py


R63 = create_builtin_relation(
    key_str="R63",
    R1__has_label="has SPARQL source",
    R2__has_description=("specifies that the subject (a scope) is featured by some unique SPARQL source code"),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=I52["string"],
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
    R2__has_description=("specifies the subject (a scope) has a certain type (currently 'OR', 'AND', 'NOT')"),
    R8__has_domain_of_argument_1=I16["scope"],
    R11__has_range_of_result=I52["string"],
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
    R11__has_range_of_result=I52["string"],
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
    R11__has_range_of_result=I52["string"],
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
    R11__has_range_of_result=I37["integer number"],
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
    R11__has_range_of_result=I53["bool"],
    R18__has_usage_hint="used to to control the behavior of rules with subjectivized predicates",
    R22__is_functional=True,
)


I45 = create_builtin_item(
    key_str="I45",
    R1__has_label="general entity",
    R2__has_description="common superclass of I1['general item'] and I40['general relation']",
    # TODO: decide where to break the circle
    # R4__is_instance_of=I2["Metaclass"],
)

I1["general item"].set_relation(R3["is subclass of"], I45["general entity"])
I40["general relation"].set_relation(R3["is subclass of"], I45["general entity"])


R72 = create_builtin_relation(
    key_str="R72",
    R1__has_label="is generally related to",
    R2__has_description=("specifies that the subject is 'somehow' related to the object"),
    R8__has_domain_of_argument_1=I45["general entity"],
    R11__has_range_of_result=I53["bool"],
    R18__has_usage_hint="used to model relationships which are not (yet) possible to model otherwise",
)

R73 = create_builtin_relation(
    key_str="R73",
    R1__has_label="conceptually depends",
    R2__has_description=("specifies that the object is needed to define the subject"),
    R8__has_domain_of_argument_1=I45["general entity"],
    R11__has_range_of_result=I53["bool"],
    R18__has_usage_hint=(
        "Used to model directed relationships which are not (yet) possible to model otherwise. "
        "See R72__is_generally_related_to."
    ),
)


# I46 is defined above

I47 = create_builtin_item(
    key_str="I47",
    R1__has_label="constraint rule",
    R2__has_description="rule that specifies which constraints a set of entities has to fulfill",
    R3__is_subclass_of=I41["semantic rule"],
)

I48 = create_builtin_item(
    key_str="I48",
    R1__has_label="constraint violation",
    R2__has_description="instances of this class specify a concrete constraint violation",
    R3__is_subclass_of=I2["Metaclass"],
)

R74 = create_builtin_relation(
    key_str="R74",
    R1__has_label="has constraint violation",
    R2__has_description=("specifies that the subject violates some I47__constraint_rule"),
    R8__has_domain_of_argument_1=I45["general entity"],
    R11__has_range_of_result=I48["constraint violation"],
)


I49 = create_builtin_item(
    key_str="I49",
    R1__has_label="reification anchor",
    R2__has_description="instances of this class serve to express statements with arity > 2",
    R3__is_subclass_of=I2["Metaclass"],
    R18__has_usage_hint="see example usage in `new_tuple(...)`",
)

R75 = create_builtin_relation(
    key_str="R75",
    R1__has_label="has reification anchor",
    R2__has_description=("specifies that the subject is described by some reificated statement"),
    R8__has_domain_of_argument_1=I45["general entity"],
    R11__has_range_of_result=I48["constraint violation"],
    R18__has_usage_hint=(
        "example usage: specify the argument order for I33__tuple instances with R39__has_element " "and R40__has_index"
    ),
)

R76 = create_builtin_relation(
    key_str="R76",
    R1__has_label="has associated rule",
    R2__has_description="...",
    R8__has_domain_of_argument_1=I45["general entity"],
    R11__has_range_of_result=I41["semantic rule"],
    R22__is_functional=True,
)

I50 = create_builtin_item(
    key_str="I50",
    R1__has_label="stub",
    R2__has_description="instances of this class represent incompletely modelled items (like wikipedia stub-articles)",
    R3__is_subclass_of=I2["Metaclass"],  # could be also R4 here but does not matter because stubs are very unspecific
    R18__has_usage_hint="This class can be used to preliminarily introduce items and refine them later",
)


R77 = create_builtin_relation(
    key_str="R77",
    R1__has_label="has alternative label",
    R2__has_description="specifies alternative labels for entities in the sense of 'also called ...'",
    R8__has_domain_of_argument_1=I45["general entity"],
    R11__has_range_of_result=I19["language-specified string literal"],  # the labels should have a language specified
    R18__has_usage_hint="allows multiple values per language (in contrast to R1__has_label)",
)


R78 = create_builtin_relation(
    key_str="R78",
    R1__has_label="is applicable to",
    R2__has_description="specifies some property can be applied to some entity",
    R8__has_domain_of_argument_1=I11["general property"],
    # TODO: introduce some mechanism to distinguish whether a relation refers to the class in a direct or abstract sense
    # (where abstract means that it actually refers to the instances of the class)
    # example the mathematical property of symmetry might applicable to the class item ma.I9904["matrix"] but this statement
    # actually means that an individual matrix might have this property
    R11__has_range_of_result=I45["general entity"],
)


# I51, I52, I53, are defined above


I54 = create_builtin_item(
    key_str="I54",
    R1__has_label="mathematical property",
    R2__has_description="base class for all mathematical properties",
    R3__is_subclass_of=I11["general property"],
)

R79 = create_builtin_relation(
    key_str="R79",
    R1__has_label="has main subject",
    R2__has_description="definition refers to this item",
    R8__has_domain_of_argument_1=I20["mathematical definition"],
    R11__has_range_of_result=I1["general item"],
)


R80 = create_builtin_relation(
    key_str="R80",
    R1__has_label="applies to",
    R2__has_description="state that a theorem applies to an item",
    R8__has_domain_of_argument_1=I14["mathematical proposition"],
    R11__has_range_of_result=I1["general item"],
)

R81 = create_builtin_relation(
    key_str="R81",
    R1__has_label="has explanation",
    R2__has_description="states that there is verbal explanation related to the subject",
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=I52["string"],
)

I60 = create_builtin_item(
    key_str="I60",
    R1__has_label="abstract addition class",
    R3__is_subclass_of=I8["mathematical operation with arity 2"],
)

I55 = create_builtin_item(
    key_str="I55",
    R1__has_label="add",
    R2__has_description="general addition operator",
    R4__is_instance_of=I60["abstract addition class"],
    R8__has_domain_of_argument_1=I12["mathematical object"],
    R9__has_domain_of_argument_2=I12["mathematical object"],
    R11__has_range_of_result=I12["mathematical object"],
)

I61 = create_builtin_item(
    key_str="I61",
    R1__has_label="abstract multiplication class",
    R3__is_subclass_of=I8["mathematical operation with arity 2"],
)

I56 = create_builtin_item(
    key_str="I56",
    R1__has_label="mul",
    R2__has_description="general multiplication operator",
    R4__is_instance_of=I61["abstract multiplication class"],
    R8__has_domain_of_argument_1=I12["mathematical object"],
    R9__has_domain_of_argument_2=I12["mathematical object"],
    R11__has_range_of_result=I12["mathematical object"],
)

I62 = create_builtin_item(
    key_str="I62",
    R1__has_label="abstract power class",
    R3__is_subclass_of=I8["mathematical operation with arity 2"],
)

I57 = create_builtin_item(
    key_str="I57",
    R1__has_label="pow",
    R2__has_description="general power operator",
    R4__is_instance_of=I62["abstract power class"],
    R8__has_domain_of_argument_1=I12["mathematical object"],
    R9__has_domain_of_argument_2=I12["mathematical object"],
    R11__has_range_of_result=I12["mathematical object"],
)

I63 = create_builtin_item(
    key_str="I63",
    R1__has_label="abstract negation class",
    R3__is_subclass_of=I7["mathematical operation with arity 1"],
)

I58 = create_builtin_item(
    key_str="I58",
    R1__has_label="neg",
    R2__has_description="general negation operator",
    R4__is_instance_of=I63["abstract negation class"],
    R8__has_domain_of_argument_1=I12["mathematical object"],
    R11__has_range_of_result=I12["mathematical object"],
)

R82 = create_builtin_relation(
    key_str="R82",
    R1__has_label="has alternative latex string",
    R2__has_description="has alternative latex notation, different from R24['has LaTeX string']",
    R8__has_domain_of_argument_1=I18["mathematical expression"],
    R11__has_range_of_result=I52["string"],
)


# NOTE: add_items moved to _builtin/operators.py
# NOTE: radd_items moved to _builtin/operators.py
# NOTE: sub_items moved to _builtin/operators.py
# NOTE: reflective_sub_items moved to _builtin/operators.py
# NOTE: mul_items moved to _builtin/operators.py
# NOTE: rmul_items moved to _builtin/operators.py
# NOTE: div_items moved to _builtin/operators.py
# NOTE: reflective_div_items moved to _builtin/operators.py
# NOTE: pow_items moved to _builtin/operators.py
# NOTE: reflective_pow_items moved to _builtin/operators.py
# NOTE: neg_item moved to _builtin/operators.py


Item.__add__ = add_items
Item.__radd__ = radd_items  # reflective addition for 1 + Item
Item.__mul__ = mul_items
Item.__rmul__ = rmul_items
Item.__sub__ = sub_items
Item.__rsub__ = reflective_sub_items
Item.__truediv__ = div_items  # truediv is the correct method for / operator
Item.__rtruediv__ = reflective_div_items
Item.__pow__ = pow_items
Item.__rpow__ = reflective_pow_items
Item.__neg__ = neg_item


# NOTE: unpack_tuple_item moved to _builtin/operators.py


I59 = create_builtin_item(
    key_str="I59",
    R1__has_label="basic statement",
    R2__has_description="an ordinary statement (e.g. from the plain text of a book or a paper)",
    R3__is_subclass_of=I15["implication proposition"],
    R18__has_usage_hint="usually such statements do not need a premise and might even omit the setting.",
)


R83 = create_builtin_relation(
    key_str="R83",
    R1__has_label="is generalized subclass of",
    R2__has_description="specifies that the object is either a direct or indirect subclass of the subject",
    R18__has_usage_hint="this relation is intended to be set by a semantic rule, but not manually",
    R8__has_domain_of_argument_1=I2["Metaclass"],
    R11__has_range_of_result=I2["Metaclass"],
)

# create necessary qualifier, see R59["has rule-prototype-graph-mode"] above
qf_prevent_duplicate_stms = qff_has_rule_ptg_mode(5)


I64 = create_builtin_item(
    key_str="I64",
    R1__has_label="introduction of generalized subclass statements",
    R2__has_description=(
        "this rule creates R83__is_generalized_subclass_of statements parallel to " "R3__is_subclass of statements"
    ),
    R4__is_instance_of=I41["semantic rule"],
)

with I64.scope("setting") as cm:
    cm.new_var(i1=instance_of(I1["general item"]))
    cm.new_var(i2=instance_of(I1["general item"]))

with I64.scope("premise") as cm:
    cm.new_rel(cm.i2, R3["is subclass of"], cm.i1)

with I64.scope("assertion") as cm:
    cm.new_rel(cm.i2, R83["is generalized subclass of"], cm.i1, qualifiers=[qf_prevent_duplicate_stms])


I65 = create_builtin_item(
    key_str="I65",
    R1__has_label="propagation of generalized subclass",
    R2__has_description=("this rule creates R83__is_generalized_subclass_of statements for inheritance structures"),
    R4__is_instance_of=I41["semantic rule"],
)

with I65.scope("setting") as cm:
    cm.new_var(i1=instance_of(I1["general item"]))
    cm.new_var(i2=instance_of(I1["general item"]))
    cm.new_var(i3=instance_of(I1["general item"]))

with I65.scope("premise") as cm:
    cm.new_rel(cm.i2, R83["is generalized subclass of"], cm.i1)
    cm.new_rel(cm.i3, R83["is generalized subclass of"], cm.i2)

with I65.scope("assertion") as cm:
    # the qualifier prevents the creation of duplicated
    cm.new_rel(cm.i3, R83["is generalized subclass of"], cm.i1, qualifiers=[qf_prevent_duplicate_stms])

R85 = create_builtin_relation(
    key_str="R85",
    R1__has_label="is modeled by",
    R2__has_description="specifies that subject (some entity) is modeled by a relation (between two other entities)",
    R8__has_domain_of_argument_1=I1["general item"],
    R11__has_range_of_result=I40["general relation"],
    R18__has_usage_hint="this relation is intended to be set when the concept (subject) is meaningful, but inadequate \
        for modeling. Example: orthogonal vectors 'Orthogonality' 'is modeled by' 'is orthogonal to'",
)

R86 = create_builtin_relation(
    key_str="R86",
    R1__has_label="is used to model",
    R2__has_description="specifies that subject (some realtion) is used to modeled a concept",
    R8__has_domain_of_argument_1=I40["general relation"],
    R11__has_range_of_result=I1["general item"],
    R18__has_usage_hint="this relation is intended to be set when the concept (subject) is meaningful, but inadequate \
        for modeling. Example: orthogonal vectors 'Orthogonality' 'is modeled by' 'is orthogonal to'",
    R68__is_inverse_of=R85["is modeled by"],
)

I66 = create_builtin_item(
    key_str="I66",
    R1__has_label="propagation transitive relations",
    R2__has_description=("create new relations resulting from transtitive relations"),
    R4__is_instance_of=I41["semantic rule"],
)

with I66.scope("setting") as cm:
    cm.new_var(i1=instance_of(I1["general item"]))
    cm.new_var(i2=instance_of(I1["general item"]))
    cm.new_var(i3=instance_of(I1["general item"]))
    cm.new_rel_var("r1")

with I66.scope("premise") as cm:
    cm.new_rel(cm.r1, R60["is transitive"], True)
    cm.new_rel(cm.i1, cm.r1, cm.i2)
    cm.new_rel(cm.i2, cm.r1, cm.i3)

with I66.scope("assertion") as cm:
    # the qualifier prevents the creation of duplicated
    cm.new_rel(cm.i1, cm.r1, cm.i3, qualifiers=[qf_prevent_duplicate_stms])

# next keys: I66, R87


# ######################################################################################################################
# auxiliary entities
# ######################################################################################################################


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

# this allows to use I000("with any label") without triggering an exception in I000.idoc
I000._ignore_mismatching_adhoc_label = True
# ... same for R000
R000._ignore_mismatching_adhoc_label = True


# ######################################################################################################################
# condition functions (to be used in the premise scope of a rule)
# ######################################################################################################################


# NOTE: label_compare_method moved to _builtin/statement_utils.py
# NOTE: does_not_have_relation moved to _builtin/statement_utils.py


# ######################################################################################################################
# consequent functions (to be used in the assertion scope of a rule)
# ######################################################################################################################


# NOTE: replacer_method moved to _builtin/statement_utils.py
# NOTE: copy_statements moved to _builtin/statement_utils.py
# NOTE: reverse_statements moved to _builtin/statement_utils.py
# NOTE: new_instance_as_object moved to _builtin/statement_utils.py
# NOTE: raise_contradiction moved to _builtin/statement_utils.py
# NOTE: raise_reasoning_goal_reached moved to _builtin/statement_utils.py


# this is the inverse operation to `core.start_mod(__URI__)` (see above)
core.end_mod()
