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