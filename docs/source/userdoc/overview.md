(sec_userdoc_overview)=
# pyerk User Documentation Overview


In Pyerk there are the following kinds of keys:
- a) short_key like `R1234`
- b) name-labeled key like `R1234__my_relation` (consisting of a short_key, a delimiter (`__`) and a label)
- c) prefixed short_key like `bi__R1234`
- d) prefixed name-labeled key like `bi__R1234__my_relation`
- e) index-labeld key like  `R1234["my relation"]`

Also, the leading character indicates the entity type (called `EType` in the code): `I` → item, `R` → relation.

The usage of these variants notations depens on the context.

% TODO: add example code.
