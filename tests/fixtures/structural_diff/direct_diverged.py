"""Direct fixture with three controlled divergences vs ``gold_mini.py``:

* snippet(1): ``vector space`` is missing entirely (no reuse hint planned).
* snippet(2): an extra item ``"affine mapping"`` appears.
* snippet(3): ``dual space``'s ``R3__is_subclass_of`` points at
  ``"linear mapping"`` instead of ``"vector space"`` -- a relation mismatch.
"""

import pyirk as p

ma = p.irkloader.load_mod_from_uri("irk:/ocse/0.2/math", prefix="ma")


__URI__ = "irk:/auto_import_test_mini_diverged"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


# ---- prelude ---------------------------------------------------------------

I700 = p.create_item(R1__has_label="snippet")
R799 = p.create_relation(R1__has_label="contains concept")

I700["snippet"].update_relations(
    R4__is_instance_of=p.I2["Metaclass"],
)


# ---- snippet(1) ------------------------------------------------------------

I701 = p.create_item(R1__has_label="snippet(1)")
I701["snippet(1)"].update_relations(
    R4__is_instance_of=I700["snippet"],
)

# Intentionally NO "vector space" here.


# ---- snippet(2) ------------------------------------------------------------

I702 = p.create_item(R1__has_label="snippet(2)")
I702["snippet(2)"].update_relations(
    R4__is_instance_of=I700["snippet"],
)

I703 = p.create_item(R1__has_label="linear mapping")
I703["linear mapping"].update_relations(
    R3__is_subclass_of=ma.I5166["vector space"],
)

# Extra item not present in gold.
I704 = p.create_item(R1__has_label="affine mapping")
I704["affine mapping"].update_relations(
    R3__is_subclass_of=I703["linear mapping"],
)


# ---- snippet(3) ------------------------------------------------------------

I705 = p.create_item(R1__has_label="snippet(3)")
I705["snippet(3)"].update_relations(
    R4__is_instance_of=I700["snippet"],
)

I706 = p.create_item(R1__has_label="dual space")
I706["dual space"].update_relations(
    R3__is_subclass_of=I703["linear mapping"],
    R24__has_LaTeX_string="$V^*$",
)
