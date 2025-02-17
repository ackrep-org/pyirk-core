# Entities

This section will explain how **Entities** in Pyirk work.
(Remember? The **Items** and **Relations** you can use in your **Statements**.)
But before that we should talk about **Keys**.

(sec_keys)=
## Keys, Labels and URIs in Pyirk

Sooner or later, you will need the reference your precious knowledge from somewhere else
in your code.
For this purpose, Pyirk has **Keys**.
The most prominent one is the so-called *short_key* (`entity.short_key`) this is a unique.
string whose leading character indicates the entity type
(called `EType` in the code), so far we have `I` for an **Item** and `R` for a
**Relation** and ends with a sequence of number characters (maximum sequence length not yet specified)
Furthermore, every **entity** has an uri (`entity.uri`).
It is recommended but not required that every entity has a label (by means of relation
`R1["has label"]`) and a description (by means of `R2["has description"]`).

For example, think of a **Relation** with the short key `"R1234"` and label `"is in special relation with"`.
To reference that, we can use:

- a) *short_key* like `"R1234"`
- b) name-labeled key like `"R1234__is_in_special_relation_with"` (consisting of a *short_key*,
  a delimiter (`__`) and the *label* but where all space spaces have been replaced by single underscores)
- c) prefixed short_key like `"mm__R1234"`
  - useful if multiple modules are loaded.
  - here the prefix `mm` refers to the (fictive) module `my_module` e.g. loaded with:
  ```python
  mod = p.irkloader.load_mod_from_path("./my_module.py", prefix="mm")
  ```
    - Note: In general it is recommended to use the same identifier for the variable name (here: `mod`) and the prefix-argument (here: `"mm"`).
      We use different identifiers here to document the technicalities.
- d) prefixed name-labeled key like `"mm__R1234__is_in_special_relation_with"` (combination of b) and c))
- e) index-labeled key like  `"R1234['is in special relation with']"`

**Why** are there these different possibilities to specify keys? Because in PyIRK we want to achieve the following goals:
- (1) Every entity should have a unique machine readable identifier.
- (2) The source code should be readable by humans.
- (3) The source code should be valid python code.

Goal (1) is achieved via URIs. The uri of each entity is composed of the URI of its defining module plus the short key of the entity. Goal (2) is achieved by adding the labels into the source code as strings or identifiers. This allows them to be checked for consistency. Goal (3) is achieved by using either index-labeled keys or name-labeled keys – depending what the context allows.


```{warning}
Not yet (fully) documented:
- keys and multilinguality
- URIs
- code example
```


```{tip}
Prefixed and name-labeled keys can optionally have a language indicator. Example: `"R1234__ist_in_spezieller_relation_mit__de"`.
The usage of these syntax variants depends on the context.
```
For more information see See also {ref}`sec_modules`.

### Key Numbers

The short key of entities consists of a leading letter usually followed by a number e.g. `"R1234"` for a relation and `"I5678"` for an item.
Exception: for automatically created items the second character is the letter `a`.
If you want to create entities and relations in a module the question arises: **Which numbers to take?** the answer is simple:
It does not really matter as long as the numbers are unique. There are two approaches:

- Manual enumeration like `"I1001"`, `"I1002"`, ...
  - Advantages:
    - Simple to use.
    - Similar entities have similar keys like `I38["non-negative integer"]` and `I39["positive integer"]`
  - Disadvantages:
    - Sooner or later there will be a situation where the order breaks because you want to create an entity which
    ontologically comes higher in the hierarchy (i.e. more abstract) and would deserve a lower number but all those
    numbers are already in use.
- Automatic generation of *random* keys
  - Command: `pyirk --load-mod my_module.py mm -nk 100`
    - Creates 100 keys for items and relations respectively (printed to stdout).
    - Loading the module (`my_module.py` in the example) ensures that no keys are output which are already used in the module.
  - Advantages:
    - Does not require manual book-keeping.
  - Disadvantages:
    - Might be confusing at the beginning.


```{tip}
A useful practice is to automatically create e.g. 100 keys and store them as a comment at the bottom of your module file.
Every used key is deleted from this comment section. If for some items consecutive numbering is desirable this can be done anyway.
If those 100 keys are used up (all lines deleted) you can generate the next ones.
```


