(sec_userdoc_overview)=
# pyerk User Documentation Overview

(sec_keys)=
## Keys in Pyerk

In Pyerk there are the following kinds of keys:
- a) short_key like `"R1234"`
- b) name-labeled key like `"R1234__my_relation"` (consisting of a short_key, a delimiter (`__`) and a label)
- c) prefixed short_key like `"bi__R1234"` (here the prefix `bi` referse to the module `builtin_entities`)
- d) prefixed name-labeled key like `"bi__R1234__my_relation"`
- e) index-labeld key like  `"R1234['my relation']"`

Also, the leading character indicates the entity type (called `EType` in the code): `I` → item, `R` → relation.

The usage of these syntax variants depens on the context.

For more information see See also {ref}`sec_modules`.

% TODO: add example code.

(sec_visualization)=
## Visualization

Currently there is some basic visualization support via the command line. To visualize your a module (including its relations to the builtin_entities) you can use a command like

```
pyerk --load-mod demo-module.py demo -vis __all__
```

(sec_cli_overview)=
## Command Line Interface

For an overview of available command line options, see the [CLI page](cli) or the command:

```
pyerk -h
```

### Interactive Usage

To open an IPython shell with a loaded module run e.g.

```
pyerk -i -l control_theory1.py ct
```

Then, you have `ct` as variable in your namespace and can e.g. run `print(ct.I5167.R1`).

(The above command assumes that the file `control_theory1.py` is in your current working directory.)

## Multilinguality

Pyerk aims to support an arbitrary number of languages by so called *language specified strings*. Currently support for English and German is preconfigured in `pyerk.settings`. These language specified strings are instances of the class `rdflib.Literal` where the `.language`-attribute is set to one of the values from `pyerk.setting.SUPPORTED_LANGUAGES` and can be created like:

```python
from pyerk import de, en

# ...

lss1 = "some english words"@en
lss2 = "ein paar deutsche Wörter"@de
```

where `en, de` are instances of `pyerk.core.LangaguageCode`.

The usage inside pyerk is best demonstrated by the unittest `test_c02__multilingual_relations`, see [test_core.py](https://github.com/ackrep-org/pyerk-core/blob/main/tests/test_core.py) (maybe change branch).




(sec_qualifiers)=
## Qualifiers


Basic statements in pyerk are modeled as `subject`-`predicate`-`object`-triples.
E.g. to express that R. Kalman works at Stanford University one could use:
```python
# example from ocse0.2 (adapted)
I2746["Rudolf Kalman"].set_relation(R1833["has employer"], I9942["Stanford University"])
#.
```

This results in the triple: `(I2746, R1833, I9942)`. In pyerk such triples are modeled as instances of class `Statement`; each such instance represents an edge in the knowledge graph, where the subject and object are the corresponding nodes and each such edge has a lable (the relation type) and optionally other information attachend to it.


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


**Summary:** Qualifiers are a flexible possibility to model "information about information" in pyerk. They are used, e.g. to model the universal quantification.


## Universal and Existential Quantification

Background, see <https://en.wikipedia.org/wiki/Quantifier_(logic)>.

> commonly used quantifiers are ∀ (`$\forall$`) and ∃ (`$\exists$`).

They are also called *universal quantifier* and *existential quantifier*. In pyerk they can be expressed via [qualifiers](sec_qualifiers)

```{warning}
Despite having similar phonetics (and spelling) quantifiers (logic operators) and qualifiers (knowledge modeling technique, in triple-based knowledge graphs) are totally different concepts. However, qualifiers can (among many other use cases) be used to model universal or existential quantification of an statement.
```


(sec_patterns)=
## Patterns for Knowledge Representation in pyerk

In pyerk knowledge is represented via *entities* and *statements* (inspired by Wikidata). There are two types of entities: *items* (mostly associated with nouns) and *relations* (mostly associated with verbs). Statements consist of *subject-predicate-object*-triples.

- subject: can be any entity (item or a relation),
- predicate: is always a relation,
- object: can be any entity or *literal*.

Literals are "atomic" values like strings, numbers or boolean values.

Every entity has short_key (`entity.short_key`, see also {ref}`sec_keys`.) and an uri (`entity.uri`). It is recommended but not requiered that every entity has a label (by means of relation `R1["has label"]`) and a description (by means of `R2["has description"]`).

(sec_items)=
### Items

The `short_key` of any items starts with "`I`" and ends with a sequence of number characters (maximum sequence length not yet specified). Optionally the second character is "`a`" which indicates that this item was generated automatically (see [below](sec_auto_gen_items)).

(Almost) All items are part of a taxonomy, i.e. a hierarchy of *"is-a"*-relations). This is expressed by the relations `R3["is_subclass_of"]` and `R4["is instance of"]`.


```{note}
Unlike in OWL (but like in Wikidata) an item can be an instance and a class at the same time. This allows to treat classes as "ordinary" items if necessary, e.g. use them directly in statements.
```


(sec_auto_gen_items)=
#### Automatically Generated Items

One consequence of expressing knowledge as a collection of triples is the necessity of auxiliary items. E.g. consider the equation {math}`y = \sin(x)` where `x, y, sin` can be assumed to be well defined items. Because the predicate must be a relation, it is not possible to relate these three items in one triple. The usual approach to deal with such situations is to introduce auxiliary items and more triples (see also [wikipedia on "reification"](https://en.wikipedia.org/wiki/Reification_(knowledge_representation))). One possible (fictional) triple representation of the above equation is

```
auxiliary_expr is_functioncall_of_type sin
auxiliary_expr has_arg x
y is_equal_to expr
```

One of the main goals of pyerk is to simplify the creation of triples which involves creating auxiliary items (such as evaluated expressions). This can be achieved by calling functions such as `pyerk.instance_of(...)`. A more sophisticated way is to overload the `__call__` method of entities.


(sec___call__mechanism)=
#### The `__call__` Method

The class `pyerk.Entity` implements the `__call__` method which formally makes all items and relations callable Python objects. However, by default no method `_custom_call` is implemented which





(sec_relations)=
### Relations

(sec_modules)=
### pyerk Modules and Packages

pyerk entities and statements are organized in pyerk *modules* (python files). Each module has to specify its own URI via the variable `__URI__`. The uri of an entity from that module is formed by `<module URI>#<entity short_key>`. Modules can be bundled together to form pyer *packages*. A pyerk package consits of a directory containing a file `erkpackage.toml` and at least one pyerk module.

Modules can depend on other modules. A usual pattern is the following:

```python
# in module control_theory1.py

import pyerk as p
mod = p.erkloader.load_mod_from_path("./math1.py", prefix="ma")
```

Here the variable `mod` is the module object (like from ordinary python import) and allows to access to the complete namespace of that module:
```python
# ...

A = p.instance_of(mod.I9904["matrix"])
```

The prefix `"ma"` can also be used to refer to that module like here
```python
# ...

res = A.ma__R8736__depends_polyonomially_on
```

Rationale: The attribute name `ma__R8736__depends_polyonomially_on` is handled as a string by Python (in the method `__getattr__`). While `mod.R8736` is the relation object we cannot use this syntax as attribute name.

See also {ref}`sec_keys`.
