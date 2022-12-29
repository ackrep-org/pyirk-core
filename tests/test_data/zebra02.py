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


I8139 = p.create_item(
    R1__has_label="pet",
    R2__has_description="base class for selected pets",
    R4__is_instance_of=p.I2["Metaclass"],
)

I8768 = p.create_item(
    R1__has_label="Fox",
    R4__is_instance_of=I8139["pet"],
)

I6020 = p.create_item(
    R1__has_label="Horse",
    R4__is_instance_of=I8139["pet"],
)

I2693 = p.create_item(
    R1__has_label="Snails",
    R4__is_instance_of=I8139["pet"],
)

I2183 = p.create_item(
    R1__has_label="Dog",
    R4__is_instance_of=I8139["pet"],
)

I1437 = p.create_item(
    R1__has_label="Zebra",
    R4__is_instance_of=I8139["pet"],
)

# R51__instances_are_from
all_pets_tuple = p.close_class_with_R51(I8139["pet"])


# ###############################################################################

"""

Hints:
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



I8809
I6448
I7582
I4735
I4785
I1383
I9040
I8098
I8592
I5611
I2353
I2850
I3606
I9412
I8499
I6258
"""




some_beverage_tuple1 = p.new_tuple(I6756, I9779, I4850, I6014)  # water missing
some_beverage_tuple2 = p.new_tuple(I7509, I9779, I4850, I6014)  # tea missing


R8216 = p.create_relation(
    R1__has_label="drinks",
    R2__has_description="specifies which beverage a person drinks",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I6990["beverage"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)


unknown_beverage1 = p.instance_of(I6990["beverage"])
unknown_beverage1.set_relation("R52__is_none_of", some_beverage_tuple1)
unknown_beverage1.set_relation("R57__is_placeholder", True)

unknown_beverage2 = p.instance_of(I6990["beverage"])
unknown_beverage2.set_relation("R52__is_none_of", some_beverage_tuple2)
unknown_beverage2.set_relation("R57__is_placeholder", True)



I4037["Englishman"].set_relation("R8216__drinks", unknown_beverage1)


# now it should be possible to reason that the Englishman drinks water (this is purely invented)


# Rules I901 and I902 where only for testing.


I903 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule3",
    R2__has_description=(
        "principle of exclusion: create difference tuple"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

# TODO: prevent a scope from being called again
with I903.scope("context") as cm:
    cm.new_var(C1=p.instance_of(p.I2["Metaclass"]))  # this is the class
    cm.new_var(P1=p.instance_of(cm.C1))  # this is the instance (this will be the beverage)
    
    cm.new_var(T1=p.instance_of(p.I33["tuple"]))  # a priori possible items
    cm.new_var(T2=p.instance_of(p.I33["tuple"]))  # excluded items
    cm.uses_external_entities(I903)
    
    
with I903.scope("premises") as cm:
    cm.new_rel(cm.C1, p.R51["instances are from"], cm.T1)
    cm.new_rel(cm.P1, p.R52["is none of"], cm.T2)
    

def tuple_difference_factory(self, tuple_item1, tuple_item2):
    """
    Create a new tuple item which contains the elements which are in tuple1 but not in tuple2
    """
    assert tuple_item1.R4__is_instance_of == p.I33["tuple"]
    assert tuple_item2.R4__is_instance_of == p.I33["tuple"]
    elements1 = tuple_item1.get_relations("R39__has_element", return_obj=True)
    elements2 = tuple_item2.get_relations("R39__has_element", return_obj=True)
    
    # TODO: this could be speed up by using dicts:
    new_elts = (e for e in elements1 if e not in elements2)
    res = p.new_tuple(*new_elts)
    
    return res
    
    
with I903.scope("assertions") as cm:
    cm.new_var(T_diff=p.instance_of(p.I33["tuple"]))  # remaining items
    cm.T_diff.add_method(tuple_difference_factory, "fiat_factory")
    cm.new_rel(cm.T_diff, p.R29["has argument"], cm.T1)
    cm.new_rel(cm.T_diff, p.R29["has argument"], cm.T2)
    
    cm.new_rel(cm.P1, p.R54["is matched by rule"], I903)
    cm.new_rel(cm.P1, p.R56["is one of"], cm.T_diff)
    
# ###############################################################################


I904 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule4",
    R2__has_description=(
        "principle of exclusion: evaluate R56__is_one_of tuple of length 1 to R47__is_same_as"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I904.scope("context") as cm:
    cm.new_var(i1=p.instance_of(p.I1["general item"]))
    cm.new_var(elt0=p.instance_of(p.I1["general item"]))
    cm.new_var(T1=p.instance_of(p.I33["tuple"]))
    cm.uses_external_entities(I904)
    
with I904.scope("premises") as cm:
    cm.new_rel(cm.i1, p.R56["is one of"], cm.T1)
    cm.new_rel(cm.T1, p.R38["has length"], 1)
    cm.new_rel(cm.T1, p.R39["has element"], cm.elt0)
    
with I904.scope("assertions") as cm:
    cm.new_rel(cm.i1, p.R54["is matched by rule"], I904)
    
    cm.new_rel(cm.i1, p.R47["is same as"], cm.elt0)

# ###############################################################################


I905 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule5",
    R2__has_description=(
        "replace placeholder items which have one R47__is_same_as statement"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I905.scope("context") as cm:
    cm.new_var(placeholder=p.instance_of(p.I1["general item"]))  
    cm.new_var(real_item=p.instance_of(p.I1["general item"]))
    
with I905.scope("premises") as cm:
    cm.new_rel(cm.placeholder, p.R57["is placeholder"], True)
    cm.new_rel(cm.placeholder, p.R47["is same as"], cm.real_item)
    
# TODO: move this to builtin_entities
def placeholder_replacer(self, old_item, new_item):
    p.replace_and_unlink_entity(old_item, new_item)
    
    # this function intentially does not return a new item; only called for its side-effects
    return None
    
with I905.scope("assertions") as cm:
    # create an item for attaching the factory
    cm.new_var(factory_anchor=p.instance_of(p.I1["general item"]))  # remaining items
    cm.factory_anchor.add_method(placeholder_replacer, "fiat_factory")
    cm.new_rel(cm.factory_anchor, p.R29["has argument"], cm.placeholder)
    cm.new_rel(cm.factory_anchor, p.R29["has argument"], cm.real_item)

# ###############################################################################


p.end_mod()


"""
key reservoir created with: `pyerk -l zebra01.py ag -nk 100`
supposed keys:
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
I1383
I9040
I8098
I8592
I5611
I2353
I2850
I3606
I9412
I8499
I6258
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
