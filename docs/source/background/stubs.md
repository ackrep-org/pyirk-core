(sec_stubs)=
# Stubs 

`I50["Stub"]`, `I000["some arbitrary label"]` and `R000["also"]`

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
