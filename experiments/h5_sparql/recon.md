# H5 SPARQL Recon (Stufe 0)

Klassifikation der 8 Zebra-Regeln mit `R63__has_SPARQL_source` auf Basis
der **rdflib-Algebra** (keine Regex auf Quelltext). Erzeugt durch
`experiments/h5_sparql/recon_dump.py`. Volle pprintAlgebra-Dumps in
`algebra_dumps.txt`.

## Uebersicht

| Regel | Klasse | #Tripel | #Filter | Minus | NotExists | Literale |
|-------|--------|---------|---------|-------|-----------|----------|
| I710 | `bgp_inequality` | 3 | 1 | nein | nein | bool=True |
| I725 | `bgp_pure` | 2 | 0 | nein | nein | — |
| I730 | `bgp_pure` | 4 | 0 | nein | nein | bool=True |
| I740 | `bgp_inequality` | 8 | 1 | nein | nein | bool=True; bool=True |
| I741 | `bgp_negation` | 9 | 1 | ja | nein | bool=True; bool=True; bool=False; bool=False; bool=True |
| I792 | `bgp_pure` | 7 | 0 | nein | nein | bool=False; bool=True |
| I798 | `bgp_pure` | 4 | 0 | nein | nein | bool=True |
| I803 | `bgp_inequality` | 8 | 1 | nein | nein | bool=False; bool=True; bool=False |

## I710 — `bgp_inequality`

**Klassifikations-Begruendung (aus Algebra):**
- 1 reine != Filter

- Tripel-Anzahl im BGP: **3**
- Filter (Top-Level): **1**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `True` (bool)

### BGP-Tripel
```
?rel1  R2850  True^^bool
?p1  ?rel1  ?some_itm
?p2  ?rel1  ?some_itm
```

### SPARQL-Quelltext
```sparql
WHERE {
        ?p1 ?rel1 ?some_itm.
        ?p2 ?rel1 ?some_itm.

        ?rel1 zb:R2850 true.      # R2850__is_functional_activity
        FILTER (?p1 != ?p2)
        }
```

## I725 — `bgp_pure`

**Klassifikations-Begruendung (aus Algebra):**
- nur BGP

- Tripel-Anzahl im BGP: **2**
- Filter (Top-Level): **0**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten: keine

### BGP-Tripel
```
?rel1  R68  ?rel2
?itm1  ?rel1  ?itm2
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?itm1 ?rel1 ?itm2.        # R3606["lives next to"]

            # ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1 :R68 ?rel2.        # R68__is_inverse_of
        }
```

## I730 — `bgp_pure`

**Klassifikations-Begruendung (aus Algebra):**
- nur BGP

- Tripel-Anzahl im BGP: **4**
- Filter (Top-Level): **0**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `True` (bool)

### BGP-Tripel
```
?rel1  R2850  True^^bool
?rel1  R43  ?rel2
?h1  ?rel1  ?itm1
?h1  R3606  ?h2
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?h1 zb:R3606 ?h2.        # R3606["lives next to"]

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1 :R43 ?rel2.        # R43__is_opposite_of

            ?h1 ?rel1 ?itm1.
        }
```

## I740 — `bgp_inequality`

**Klassifikations-Begruendung (aus Algebra):**
- 1 reine != Filter

- Tripel-Anzahl im BGP: **8**
- Filter (Top-Level): **1**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `True` (bool)
  - `True` (bool)

### BGP-Tripel
```
?rel1  R2850  True^^bool
?rel2  R2850  True^^bool
?rel1  R43  ?rel1_not
?rel2  R43  ?rel2_not
?h1  ?rel1  ?itm1
?h1  ?rel2  ?itm2
?h2  ?rel1  ?itm3
?h2  ?rel2_not  ?itm2
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?h1 ?rel1 ?itm1.          # e.g. h1 owns dog
            ?h1 ?rel2 ?itm2.          # e.g. h1 drinks milk
            ?h2 ?rel1 ?itm3.          # e.g. h2 owns zebra

            FILTER (?rel1 != ?rel2)
            FILTER (?itm1 != ?itm2)
            FILTER (?itm1 != ?itm3)
            FILTER (?h1 != ?h2)
            FILTER (?itm2 != ?itm3)

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel2 zb:R2850 true.     # R2850__is_functional_activity

            ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of
            ?rel2 :R43 ?rel2_not.        # R43__is_opposite_of

            ?h2 ?rel2_not ?itm2.

            # prevent the addition of already known relations
            # MINUS { ?h2 ?rel1_not ?itm1.}
        }
```

## I741 — `bgp_negation`

**Klassifikations-Begruendung (aus Algebra):**
- Minus-Subpattern vorhanden

- Tripel-Anzahl im BGP: **9**
- Filter (Top-Level): **1**
- Minus-Subpattern: **ja**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `True` (bool)
  - `True` (bool)
  - `False` (bool)
  - `False` (bool)
  - `True` (bool)

