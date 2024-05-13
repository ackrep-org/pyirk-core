import pyirk as p

# pyirk boilerplate
__URI__ = "irk:/examples/0.2/pythagorean_thm"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

# create the theorem
I5000 = p.create_item(
    R1__has_label="simplified Pythagorean theorem",
    R4__is_instance_of=p.I15["implication proposition"],
)

# create the setting
with I5000["simplified Pythagorean theorem"].scope("setting") as st:
    # the theorem should hold for every planar triangle,
    # thus a universally quantified instance is created
    st.new_var(ta=p.uq_instance_of(I2917["planar triangle"]))
    st.new_var(sides=I9148["get polygon sides ordered by length"](st.ta))

    a, b, c = p.unpack_tuple_item(st.sides)
    la, lb, lc = a.R2495__has_length, b.R2495, c.R2495

# create the premise
with I5000["simplified Pythagorean theorem"].scope("premise") as st:
    st.new_equation(lhs=I1002["angle"](a, b), rhs=I1003["right angle"])

# create the assertion
with I5000["simplified Pythagorean theorem"].scope("assertion") as st:
    # convert a pyirk items into  sympy.Symbol instances to conveniently
    # denote formulas (see documentation below)
    La, Lb, Lc = p.items_to_symbols(la, lb, lc)
    st.new_equation(La ** 2 + Lb ** 2, "==", Lc ** 2)
