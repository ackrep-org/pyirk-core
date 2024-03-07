# Basic Patterns of Knowledge Representation

This section explains the basic patterns for Knowledge Representation in Pyirk

## Knowledge Graphs

Pyirk stores knowledge inside a knowledge graph.
As every mathematical graph, it consists of *nodes* that are connected by *edges*.
Roughly speaking, the nodes contain the facts and the edges encode how these
facts are related to each other.
However, to sustain the impression that Pyirk is indeed a serious toolbox, we work with
**Items** and **Relations** (inspired by Wikidata).
For the following, just assume that **Items** and **Relations** are fancy names for
nodes and edges.

## Semantic Triples
In Representation Theory (*link*), the concept of a *Semantic Triple*, consisting of

- Subject,
- Predicate and
- Object

is used to encode knowledge. For example: *Pythagoras* (Subj) *was a* (Predicate)
*Scientist* (Object).
As one can see, this concept works quite nicely in connection with knowledge graphs
where a *Semantic Triple* connects two nodes (subject and object) using an edge
(the predicate).
Consequently, in Pyirk-lingo a *Semantic Triple* typically connects two **Items** using
a **Relation** and is called a **Statement**.
Thus, **Items** are  mostly associated with Subjects or Objects and **Relations** with
Predicates.
One more thing: To save some precious bytes, when talking about cases where either an
**Item** or a **Relations** can be used, we use the word **Entity**.

## Literals

At some point in your knowledge representation workflow you may actually want to encode
some data, for example a name or date of birth.
For these *atomic* bits of knowledge Pyirk uses **Literals**.


## Summary

Alright, what follows is a the detailed summary of how all these classes work together:

We have **Statements**, those consist of *subject-predicate-object*-triples. In Detail,

- *subjects*: can be any **Entity** or **Statement**,
- *predicates*: is always a **Relation**,
- *objects*: can be any **Entity** or **Literal**.

As you can see, we sneaked in **Statements** for the *subject*, so you can make statements
about statements. Quite nice, heh?
