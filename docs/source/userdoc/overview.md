(sec_userdoc_overview)=
# pyerk User Documentation Overview


## Keys in Pyerk

In Pyerk there are the following kinds of keys:
- a) short_key like `R1234`
- b) name-labeled key like `R1234__my_relation` (consisting of a short_key, a delimiter (`__`) and a label)
- c) prefixed short_key like `bi__R1234`
- d) prefixed name-labeled key like `bi__R1234__my_relation`
- e) index-labeld key like  `R1234["my relation"]`

Also, the leading character indicates the entity type (called `EType` in the code): `I` → item, `R` → relation.

The usage of these variants notations depens on the context.

% TODO: add example code.


## Visualization

Currently there is some basic visualization support via the command line. To visualize your a module (including its relations to the builtin_entities) you can use a command like

```
pyerk --load-mod demo-module.py demo -vis __all__
```


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

This results in the triple: `(I2746, R1833, I9942)`. In pyerk such triples are modeled as instances of class `RelationEdge`; each such instance represents an edge in the knowledge graph, where the subject and object are the corresponding nodes and each such edge has a lable (the relation type) and optionally other information attachend to it.


However, in many cases more complexity is needed. To express that Kalman worked at Stanford between 1964 and 1971, we can exploit that `RelationEdge`-instances can themselves be use as subject of other triples, by means of so called qualifiers:
```python
start_time = p.QualifierFactory(R4156["has start time"])
end_time = p.QualifierFactory(R4698["has end time"])

I2746["Rudolf Kalman"].set_relation(
    R1833["has employer"], I9942["Stanford University"], qualifiers=[start_time("1964"), end_time("1971")]
)
#.
```

Here `start_time` and `end_time` are instances of the class `QualifierFactory`. If such an instance is called, it returns an instance of class `RawQualifier` which is basically a yet incomplete triple where only the predicate and the object is fixed. The subject of this triple will be formed by the main statement itself (modeled by an instance of `RelationEdge`).

Thus the above code creates three `RelationEdge` instances here simplified:

```
RE(2746, R1833, I9942) # the main statement, now referenced as rel_edge1
RE(rel_edge1, R4156, "1964")
RE(rel_edge1, R4698, "1971")
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


