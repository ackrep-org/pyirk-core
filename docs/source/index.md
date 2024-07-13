# Python Based Imperative Representation of Knowledge (Pyirk)

```{toctree}
:maxdepth: 1
:hidden:

intro/index
userdoc/index
apidocs/index
devdoc/overview
```

Pyirk is an experimental framework for *imperative* knowledge representation. It is
basically a collection of classes and functions which facilitates the construction of
and the interaction with knowledge graphs.

The framework is structurally inspired by

- [wikidata](https://wikidata.org/)
    - allow for statements about statements by means of *qualifiers*
    - provide an RDF export and SPARQL interface
- [ORKG](https://orkg.org)
    - model the *content* of scientific contributions, instead of mostly the metadata
- [Suggested Upper Merged Ontology (SUMO)](https://www.ontologyportal.org/)
    - modelling of higher order statements

However, pyirk is a pure python framework and aims to be intuitively usable without
prior familiarity with knowledge engineering techniques such as OWL, but instead
requiring only some understanding of programming.


## Motivation

Humankind is faced with an growing amount of knowledge available (in principle) and this
growth is accelerating by itself. However, this knowledge often cannot be applied to
solve actual problems because it is stored somewhere out of reach and often also
distributed over several documents which often are not entirely consistent.
While library catalogues, full text search engines and similar facilities help a lot in
the procurement of relevant knowledge, they underlie some fundamental limitations. In
2001 the term [Semantic Web](https://en.wikipedia.org/wiki/Semantic_Web) was introduced
to refer to (existing and future) technologies which allow a machine – in some sense –
to *understand* information instead of just storing and processing it. However, even
after more than two decades, apart from some niche fields such **semantic technologies**
yet have not had a mayor impact on science and societies, especially if compared with
technologies such as machine learning.
One reason is that the available technologies like OWL (based on so
called [description logic](https://en.wikipedia.org/wiki/description_logic)) are widely
considered to be hard to grasp by non-specialists. The current mainstream approach of
formal knowledge representation thus consists the cooperation between domain-experts and
knowledge engineers to create useful knowledge bases for specific domains.
In contrast, Pyirk aims to enable domain-experts themselves to create such knowledge
bases, by providing an interface in the widespread Python programming language, which
poses a significantly lower barrier compared to the special purpose OWL.
Pyirk also aims to allow for much
greater [expressive power](https://en.wikipedia.org/wiki/Expressive_power_(computer_science)) (
e.g. allowing higher order logic statements) than most other approaches, despite the
computational consequences.


## Status

The whole Pyirk project and even much more this documentation is currently still under
development and should be considered as incomplete and only partially functional.

## Where to start

The best way to get started with Pyirk is to follow the [Beginners Guide](sec_intro) which will introduce the
basics and shows how the design principles translate into actual code in a short example.
If you are more curious about how a certain task can be accomplished or simplified, have a look at
the [User Guide](sec_userdoc).
Certainly, you can also have a look at how exactly a certain function should be called in the API reference.
Last but not least, if you are curious how the internals of pyirk work or how you can contribute to it have a look at
the [Developer Guide](sec_devdoc).