```{tip}
See [Practically working with keys](sec_practical_work_with_keys) for hints on who to deal with such lengthy keys conveniently.
```

(sec_items)=
## Items (Python Subclass of `core.Entity`)

The `short_key` of any items starts with "`I`" . Optionally the second character is
"`a`" which indicates that this item was generated automatically
(see [below](sec_auto_gen_items)).

(Almost) all items are part of a taxonomy, i.e. a hierarchy of *"is-a"*-relations.
This is expressed by the relations `R3["is_subclass_of"]` and `R4["is instance of"]`.

```{error}
Add code example.
```

```{hint}
Unlike in OWL (but like in Wikidata) an item can be an instance and a class at the same time. This allows to treat classes as "ordinary" items if necessary, e.g. use them directly in statements.
```

(sec_auto_gen_items)=
### Automatically Generated Items

One consequence of expressing knowledge as a collection of triples is the necessity of
auxiliary items. E.g. consider the equation {math}`y = \sin(x)` where `x, y, sin` can
be assumed to be well defined items. Because the predicate must be a relation, it is
not possible to relate these three items in one triple.
The usual approach to deal with such situations is to introduce auxiliary items and
more triples (see also [wikipedia on "reification"](https://en.wikipedia.org/wiki/Reification_(knowledge_representation))).
One possible (fictional) triple representation of the above equation is

```
auxiliary_expr is_function_call_of_type sin
auxiliary_expr has_arg x
y is_equal_to expr
```

One of the main goals of Pyirk is to simplify the creation of triples which involves
creating auxiliary items (such as evaluated expressions). This can be achieved by calling functions such as `pyirk.instance_of(...)`.

```{error}
Add code example.
```

A more sophisticated way is to overload the `__call__` method of entities.


(sec___call__mechanism)=
### The `__call__`-Method

The class `pyirk.Entity` implements the `__call__` method which formally makes all items and relations callable Python objects. However, by default no method `_custom_call` is implemented which results in an exception. Associating a `_custom_call` method and thus truly make an item callable can be achieved by

- explicitly adding the method, like e.g. in `I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call")`
- creating an item which is a subclass (`R3`) or instance (`R4`) of a method which already has a `_custom_call` method, see `core.Entity._perform_inheritance` and `core.Entity._perform_instantiation` for details.


(sec___adding_convenience_methods)=
### Adding Convenience Methods

The method `core.Entity.add_method(...)` can be used to add arbitrary methods to items (which then can be inherited by other items). Example: see how the function `builtin_entities.get_arguments` is attached to every result of `builtin_entities.create_evaluated_mapping` (which itself is used as `_custom_call` method).


(sec_relations)=
## Relations (`core.Relation`, subclass of `core.Entity`)

The `.short_key` of any relation starts with `R`.
From a graph perspective the relation defines the type of the edge between two nodes
while nodes are typically `Item`-instances.
The *predicate* part of a semantic triple must always be a (python) instance of
`Core.Relation`.
In general they can occur as *subject* or *object* as well.


(ssec_common_relations)=
### Common relations

What follows is a short overview about the most common relations that pyirk ships with (see more in the
{py:mod}`pyirk.builtin_entities` module.)
You can of course always create your own ones.

* {py:obj}`pyirk.builtin_entities.R1`: `has_label`
* {py:obj}`pyirk.builtin_entities.R3`: `is_subclass_of`
* {py:obj}`pyirk.builtin_entities.R4`: `is_instance_of`
* {py:obj}`pyirk.builtin_entities.R5`: `is_part_of`
* {py:obj}`pyirk.builtin_entities.R15`: `is_element_of`
* {py:obj}`pyirk.builtin_entities.R16`: `has_property`
* {py:obj}`pyirk.builtin_entities.R68`: `is_inverse_of`

```{hint}
Do not be afraid: There is no need to remember all of these, the syntax completion of your IDE will help
you here. See also notes on *irk-fzf* in the section [Practically working with keys](sec_practical_work_with_keys).
```
