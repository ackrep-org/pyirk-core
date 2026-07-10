"""
Math-/expression-related helper functions extracted from
:mod:`pyirk.builtin_entities`.

Like the sibling modules :mod:`pyirk._builtin.taxonomy` and
:mod:`pyirk._builtin.scopes`, this module only binds the (partially loaded)
``builtin_entities`` module object as ``_be``. All accesses to its
module-globals (items like ``I18``, relations like ``R24`` and qualifier
factories like ``proxy_item``) happen module-qualified and exclusively at
*call* time inside function/method bodies — never at import time. References to
symbols that also live in this module (e.g. ``new_tuple``, ``get_arguments``,
``new_mathematical_relation``) stay direct names.
"""

from typing import Optional, Tuple

from pyirk import core
from pyirk.core import Item, Statement, ds

# Note: this import only binds the (already loaded) module object; its attributes
# are accessed lazily inside the function/method bodies (i.e. at call time, not import time).
from pyirk import builtin_entities as _be


__all__ = [
    "create_expression",
    "get_arguments",
    "create_evaluated_mapping",
    "new_equation",
    "new_mathematical_relation",
    "get_proxy_item",
    "new_tuple",
    "uq_instance_of",
    "ImplicationStatement",
]


# TODO: how does this relate to I21["mathematical relation"]?
# -> Latex expressions are for human readable representation
# they should be used only as an addendum to semantic representations
# TODO: Fix ocse_ct.I6091["control affinity"]
def create_expression(latex_src: str, r1: str = None, r2: str = None) -> Item:
    if r1 is None:
        r1 = f"generic expression ({latex_src})"

    # TODO: hide such automatically created instances in search results by default (because there will be many)
    expression = _be.instance_of(_be.I18["mathematical expression"], r1=r1, r2=r2)

    expression.set_relation(_be.R24["has LaTeX string"], latex_src)

    return expression


# this function is added as a method to the results of `create_evaluated_mapping(...)` see below
def get_arguments(self: Item) -> Tuple[Item]:
    """
    Convenience function to simplify the access to the entities which are in
    itm.R36__has_argument_tuple.
    """

    arg_tuple_item = self.R36__has_argument_tuple
    if arg_tuple_item is None:
        msg = f"Unexpected: {self} has no arguments (associated via R36__has_argument_tuple)"
        raise core.aux.UndefinedRelationError

    args = arg_tuple_item.get_relations("R39__has_element", return_obj=True)
    return args


# TODO: doc: this mechanism needs documentation
# this function can be added to mapping objects as `_custom_call`-method
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
    # TODO: this should be ensured by consistency check: for operators R11 should be functional
    if target_class:
        assert len(target_class) == 1
        target_class = target_class[0]
    else:
        target_class = _be.I32["evaluated mapping"]

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
    ev_mapping = _be.instance_of(target_class, r1=r1)
    ev_mapping.set_relation(_be.R35["is applied mapping of"], mapping)

    arg_tup = new_tuple(*args)
    ev_mapping.set_relation(_be.R36["has argument tuple"], arg_tup)

    # honor auto-applied result relations declared on the operator via R88 (see above)
    for spec_stm in mapping.get_relations("R88"):
        result_relation = spec_stm.object
        target = None
        for qstm in spec_stm.qualifiers:
            if qstm.predicate == _be.R89["has result-relation target"]:
                target = qstm.object
                break
        if isinstance(target, int):
            # an integer target refers to the n-th argument of the application (1-based)
            target = args[target - 1]
        if target is not None:
            ev_mapping.set_relation(result_relation, target)

    # add convenience method
    ev_mapping.add_method(get_arguments, "get_arguments")

    ev_mapping.finalize()

    return ev_mapping


def new_equation(lhs: Item, rhs: Item, doc=None, scope: Optional[Item] = None, force_key: str = None) -> Item:
    """common special case of mathematical relation, also ensures backwards compatibility"""

    eq = new_mathematical_relation(lhs, "==", rhs, doc, scope, force_key=force_key)

    return eq


