"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module aims to model information with a similar structure to that of the logical "zebra puzzle" by A. Einstein.
It serves to explore the solution of the full puzzle.
See https://en.wikipedia.org/wiki/Zebra_Puzzle
"""


import pyerk as p


__URI__ = "erk:/ocse/0.2/zebra01"

keymanager = p.KeyManager(keyseed=1835)
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I7435 = p.create_item(
    R1__has_label="human",
    R2__has_description="human being",
    R4__is_instance_of=p.I2["Metaclass"],
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/entity/Q5",
)


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

I4037 = p.create_item(
    R1__has_label="Englishman",
    R4__is_instance_of=I7435["human"],
)


unknown_beverage1 = p.instance_of(I6990["beverage"])
unknown_beverage1.set_relation("R52__is_none_of", some_beverage_tuple1)
unknown_beverage1.set_relation("R57__is_placeholder", True)

unknown_beverage2 = p.instance_of(I6990["beverage"])
unknown_beverage2.set_relation("R52__is_none_of", some_beverage_tuple2)
unknown_beverage2.set_relation("R57__is_placeholder", True)


I4037["Englishman"].set_relation("R8216__drinks", unknown_beverage1)


# now, it should be possible to reason that the Englishman drinks water (this is purely invented)
# however, some basic rules have to be tested first
# Note: in the real zebra puzzle the Englishman drinks milk.


I901 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule1",
    R2__has_description=("simple testing rule"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I901.scope("context") as cm:
    cm.new_var(P1=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(I901)
#
with I901.scope("premises") as cm:
    cm.new_rel(cm.P1, p.R57["is placeholder"], True)

with I901.scope("assertions") as cm:
    cm.new_rel(cm.P1, p.R54["is matched by rule"], I901)

# ###############################################################################


I902 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule2",
    R2__has_description=("a step towards identification of beverage by principle of exclusion"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I902.scope("context") as cm:
    cm.new_var(C1=p.instance_of(p.I2["Metaclass"]))  # this is the class
    cm.new_var(P1=p.instance_of(cm.C1))  # this is the instance (this will be the beverage)

    cm.new_var(T1=p.instance_of(p.I33["tuple"]))
    cm.new_var(T2=p.instance_of(p.I33["tuple"]))
    cm.uses_external_entities(I902)

with I902.scope("premises") as cm:
    cm.new_rel(cm.C1, p.R51["instances are from"], cm.T1)
    cm.new_rel(cm.P1, p.R52["is none of"], cm.T2)

with I902.scope("assertions") as cm:
    cm.new_rel(cm.P1, p.R54["is matched by rule"], I902)

# ###############################################################################


I903 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule3",
    R2__has_description=("principle of exclusion: create difference tuple"),
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
    res = p.RuleResult()
    assert tuple_item1.R4__is_instance_of == p.I33["tuple"]
    assert tuple_item2.R4__is_instance_of == p.I33["tuple"]
    elements1 = tuple_item1.get_relations("R39__has_element", return_obj=True)
    elements2 = tuple_item2.get_relations("R39__has_element", return_obj=True)

    # TODO: this could be speed up by using dicts:
    new_elts = (e for e in elements1 if e not in elements2)
    res.new_entities.append(p.new_tuple(*new_elts))

    return res


with I903.scope("assertions") as cm:
    cm.new_var(T_diff=p.instance_of(p.I33["tuple"]))  # remaining items
    cm.T_diff.add_method(tuple_difference_factory, "fiat_factory")

    cm.new_consequent_func(tuple_difference_factory, cm.T1, cm.T2, anchor_item=cm.T_diff)

    cm.new_rel(cm.P1, p.R54["is matched by rule"], I903)
    cm.new_rel(cm.P1, p.R56["is one of"], cm.T_diff)

# ###############################################################################


I904 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule4",
    R2__has_description=("principle of exclusion: evaluate R56__is_one_of tuple of length 1 to R47__is_same_as"),
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
    R2__has_description=("replace placeholder items which have one R47__is_same_as statement"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I905.scope("context") as cm:
    cm.new_var(placeholder=p.instance_of(p.I1["general item"]))
    cm.new_var(real_item=p.instance_of(p.I1["general item"]))

with I905.scope("premises") as cm:
    cm.new_rel(cm.placeholder, p.R57["is placeholder"], True)
    cm.new_rel(cm.placeholder, p.R47["is same as"], cm.real_item)

with I905.scope("assertions") as cm:
    cm.new_consequent_func(p.replacer_method, cm.placeholder, cm.real_item)

# ###############################################################################


p.end_mod()


"""
key reservoir created with: `pyerk -l zebra01.py ag -nk 100`
supposed keys:
I3896      R3896
I4118      R4118
I5209      R5209
I1497      R1497
I7612      R7612
I8065      R8065
I2341      R2341
I9848      R9848
I3132      R3132
I2552      R2552
I5931      R5931
I9803      R9803
I2835      R2835
I9122      R9122
I1055      R1055
I5109      R5109
I4872      R4872
I8139      R8139
I8768      R8768
I6020      R6020
I2693      R2693
I2183      R2183
I1437      R1437
I8809      R8809
I6448      R6448
I7582      R7582
I4735      R4735
I4785      R4785
I1383      R1383
I9040      R9040
I8098      R8098
I8592      R8592
I5611      R5611
I2353      R2353
I2850      R2850
I3606      R3606
I9412      R9412
I8499      R8499
I6258      R6258
I7258      R7258
I1933      R1933
I4892      R4892
I2911      R2911
I4715      R4715
I6147      R6147
I7536      R7536
I9491      R9491
I7825      R7825
I6844      R6844
I6970      R6970
I1835      R1835
I3560      R3560
I9209      R9209
I5644      R5644
I1873      R1873
I8554      R8554
I2406      R2406
I3914      R3914
I9756      R9756
I1420      R1420
I9987      R9987
I4269      R4269
I3798      R3798
I7141      R7141
I3852      R3852
I3536      R3536
I8232      R8232
I1321      R1321
I6487      R6487
I3724      R3724
I6615      R6615
I6642      R6642
I8100      R8100
I5157      R5157
I2116      R2116
I2231      R2231
I8503      R8503
I2831      R2831
I9596      R9596
I5390      R5390
I7359      R7359
I8782      R8782
I4296      R4296
I7097      R7097
I6415      R6415
I4738      R4738
I1897      R1897
I5216      R5216
I4466      R4466
I3016      R3016
I9202      R9202
`

"""
