"""
Taxonomy-related helper functions extracted from :mod:`pyirk.builtin_entities`.

These functions are pure with respect to import time (they do not need any
module-globals of ``builtin_entities`` while this module is being imported).
Functions that use ``builtin_entities`` module-globals (I.., R.., qff_*) at
*call* time access them module-qualified via the ``_be`` module object, whose
attributes are only read once the functions are actually called.
"""

from typing import List, Union, Any

from pyirk import core
from pyirk.core import Item, Entity, Statement

# Note: this import only binds the (already loaded) module object; its attributes
# are accessed lazily inside the function bodies (i.e. at call time, not import time).
from pyirk import builtin_entities as _be


__all__ = [
    "allows_instantiation",
    "get_taxonomy_tree",
    "is_subclass_of",
    "is_instance_of",
    "instance_of",
    "is_generic_instance",
    "is_relevant_item",
    "get_direct_instances_of",
    "get_all_instances_of",
    "get_all_subclasses_of",
    "close_class_with_R51",
]


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
    #  ('R3', <Item I1["general item"]>)
    #  ('R3', <Item I45["general entity"]>)]

    if len(taxtree) < 2:
        return False

    relation_keys, items = zip(*taxtree)

    if len(items) < 3:
        # this is the case e.g. for:
        # [
        # ('R3', <Item I1["general item"]>)
        #  ('R3', <Item I45["general entity"]>)]
        return False

    if items[-3] is not _be.I2["Metaclass"]:
        return False

    if relation_keys.count("R4") > 1:
        return False

    return True


