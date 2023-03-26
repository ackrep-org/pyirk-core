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


I705 = p.create_item(
    R1__has_label="rule: deduce trivial different-from-facts",
    R2__has_description=("deduce trivial different-from-facts like Norwegian is different from Englishman"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I705.scope("context") as cm:
    cm.new_var(p1=p.instance_of(zb.I7435["human"]))
    cm.new_var(p2=p.instance_of(zb.I7435["human"]))
    cm.uses_external_entities(zb.I7435["human"])


with I705.scope("premises") as cm:
    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p2, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p1, p.R57["is placeholder"], False)
    cm.new_rel(cm.p2, p.R57["is placeholder"], False)


with I705.scope("assertions") as cm:
    cm.new_rel(cm.p1, p.R50["is different from"], cm.p2, qualifiers=[p.qff_has_rule_ptg_mode(5)])
    cm.new_rel(cm.p2, p.R50["is different from"], cm.p1, qualifiers=[p.qff_has_rule_ptg_mode(5)])


# ###############################################################################


I710 = p.create_item(
    R1__has_label="rule: identify same items via zb__R2850__is_functional_activity",
    R2__has_description=(
        "match two persons which are relate by a functional activity (R2850) with the same other items"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I710.scope("context") as cm:
    cm.new_var(p1=p.instance_of(p.I1["general item"]))
    cm.new_var(p2=p.instance_of(p.I1["general item"]))
    cm.new_var(some_itm=p.instance_of(p.I1["general item"]))
    cm.new_rel_var("rel1")  # -> p.instance_of(p.I40["general relation"]))

with I710.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
        ?p1 ?rel1 ?some_itm.
        ?p2 ?rel1 ?some_itm.

        ?rel1 zb:R2850 true.      # R2850__is_functional_activity
        FILTER (?p1 != ?p2)
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
    cm.new_rel(cm.p1, p.R47["is same as"], cm.p2, qualifiers=[p.qff_has_rule_ptg_mode(5)])

txt = r"{p1} {rel1} {some_itm}  AND  {p2} {rel1} {some_itm}."

I710.set_relation(p.R69["has explanation text template"], txt)

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

I725 = p.create_item(
    R1__has_label="rule: deduce facts from inverse relations",
    R2__has_description=("deduce facts from inverse relations e.g. if p1 lives right of p2 then p2 lives left of p1"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I725.scope("context") as cm:
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel2")

with I725.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?itm1 ?rel1 ?itm2.        # R3606["lives next to"]

            # ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1 :R68 ?rel2.        # R68__is_inverse_of
        }
        """
    )

with I725.scope("assertions") as cm:
    cm.new_rel(cm.itm2, cm.rel2, cm.itm1, qualifiers=[p.qff_has_rule_ptg_mode(5)])

txt = r"{h1} {rel1} {h2}  AND  {rel1} R68__is_invsere_of {rel2}."

I725.set_relation(p.R69["has explanation text template"], txt)

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
    cm.new_rel(cm.h2, cm.rel2, cm.itm1, qualifiers=[p.qff_has_rule_ptg_mode(5)])

# ###############################################################################

I740 = p.create_item(
    R1__has_label="rule: deduce more negative facts from negative facts",
    R2__has_description=("deduce e.g. if h1 onws dog and h1 drinks milk and h2 owns zebra then h2 drinks not milk"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I740.scope("context") as cm:
    cm.new_var(h1=p.instance_of(zb.I7435["human"]))
    cm.new_var(h2=p.instance_of(zb.I7435["human"]))
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))
    cm.new_var(itm3=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel2")
    cm.new_rel_var("rel1_not")
    cm.new_rel_var("rel2_not")

with I740.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?h1 ?rel1 ?itm1.          # e.g. h1 owns dog
            ?h1 ?rel2 ?itm2.          # e.g. h1 drinks milk
            ?h2 ?rel1 ?itm3.          # e.g. h2 owns zebra

            FILTER (?rel1 != ?rel2)
            FILTER (?itm1 != ?itm2)
            FILTER (?itm1 != ?itm3)
            FILTER (?h1 != ?h2)
            FILTER (?itm2 != ?itm3)

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel2 zb:R2850 true.     # R2850__is_functional_activity

            ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of
            ?rel2 :R43 ?rel2_not.        # R43__is_opposite_of

            ?h2 ?rel2_not ?itm2.

            # prevent the addition of already known relations
            # MINUS { ?h2 ?rel1_not ?itm1.}
        }
        """
    )

with I740.scope("assertions") as cm:
    cm.new_rel(cm.h2, cm.rel2_not, cm.itm2, qualifiers=[p.qff_has_rule_ptg_mode(5)])

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

    if nbr_hn.R40__has_index:
        # the index of this house is already known -> no further information required
        return res

    possible_indices = {primal_house_index - 1, primal_house_index + 1}
    impossible_indices = set(zb.possible_house_indices.R39__has_element).difference(possible_indices)

    imp_idcs_tup = p.new_tuple(*impossible_indices)

    stm = nbr_hn.set_relation(zb.R8139["has impossible indices"], imp_idcs_tup, prevent_duplicate=True)
    if stm:
        res.add_statement(stm)
        res.add_entity(imp_idcs_tup)
    return res


with I760.scope("assertions") as cm:
    cm.new_consequent_func(exclude_house_numbers_for_neighbour, cm.hn2, cm.house_index1)

# ###############################################################################

I763 = p.create_item(
    R1__has_label="rule: deduce impossible house index for left-right neighbours",
    R2__has_description=("deduce impossible house indices for right neighbour"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I763.scope("context") as cm:
    # persons
    cm.new_var(p1=p.instance_of(zb.I7435["human"]))
    cm.new_var(p2=p.instance_of(zb.I7435["human"]))
    cm.uses_external_entities(zb.I6448["house 1"], zb.I1383["house 5"])

with I763.scope("premises") as cm:
    cm.new_rel(cm.p1, zb.R2353["lives immediately right of"], cm.p2)

with I763.scope("assertions") as cm:
    cm.new_rel(
        cm.p1, zb.R2835["lives not in numbered house"], zb.I6448["house 1"], qualifiers=[p.qff_has_rule_ptg_mode(5)]
    )
    cm.new_rel(
        cm.p2, zb.R2835["lives not in numbered house"], zb.I1383["house 5"], qualifiers=[p.qff_has_rule_ptg_mode(5)]
    )



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

    if hn_item.R40__has_index:
        # the index of this house is already known -> no further information required
        return res

    all_house_numbers: list = zb.all_house_number_tuple.R39__has_element

    # tuple-item -> list
    imp_idcs: list = imp_idcs_tup.R39__has_element

    impossible_house_numbers = [h for h in all_house_numbers if getattr(h, "R40__has_index")[0] in imp_idcs]

    # possible problem: this creates a new tuple whose key might have been used during loading rdf data
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

    cm.new_rel(cm.itm1, p.R56["is one of"], cm.tup_diff, qualifiers=[p.qff_has_rule_ptg_mode(5)])

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


# ###############################################################################

I741 = p.create_item(
    R1__has_label="rule: deduce more negative facts from negative facts",
    R2__has_description=("deduce e.g. if h1 onws dog and h1 drinks milk and h2 owns zebra then h2 drinks not milk"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I741.scope("context") as cm:
    cm.new_var(h1=p.instance_of(zb.I7435["human"]))
    cm.new_var(h2=p.instance_of(zb.I7435["human"]))
    cm.new_var(itm1a=p.instance_of(p.I1["general item"]))
    cm.new_var(itm1b=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel2")
    # cm.new_rel_var("rel1_not")
    cm.new_rel_var("rel2_not")

with I741.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?h1 ?rel1 ?itm1a.          # e.g. h1 owns dog
            ?h1 ?rel2 ?itm1b.          # e.g. h1 drinks milk
            ?h2 ?rel1 ?itm2.          # e.g. h2 owns zebra

            ?itm1a :R57 false.        # itm1 is no placeholder
            ?itm1b :R57 false.        # itm1 is no placeholder
            # ?itm2 :R57 false.        # itm1 is no placeholder

            FILTER (?rel1 != ?rel2)
            FILTER (?itm1a != ?itm1b)
            FILTER (?itm1a != ?itm2)
            FILTER (?h1 != ?h2)
            FILTER (?itm1b != ?itm2)

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel2 zb:R2850 true.     # R2850__is_functional_activity

            # ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of
            ?rel2 :R43 ?rel2_not.        # R43__is_opposite_of

            # prevent the addition of statements on placeholder persons (not sure yet)

            # MINUS { ?h1 :R57 true.}
            MINUS { ?itm2 :R57 true.}
        }
        """
    )

with I741.scope("assertions") as cm:
    # qualifier means: 5 -> create_asserted_statement_only_if_new
    cm.new_rel(cm.h2, cm.rel2_not, cm.itm1b, qualifiers=[p.qff_has_rule_ptg_mode(5)])

txt = r"{h1} {rel1} {itm1a}  AND  {rel2} {itm1b}. HOWEVER {h2} {rel1} {itm2}."

I741.set_relation(p.R69["has explanation text template"], txt)

# ###############################################################################

I792 = p.create_item(
    R1__has_label="rule: deduce different-from-facts from negative facts",
    R2__has_description=("deduce e.g. if h1 not onws dog and h2 onws dog then h2 different from h1 and vice versa."),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I792.scope("context") as cm:
    cm.new_var(h1=p.instance_of(zb.I7435["human"]))
    cm.new_var(h2=p.instance_of(zb.I7435["human"]))
    cm.new_var(itm1a=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(p.R50["is different from"])

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel1_not")

with I792.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?h1 ?rel1 ?itm1a.          # e.g. h1 owns dog
            ?h2 ?rel1_not ?itm1a.      # e.g. h2 not_owns dog

            ?h1 :R4 zb:I7435.          # h1 is human
            ?h2 :R4 zb:I7435.          # h2 is human

            ?itm1a :R57 false.        # itm1 is no placeholder
            ?rel1 zb:R2850 true.      # R2850__is_functional_activity
            ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of

        }
        """
    )

with I792.scope("assertions") as cm:
    # qualifier means: 5 -> create_asserted_statement_only_if_new
    cm.new_rel(cm.h1, p.R50["is different from"], cm.h2, qualifiers=[p.qff_has_rule_ptg_mode(5)])
    cm.new_rel(cm.h2, p.R50["is different from"], cm.h1, qualifiers=[p.qff_has_rule_ptg_mode(5)])

txt = r"{h1} {rel1} {itm1a}  AND  {h2} {rel1_not} {itm1a}."

I792.set_relation(p.R69["has explanation text template"], txt)

# ###############################################################################


I794 = p.create_item(
    R1__has_label="rule: deduce neighbour-facts from house indices",
    R4__is_instance_of=p.I41["semantic rule"],
)

with I794.scope("context") as cm:
    # persons
    cm.new_var(p1=p.instance_of(zb.I7435["human"]))
    cm.new_var(p2=p.instance_of(zb.I7435["human"]))

    # house numbers
    cm.new_var(hn1=p.instance_of(p.I1["general item"]))
    cm.new_var(hn2=p.instance_of(p.I1["general item"]))

    # house number indices
    cm.new_variable_literal("house_index1")
    cm.new_variable_literal("house_index2")


with I794.scope("premises") as cm:
    cm.new_rel(cm.p1, zb.R9040["lives in numbered house"], cm.hn1)
    cm.new_rel(cm.p2, zb.R9040["lives in numbered house"], cm.hn2)

    cm.new_rel(cm.hn1, p.R40["has index"], cm.house_index1)
    cm.new_rel(cm.hn2, p.R40["has index"], cm.house_index2)

    cm.new_condition_func(lambda self, x, y: y == x+1, cm.house_index1, cm.house_index2)

I794.set_relation(p.R70["has number of prototype-graph-components"], 2)

with I794.scope("assertions") as cm:
    # qualifier means: 5 -> create_asserted_statement_only_if_new
    cm.new_rel(cm.p2, zb.R2353["lives immediately right of"], cm.p1, qualifiers=[p.qff_has_rule_ptg_mode(5)])
    cm.new_rel(cm.p1, p.R50["is different from"], cm.p2, qualifiers=[p.qff_has_rule_ptg_mode(5)])
    cm.new_rel(cm.p2, p.R50["is different from"], cm.p1, qualifiers=[p.qff_has_rule_ptg_mode(5)])

txt = "{p1} lives in {hn1} (with index {house_index1}) and {p2} lives in {hn2} (with index {house_index2})"
I794.set_relation(p.R69["has explanation text template"], txt)

# ###############################################################################


I796 = p.create_item(
    R1__has_label="rule: deduce different-from facts for neighbour-pairs",
    R4__is_instance_of=p.I41["semantic rule"],
)

with I796.scope("context") as cm:
    # persons
    cm.new_var(p1=p.instance_of(p.I1["general item"]))
    cm.new_var(p2=p.instance_of(p.I1["general item"]))
    cm.new_var(p3=p.instance_of(p.I1["general item"]))
    cm.new_var(p4=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(zb.I7435["human"])

with I796.scope("premises") as cm:
    # this serves to speed up the rule (for being more specific)
    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p2, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p3, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p4, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p1, zb.R2353["lives immediately right of"], cm.p2)
    cm.new_rel(cm.p3, zb.R2353["lives immediately right of"], cm.p4)
    cm.new_rel(cm.p1, p.R50["is different from"], cm.p3)


# I798.set_relation(p.R70["has number of prototype-graph-components"], 2)

with I796.scope("assertions") as cm:
    # qualifier means: 5 -> create_asserted_statement_only_if_new
    cm.new_rel(cm.p2, p.R50["is different from"], cm.p4, qualifiers=[p.qff_has_rule_ptg_mode(5)])
    cm.new_rel(cm.p4, p.R50["is different from"], cm.p2, qualifiers=[p.qff_has_rule_ptg_mode(5)])

# ###############################################################################


# TODO: merge this with I730
I798 = p.create_item(
    R1__has_label="rule: deduce negative facts from different-from-facts",
    R2__has_description=("deduce negative facts from different-from-facts"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I798.scope("context") as cm:
    cm.new_var(p1=p.instance_of(zb.I7435["human"]))
    cm.new_var(p2=p.instance_of(zb.I7435["human"]))
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel2")

with I798.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?p1 :R50 ?p2.        # R50["is different from"]

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1 :R43 ?rel2.        # R43__is_opposite_of

            ?p1 ?rel1 ?itm1.
        }
        """
    )

with I798.scope("assertions") as cm:
    cm.new_rel(cm.p2, cm.rel2, cm.itm1, qualifiers=[p.qff_has_rule_ptg_mode(5)])


# ###############################################################################


# ###############################################################################


I800 = p.create_item(
    R1__has_label="rule: mark relations which are opposite of functional activities",
    R4__is_instance_of=p.I41["semantic rule"],
)

with I800.scope("context") as cm:

    cm.new_var(rel1=p.instance_of(p.I40["general relation"]))
    cm.new_var(rel1_not=p.instance_of(p.I40["general relation"]))

with I800.scope("premises") as cm:
    cm.new_rel(cm.rel1_not, p.R43["is opposite of"], cm.rel1)
    cm.new_rel(cm.rel1, zb.R2850["is functional activity"], True)

with I800.scope("assertions") as cm:
    cm.new_rel(cm.rel1_not, zb.R6020["is opposite of functional activity"], True, qualifiers=[p.qff_has_rule_ptg_mode(5)])
    cm.new_rel(cm.rel1_not, p.R71["enforce matching result type"], True, qualifiers=[p.qff_has_rule_ptg_mode(5)])



# ###############################################################################


I803 = p.create_item(
    R1__has_label="rule: deduce different-from-facts from functional activities",
    R4__is_instance_of=p.I41["semantic rule"],
)

with I803.scope("context") as cm:

    cm.new_var(p1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))
    cm.new_var(type_of_itm1=p.instance_of(p.I1["general item"]))

    cm.new_rel_var("rel1")
    cm.new_rel_var("rel1_not")

with I803.scope("premises") as cm:
    cm.set_sparql(
        """
        WHERE {
            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1_not :R43 ?rel1.        # R43__is_opposite_of
            ?p1 ?rel1 ?itm1.
            ?itm1 :R4 ?type_of_itm1.   # R4__is_instance_of
            ?type_of_itm1 :R51 ?tuple.  # R51__instances_are_from
            ?tuple :R39 ?itm2.           # R39__has_element
            ?itm1 :R57 false.          # R57__is_placeholder
            ?itm2 :R57 false.

            FILTER (?itm1 != ?itm2)

        }
        """
    )

with I803.scope("assertions") as cm:
    cm.new_rel(cm.p1, cm.rel1_not, cm.itm2, qualifiers=[p.qff_has_rule_ptg_mode(5)])


# ###############################################################################

# this function is needed by ruleengine.AlgorithmicRuleApplicationWorker.experiment

def add_stm_by_exclusion(self, p1, oppo_rel, not_itm1, not_itm2, not_itm3, not_itm4):
    """
    Assume that four negative facts are known and add the corresponding positive fact
    """

    # check arguments:
    args = [elt for elt in (not_itm1, not_itm2, not_itm3, not_itm4) if p.is_relevant_item(elt)]
    if not len(args) == 4:
        return p.RuleResult()

    itm_type = not_itm1.R4__is_instance_of
    assert itm_type == not_itm2.R4__is_instance_of
    assert itm_type == not_itm3.R4__is_instance_of
    assert itm_type == not_itm4.R4__is_instance_of

    all_itms = itm_type.get_inv_relations("R4__is_instance_of", return_subj=True)

    all_itms_map = dict(
        [(itm.uri, itm) for itm in all_itms if p.is_relevant_item(itm)]
    )
    all_itms_set = set(all_itms_map.keys())

    assert len(all_itms_set) == 5
    rest_uris = list(all_itms_set.difference((not_itm1.uri, not_itm2.uri, not_itm3.uri, not_itm4.uri)))
    assert len(rest_uris) == 1
    rest = all_itms_map[rest_uris[0]]

    rel1 = oppo_rel.R43__is_opposite_of[0]
    res = p.RuleResult()

    # check for existing relations
    objs = p1.get_relations(rel1.uri, return_obj=True)
    if not objs:
        # set new relation
        stm = p1.set_relation(rel1, rest)
        res.add_statement(stm)
    elif len(objs) == 1 and objs[0].R57__is_placeholder:
        # replace a placeholder item if unique
        chgd_stm = p.core.replace_and_unlink_entity(objs[0], rest)
        res.changed_statements.append(chgd_stm)

    return res

# ###############################################################################


I820 = p.create_item(
    R1__has_label="rule: deduce personhood by exclusion",
    R4__is_instance_of=p.I41["semantic rule"],
)

I810 = p.create_item(
    R1__has_label="rule: deduce positive fact from 4 negative facts (hardcoded cheat)",
    R2__has_description=("deduce positive fact from 4 negative facts (graph version)"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I810.scope("context") as cm:
    pass

with I810.scope("premises") as cm:
    pass

with I810.scope("assertions") as cm:
    pass

# this is a temporary solution until the AlgorithmicRuleApplicationWorker is implemented
I810.cheat = [p.ruleengine.AlgorithmicRuleApplicationWorker.hardcoded_I810, zb, add_stm_by_exclusion]

with I820.scope("context") as cm:

    cm.new_var(p0=p.instance_of(p.I1["general item"]))

    cm.new_var(p1=p.instance_of(p.I1["general item"]))
    cm.new_var(p2=p.instance_of(p.I1["general item"]))
    cm.new_var(p3=p.instance_of(p.I1["general item"]))
    cm.new_var(p4=p.instance_of(p.I1["general item"]))
    cm.new_var(p5=p.instance_of(p.I1["general item"]))

    cm.uses_external_entities(zb.I7435["human"])


with I820.scope("premises") as cm:
    cm.new_rel(cm.p0, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p2, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p3, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p4, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p5, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p0, p.R50["is different from"], cm.p1)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p2)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p3)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p4)

    cm.new_rel(cm.p0, p.R57["is placeholder"], True)

    cm.new_rel(cm.p1, p.R57["is placeholder"], False)
    cm.new_rel(cm.p2, p.R57["is placeholder"], False)
    cm.new_rel(cm.p3, p.R57["is placeholder"], False)
    cm.new_rel(cm.p4, p.R57["is placeholder"], False)
    cm.new_rel(cm.p5, p.R57["is placeholder"], False)

with I820.scope("assertions") as cm:
    cm.new_rel(cm.p0, p.R47["is same as"], cm.p5, qualifiers=[p.qff_has_rule_ptg_mode(5)])


# ###############################################################################


I830 = p.create_item(
    R1__has_label="rule: ensure absence of contradictions (5 different-from statements) (hardcoded cheat)",
    R4__is_instance_of=p.I41["semantic rule"],
)

I830.cheat = [
    p.ruleengine.AlgorithmicRuleApplicationWorker.hardcoded_I830,
    zb, p.raise_contradiction,
    "{} has too many `R50__is_differnt_from` statements"
]


# currently obsolete because of hardcoded cheat
with I830.scope("context") as cm:

    cm.new_var(p0=p.instance_of(p.I1["general item"]))

    cm.new_var(p1=p.instance_of(p.I1["general item"]))
    cm.new_var(p2=p.instance_of(p.I1["general item"]))
    cm.new_var(p3=p.instance_of(p.I1["general item"]))
    cm.new_var(p4=p.instance_of(p.I1["general item"]))
    cm.new_var(p5=p.instance_of(p.I1["general item"]))

    cm.uses_external_entities(zb.I7435["human"])


with I830.scope("premises") as cm:
    cm.new_rel(cm.p0, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p2, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p3, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p4, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p5, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p0, p.R50["is different from"], cm.p1)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p2)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p3)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p4)
    cm.new_rel(cm.p0, p.R50["is different from"], cm.p5)

    cm.new_rel(cm.p1, p.R57["is placeholder"], False)
    cm.new_rel(cm.p2, p.R57["is placeholder"], False)
    cm.new_rel(cm.p3, p.R57["is placeholder"], False)
    cm.new_rel(cm.p4, p.R57["is placeholder"], False)
    cm.new_rel(cm.p5, p.R57["is placeholder"], False)

with I830.scope("assertions") as cm:
    cm.new_consequent_func(p.raise_contradiction, "{} has too many `R50__is_differnt_from` statements", cm.p0)

# ###############################################################################


I840 = p.create_item(
    R1__has_label="rule: detect if puzzle is solved (hardcoded cheat)",
    R4__is_instance_of=p.I41["semantic rule"],
)

I840.cheat = [
    p.ruleengine.AlgorithmicRuleApplicationWorker.hardcoded_I840,
    zb, p.raise_reasoning_goal_reached,
    "puzzle solved"
]

with I840.scope("context") as cm:
    pass

with I840.scope("premises") as cm:
    pass

with I840.scope("assertions") as cm:
    pass

# ###############################################################################

I825 = p.create_item(
    R1__has_label="rule: deduce lives-not-in... from lives-next-to",
    R4__is_instance_of=p.I41["semantic rule"],
)


with I825.scope("context") as cm:
    cm.new_var(p1=p.instance_of(p.I1["general item"]))
    cm.new_var(p2=p.instance_of(p.I1["general item"]))

    cm.new_var(hn2=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(zb.I7435["human"])

    cm.new_variable_literal("house_index2")

with I825.scope("premises") as cm:
    cm.new_rel(cm.p1, p.R4["is instance of"], zb.I7435["human"], overwrite=True)
    cm.new_rel(cm.p2, p.R4["is instance of"], zb.I7435["human"], overwrite=True)

    cm.new_rel(cm.p1, zb.R3606["lives next to"], cm.p2)
    cm.new_rel(cm.p2, zb.R9040["lives in numbered house"], cm.hn2)

    cm.new_rel(cm.hn2, p.R40["has index"], cm.house_index2)

def exclude_houses(self, p1, nbr_hn):

    # construct the neighbours of the neighbour
    left_nbrs = []
    right_nbrs = []

    tmp_entity = nbr_hn
    while True:
        right_nbr = tmp_entity.zb__R2693__is_located_immediately_right_of
        if right_nbr:
            right_nbrs.append(right_nbr)
            tmp_entity = right_nbr
        else:
            break

    tmp_entity = nbr_hn
    while True:
        left_nbr = tmp_entity.zb__R2183__is_located_immediately_left_of
        if left_nbr:
            left_nbrs.append(left_nbr)
            tmp_entity = left_nbr
        else:
            break

    # the first elements of these lists are admissible for p1 the rest is not
    exclude_list = left_nbrs[1:] + right_nbrs[1:]

    res = p.RuleResult()
    for hn in exclude_list:
        stm = p1.set_relation(zb.R2835["lives not in numbered house"], hn, prevent_duplicate=True)
        res.add_statement(stm)

    return res


with I825.scope("assertions") as cm:
    cm.new_consequent_func(exclude_houses, cm.p1, cm.hn2)

# ###############################################################################

p.end_mod()
