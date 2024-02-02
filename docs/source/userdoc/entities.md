# Entities

This section will explain how **Entities** in Pyirk work. 
(Remember? Those things you can use in your **Statements**.) 
But before that we should talk about *Keys*.

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

For example, think of a **Relation** with the short key `"R1234"` and label `"my_relation"`.
To reference that, we can use:

- a) *short_key* like `"R1234"`
- b) name-labeled key like `"R1234__my_relation"` (consisting of a *short_key*, 
  a delimiter (`__`) and a *label*)
- c) prefixed short_key like `"bi__R1234"` (here the prefix `bi` refers to the module `builtin_entities`)
- d) prefixed name-labeled key like `"bi__R1234__my_relation"`
- e) index-labeled key like  `"R1234['my relation']"`

```{error}
Add code example.
```

```{tip}
Prefixed and name-labeled keys can optionally have a language indicator. Examples: ``"bi__R1__de"`` or `"R1__has_label__fr"`.
The usage of these syntax variants depends on the context.
```
For more information see See also {ref}`sec_modules`.


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
