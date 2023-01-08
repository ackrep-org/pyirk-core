"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module contains some rules for determining the solution of the zebra puzzle by logical reasoning.

See https://en.wikipedia.org/wiki/Zebra_Puzzle
"""

import pyerk as p

from ipydex import IPS  # for debugging

zb = p.erkloader.load_mod_from_path("./zebra_base_data.py", prefix="zb", reuse_loaded=True)


__URI__ = "erk:/ocse/0.2/zebra_puzzle_rules"

keymanager = p.KeyManager(keyseed=1629)
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I701 = p.create_item(
    R1__has_label="rule: imply parent relation of a subrelation",
    R2__has_description=("items which are related by a subrelation should also be related by the parent relation"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I701.scope("context") as cm:
    cm.new_var(rel1=p.instance_of(p.I40["general relation"]))
    cm.new_var(rel2=p.instance_of(p.I40["general relation"]))

with I701.scope("premises") as cm:
    cm.new_rel(cm.rel1, p.R17["is subproperty of"], cm.rel2)

with I701.scope("assertions") as cm:
    cm.new_consequent_func(p.copy_statements, cm.rel1, cm.rel2)

# ###############################################################################


I702 = p.create_item(
    R1__has_label="rule: add reverse statement for symmetrical relations",
    R2__has_description=("given statement (s, p, o) where p.R42__is_symmetrical==True implies statement (o, p, s)"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I702.scope("context") as cm:
    cm.new_var(rel1=p.instance_of(p.I40["general relation"]))

with I702.scope("premises") as cm:
    cm.new_rel(cm.rel1, p.R42["is symmetrical"], True)

with I702.scope("assertions") as cm:
    cm.new_consequent_func(p.reverse_statements, cm.rel1)

# ###############################################################################


I710 = p.create_item(
    R1__has_label="rule: identify same items via zb__R2850__is_functional_activity",
    R2__has_description=(
        "match two placeholders which are relate by a functional activity (R2850) with the same other items"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I710.scope("context") as cm:
    cm.new_var(ph1=p.instance_of(p.I1["general item"]))
    cm.new_var(ph2=p.instance_of(p.I1["general item"]))
    cm.new_var(some_itm=p.instance_of(p.I1["general item"]))
    cm.new_rel_var("rel1")  # -> p.instance_of(p.I40["general relation"]))

with I710.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
        ?ph1 :R57 true.
        ?ph2 :R57 true.
        ?ph1 ?rel1 ?some_itm.
        ?ph2 ?rel1 ?some_itm.

        ?rel1 zb:R2850 true.
        FILTER (?ph1 != ?ph2)
        }
        """
    )
    # ?rel1 :zb__R2850__is_functional_activity True.
    # cm.new_rel(cm.ph1, p.R57["is placeholder"], True)
    # cm.new_rel(cm.ph2, p.R57["is placeholder"], True)

    # # both placeholders are related to the same item via the same relation
    # cm.new_rel(cm.ph1, cm.rel1, cm.some_itm)  # -> p.R58["wildcard relation"]
    # cm.new_rel(cm.ph2, cm.rel1, cm.some_itm)  # -> p.R58["wildcard relation"]

    # cm.new_rel(cm.rel1, zb.R2850["is functional activity"], True)

with I710.scope("assertions") as cm:
    cm.new_rel(cm.ph1, p.R47["is same as"], cm.ph2)

# ###############################################################################


