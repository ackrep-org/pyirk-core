"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module aims to model part of the logical "zebra puzzle" by A. Einstein
"""


import pyerk as p


__URI__ = "erk:/ocse/0.2/zebra"

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


all_beverage_list = p.new_tuple(I7509, I6756, I9779, I4850, I6014)

I6990["beverage"].set_relation("R51__is_one_of", all_beverage_list)


some_beverage_list = p.new_tuple(I6756, I9779, I4850, I6014)


R8216 = p.create_relation(
    R1__has_label="drinks",
    R2__has_description="specifies which beverage a person drinks",
    R8__has_domain_of_argument_1=I7435["human"],
    R11__has_range_of_result=I6990["beverage"],
    R22__is_functional=True,
    R53__is_inverse_functional=True,
)

R8314 = p.create_relation(
    R1__has_label="is placeholder",
    R2__has_description="specifies that the subject is a placeholder and might be replaced by other itmes",
    # R8__has_domain_of_argument_1=<any ordinary instance>,
    R11__has_range_of_result=bool,
    R22__is_functional=True,
)

I4037 = p.create_item(
    R1__has_label="Englishman",
    R4__is_instance_of=I7435["human"],
)


unknown_beverage = p.instance_of(I6990["beverage"])
unknown_beverage.set_relation("R52__is_none_of", some_beverage_list)
unknown_beverage.set_relation("R8314__is_placeholder", True)



I4037["Englishman"].set_relation("R8216__drinks", unknown_beverage)


# now it should be possible to reason that the Englishman drinks water (this is purely invented)
# however, some basic rules have to be tested first


I901 = p.create_item(
    R1__has_label="zebra puzzle reasoning rule1",
    R2__has_description=(
        "simple testing rule"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I901.scope("context") as cm:
    cm.new_var(P1=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(I901)
#
with I901.scope("premises") as cm:
    cm.new_rel(cm.P1, R8314["is placeholder"], True)

with I901.scope("assertions") as cm:
    cm.new_rel(cm.P1, p.R54["is matched by rule"], I901)


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