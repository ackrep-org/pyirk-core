# Encode a theorem or a definition

In this how to we will show you how to encode a theorem (this concept will also work for many other knowledge
artifacts like definitions).
To do so, we will make use of pyirk *scopes* and pythons context managers.
The resulting script can be found [here](theorem.py).


## The example theorem

As an example, we want to encode a simplified version of the Pythagorean theorem, which reads:
> Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and {math}`(l_a, l_b, l_c)` the
> respective lengths. If the angle between a and b is a right angle then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds.

As you can see, the theorem consists of several "semantic parts", which in the context of Pyirk are
called *scopes*. In particular we have the three following scopes:

- *setting*: "Let {math}`(a, b, c)` be the sides of a triangle, ordered from shortest to longest, and (la, lb, lc) the
  respective lengths."
- *premise*: "If the angle between a and b is a rect angle"
- *assertion*: "then the equation {math}`l_c^2 = l_a^2 + l_b^2` holds."

In the following, we will see how this structure can be exploited to encode the theorem.


## Dependencies and bootstrap

The example reuses geometry items from the [OCSE](https://github.com/ackrep-org/ocse) (planar triangle,
polygon sides ordered by length, has length, ...). We load the OCSE math module via its URI; pyirk
resolves the URI through the ``[package.ocse]`` entry in the user configuration file.

```{eval-rst}
.. literalinclude:: theorem.py
    :language: python
    :linenos:
    :lines: 10-18
```


## The theorem item

As usual, we start by creating a "blank" item to encode the theorem.
Note however, that we make it an instance of {py:class}`I15["implication proposition"] <pyirk.builtin_entities.I15>`,
which is one of several mathematical propositions are already included in pyirk.
```{eval-rst}
.. literalinclude:: theorem.py
    :language: python
    :linenos:
    :lines: 47-50
```


## Local additions for missing concepts

OCSE does not yet provide items for angle quantities or right angles, so we add them locally inside
this example. Using a shared value type ``angle (quantity)`` (a subclass of ``real number``) makes
the operator ``angle`` and the named constant ``right angle`` explicitly typed as the same kind of
quantity, rather than only sharing ``real number`` by coincidence.
```{eval-rst}
.. literalinclude:: theorem.py
    :language: python
    :linenos:
    :lines: 26-43
```


## Defining setting, premise and assertion

With our theorem `I5000` being an implication, it possesses a `scope()` method
that returns a context manager that we can use in a `with` statement to define the setting:
```{eval-rst}
.. literalinclude:: theorem.py
    :language: python
    :linenos:
    :lines: 52-64
```
Next, we encode the premise:
```{eval-rst}
.. literalinclude:: theorem.py
    :language: python
    :linenos:
    :lines: 66-68
```
At last, we  are able to state the assertion:
```{eval-rst}
.. literalinclude:: theorem.py
    :language: python
    :linenos:
    :lines: 70-74
```
