(sec_miscellaneous)=
# Miscellaneous topics

This section contains examples how to retrieve certain internal information which might be useful for experimenting and development

## Retrieve all statements for a certain relation

- Start pyirk in interactive mode: `pyirk -i`.  To load the [OCSE](https://github.com/ackrep-org/ocse) as example content you can use `pyirk -l control_theory1.py ct -i` from its root directory.

```
p.ds.relation_statements[p.R64.uri]
```

- Example Result:

```
[S5660(<Item Ia1806["scp__setting"]>, <Relation R64["has scope type"]>, 'SETTING'),
 S7193(<Item Ia2780["scp__premise"]>, <Relation R64["has scope type"]>, 'PREMISE'),
 S4607(<Item Ia9662["scp__assertion"]>, <Relation R64["has scope type"]>, 'ASSERTION'),
 S3253(<Item Ia9112["scp__setting"]>, <Relation R64["has scope type"]>, 'SETTING'),
 S9836(<Item Ia1367["scp__premise"]>, <Relation R64["has scope type"]>, 'PREMISE'),
 S8246(<Item Ia2746["scp__assertion"]>, <Relation R64["has scope type"]>, 'ASSERTION'),
 ...
]
```

## Visualize subclasses of `ScopingCM`


- Start pyirk in interactive mode: `pyirk -i`

```
p.aux.print_inheritance_tree(p.ScopingCM)
```

- Result based on version 0.13.2:

```
ScopingCM
└── AbstractMathRelatedScopeCM
    ├── ConditionSubScopeCM
        └── QuantifiedSubScopeCM
    ├── _proposition__CM
    └── _rule__CM
        └── RulePremiseSubScopeCM
```



(sec_practical_work_with_keys)=
## Practically working with keys

To learn about the different kinds of keys in PyIRK see section [Keys](sec_keys).

With a growing module it becomes infeasible to memorize the keys like `R1234['is in special relation with']` and it is also time-consuming
to type. Solutions:
  - Search in existing code and use copy-paste.
    - Advantage:
      - Simple.
      - Acceptably convenient for smaller modules or small editing tasks.
    - Disadvantage:
      - Too much effort for larger editing jobs.
  - Use fuzzy **autocompletion** via the VS Code extension [irk-fzf](https://github.com/ackrep-org/irk-fzf/releases):
    - Install the extension from the `.vsix`-File (see [README.md](https://github.com/ackrep-org/irk-fzf/blob/main/README.md))
    - Use `pyirk --load-mod my_mod.py mm -ac` to create a file called `.ac_candidates.txt`.
    - The extension uses the entries in this file to offer auto-complete suggestions when the `erk-fzf.search` command is triggered (either via the VS code command pallette or via a manually assigned keyboard shortcut (recommended, see [README.md](https://github.com/ackrep-org/irk-fzf/blob/main/README.md)).
    - The command `erk-fzf.search` performs a fuzzy search using the string left of the cursor (and then the user input).
    It displays fuzzy-matching lines from `.ac_candidates.txt`. It searches short_keys, labels and descriptions.


## How to perform a SPARQL query


### Simple Query

Example from `test_core.py:Test_04_Core.test_c020__sparql_query2`

```python

import pyirk as p

qsrc = f"""
PREFIX : <{p.rdfstack.IRK_URI}>
PREFIX ct: <{mod1.__URI__}#>
SELECT ?s ?o
WHERE {{
    ?s :R16 ct:I7864.
}}
"""

res = p.rdfstack.perform_sparql_query(qsrc)
```


### Query Involving Qualifiers

Example from `test_core.py:Test_04_Core.test_c040__sparql_queries_with_qualifiers`

```python

import pyirk as p
ag = p.irkloader.load_mod_from_path(TEST_DATA_PATH3, prefix="ag")

qsrc = f"""
  PREFIX : <{p.rdfstack.IRK_URI}>
  PREFIX qf: <{p.rdfstack.IRK_QF_URI}>
  PREFIX ag: <{ag.__URI__}#>
  PREFIX ag_s: <{ag.__URI__}/STATEMENTS#>
  PREFIX ag_p: <{ag.__URI__}/PREDICATES#>
  SELECT ?emp ?start_time ?end_time
  WHERE {{
      ag:I2746 ag_s:R1833 ?stm.
      ?stm ag_p:R1833 ?emp.
      ?stm qf:R48 ?start_time.
      ?stm qf:R49 ?end_time.
  }}
"""

  # due to the keyword arguments it is necessary to call this explicitly
  p.ds.rdfgraph = p.rdfstack.create_rdf_triples(add_qualifiers=True, modfilter=ag.__URI__)
  res1 = p.rdfstack.perform_sparql_query(qsrc)

  self.assertIn([ag.I9942["Stanford University"], "1964", "1971"], res1)
  self.assertIn([ag.I7301["ETH Zürich"], "1973", "1997"], res1)

```