(sec_formulas)=
# Representing Formulas

In the module `math1.py` of OCSE there is an implementation for a convenient formula
notation (write `x + y + z` instead of `add_item(x, add_item(y, z))`). See this example
from the OCSE unittests:

```python
ma = p.irkloader.load_mod_from_path(pjoin(OCSE_PATH, "math1.py"), prefix="ma")
t = p.instance_of(ma.I2917["planar triangle"])
sides = ma.I9148["get polygon sides ordered by length"](t)
a, b, c = sides.R39__has_element

la, lb, lc = ma.items_to_symbols(a, b, c, relation=ma.R2495["has length"])
symbolic_sum = la + lb + lc

sum_item = ma.symbolic_expression_to_graph_expression(symbolic_sum)
```


## Convenience-Expressions

```{warning}
This is not yet implemented. However, see [formula representation](sec_formulas).
```

While the operator approach is suitable to create the appropriate notes and edges in the
knowledge graph it is not very convenient to write more complex formulas in that way.
Thus pyirk offers a convenience mechanism based on the computer algebra
package [Sympy](https://docs.sympy.org/dev/install.html). The
function `builtin_entities.items_to_symbols()` creates a sympy symbol for every passed
item (and keeps track of the associations). Then, a formula can be denoted using "usual"
python syntax with operator signs `+`, `-`, `*`, `/`, and `**` which results in an
instance of `sympy.core.expr.Expr`. These expressions can be passed, e.g.,
to `cm.new_equation` where they are converted back to pyirk-items. In other words the
following two snippets are equivalent:

```python
# approach 1: using intermediate symbolic expressions
La, Lb, Lc = p.items_to_symbols(la, lb, lc)
cm.new_equation( La**2 + Lb**2, "==", Lc**2 )

# approach 0: without using intermediate symbolic expressions
sq = I1010["squared"]
plus = I1011["plus"]
cm.new_equation( plus(sq(La), sq(Lb)), "==", sq(Lc) )
```

<!-- TODO: introduce real squared and plus operators -->
<!-- TODO: implement this mechanism and refer to unit test here -->
