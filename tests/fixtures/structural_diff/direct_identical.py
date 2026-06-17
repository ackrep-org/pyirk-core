"""Label-identical sibling of ``gold_mini.py`` with different I/R keys.

The structural diff must collapse this to score == 1.0 even though every
key was reallocated -- matching is by R1 label, not by key.
"""

import pyirk as p

ma = p.irkloader.load_mod_from_uri("irk:/ocse/0.2/math", prefix="ma")


__URI__ = "irk:/auto_import_test_mini_direct"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


# ---- prelude ---------------------------------------------------------------

I900 = p.create_item(R1__has_label="snippet")
R999 = p.create_relation(R1__has_label="contains concept")

I900["snippet"].update_relations(
    R4__is_instance_of=p.I2["Metaclass"],
)


# ---- snippet(1) ------------------------------------------------------------

I901 = p.create_item(R1__has_label="snippet(1)")
I901["snippet(1)"].update_relations(
    R4__is_instance_of=I900["snippet"],
)

I902 = p.create_item(R1__has_label="vector space")
I902["vector space"].update_relations(
    R3__is_subclass_of=ma.I13["mathematical set"],
    R77__has_alternative_label__de="Vektorraum",
)


# ---- snippet(2) ------------------------------------------------------------

I903 = p.create_item(R1__has_label="snippet(2)")
I903["snippet(2)"].update_relations(
    R4__is_instance_of=I900["snippet"],
)

I904 = p.create_item(R1__has_label="linear mapping")
I904["linear mapping"].update_relations(
    R3__is_subclass_of=I902["vector space"],
)


# ---- snippet(3) ------------------------------------------------------------

I905 = p.create_item(R1__has_label="snippet(3)")
I905["snippet(3)"].update_relations(
    R4__is_instance_of=I900["snippet"],
)

I906 = p.create_item(R1__has_label="dual space")
I906["dual space"].update_relations(
    R3__is_subclass_of=I902["vector space"],
    R24__has_LaTeX_string="$V^*$",
)
