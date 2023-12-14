(sec_userdoc_overview)=
# Pyirk User Documentation Overview

(sec_keys)=
## Keys in Pyirk

In Pyirk there are the following kinds of keys:
- a) short_key like `"R1234"`
- b) name-labeled key like `"R1234__my_relation"` (consisting of a short_key, a delimiter (`__`) and a label)
- c) prefixed short_key like `"bi__R1234"` (here the prefix `bi` refers to the module `builtin_entities`)
- d) prefixed name-labeled key like `"bi__R1234__my_relation"`
- e) index-labeled key like  `"R1234['my relation']"`

Note: prefixed and name-labeled keys can optionally have a language indicator. Examples: ``"bi__R1__de"`` or `"R1__has_label__fr"`.

Also, the leading character indicates the entity type (called `EType` in the code): `I` → item, `R` → relation.

The usage of these syntax variants depends on the context.

For more information see See also {ref}`sec_modules`.

% TODO: add example code.

(sec_visualization)=
## Visualization

Currently there is some basic visualization support via the command line. To visualize your a module (including its relations to the builtin_entities) you can use a command like

```
pyirk --load-mod demo-module.py demo -vis __all__
```

(sec_cli_overview)=
## Command Line Interface

For an overview of available command line options, see the [CLI page](cli) or the command:

```
pyirk -h
```

### Interactive Usage

To open an IPython shell with a loaded module run e.g.

```
pyirk -i -l control_theory1.py ct
```

Then, you have `ct` as variable in your namespace and can e.g. run `print(ct.I5167.R1)`.

(The above command assumes that the file `control_theory1.py` is in your current working directory.)


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



(sec_patterns)=
## Patterns for Knowledge Representation in Pyirk

In Pyirk knowledge is represented via *entities* and *statements* (inspired by Wikidata). There are two types of entities: *items* (mostly associated with nouns) and *relations* (mostly associated with verbs). Statements consist of *subject-predicate-object*-triples.

- subject: can be any entity (item or a relation),
- predicate: is always a relation,
- object: can be any entity or *literal*.

Literals are "atomic" values like strings, numbers or boolean values.

Every entity has short_key (`entity.short_key`, see also {ref}`sec_keys`.) and an uri (`entity.uri`). It is recommended but not required that every entity has a label (by means of relation `R1["has label"]`) and a description (by means of `R2["has description"]`).

(sec_items)=
### Item (subclass of `core.Entity`)

The `short_key` of any items starts with "`I`" and ends with a sequence of number characters (maximum sequence length not yet specified). Optionally the second character is "`a`" which indicates that this item was generated automatically (see [below](sec_auto_gen_items)).

(Almost) All items are part of a taxonomy, i.e. a hierarchy of *"is-a"*-relations). This is expressed by the relations `R3["is_subclass_of"]` and `R4["is instance of"]`.


```{note}
Unlike in OWL (but like in Wikidata) an item can be an instance and a class at the same time. This allows to treat classes as "ordinary" items if necessary, e.g. use them directly in statements.
```


(sec_auto_gen_items)=
#### Automatically Generated Items

