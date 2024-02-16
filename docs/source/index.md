# Python Based Imperative Representation of Knowledge (Pyirk)

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

## Getting Started

The best way to get started with Pyirk is to read about the basics in the user 
documentation and to have a look at the first example to see how the design principles
translate into actual code.



(sec_visualization)=
## Visualization

Currently there is some basic visualization support via the command line. To visualize
your a module (including its relations to the builtin_entities) you can use a command
like

```
pyirk --load-mod demo-module.py demo -vis __all__
```

### Interactive Usage

To open an IPython shell with a loaded module run e.g.

```
pyirk -i -l control_theory1.py ct
```

Then, you have `ct` as variable in your namespace and can e.g. run `print(ct.I5167.R1)`.

(The above command assumes that the file `control_theory1.py` is in your current working
directory.)


## Developer Documentation
Information regarding actively contributing to pyirk.
- [Overview](devdoc/overview)


## Full Table of Contents
```{toctree}
:maxdepth: 2

intro/index
userdoc/index
devdoc/overview
apidocs/index
```
