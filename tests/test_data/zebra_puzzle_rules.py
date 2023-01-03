"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module contains some rules for determining the solution of the zebra puzzle by logical reasoning.

See https://en.wikipedia.org/wiki/Zebra_Puzzle
"""


import pyerk as p

zb = p.erkloader.load_mod_from_path("./zebra_base_data.py", prefix="zb", reuse_loaded=True)


__URI__ = "erk:/ocse/0.2/zebra_puzzle_rules"

keymanager = p.KeyManager(keyseed=1629)
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


I701 = p.create_item(
    R1__has_label="rule: identify same items via zb__R2850__is_functional_activity",
    R2__has_description=(
        "match two placeholders which are relate by a functional activity (R2850) with the same other items"
    ),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I701.scope("context") as cm:
    cm.new_var(ph1=p.instance_of(p.I1["general item"]))
    cm.new_var(ph2=p.instance_of(p.I1["general item"]))
    cm.new_var(some_itm=p.instance_of(p.I1["general item"]))
    cm.new_rel_var("rel1")  # -> p.instance_of(p.I40["general relation"]))

with I701.scope("premises") as cm:
    cm.new_rel(cm.ph1, p.R57["is placeholder"], True)
    cm.new_rel(cm.ph2, p.R57["is placeholder"], True)

    # both placeholders are related to the same item via the same relation
    cm.new_rel(cm.ph1, cm.rel1, cm.some_itm)  # -> p.R58["wildcard relation"]
    cm.new_rel(cm.ph2, cm.rel1, cm.some_itm)  # -> p.R58["wildcard relation"]

    cm.new_rel(cm.rel1, zb.R2850["is functional activity"], True)

with I701.scope("assertions") as cm:
    cm.new_rel(cm.ph1, p.R47["is same as"], cm.ph2)

# ###############################################################################


I702 = p.create_item(
    R1__has_label="rule: replace (some) same_as-items",
    R2__has_description=("replace placeholder items which have one R47__is_same_as statement"),
    R4__is_instance_of=p.I41["semantic rule"],
)

with I702.scope("context") as cm:
    cm.new_var(itm1=p.instance_of(p.I1["general item"]))
    cm.new_var(itm2=p.instance_of(p.I1["general item"]))
    cm.uses_external_entities(I702)

with I702.scope("premises") as cm:
    cm.new_rel(cm.itm1, p.R57["is placeholder"], True)
    cm.new_rel(cm.itm1, p.R47["is same as"], cm.itm2)

with I702.scope("assertions") as cm:
    cm.new_consequent_func(p.replacer_method, cm.itm1, cm.itm2)

# ###############################################################################
p.end_mod()