One consequence of expressing knowledge as a collection of triples is the necessity of auxiliary items. E.g. consider the equation {math}`y = \sin(x)` where `x, y, sin` can be assumed to be well defined items. Because the predicate must be a relation, it is not possible to relate these three items in one triple. The usual approach to deal with such situations is to introduce auxiliary items and more triples (see also [wikipedia on "reification"](https://en.wikipedia.org/wiki/Reification_(knowledge_representation))). One possible (fictional) triple representation of the above equation is

```
auxiliary_expr is_function_call_of_type sin
auxiliary_expr has_arg x
y is_equal_to expr
```

One of the main goals of Pyirk is to simplify the creation of triples which involves creating auxiliary items (such as evaluated expressions). This can be achieved by calling functions such as `pyirk.instance_of(...)`. A more sophisticated way is to overload the `__call__` method of entities.


(sec___call__mechanism)=
#### The `__call__`-Method

The class `pyirk.Entity` implements the `__call__` method which formally makes all items and relations callable Python objects. However, by default no method `_custom_call` is implemented which results in an exception. Associating a `_custom_call` method and thus truly make an item callable can be achieved by

- explicitly adding the method, like e.g. in `I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call")`
- creating an item which is a subclass (`R3`) or instance (`R4`) of a method which already has a `_custom_call` method, see `core.Entity._perform_inheritance` and `core.Entity._perform_instantiation` for details.


(sec___adding_convenience_methods)=
#### Adding Convenience Methods

The method `core.Entity.add_method(...)` can be used to add arbitrary methods to items (which then can be inherited by other items). Example: see how the function `builtin_entities.get_arguments` is attached to every result of `builtin_entities.create_evaluated_mapping` (which itself is used as `_custom_call` method).


(sec_relations)=
### Relations (`core.Relation`, subclass of `core.Entity`)

The `.short_key` of any relation starts with `R`. The *predicate* part of a semantic triple must always be a (python) instance of `Core.Relation` .  In general they can occur as *subject* or *object* as well.

From a graph perspective the relation defines the type of the edge between two nodes. The nodes are typically `Item`-instances.

(sec_Literals)=
### Literals (`core.Literal` imported from `rdflib`)

Instances of the class model string values (including a `.language` attribute).

(sec_Statements)=
### Statements (`core.Statement`)

Instances of this class model semantic triples (subject, predicate, object) and corresponding [qualifiers](sec_qualifiers). Every edge in the knowledge graph corresponds to a statement instance.

Note: For technical reasons for every `Statement` instance there exits a dual `Statement` instance. For most situations this does not matter, though.

The whole knowledge graph is a collection of Entities (Items, Relation, Literals) and Statements. Roughly speaking, the collection of Entities defines what exists (in the respective universe of discourse) while the collection of Statements defines how these things are related. Because flat subject-predicate-object triples have very limited expressivity it is possible to "make statements about statements", i.e. use a `Statement` instance as subject another triple. This [Wikidata](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial#Qualifiers)-inspired mechanism is called [qualifiers](sec_qualifiers) (see below).



(sec_qualifiers)=
## Qualifiers


Basic statements in Pyirk are modeled as `subject`-`predicate`-`object`-triples.
E.g. to express that R. Kalman works at Stanford University one could use:
```python
# example from ocse0.2 (adapted)
I2746["Rudolf Kalman"].set_relation(R1833["has employer"], I9942["Stanford University"])
#.
```

This results in the triple: `(I2746, R1833, I9942)`. In Pyirk such triples are modeled as instances of class `Statement`; each such instance represents an edge in the knowledge graph, where the subject and object are the corresponding nodes and each such edge has a lable (the relation type) and optionally other information attached to it.


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
## Scopes

### Basics
Many knowledge artifacts (such as theorems or definitions) consists of multiple simpler statements which are in a specific semantic relation to each other. Consider the example theorem:

> Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and {math}`(l_a, l_b, l_c)` the respective lengths. If the angle between a and b is a rect angle then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds.


Such a theorem consists of several "semantic parts", which in the context of Pyirk are called *scopes*. In particular we the three following scopes:

- *setting*: "Let (a, b, c) be the sides of a triangle, ordered from shortest to longest, and (la, lb, lc) the respective lengths."
- *premise*: "If the angle between a and b is a rect angle"
- *assertion*: "then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds."

While the concepts "premise" and "assertion" are usually used to refer to parts of theorems (etc). The concept of "setting" is used to refer to those statements which do "set the stage" to properly formulate the premise and the assertion (e.g. by introducing and specifying the relevant objects).

### Scopes in Pyirk

Scopes are represented by  Items (instances (`R4`) of `I16["scope"]`). A scope item is specified by `R64__has_scope_type`. It is associated with a parent item (e.g. a theorem) via `R21__is_scope_of`. A statement which semantically belongs to a specific scope is associated to the respective scope item via the [qualifier](sec_qualifiers) `R20__has_defining_scope`.

```{note}
`R21__is_scope_of` and `R20__has_defining_scope` are not inverse (`R68__is_inverse_of`) to each other.
```

### Notation of Scopes via Context Managers (`with ... as cm`)

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

(sec_formulas)=
## Representing Formulas

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

### Convenience-Expressions

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


## Universal and Existential Quantification

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
Despite having similar phonetics (and spelling) quantifiers (logic operators) and qualifiers (knowledge modeling technique, in triple-based knowledge graphs) are totally different concepts. However, qualifiers can (among many other use cases) be used to model universal or existential quantification of an statement.
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