def get_taxonomy_tree(itm, add_self=True) -> list:
    """
    Recursively iterate over super and parent classes and

    :param itm:     an item
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
        msg = f"currently not allowed together: R3__is_subclass_of and R4__is_instance_of (Entity: {itm}"
        raise NotImplementedError(msg)

    if super_class:
        res.append(("R3", super_class))
        res.extend(get_taxonomy_tree(super_class, add_self=False))
    elif parent_class:
        res.append(("R4", parent_class))
        res.extend(get_taxonomy_tree(parent_class, add_self=False))

    return res


def is_subclass_of(itm1: Item, itm2: Item, allow_id=False, strict=True) -> bool:
    """
    Return True if itm1 is an (indirect) subclass (via) R3__is_subclass_of itm2

    :param allow_id:    bool, indicate that itm1 == itm2 is also considered
                        as valid. default: False
    """

    if allow_id and itm1 == itm2:
        return True

    if strict:
        for i, itm in enumerate((itm1, itm2), start=1):
            if not allows_instantiation(itm):
                msg = f"itm{i} ({itm}) is not a instantiable class"
                raise core.aux.TaxonomicError(msg)

    taxtree1 = get_taxonomy_tree(itm1)

    # This is a list of 2-tuples like the following:
    # [(None, <Item I4239["monovariate polynomial"]>),
    #  ('R3', <Item I4237["monovariate rational function"]>),
    #  ('R3', <Item I4236["mathematical expression"]>),
    #  ('R3', <Item I4235["mathematical object"]>),
    #  ('R4', <Item I2["Metaclass"]>),
    #  ('R3', <Item I1["general item"]>)
    #  ('R3', <Item I45["general entity"]>)]

    # reminder: R3__is_subclass_of, R4__is_instance_of

    res = ("R3", itm2) in taxtree1

    return res


def is_instance_of(inst_itm: Item, cls_itm: Item, allow_R30_secondary: bool = False, strict=True) -> bool:
    """
    Returns True if instance_itm.R4 is cls_itm or an (indirect) subclass (R3) of cls_itm.

    :param inst_itm:                Item representing the instance
    :param cls_itm:                 Item representing the class
    :param allow_R30_secondary:     bool, accept also relations via R30__is_secondary_instance_of
    :param strict:                  bool; if true we raise an exception if there is no parent class
    """
    parent_class = inst_itm.R4__is_instance_of

    if parent_class is None:
        if strict:
            msg = (
                f"instance_itm ({inst_itm}) has no Statement for relation `R4__is_instance_of`. "
                "You might use kwarg `strict=False`."
            )
            raise core.aux.TaxonomicError(msg)
        else:
            return False

    if parent_class == cls_itm:
        return True
    if is_subclass_of(parent_class, cls_itm, strict=strict):
        return True
    if allow_R30_secondary:

        for test_cls_item in inst_itm.R30__is_secondary_instance_of:
            if test_cls_item == cls_itm:
                return True
            if is_subclass_of(test_cls_item, cls_itm, strict=strict):
                return True
    return False


def instance_of(
    cls_entity, r1: str = None, r2: str = None, qualifiers: List[Item] = None, force_key: str = None
) -> Item:
    """
    Create an instance (R4) of an item. Try to obtain the label by inspection of the calling context (if r1 is None).

    :param cls_entity:      the type of which an instance is created
    :param r1:          the label; if None use inspection to fetch it from the left hand side of the assignment
    :param r2:          the description (optional)
    :param qualifiers:  list of RawQualifiers (optional); will be passed to the R4__is_instance_of relation

    if `cls_entity` has a defining scope and `qualifiers` is None, then an appropriate R20__has_defining_scope-
    qualifier will be added to the R4__is_instance_of-relation of the new item.

    :return:        new item
    """

    has_super_class = cls_entity.R3 is not None

    class_scope = cls_entity.R20__has_defining_scope

    # we have to determine if `cls_entity` is an instance of I2_metaclass or a subclass of it

    is_instance_of_metaclass = allows_instantiation(cls_entity)

    cls_exceptions = (_be.I1["general item"], _be.I40["general relation"])

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

    if force_key:
        key = force_key
    else:
        # add prefix2 "a" for "autogenerated"
        key = core.pop_uri_based_key(prefix="I", prefix2="a")

    new_item = core.create_item(
        key_str=key,
        R1__has_label=r1,
        R2__has_description=r2,
    )

    if not qualifiers and class_scope is not None:
        qualifiers = [_be.qff_has_defining_scope(class_scope)]
    new_item.set_relation(_be.R4["is instance of"], cls_entity, qualifiers=qualifiers)

    # add consistency relevant relations:
    # note that the could be overwritten with item.overwrite_statement
    for rel in [
        _be.R8["has domain of argument 1"],
        _be.R9["has domain of argument 2"],
        _be.R10["has domain of argument 3"],
        _be.R11["has range of result"],
    ]:

        obj = cls_entity.get_relations(rel.uri, return_obj=True)
        if obj not in ([], None):
            if isinstance(obj, list):
                assert len(obj) == 1
                obj = obj[0]
            new_item.set_relation(rel, obj)

    # TODO: solve this more elegantly
    # this has to be run again after setting R4
    new_item.__post_init__()

    return new_item


def is_generic_instance(itm: Item) -> bool:
    # TODO: make this more robust
    return itm.short_key[1] == "a"


def is_relevant_item(itm):
    return not itm.R57__is_placeholder and not itm.R20__has_defining_scope


def get_direct_instances_of(cls_item: Item, filter=None) -> List[Item]:
    assert allows_instantiation(cls_item)

    if filter is None:
        filter = lambda obj: True
    assert callable(filter)

    all_instances = cls_item.get_inv_relations("R4__is_instance_of", return_subj=True)
    res = [elt for elt in all_instances if filter(elt)]
    return res


def get_all_instances_of(cls_item: Item, filter=None) -> List[Item]:
    """
    Return all direct and indirect instances of a class
    """
    assert allows_instantiation(cls_item)

    # TODO: get (indirect) subclasses and then apply get_direct_instances
    subclasses = get_all_subclasses_of(cls_item=cls_item)

    instances: List = get_direct_instances_of(cls_item=cls_item, filter=filter)
    for sc in subclasses:
        instances.extend(get_direct_instances_of(sc, filter=filter))

    return instances


def get_all_subclasses_of(cls_item: Item, strict=True) -> List[Item]:
    """
    Recursively compile a list of all subclasses.
    """

    subclasses = cls_item.get_inv_relations("R3__is_subclass_of", return_subj=True)

    if strict:
        assert allows_instantiation(cls_item)

    indirect_subclasses = []
    for sc in subclasses:
        indirect_subclasses.extend(get_all_subclasses_of(sc, strict=strict))

    subclasses.extend(indirect_subclasses)

    return subclasses


def close_class_with_R51(cls_item: Item):
    """
    Set R51__instances_are_from for all current instances of a class.

    Note: this does not prevent the creation of further instances (because they can be related via R47__is_same_as to
    the existing instances).

    :returns:   tuple-item containing all instances
    """

    instances = get_direct_instances_of(cls_item)
    tpl = _be.new_tuple(*instances)

    cls_item.set_relation("R51__instances_are_from", tpl)

    return tpl