def new_mathematical_relation(
    lhs: Item,
    rsgn: str,
    rhs: Item,
    doc=None,
    scope: Optional[Item] = None,
    add_relations: dict = {},
    force_key: str = None,
) -> Item:
    rsgn_dict = {
        "==": _be.I23["equation"],
        "<": _be.I29["less-than-relation"],
        ">": _be.I28["greater-than-relation"],
        "<=": _be.I31["less-or-equal-than-relation"],
        ">=": _be.I30["greater-or-equal-than-relation"],
        "!=": _be.I26["strict inequality"],
    }
    if doc is not None:
        assert isinstance(doc, str)
    mr = _be.instance_of(rsgn_dict[rsgn], force_key=force_key)

    if scope is not None:
        mr.set_relation(_be.R20["has defining scope"], scope)

    if add_relations:
        for key, val in add_relations.items():
            mr.set_relation(key, val)

    # TODO: perform type checking
    # assert check_is_instance_of(lhs, I23("mathematical term"))

    mr.set_relation(_be.R26["has lhs"], lhs)
    mr.set_relation(_be.R27["has rhs"], rhs)

    re = lhs.set_relation(_be.R31["is in mathematical relation with"], rhs, scope=scope, qualifiers=[_be.proxy_item(mr)])

    return mr


def get_proxy_item(stm: Statement, strict=True) -> Item:
    assert isinstance(stm, Statement)

    if not stm.qualifiers:
        if strict:
            msg = f"No qualifiers found while searching for proxy-item-qualifier for {stm}."
            raise core.aux.MissingQualifierError(msg)
        else:
            return None

    relevant_qualifiers = [q for q in stm.qualifiers if q.predicate == _be.R34["has proxy item"]]

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


def new_tuple(*args, **kwargs) -> Item:
    """
    Create a new tuple entity
    :param args:
    :return:
    """

    # ensure this function is called with an active irk module (to define URIs of new instances )
    _ = core.get_active_mod_uri()

    scope = kwargs.pop("scope", None)
    assert len(kwargs) == 0, f"Unexpected keyword argument(s): {kwargs}"

    length = len(args)

    # TODO generate a useful label for the tuple instance
    args_str = str(args)
    if len(args_str) > 15:
        args_str = f"{args_str[:12]}..."
    tup = _be.instance_of(_be.I33["tuple"], r1=f"{length}-tuple: {args_str}")

    if scope is not None:
        tup.set_relation(_be.R20["has defining scope"], scope)

    tup.set_relation(_be.R38["has length"], len(args))

    for idx, arg in enumerate(args):
        tup.set_relation(_be.R39["has element"], arg, qualifiers=[_be.has_index(idx)])

        # new specification of index (allow easy access in rules)
        ra = _be.instance_of(_be.I49["reification anchor"])
        ra.set_relation(_be.R39["has element"], arg)
        ra.set_relation(_be.R40["has index"], idx)
        tup.set_relation(_be.R75["has reification anchor"], ra)

    return tup


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

    instance = _be.instance_of(type_entity, r1, r2, qualifiers=[_be.univ_quant(True)])
    # TODO: This should be used as a qualifier
    # instance.set_relation(R44["is universally quantified"], True)
    return instance


class ImplicationStatement:
    """
    Context manager to model conditional statements.

    Example from irk:/math/0.2#I7169["definition of identity matrix"]

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

        self.antecedent_scope = _be.instance_of(_be.I16["scope"], r1=scope_name_a, r2=r2a)
        self.antecedent_scope.set_relation(_be.R45["is subscope of"], parent_scope)

        self.consequent_scope = _be.instance_of(_be.I16["scope"], r1=scope_name_c, r2=r2c)
        self.consequent_scope.set_relation(_be.R45["is subscope of"], parent_scope)

    def __enter__(self):
        """
        implicitly called in the head of the with-statement
        """

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is the place to handle exceptions
        pass

    # todo why is this restricted to math. relations?
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
