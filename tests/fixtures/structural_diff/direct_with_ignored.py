"""Direct fixture with an extra ``snippet(1i)`` (ignored) block.

The diff is run with explicit snippet IDs ``["1", "2", "3"]`` and must
skip the ignored block.  ``parse_pyirk_module`` must still surface ``"1i"``
as its own bucket.
"""

import pyirk as p

ma = p.irkloader.load_mod_from_uri("irk:/ocse/0.2/math", prefix="ma")


__URI__ = "irk:/auto_import_test_mini_ignored"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


# ---- prelude ---------------------------------------------------------------

I600 = p.create_item(R1__has_label="snippet")
R699 = p.create_relation(R1__has_label="contains concept")

I600["snippet"].update_relations(
    R4__is_instance_of=p.I2["Metaclass"],
)


# ---- snippet(1) ------------------------------------------------------------

I601 = p.create_item(R1__has_label="snippet(1)")
I601["snippet(1)"].update_relations(
    R4__is_instance_of=I600["snippet"],
)

I602 = p.create_item(R1__has_label="vector space")
I602["vector space"].update_relations(
    R3__is_subclass_of=ma.I13["mathematical set"],
    R77__has_alternative_label__de="Vektorraum",
)


# ---- snippet(1i) -- ignored ------------------------------------------------

I610 = p.create_item(R1__has_label="snippet(1i)")
I610["snippet(1i)"].update_relations(
    R4__is_instance_of=I600["snippet"],
)

I611 = p.create_item(R1__has_label="experimental notion")
I611["experimental notion"].update_relations(
    R3__is_subclass_of=I602["vector space"],
)


# ---- snippet(2) ------------------------------------------------------------

I603 = p.create_item(R1__has_label="snippet(2)")
I603["snippet(2)"].update_relations(
    R4__is_instance_of=I600["snippet"],
)

I604 = p.create_item(R1__has_label="linear mapping")
I604["linear mapping"].update_relations(
    R3__is_subclass_of=I602["vector space"],
)


# ---- snippet(3) ------------------------------------------------------------

I605 = p.create_item(R1__has_label="snippet(3)")
I605["snippet(3)"].update_relations(
    R4__is_instance_of=I600["snippet"],
)

I606 = p.create_item(R1__has_label="dual space")
I606["dual space"].update_relations(
    R3__is_subclass_of=I602["vector space"],
    R24__has_LaTeX_string="$V^*$",
)
