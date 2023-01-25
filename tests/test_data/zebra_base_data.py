"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module contains the basis information of the logical "zebra puzzle" by A. Einstein:
(Which entities and which relations exist). It does not contain the hints like "4. Coffee is drunk in the green house."

See also https://en.wikipedia.org/wiki/Zebra_Puzzle

This module is to be imported in other modules
"""


import pyerk as p


__URI__ = "erk:/ocse/0.2/zebra_base_data"

keymanager = p.KeyManager(keyseed=1835)
p.register_mod(__URI__, keymanager)


p.start_mod(__URI__)


I7435 = p.create_item(
    R1__has_label="human",
    R2__has_description="human being",
    R4__is_instance_of=p.I2["Metaclass"],
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/entity/Q5",
)


I4037 = p.create_item(
    R1__has_label="Englishman",
    R4__is_instance_of=I7435["human"],
)

I9848 = p.create_item(
    R1__has_label="Norwegian",
    R4__is_instance_of=I7435["human"],
)

I3132 = p.create_item(
    R1__has_label="Ukrainian",
    R4__is_instance_of=I7435["human"],
)

I2552 = p.create_item(
    R1__has_label="Spaniard",
    R4__is_instance_of=I7435["human"],
)

I5931 = p.create_item(
    R1__has_label="Japanese",
    R4__is_instance_of=I7435["human"],
)

all_humans_tuple = p.close_class_with_R51(I7435["human"])

# ######################################################################################################################


I6990 = p.create_item(
    R1__has_label="beverage",
    R2__has_description="base class for selected beverages",
    R4__is_instance_of=p.I2["Metaclass"],
)


I7509 = p.create_item(
    R1__has_label="water",
    R4__is_instance_of=I6990["beverage"],
)

I6756 = p.create_item(
    R1__has_label="tea",
    R4__is_instance_of=I6990["beverage"],
)

I9779 = p.create_item(
    R1__has_label="milk",
    R4__is_instance_of=I6990["beverage"],
)

I4850 = p.create_item(
    R1__has_label="coffee",
    R4__is_instance_of=I6990["beverage"],
)

I6014 = p.create_item(
    R1__has_label="orange juice",
    R4__is_instance_of=I6990["beverage"],
)

# R51__instances_are_from
all_beverage_tuple = p.close_class_with_R51(I6990["beverage"])

# ######################################################################################################################


I3896 = p.create_item(
    R1__has_label="house color",
    R2__has_description="base class for selected house colors",
    R4__is_instance_of=p.I2["Metaclass"],
)

I4118 = p.create_item(
    R1__has_label="yellow",
    R4__is_instance_of=I3896["house color"],
)

I5209 = p.create_item(
    R1__has_label="red",
    R4__is_instance_of=I3896["house color"],
)

I1497 = p.create_item(
    R1__has_label="blue",
    R4__is_instance_of=I3896["house color"],
)

I7612 = p.create_item(
    R1__has_label="ivory",
    R4__is_instance_of=I3896["house color"],
)

I8065 = p.create_item(
    R1__has_label="green",
    R4__is_instance_of=I3896["house color"],
)


# R51__instances_are_from
all_colors_tuple = p.close_class_with_R51(I3896["house color"])

# ######################################################################################################################


I9803 = p.create_item(
    R1__has_label="cigarette brand",
    R2__has_description="base class for selected cigarette brands",
    R4__is_instance_of=p.I2["Metaclass"],
)

I2835 = p.create_item(
    R1__has_label="Kools",
    R4__is_instance_of=I9803["cigarette brand"],
)

I9122 = p.create_item(
    R1__has_label="Chesterfield",
    R4__is_instance_of=I9803["cigarette brand"],
)

I1055 = p.create_item(
    R1__has_label="Old Gold",
    R4__is_instance_of=I9803["cigarette brand"],
)

I5109 = p.create_item(
    R1__has_label="Lucky Strike",
    R4__is_instance_of=I9803["cigarette brand"],
)

I4872 = p.create_item(
    R1__has_label="Parliaments",
    R4__is_instance_of=I9803["cigarette brand"],
)

# R51__instances_are_from
all_cigerette_brands_tuple = p.close_class_with_R51(I9803["cigarette brand"])

# ######################################################################################################################


I8809 = p.create_item(
    R1__has_label="house number",
    R2__has_description="base class for numbered houses",
    R4__is_instance_of=p.I2["Metaclass"],
)

I6448 = p.create_item(
    R1__has_label="house 1",
    R4__is_instance_of=I8809["house number"],
    R40__has_index=1,
)

I7582 = p.create_item(
    R1__has_label="house 2",
    R4__is_instance_of=I8809["house number"],
    R40__has_index=2,
)

I4735 = p.create_item(
    R1__has_label="house 3",
    R4__is_instance_of=I8809["house number"],
    R40__has_index=3,
)

I4785 = p.create_item(
    R1__has_label="house 4",
    R4__is_instance_of=I8809["house number"],
    R40__has_index=4,
)

I1383 = p.create_item(
    R1__has_label="house 5",
    R4__is_instance_of=I8809["house number"],
    R40__has_index=5,
)

all_house_number_tuple = p.close_class_with_R51(I8809["house number"])

# ######################################################################################################################


I8139 = p.create_item(
    R1__has_label="pet",
    R2__has_description="base class for selected pets",
    R4__is_instance_of=p.I2["Metaclass"],
)

I8768 = p.create_item(
    R1__has_label="fox",
    R4__is_instance_of=I8139["pet"],
)

I6020 = p.create_item(
    R1__has_label="horse",
    R4__is_instance_of=I8139["pet"],
)

I2693 = p.create_item(
    R1__has_label="snails",
    R4__is_instance_of=I8139["pet"],
)

I2183 = p.create_item(
    R1__has_label="dog",
    R4__is_instance_of=I8139["pet"],
)

I1437 = p.create_item(
    R1__has_label="zebra",
    R4__is_instance_of=I8139["pet"],
)

# R51__instances_are_from
all_pets_tuple = p.close_class_with_R51(I8139["pet"])

# ######################################################################################################################


# Relations

R2850 = p.create_relation(
    R1__has_label="is functional activity",
    R2__has_description="specifies that a relation is functional in the context of the zebra puzzle",
    R8__has_domain_of_argument_1=p.I40["general relation"],
    R11__has_range_of_result=bool,
    R22__is_functional=True,
    R62__is_relation_property=True,
)

R8216 = p.create_relation(
    R1__has_label="drinks",
    R2__has_description="specifies which beverage a person drinks",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I6990["beverage"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
    R2850__is_functional_activity=True,
)


R9040 = p.create_relation(
    R1__has_label="lives in numbered house",
    R2__has_description="specifies in which house a person lives",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I8809["house number"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
    R2850__is_functional_activity=True,
)

R5611 = p.create_relation(
    R1__has_label="owns",
    R2__has_description="specifies which pet a person owns",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I8139["pet"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
    R2850__is_functional_activity=True,
)

R8098 = p.create_relation(
    R1__has_label="has house color",
    R2__has_description="specifies which color a persons house has",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I3896["house color"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
    R2850__is_functional_activity=True,
)

R8592 = p.create_relation(
    R1__has_label="smokes",
    R2__has_description="specifies which cigarette brand a person smokes (prefers)",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I9803["cigarette brand"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
    R2850__is_functional_activity=True,
)

R3606 = p.create_relation(
    R1__has_label="lives next to",
    R2__has_description="specifies that the difference in the house index between two persons is 1",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I7435["human"],
    R42__is_symmetrical=True,
)

R2353 = p.create_relation(
    R1__has_label="lives immediately right of",
    R2__has_description="specifies that the house index of the subject equals the house index of the object plus one",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I7435["human"],
    R22__is_functional=True,
    R17__is_subproperty_of=R3606["lives next to"],
    R2850__is_functional_activity=True,
)

R8768 = p.create_relation(
    R1__has_label="lives immediately left of",
    R2__has_description="specifies that the house index of the subject equals the house index of the object minus one",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I7435["human"],
    R22__is_functional=True,
    R17__is_subproperty_of=R3606["lives next to"],
    R2850__is_functional_activity=True,
    R68__is_inverse_of=R2353["lives immediately right of"]
)

R2693 = p.create_relation(
    R1__has_label="is located immediately right of",
    R2__has_description="specifies that one house number is located directly right of another house number",
    R8__has_domain_of_argument_1=I8809["house number"],
    R11__has_range_of_result=I8809["house number"],
    R22__is_functional=True,
)

R2183 = p.create_relation(
    R1__has_label="is located immediately left of",
    R2__has_description="specifies that one house number is located directly left of another house number",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I7435["human"],
    R22__is_functional=True,
    R68__is_inverse_of=R2693["is located immediately right of"]
)


I6448["house 1"].set_relation(R2183["is located immediately left of"], I7582["house 2"])
I7582["house 2"].set_relation(R2183["is located immediately left of"], I4735["house 3"])
I4735["house 3"].set_relation(R2183["is located immediately left of"], I4785["house 4"])
I4785["house 4"].set_relation(R2183["is located immediately left of"], I1383["house 5"])
I1383["house 5"]


# negative relations


R9803 = p.create_relation(
    R1__has_label="drinks not",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I6990["beverage"],
    R43__is_opposite_of=R8216["drinks"],
)


R2835 = p.create_relation(
    R1__has_label="lives not in numbered house",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I8809["house number"],
    R43__is_opposite_of=R9040["lives in numbered house"],
)

R9122 = p.create_relation(
    R1__has_label="owns not",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I8139["pet"],
    R43__is_opposite_of=R5611["owns"],
)

R1055 = p.create_relation(
    R1__has_label="has not house color",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I3896["house color"],
    R43__is_opposite_of=R8098["has house color"],
)

R5109 = p.create_relation(
    R1__has_label="smokes not",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I9803["cigarette brand"],
    R43__is_opposite_of=R8592["smokes"],
)

R4872 = p.create_relation(
    R1__has_label="lives not next to",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I7435["human"],
    R43__is_opposite_of=R3606["lives next to"],
)

# auxiliary relations

R8139 = p.create_relation(
    R1__has_label="has impossible indices",
    R8__has_domain_of_argument_1=I8809["house number"],
    R11__has_range_of_result=p.I33["tuple"],
    # R43__is_opposite_of=R40["has_index"],
)


R6020 = p.create_relation(
    R1__has_label="is opposite of functional activity",
    R2__has_description=(
        "specifies that the subject (a relation) is the opposite of a relation with R2850__is_functional_activity=True"
    ),
    R8__has_domain_of_argument_1=p.I40["general relation"],
    R11__has_range_of_result=bool,
    R22__is_functional=True,
    R62__is_relation_property=True,
)


# further information:
possible_house_indices = p.new_tuple(1, 2, 3, 4, 5)

p.set_multiple_statements(all_humans_tuple.R39__has_element, p.R57["is placeholder"], False)
p.set_multiple_statements(all_beverage_tuple.R39__has_element, p.R57["is placeholder"], False)
p.set_multiple_statements(all_pets_tuple.R39__has_element, p.R57["is placeholder"], False)
p.set_multiple_statements(all_colors_tuple.R39__has_element, p.R57["is placeholder"], False)
p.set_multiple_statements(all_cigerette_brands_tuple.R39__has_element, p.R57["is placeholder"], False)
p.set_multiple_statements(all_house_number_tuple.R39__has_element, p.R57["is placeholder"], False)



# ###############################################################################

"""
All Hints (from https://en.wikipedia.org/wiki/Zebra_Puzzle):

1. There are five houses.
2. The Englishman lives in the red house.
3. The Spaniard owns the dog.
4. Coffee is drunk in the green house.
5. The Ukrainian drinks tea.
6. The green house is immediately to the right (from perspective of the viewer) of the ivory house.
7. The Old Gold smoker owns snails.
8. Kools are smoked in the yellow house.
9. Milk is drunk in the middle house.
10. The Norwegian lives in the first house.
11. The man who smokes Chesterfields lives in the house next to the man with the fox.
12. Kools are smoked in the house next to the house where the horse is kept.
13. The Lucky Strike smoker drinks orange juice.
14. The Japanese smokes Parliaments.
15. The Norwegian lives next to the blue house.
"""


# ###############################################################################


p.end_mod()


def report(display=True, title=""):

    # all_humans = I7435["human"].get_inv_relations("R4", return_subj=True)

    # this makes this function paste-able
    human = p.ds.get_entity_by_uri("erk:/ocse/0.2/zebra_base_data#I7435")
    all_humans = human.get_inv_relations("R4", return_subj=True)

    res = []
    res_negative = []
    res_diff = []

    log = res.append
    log_neg = res_negative.append
    log_diff = res_diff.append
    log(title)
    green = p.aux.bgreen
    yellow = p.aux.byellow

    for h in all_humans:
        if h.R20__has_defining_scope:
            continue

        log(f"{h.R1}\n")
        stm_dict = h.get_relations()
        stms = []
        for v in stm_dict.values():
            stms.extend(v)

        for stm in stms:
            if (stm.predicate.zb__R2850__is_functional_activity):
                if stm.object.R57__is_placeholder:
                    log(f"  {stm.predicate.R1:>30}  {stm.object.R1}")
                else:
                    log(f"  {stm.predicate.R1:>30}  {green(stm.object.R1)}")

            elif stm.predicate == p.R50["is different from"]:
                if stm.object.R57__is_placeholder:
                    log_diff(f"  {stm.predicate.R1:>30}  {stm.object.R1}")
                else:
                    log_diff(f"  {stm.predicate.R1:>30}  {yellow(stm.object.R1)}")

            elif oppo := stm.predicate.R43__is_opposite_of:
                stm2 = stm.subject.get_relations(oppo[0].uri)
                if stm2 and not stm2[0].object.R57__is_placeholder:
                    # the primal statement is known (X drinks Y) -> no need to print the opposite (X drinks not Z)
                    pass
                    # log(f"  {stm.predicate.R1:>26}  {stm.object.R1}")
                else:
                    log_neg(f"  {stm.predicate.R1:>30}  {stm.object.R1}")

        # add the negative facts at the end
        res.extend(res_diff)
        res_diff.clear()
        res.extend(res_negative)
        res_negative.clear()

        log(f'{"-" * 40}\n')

    res_str = "\n".join(res)
    if display:
        print(res_str)
    else:
        return res_str
