# Introductory Example

In this section, we want to us Pyirk to encode so knowledge about trains,
because I like trains.

## The fundamentals

To make things easier late ron, we import pyirk under the alias `p` tell pyirk under 
which `URI` we want to store our knowledge:

```{eval-rst}
.. literalinclude:: trains.py
    :language: python
    :linenos:
    :lines: 1-6
```

For now, just see this as boilerplate code, the details can be found [here](URI).

As Wikidata says, trains are a mode of transport, which means we will start
with that by creating an {py:class}`pyirk.Item`:

```{eval-rst}
.. literalinclude:: trains.py
    :language: python
    :linenos:
    :lines: 11-14
```

Conveniently, pyirks directly allows us to provide some more information about this new 
item by making the statement that our new item is connected to the **Literal** 
`mode of transport` in terms of the relation `has_label` via a kwarg.
In the same manner, we can also provide an detailed description 
(via `R2_has_description`).



```{eval-rst}
.. literalinclude:: trains.py
    :language: python
    :linenos:
    :lines: 16-20
```
```{hint}
The actual names of the items (`I1` and `I2`) do not matter that much, for this example we will just
assign them growing numbers.
```