I720 = p.create_item(
    R1__has_label="rule: replace (some) same_as-items",
    R2__has_description=("replace placeholder items which have one R47__is_same_as statement"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I720.scope("context") as cm:
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(p.R57["is placeholder"])

with I720.scope("premises") as cm:
    cm.new_rel(cm.itm1, p.R47["is same as"], cm.itm2)  # itm1 should stay, itm2 will be replaced by it
    cm.new_rel(cm.itm2, p.R57["is placeholder"], True)

    # ensure that item with the alphabetically bigger label will be replaced by the item with the lower label
    # e.g. person2 will be replaced by person1 etc.# the `self` is necessary because this function will become a method

    # This is the desired premise which does not yet work (due to functionality (R22) of placeholder)
    with cm.OR() as cm_OR:

        # case 1:  both are placeholders (- then itm1 must be alphabetically smaller)
        with cm_OR.AND() as cm_AND:
            cm_AND.new_rel(cm.itm1, p.R57["is placeholder"], True)
            cm_AND.new_condition_func(p.label_compare_method, cm.itm1, cm.itm2)

        # case 2:  itm1 is not a placholder (no statement)
        with cm_OR.AND() as cm_AND:
            cm_AND.new_condition_func(p.does_not_have_relation, cm.itm1, p.R57["is placeholder"])

        # case 3:  itm1 is not a placholder (explicit statement with object `False`)
        cm_OR.new_rel(cm.itm1, p.R57["is placeholder"], False, qualifiers=[p.qff_allows_alt_functional_value(True)])

    # TODO: this blocks the second application because only one itm is placeholder -> introduce logical OR
    # cm.new_condition_func(p.label_compare_method, cm.itm1, cm.itm2)

with I720.scope("assertions") as cm:
    # replace the certain placeholder (itm2) by the other item
    cm.new_consequent_func(p.replacer_method, cm.itm2, cm.itm1)

# ###############################################################################

I730 = p.create_item(
    R1__has_label="rule: deduce negative facts for neighbours",
    R2__has_description=("deduce some negative facts e.g. which pet a person does not own"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I730.scope("context") as cm:
    cm.new_var(h1=p.instance_of(zb.I7435["human"]))
    cm.new_var(h2=p.instance_of(zb.I7435["human"]))
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel2")

with I730.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?h1 zb:R3606 ?h2.        # R3606["lives next to"]

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1 :R43 ?rel2.        # R43__is_opposite_of

            ?h1 ?rel1 ?itm1.
        }
        """
    )

with I730.scope("assertions") as cm:
    cm.new_rel(cm.h2, cm.rel2, cm.itm1)

# ###############################################################################

I740 = p.create_item(
    R1__has_label="rule: deduce more negative facts from negative facts",
    R2__has_description=("deduce e.g. if h1 onws not dog, but dog owner drinks milk then h1 drinks not milk"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I740.scope("context") as cm:
    cm.new_var(h1=p.instance_of(zb.I7435["human"]))
    cm.new_var(h2=p.instance_of(zb.I7435["human"]))
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel2")
    cm.new_rel_var("rel1_not")
    cm.new_rel_var("rel2_not")

with I740.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?h1 ?rel1 ?itm1.
            ?h1 ?rel2 ?itm2.
            FILTER (?rel1 != ?rel2)
            FILTER (?itm1 != ?itm2)

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel2 zb:R2850 true.     # R2850__is_functional_activity

            ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of
            ?rel2 :R43 ?rel2_not.        # R43__is_opposite_of

            ?h2 ?rel1_not ?itm1.

            # prevent the addition of already known relations
            MINUS { ?h2 ?rel2_not ?itm2.}
        }
        """
    )

with I740.scope("assertions") as cm:
    cm.new_rel(cm.h2, cm.rel2_not, cm.itm2)

# ###############################################################################


I750 = p.create_item(
    R1__has_label="rule: every human lives in one house",
    R2__has_description=("human should have a house associated, create a new instance if neccessary"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I750.scope("context") as cm:
    cm.new_var(p1=p.instance_of(zb.I7435["human"]))
    cm.uses_external_entities(zb.I7435["human"], zb.R9040["lives in numbered house"], zb.I8809["house number"])

with I750.scope("premises") as cm:
    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_condition_func(p.does_not_have_relation, cm.p1, zb.R9040["lives in numbered house"])

with I750.scope("assertions") as cm:
    cm.new_consequent_func(
        # the last argument (True) specifies that the new entity will be a placeholder
        p.new_instance_as_object,
        cm.p1,
        zb.R9040["lives in numbered house"],
        zb.I8809["house number"],
        True,
    )
    # cm.new_rel(cm.h2, cm.rel2_not, cm.itm2)
    # zb.I8809["house number"]
    #     cm.new_variable_literal("house_index1")

# ###############################################################################


I760 = p.create_item(
    R1__has_label="rule: deduce impossible house indices of neighbour",
    R2__has_description=("next to house 1 is house 2"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I760.scope("context") as cm:
    # persons
    cm.new_var(p1=p.instance_of(zb.I7435["human"]))
    cm.new_var(p2=p.instance_of(zb.I7435["human"]))

    # house numbers
    cm.new_var(hn1=p.instance_of(p.I1["general item"]))
    cm.new_var(hn2=p.instance_of(p.I1["general item"]))

    # house number indices
    cm.new_variable_literal("house_index1")

with I760.scope("premises") as cm:
    cm.new_rel(cm.p1, zb.R3606["lives next to"], cm.p2)
    cm.new_rel(cm.p1, zb.R9040["lives in numbered house"], cm.hn1)
    cm.new_rel(cm.p2, zb.R9040["lives in numbered house"], cm.hn2)

    cm.new_rel(cm.hn1, p.R40["has index"], cm.house_index1)


def exclude_house_numbers_for_neighbour(self, nbr_hn: p.Item, primal_house_index: int) -> p.RuleResult:
    """
    Given the index (int) of a (primal) house, inferre which house_number (represented by nbr_hn) are not allowed
    for the neighbour
    """

    res = p.RuleResult()

    possible_indices = {primal_house_index - 1, primal_house_index + 1}
    impossible_indices = set(zb.possible_house_indices.R39__has_element).difference(possible_indices)

    imp_idcs_tup = p.new_tuple(*impossible_indices)

    stm = nbr_hn.set_relation(zb.R8139["has impossible indices"], imp_idcs_tup)
    res.add_statement(stm)
    res.add_entity(imp_idcs_tup)
    return res


with I760.scope("assertions") as cm:
    cm.new_consequent_func(exclude_house_numbers_for_neighbour, cm.hn2, cm.house_index1)

# ###############################################################################


I770 = p.create_item(
    R1__has_label="rule: deduce impossible house_number items from impossible indices",
    R2__has_description=("deduce impossible house_number items (R52__is_none_of) from impossible indices"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I770.scope("context") as cm:
    cm.new_var(hn1=p.instance_of(zb.I8809["house number"]))
    cm.new_var(imp_idcs_tup=p.instance_of(p.I33["tuple"]))

    cm.uses_external_entities(zb.I8809["house number"])

with I770.scope("premises") as cm:
    cm.new_rel(cm.hn1, p.R4["is instance of"], zb.I8809["house number"], overwrite=True)
    cm.new_rel(cm.hn1, zb.R8139["has impossible indices"], cm.imp_idcs_tup)


def create_none_of_tuple(self, hn_item, imp_idcs_tup):

    res = p.RuleResult()

    all_house_numbers: list = zb.all_house_number_tuple.R39__has_element

    # tuple-item -> list
    imp_idcs: list = imp_idcs_tup.R39__has_element

    impossible_house_numbers = [h for h in all_house_numbers if getattr(h, "R40__has_index")[0] in imp_idcs]

    imp_hn_tup = p.new_tuple(*impossible_house_numbers)

    stm = hn_item.set_relation(p.R52["is none of"], imp_hn_tup)

    res.add_entity(hn_item)
    res.add_statement(stm)

    return res


with I770.scope("assertions") as cm:
    cm.new_consequent_func(create_none_of_tuple, cm.hn1, cm.imp_idcs_tup)


# ###############################################################################

I780 = p.create_item(
    R1__has_label="rule: infere from 'is none of' -> 'is one of'",
    R2__has_description=("principle of exclusion, part 1: infere from 'is none of' -> 'is one of'"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I780.scope("context") as cm:
    cm.new_var(cls1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(tup1=p.instance_of(p.I33["tuple"]))
    cm.new_var(tup2=p.instance_of(p.I33["tuple"]))

    cm.uses_external_entities(p.I2["Metaclass"])


with I780.scope("premises") as cm:
    cm.new_rel(cm.cls1, p.R4["is instance of"], p.I2["Metaclass"], overwrite=True)
    cm.new_rel(cm.itm1, p.R4["is instance of"], cm.cls1, overwrite=True)
    cm.new_rel(cm.cls1, p.R51["instances are from"], cm.tup1)
    cm.new_rel(cm.itm1, p.R52["is none of"], cm.tup2)


def tuple_difference_factory(self, tuple_item1, tuple_item2):
    """
    Create a new tuple item which contains the elements which are in tuple1 but not in tuple2
    """
    res = p.RuleResult()
    assert tuple_item1.R4__is_instance_of == p.I33["tuple"]
    assert tuple_item2.R4__is_instance_of == p.I33["tuple"]
    elements1 = tuple_item1.get_relations("R39__has_element", return_obj=True)
    elements2 = tuple_item2.get_relations("R39__has_element", return_obj=True)

    # TODO: this could be speed up by using dicts:
    new_elts = (e for e in elements1 if e not in elements2)
    res.new_entities.append(p.new_tuple(*new_elts))

    return res


with I780.scope("assertions") as cm:
    cm.new_var(tup_diff=p.instance_of(p.I33["tuple"]))  # remaining items
    # cm.tup_diff.add_method(tuple_difference_factory, "fiat_factory")

    cm.new_consequent_func(tuple_difference_factory, cm.tup1, cm.tup2, anchor_item=cm.tup_diff)

    cm.new_rel(cm.itm1, p.R56["is one of"], cm.tup_diff)

# ###############################################################################


I790 = p.create_item(
    R1__has_label="rule: infere from 'is one of' -> 'is same as'",
    R2__has_description=("principle of exclusion part 2: infere from 'is one of' -> 'is same as of'"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I790.scope("context") as cm:
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(elt0=p.instance_of(p.I1["general item"]))
    cm.new_var(tup1=p.instance_of(p.I33["tuple"]))

with I790.scope("premises") as cm:
    cm.new_rel(cm.itm1, p.R56["is one of"], cm.tup1)
    cm.new_rel(cm.tup1, p.R38["has length"], 1)
    cm.new_rel(cm.tup1, p.R39["has element"], cm.elt0)

with I790.scope("assertions") as cm:
    cm.new_rel(cm.elt0, p.R47["is same as"], cm.itm1)

# ###############################################################################

p.end_mod()