### BGP-Tripel
```
?rel1  R2850  True^^bool
?rel2  R2850  True^^bool
?itm1a  R57  False^^bool
?itm1b  R57  False^^bool
?h1  ?rel1  ?itm1a
?h1  ?rel2  ?itm1b
?rel2  R43  ?rel2_not
?h2  ?rel1  ?itm2
?itm2  R57  True^^bool
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?h1 ?rel1 ?itm1a.          # e.g. h1 owns dog
            ?h1 ?rel2 ?itm1b.          # e.g. h1 drinks milk
            ?h2 ?rel1 ?itm2.          # e.g. h2 owns zebra

            ?itm1a :R57 false.        # itm1 is no placeholder
            ?itm1b :R57 false.        # itm1 is no placeholder
            # ?itm2 :R57 false.        # itm1 is no placeholder

            FILTER (?rel1 != ?rel2)
            FILTER (?itm1a != ?itm1b)
            FILTER (?itm1a != ?itm2)
            FILTER (?h1 != ?h2)
            FILTER (?itm1b != ?itm2)

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel2 zb:R2850 true.     # R2850__is_functional_activity

            # ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of
            ?rel2 :R43 ?rel2_not.        # R43__is_opposite_of

            # prevent the addition of statements on placeholder persons (not sure yet)

            # MINUS { ?h1 :R57 true.}
            MINUS { ?itm2 :R57 true.}
        }
```

## I792 — `bgp_pure`

**Klassifikations-Begruendung (aus Algebra):**
- nur BGP

- Tripel-Anzahl im BGP: **7**
- Filter (Top-Level): **0**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `False` (bool)
  - `True` (bool)

### BGP-Tripel
```
?itm1a  R57  False^^bool
?h1  ?rel1  ?itm1a
?rel1  R2850  True^^bool
?h1  R4  I7435
?h2  R4  I7435
?h2  ?rel1_not  ?itm1a
?rel1  R43  ?rel1_not
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?h1 ?rel1 ?itm1a.          # e.g. h1 owns dog
            ?h2 ?rel1_not ?itm1a.      # e.g. h2 not_owns dog

            ?h1 :R4 zb:I7435.          # h1 is human
            ?h2 :R4 zb:I7435.          # h2 is human

            ?itm1a :R57 false.        # itm1 is no placeholder
            ?rel1 zb:R2850 true.      # R2850__is_functional_activity
            ?rel1 :R43 ?rel1_not.        # R43__is_opposite_of

        }
```

## I798 — `bgp_pure`

**Klassifikations-Begruendung (aus Algebra):**
- nur BGP

- Tripel-Anzahl im BGP: **4**
- Filter (Top-Level): **0**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `True` (bool)

### BGP-Tripel
```
?rel1  R2850  True^^bool
?rel1  R43  ?rel2
?p1  ?rel1  ?itm1
?p1  R50  ?p2
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?p1 :R50 ?p2.        # R50["is different from"]

            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1 :R43 ?rel2.        # R43__is_opposite_of

            ?p1 ?rel1 ?itm1.
        }
```

## I803 — `bgp_inequality`

**Klassifikations-Begruendung (aus Algebra):**
- 1 reine != Filter

- Tripel-Anzahl im BGP: **8**
- Filter (Top-Level): **1**
- Minus-Subpattern: **nein**
- NotExists-Filter: **nein**
- Literal-Konstanten:
  - `False` (bool)
  - `True` (bool)
  - `False` (bool)

### BGP-Tripel
```
?itm1  R57  False^^bool
?rel1  R2850  True^^bool
?itm2  R57  False^^bool
?p1  ?rel1  ?itm1
?itm1  R4  ?type_of_itm1
?rel1_not  R43  ?rel1
?tuple  R39  ?itm2
?type_of_itm1  R51  ?tuple
```

### SPARQL-Quelltext
```sparql
WHERE {
            ?rel1 zb:R2850 true.     # R2850__is_functional_activity
            ?rel1_not :R43 ?rel1.        # R43__is_opposite_of
            ?p1 ?rel1 ?itm1.
            ?itm1 :R4 ?type_of_itm1.   # R4__is_instance_of
            ?type_of_itm1 :R51 ?tuple.  # R51__instances_are_from
            ?tuple :R39 ?itm2.           # R39__has_element
            ?itm1 :R57 false.          # R57__is_placeholder
            ?itm2 :R57 false.

            FILTER (?itm1 != ?itm2)

        }
```

## Sanity der rdflib-Klassifikation

Erwartungen aus `docs/design/h5_extension_report.md` §5.1 (I798 = 4 Tripel BGP + Literal-Konstante) und der Aufgabenstellung selbst.

| Regel | erwartet | erkannt | Match |
|-------|----------|---------|-------|
| I798 | `bgp_pure` | `bgp_pure` | ja |
| I710 | `bgp_inequality` | `bgp_inequality` | ja |
| I741 | `bgp_negation` | `bgp_negation` | ja |

## I725 — Native-Verhalten auf zebra-only-KB

`SUMMARY: outcome=crash exc=AssertionError file=ruleengine.py line=771 func=_process_result_map`

Letzter Traceback-Frame:
```
    res = self._process_result_map(result_maps)
  File "src/pyirk/ruleengine.py", line 771, in _process_result_map
    assert isinstance(new_subj, core.Entity)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```

**Fazit:** Wie in `docs/design/h5_extension_report.md` §5.2 dokumentiert scheitert I725 nativ mit `AssertionError` (`isinstance(new_subj, core.Entity)` in `ruleengine.py:_process_result_map`). I725's SPARQL-Praemisse bindet Objektpositionen, die nativ zu Literalen aufloesen koennen. Da die native Engine das Referenz-Orakel ist und auf dieser KB kein wohldefiniertes Aequivalenzziel existiert, bleibt I725 aus dem Gate-Regelsatz (Stufe 1).

