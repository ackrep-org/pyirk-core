(sec_userdoc_overview)=
# More Stuff

**TODO** add intro

(sec_patterns)=

(sec_keys)=
(sec_Literals)=
### Literals (`core.Literal` imported from `rdflib`)

Instances of the class model string values (including a `.language` attribute).

(sec_Statements)=
### Statements (`core.Statement`)

Instances of this class model semantic triples (subject, predicate, object) and corresponding [qualifiers](sec_qualifiers). Every edge in the knowledge graph corresponds to a statement instance.

```{note}
Note: For technical reasons for every `Statement` instance there exits a dual `Statement` instance. For most situations this does not matter, though.
```

The whole knowledge graph is a collection of Entities (Items, Relation, Literals) and Statements. Roughly speaking, the collection of Entities defines what exists (in the respective universe of discourse) while the collection of Statements defines how these things are related. Because flat subject-predicate-object triples have very limited expressivity it is possible to "make statements about statements", i.e. use a `Statement` instance as subject another triple. This [Wikidata](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial#Qualifiers)-inspired mechanism is called [qualifiers](sec_qualifiers) (see below).



(sec_qualifiers)=
### Qualifiers


Basic statements in Pyirk are modeled as `subject`-`predicate`-`object`-triples.
E.g. to express that R. Kalman works at Stanford University one could use:
```python
# example from ocse0.2 (adapted)
I2746["Rudolf Kalman"].set_relation(R1833["has employer"], I9942["Stanford University"])
#.
```

This results in the triple: `(I2746, R1833, I9942)`. In Pyirk such triples are modeled as instances of class `Statement`; each such instance represents an edge in the knowledge graph, where the subject and object are the corresponding nodes and each such edge has a label (the relation type) and optionally other information attached to it.


However, in many cases more complexity is needed. To express that Kalman worked at Stanford between 1964 and 1971, we can exploit that `Statement`-instances can themselves be use as subject of other triples, by means of so called qualifiers:
```python
start_time = p.QualifierFactory(R4156["has start time"])
end_time = p.QualifierFactory(R4698["has end time"])

I2746["Rudolf Kalman"].set_relation(
    R1833["has employer"], I9942["Stanford University"], qualifiers=[start_time("1964"), end_time("1971")]
)
#.
```

Here `start_time` and `end_time` are instances of the class `QualifierFactory`. If such an instance is called, it returns an instance of class `RawQualifier` which is basically a yet incomplete triple where only the predicate and the object is fixed. The subject of this triple will be formed by the main statement itself (modeled by an instance of `Statement`).

Thus the above code creates three `Statement` instances here simplified:

```
S(2746, R1833, I9942) # the main statement, now referenced as stm1
S(stm1, R4156, "1964")
S(stm1, R4698, "1971")
#.
```


```{note}
The concept of qualifiers is borrowed from Wikidata, see e.g the [WD-SPARQL-tutorial](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial#Qualifiers)
```


**Summary:** Qualifiers are a flexible possibility to model "information about information" in Pyirk. They are used, e.g. to model the universal quantification.



(sec_scopes)=
### Scopes

#### Basics
Many knowledge artifacts (such as theorems or definitions) consists of multiple simpler statements which are in a specific semantic relation to each other. Consider the example theorem:

> Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and {math}`(l_a, l_b, l_c)` the respective lengths. If the angle between a and b is a right angle then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds.


Such a theorem consists of several "semantic parts", which in the context of Pyirk are called *scopes*. In particular we have the three following scopes:

- *setting*: "Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and (la, lb, lc) the respective lengths."
- *premise*: "If the angle between a and b is a rect angle"
- *assertion*: "then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds."

The concepts "premise" and "assertion" are usually used to refer to parts of theorems (etc). Additionally PyIRK uses the "setting"-scope to refer to those statements which do "set the stage" to properly formulate the premise and the assertion (e.g. by introducing and specifying the relevant objects).

#### Scopes in Pyirk

Scopes are represented by  Items (instances (`R4`) of `I16["scope"]`). A scope item is specified by `R64__has_scope_type`. It is associated with a parent item (e.g. a theorem) via `R21__is_scope_of`. A statement which semantically belongs to a specific scope is associated to the respective scope item via the [qualifier](sec_qualifiers) `R20__has_defining_scope`.

```{note}
`R21__is_scope_of` and `R20__has_defining_scope` are not inverse (`R68__is_inverse_of`) to each other.
```

#### Notation of Scopes via Context Managers (`with ... as cm`)

To simplify the creation of the auxiliary scope-items [python context managers](https://docs.python.org/3/reference/datamodel.html#context-managers) (i.e. `with`-statements) are used. This is illustrated by the following example:

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

(sec_operators)=
### Operators

Example from `math.py` (OCSE):


```python
I4895 = p.create_item(
    R1__has_label="mathematical operator",
    R2__has_description="general (unspecified) mathematical operator",
    R3__is_subclass_of=p.I12["mathematical object"],
)

I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call")


I5177 = p.create_item(
    R1__has_label="matmul",
    R2__has_description=("matrix multiplication operator"),
    R4__is_instance_of=I4895["mathematical operator"],
    R8__has_domain_of_argument_1=I9904["matrix"],
    R9__has_domain_of_argument_2=I9904["matrix"],
    R11__has_range_of_result=I9904["matrix"],
)

# representing the product of two matrices:

A = p.instance_of(I9904["matrix"])
B = p.instance_of(I9904["matrix"]])

# this call creates and returns a new item
# (instance of `I32["evaluated mapping"]`)
C = I5177["matmul"](A, B)

# equivalent but more readable:
mul = I5177["matmul"]
C = mul(A, B)
```

(sec_formulas)=
### Representing Formulas

In the module `math1.py` of OCSE there is an implementation for a convenient formula notation (write `x + y + z` instead of `add_item(x, add_item(y, z))`). See this example from the OCSE unittests:

```python
ma = p.irkloader.load_mod_from_path(pjoin(OCSE_PATH, "math1.py"), prefix="ma")
t = p.instance_of(ma.I2917["planar triangle"])
sides = ma.I9148["get polygon sides ordered by length"](t)
a, b, c = sides.R39__has_element

la, lb, lc = ma.items_to_symbols(a, b, c, relation=ma.R2495["has length"])
symbolic_sum = la + lb + lc

sum_item = ma.symbolic_expression_to_graph_expression(symbolic_sum)
```


#### Convenience-Expressions

```{warning}
This is not yet implemented. However, see [formula representation](sec_formulas).
```

While the operator approach is suitable to create the appropriate notes and edges in the knowledge graph it is not very convenient to write more complex formulas in that way. Thus pyirk offers a convenience mechanism based on the computer algebra package [Sympy](https://docs.sympy.org/dev/install.html). The function `builtin_entities.items_to_symbols()` creates a sympy symbol for every passed item (and keeps track of the associations). Then, a formula can be denoted using "usual" python syntax with operator signs `+`, `-`, `*`, `/`, and `**` which results in an instance of `sympy.core.expr.Expr`. These expressions can be passed, e.g., to `cm.new_equation` where they are converted back to pyirk-items. In other words the following two snippets are equivalent:

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


(sec_stubs)=
### Stubs (`I50["Stub"]`, `I000["some arbitrary label"]` and `R000["also"]`)

One challenge in formal knowledge representation is  *Where to begin?* 
Suppose you want to formalize some knowledge about triangles. 
It seems natural that you introduce the class *triangle* as a subclass of *polygon*. 
However, the class polygon should also be a subclass of something and so on.

As modelling *all* knowledge is unfeasible at some points it is necessary to model incomplete entities (Ideally, theses
are some relation-steps away from the relevant entities of the domain). To facilitate this there exists `I50["stub"]`.
This item can be used as (base) class for any item which at the moment no further (taxonomic) information should be
modeled. The name "stub" is inspired by Wikipedia's [stub-pages](https://en.wikipedia.org/wiki/Wikipedia:Stub). Example:


```python
I1234 = p.create_item(
    R1__has_label="polygon",
    R2__has_description="",
    R3__is_subclass_of=p.I50["stub"],
)
```

In some situations it is desirable to use items and relations which do not yet exist. This can be done by `I000["dummy item]` and `R000["dummy relation"]`. Both entities can be used with **arbitrary labels** and can thus be used regarded as a special kind of comment. Example:

```python
I1234 = p.create_item(
    R1__has_label="polygon",
    R2__has_description="",
    R3__is_subclass_of=p.I000["general geometric figure"],
    R000__has_dimension=2,
)

```

This allows to focus a modeling session on the important items and relations and prevents to get distracted by introducing entities of subordinate relevance.

It is quite probable that even mature irk-ontologies contain relations involving `I50`. Such items can be considered to constitute the "border of the domain of discourse". On the other hand, `I000` and `R000` should be used only temporarily and be replaced soon, e.g., by new instances/subclasses of `I50`.


(sec_quantification)=
### Universal and Existential Quantification

Background, see <https://en.wikipedia.org/wiki/Quantifier_(logic)>.

> commonly used quantifiers are ∀ (`$\forall$`) and ∃ (`$\exists$`).

They are also called *universal quantifier* and *existential quantifier*. In Pyirk they can be expressed via

- [Qualifiers](sec_qualifiers). In particular (defined in module `builtin_entities`):
    - `univ_quant = QualifierFactory(R44["is universally quantified"])`
        - usage (in OCSE): `cm.new_rel(cm.z, p.R15["is element of"], cm.HP, qualifiers=p.univ_quant(True))`
    - `exis_quant = QualifierFactory(R66["is existentially quantified"])`
        - usage (in OCSE): `cm.new_var(y=p.instance_of(p.I37["integer number"], qualifiers=[p.exis_quant(True)]))`
- (Sub)scopes:
    ```python
    # excerpt from test_core.py
    with I7324["definition of something"].scope("premise") as cm:
                with cm.universally_quantified() as cm2:
                    cm2.add_condition_statement(cm.x, p.R15["is element of"], my_set)
    # ...
    with I7324["definition of something"].scope("assertion") as cm:
                # also pointless direct meaning, only to test contexts
                with cm.existentially_quantified() as cm2:
                    z = cm2.new_condition_var(z=p.instance_of(p.I39["positive integer"]))
    ```


```{warning}
Despite having similar phonetics (and spelling) quantifiers (logic operators) and qualifiers (knowledge modeling technique, in triple-based knowledge graphs) are totally different concepts. However, qualifiers can (among many other use cases) be used to model universal or existential quantification of a statement.
```


(sec_modules)=
## Pyirk Modules and Packages

Pyirk entities and statements are organized in Pyirk *modules* (python files). Each module has to specify its own URI via the variable `__URI__`. The uri of an entity from that module is formed by `<module URI>#<entity short_key>`. Modules can be bundled together to form pyirk *packages*. A Pyirk package consists of a directory containing a file `irkpackage.toml` and at least one Pyirk module.

Modules can depend on other modules. A usual pattern is the following:

```python
# in module control_theory1.py

import pyirk as p
mod = p.irkloader.load_mod_from_path("./math1.py", prefix="ma")
```

Here the variable `mod` is the module object (like from ordinary python import) and allows to access to the complete namespace of that module:
```python
# ...

A = p.instance_of(mod.I9904["matrix"])
```

The prefix `"ma"` can also be used to refer to that module like here
```python
# ...

res = A.ma__R8736__depends_polynomially_on
```

Rationale: The attribute name `ma__R8736__depends_polynomially_on` is handled as a string by Python (in the method `__getattr__`). While `mod.R8736` is the relation object we cannot use this syntax as attribute name.

See also {ref}`sec_keys`.
### Update Test Data

```
pyirk --update-test-data
```

For details see [devdoc#test_data](sec_test_data)


## Multilinguality

Pyirk aims to support an arbitrary number of languages by so called *language specified strings*. Currently support for English and German is preconfigured in `pyirk.settings`. These language specified strings are instances of the class `rdflib.Literal` where the `.language`-attribute is set to one of the values from `pyirk.setting.SUPPORTED_LANGUAGES` and can be created like:

```python
from pyirk import de, en

# ...

lss1 = "some english words"@en
lss2 = "ein paar deutsche Wörter"@de
```

where `en, de` are instances of `pyirk.core.LanguageCode`.

The usage inside Pyirk is best demonstrated by the unittest `test_c02__multilingual_relations`, see [test_core.py](https://github.com/ackrep-org/pyirk-core/blob/main/tests/test_core.py) (maybe change branch).
