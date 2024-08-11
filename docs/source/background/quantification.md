(sec_quantification)=
# Universal and Existential Quantification

Background, see <https://en.wikipedia.org/wiki/Quantifier_(logic)>.

> commonly used quantifiers are ∀ (`$\forall$`) and ∃ (`$\exists$`).

They are also called *universal quantifier* and *existential quantifier*. In Pyirk they can be expressed via

- [Qualifiers](sec_qualifiers). In particular (defined in module `builtin_entities`):
    - `univ_quant = QualifierFactory(R44["is universally quantified"])`
        - usage (in OCSE): `cm.new_rel(cm.z, p.R15["is element of"], cm.HP, qualifiers=p.univ_quant(True))`
    - `exis_quant = QualifierFactory(R66["is existentially quantified"])`
        - usage (in OCSE): `cm.new_var(y=p.instance_of(p.I37["integer number"], qualifiers=[p.exis_quant(True)]))`
- (Sub)scopes:
    ```python
    # excerpt from test_core.py
    with I7324["definition of something"].scope("premise") as cm:
                with cm.universally_quantified() as cm2:
                    cm2.add_condition_statement(cm.x, p.R15["is element of"], my_set)
    # ...
    with I7324["definition of something"].scope("assertion") as cm:
                # also pointless direct meaning, only to test contexts
                with cm.existentially_quantified() as cm2:
                    z = cm2.new_condition_var(z=p.instance_of(p.I39["positive integer"]))
    ```


```{warning}
Despite having similar phonetics (and spelling) quantifiers (logic operators) and qualifiers (knowledge modeling technique, in triple-based knowledge graphs) are totally different concepts. However, qualifiers can (among many other use cases) be used to model universal or existential quantification of a statement.
```
