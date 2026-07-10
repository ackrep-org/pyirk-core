"""Tiny pyirk-gold fixture: prelude + 3 snippets.

Used by ``tests/test_structural_diff.py`` to exercise the structural-diff
parser.  Not a runnable pyirk module -- the references are dummies.
"""

import pyirk as p

ma = p.irkloader.load_mod_from_uri("irk:/ocse/0.2/math", prefix="ma")


__URI__ = "irk:/auto_import_test_mini"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


# ---- prelude ---------------------------------------------------------------

I100 = p.create_item(R1__has_label="snippet")
R200 = p.create_relation(R1__has_label="contains concept")

I100["snippet"].update_relations(
    R4__is_instance_of=p.I2["Metaclass"],
)


# ---- snippet(1) ------------------------------------------------------------

I101 = p.create_item(R1__has_label="snippet(1)")
I101["snippet(1)"].update_relations(
    R4__is_instance_of=I100["snippet"],
)

I102 = p.create_item(R1__has_label="vector space")
I102["vector space"].update_relations(
    R3__is_subclass_of=ma.I13["mathematical set"],
    R77__has_alternative_label__de="Vektorraum",
)


# ---- snippet(2) ------------------------------------------------------------

I103 = p.create_item(R1__has_label="snippet(2)")
I103["snippet(2)"].update_relations(
    R4__is_instance_of=I100["snippet"],
)

I104 = p.create_item(R1__has_label="linear mapping")
I104["linear mapping"].update_relations(
    R3__is_subclass_of=I102["vector space"],
)


# ---- snippet(3) ------------------------------------------------------------

I105 = p.create_item(R1__has_label="snippet(3)")
I105["snippet(3)"].update_relations(
    R4__is_instance_of=I100["snippet"],
)

I106 = p.create_item(R1__has_label="dual space")
I106["dual space"].update_relations(
    R3__is_subclass_of=I102["vector space"],
    R24__has_LaTeX_string="$V^*$",
)
