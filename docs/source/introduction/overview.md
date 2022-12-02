(sec_intro_overview)=
# pyerk Overview


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
