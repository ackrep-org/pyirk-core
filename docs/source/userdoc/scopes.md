(sec_scopes)=
# Scopes

## Basics

Many knowledge artifacts (such as theorems or definitions) consists of multiple simpler
statements which are in a specific semantic relation to each other. Consider the example
theorem:

> Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and {math}`(l_a, l_b, l_c)` the respective lengths. If the angle between a and b is a right angle then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds.


Such a theorem consists of several "semantic parts", which in the context of Pyirk are
called *scopes*. In particular we have the three following scopes:

- *setting*: "Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and (la, lb, lc) the respective lengths."
- *premise*: "If the angle between a and b is a rect angle"
- *assertion*: "then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds."

The concepts "premise" and "assertion" are usually used to refer to parts of theorems (
etc). Additionally PyIRK uses the "setting"-scope to refer to those statements which
do "set the stage" to properly formulate the premise and the assertion (e.g. by
introducing and specifying the relevant objects).

In Pyirk, scopes are represented by Items (instances (`R4`) of `I16["scope"]`). A scope
item is
specified by `R64__has_scope_type`. It is associated with a parent item (e.g. a theorem)
via `R21__is_scope_of`. A statement which semantically belongs to a specific scope is
associated to the respective scope item via
the [qualifier](sec_qualifiers) `R20__has_defining_scope`.

```{note}
`R21__is_scope_of` and `R20__has_defining_scope` are not inverse (`R68__is_inverse_of`) to each other.
```

## Notation of Scopes via Context Managers (`with ... as cm`)

To simplify the creation of the auxiliary
scope-items [python context managers](https://docs.python.org/3/reference/datamodel.html#context-managers) (
i.e. `with`-statements) are used. This is illustrated by the following example:

```python
I5000 = p.create_item(
    R1__has_label="simplified Pythagorean theorem",
    R4__is_instance_of=p.I15["implication proposition"],
)

# because I5000 is an instance of I15 it has a `.scope` method:
with I5000["simplified Pythagorean theorem"].scope("setting") as cm:
    # the theorem should hold for every planar triangle,
    # thus a universally quantified instance is created
    cm.new_var(ta=p.uq_instance_of(I1000["planar triangle"]))
    cm.new_var(sides=I1001["get polygon sides ordered by length"](cm.ta))

    a, b, c = p.unpack_tuple_item(cm.sides)
    la, lb, lc = a.R2000__has_length, b.R2000, c.R2000

with I5000["simplified Pythagorean theorem"].scope("premise") as cm:
    cm.new_equation(lhs=I1002["angle"](a, b), rhs=I1003["right angle"])

with I5000["simplified Pythagorean theorem"].scope("assertion") as cm:

    # convert a pyirk items into  sympy.Symbol instances to conveniently
    # denote formulas (see documentation below)
    La, Lb, Lc = p.items_to_symbols(la, lb, lc)
    cm.new_equation( La**2 + Lb**2, "==", Lc**2 )
```
