"""Direct fixture where 'vector space' is reused via an external OCSE key.

The item is *not* redeclared.  When the diff is run with a ``reuse_index``
that maps ``"vector space"`` to that external key, no missing/extra is
flagged.  Other content is identical to ``gold_mini.py`` (modulo keys).
"""

import pyirk as p

ma = p.irkloader.load_mod_from_uri("irk:/ocse/0.2/math", prefix="ma")


__URI__ = "irk:/auto_import_test_mini_reuse"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


# ---- prelude ---------------------------------------------------------------

I800 = p.create_item(R1__has_label="snippet")
R899 = p.create_relation(R1__has_label="contains concept")

I800["snippet"].update_relations(
    R4__is_instance_of=p.I2["Metaclass"],
)


# ---- snippet(1) ------------------------------------------------------------

I801 = p.create_item(R1__has_label="snippet(1)")
I801["snippet(1)"].update_relations(
    R4__is_instance_of=I800["snippet"],
)

# 'vector space' is reused from the OCSE math module -- intentionally not
# redeclared here.  Note: no inline external decoration either; the
# reuse_index alone must sanction the absence.


# ---- snippet(2) ------------------------------------------------------------

I802 = p.create_item(R1__has_label="snippet(2)")
I802["snippet(2)"].update_relations(
    R4__is_instance_of=I800["snippet"],
)

I803 = p.create_item(R1__has_label="linear mapping")
I803["linear mapping"].update_relations(
    R3__is_subclass_of=ma.I5166["vector space"],
)


# ---- snippet(3) ------------------------------------------------------------

I804 = p.create_item(R1__has_label="snippet(3)")
I804["snippet(3)"].update_relations(
    R4__is_instance_of=I800["snippet"],
)

I805 = p.create_item(R1__has_label="dual space")
I805["dual space"].update_relations(
    R3__is_subclass_of=ma.I5166["vector space"],
    R24__has_LaTeX_string="$V^*$",
)
