"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module aims to model information with a similar structure to that of the logical "zebra puzzle" by A. Einstein.
It serves to explore the solution of the full puzzle.
See https://en.wikipedia.org/wiki/Zebra_Puzzle
"""


import pyerk as p


__URI__ = "erk:/ocse/0.2/zebra02"

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

# ###############################################################################


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
    R1__has_label="juice",
    R4__is_instance_of=I6990["beverage"],
)

# R51__instances_are_from
all_beverage_tuple = p.close_class_with_R51(I6990["beverage"])

# ###############################################################################


I3896 = p.create_item(
    R1__has_label="house color",
    R2__has_description="base class for selected house colors",
    R4__is_instance_of=p.I2["Metaclass"],
)

I4118 = p.create_item(
    R1__has_label="yellow",
    R4__is_instance_of=I3896["house color"],
)

I5209  = p.create_item(
    R1__has_label="red",
    R4__is_instance_of=I3896["house color"],
)

I1497  = p.create_item(
    R1__has_label="blue",
    R4__is_instance_of=I3896["house color"],
)

I7612 = p.create_item(
    R1__has_label="white",
    R4__is_instance_of=I3896["house color"],
)

I8065  = p.create_item(
    R1__has_label="green",
    R4__is_instance_of=I3896["house color"],
)


# R51__instances_are_from
all_colors_tuple = p.close_class_with_R51(I3896["house color"])


# ###############################################################################


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
    R1__has_label="Parliament",
    R4__is_instance_of=I9803["cigarette brand"],
)

# R51__instances_are_from
all_cigerette_brands_tuple = p.close_class_with_R51(I9803["cigarette brand"])


# ###############################################################################


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


# ###############################################################################


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


# ###############################################################################

# Relations

R8216 = p.create_relation(
    R1__has_label="drinks",
    R2__has_description="specifies which beverage a person drinks",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I6990["beverage"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)

R9040 = p.create_relation(
    R1__has_label="lives in numbered house",
    R2__has_description="specifies in which house a person lives",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I6990["beverage"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)

R5611 = p.create_relation(
    R1__has_label="owns",
    R2__has_description="specifies which pet a person owns",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I8139["pet"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)

R8098 = p.create_relation(
    R1__has_label="has house color",
    R2__has_description="specifies which color a persons house has",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I3896["house color"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)

R8592 = p.create_relation(
    R1__has_label="somkes",
    R2__has_description="specifies which cigarette brand a person smokes (prefers)",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I9803["cigarette brand"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)


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

# model hint by hint

# 1. There are five houses. ✓
# 2. The Englishman lives in the red house.

I4037["Englishman"].set_relation("R8098__has_house_color", I5209["red"])

# 3. The Spaniard owns the dog.

I2552["Spaniard"].set_relation("R5611__owns", I2183["dog"])


"""

I3606
I9412
I8499
I6258
"""


# ###############################################################################


p.end_mod()


"""
key reservoir created with: `pyerk -l zebra01.py ag -nk 100`
supposed keys:
    
R2353
R2850
    
I9803
I2835
I9122
I1055
I5109
I4872
I8139
I8768
I6020
I2693
I2183
I1437
I8809
I6448
I7582
I4735
I4785
I7258
I1933
I4892
I2911
I4715
I6147
I7536
I9491
I7825
I6844
I6970
I1835
I3560
I9209
I5644
I1873
I8554
I2406
I3914
I9756
I1420
I9987
I4269
I3798
I7141
I3852
I3536
I8232
I1321
I6487
I3724
I6615
I6642
I8100
I5157
I2116
I2231
I8503
I2831
I9596
I5390
I7359
I8782
I4296
I7097
I6415
I4738
I1897
I5216
I4466
I3016
I9202
`

"""
