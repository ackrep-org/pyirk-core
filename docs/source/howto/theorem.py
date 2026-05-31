"""Encode a theorem statement in pyirk -- see howto/theorem.md.

This example reuses a few geometry items from a small subset of the OCSE
(Ontology of Control Systems Engineering) that ships with the pyirk repo
as test data. No external data dependency is required to run it.
"""

import os
import pyirk as p

_HERE = os.path.dirname(os.path.abspath(__file__))
_OCSE_MATH = os.path.join(_HERE, "..", "..", "..", "tests", "test_data", "ocse_subset", "math1.py")
ma = p.irkloader.load_mod_from_path(_OCSE_MATH, prefix="ma")

# pyirk boilerplate
__URI__ = "irk:/examples/0.2/pythagorean_thm"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)


# OCSE does not (yet) contain items for angle quantities or right angles,
# so we add them locally. This also shows how to extend an external
# knowledge base without modifying it. We use three items so the operator
# result and the named constant are explicitly typed as the same kind of
# quantity (rather than just sharing 'real number' by coincidence):
I999 = p.create_item(
    R1__has_label="angle (quantity)",
    R2__has_description="real-number-valued type for angle magnitudes (in radians)",
    R3__is_subclass_of=p.I35["real number"],
)
I1000 = p.create_item(
    R1__has_label="angle",
    R2__has_description="binary operator: angle enclosed by two sides of a polygon",
    R4__is_instance_of=p.I8["mathematical operation with arity 2"],
    R8__has_domain_of_argument_1=ma.I8172["polygon side"],
    R9__has_domain_of_argument_2=ma.I8172["polygon side"],
    R11__has_range_of_result=I999["angle (quantity)"],
)
I1001 = p.create_item(
    R1__has_label="right angle",
    R2__has_description="constant: an angle of pi/2 (90 degrees)",
    R4__is_instance_of=I999["angle (quantity)"],
)


# create the theorem
I5000 = p.create_item(
    R1__has_label="simplified Pythagorean theorem",
    R4__is_instance_of=p.I15["implication proposition"],
)

# create the setting
with I5000["simplified Pythagorean theorem"].scope("setting") as st:
    # the theorem should hold for every planar triangle,
    # thus a universally quantified instance is created
    st.new_var(ta=p.uq_instance_of(ma.I2917["planar triangle"]))
    st.new_var(sides=ma.I9148["get polygon sides ordered by length"](st.ta))

    a, b, c = p.unpack_tuple_item(st.sides)
    # R2495 ("has length") lives in the OCSE math module, so the
    # cross-module prefix 'ma__' is required for attribute access:
    la = a.ma__R2495__has_length
    lb = b.ma__R2495__has_length
    lc = c.ma__R2495__has_length

# create the premise
with I5000["simplified Pythagorean theorem"].scope("premise") as st:
    st.new_equation(lhs=I1000["angle"](a, b), rhs=I1001["right angle"])

# create the assertion
with I5000["simplified Pythagorean theorem"].scope("assertion") as st:
    # pyirk items overload **, +, *, so we can write the equation directly
    # on the length items (la, lb, lc); no sympy detour required.
    st.new_equation(lhs=la**2 + lb**2, rhs=lc**2)

p.end_mod()
