(sec_Statements)=
# Statements

Instances of this class model semantic triples (subject, predicate, object) and
corresponding [qualifiers](sec_qualifiers). Every edge in the knowledge graph
corresponds to a statement instance.

```{note}
Note: For technical reasons for every `Statement` instance there exits a dual 
`Statement` instance. For most situations this does not matter, though.
```

The whole knowledge graph is a collection of Entities (Items, Relation, Literals) and 
Statements. Roughly speaking, the collection of Entities defines what exists (in the 
respective universe of discourse) while the collection of Statements defines how these 
things are related. Because flat subject-predicate-object triples have very limited
expressivity it is possible to "make statements about statements", i.e. use
a `Statement` instance as subject another triple.
This [Wikidata](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial#Qualifiers)
-inspired mechanism is called [qualifiers](sec_qualifiers) (see next page).
