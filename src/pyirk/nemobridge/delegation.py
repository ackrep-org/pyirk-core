"""
pyirk.nemobridge.delegation — Hilfsfunktionen für den PYIRK_NEMO_DELEGATION-Pfad.

Wird von ruleengine.apply_semantic_rules() aufgerufen, wenn das Feature-Flag
PYIRK_NEMO_DELEGATION gesetzt ist.

Stand (Phase 2.1 — Gate-1/Gate-3-Fix):
  - _nemo_available(), _split_rules_by_nemo_delegation() unverändert.
  - _apply_via_nemo() führt Export → RLS-Codegen → nmo-Run → CSV→Statement-
    Mapping aus. Rückgabewert: Anzahl neu eingefügter Statements.
  - Ternäres ``output_fact.csv`` (subj_uri, pred_uri, obj_uri) — Auflösung
    jeder Spalte direkt per ``ds.get_entity_by_uri``. Kein short_key-Pfad
    mehr → kollisionsfest (Gate 1).
  - V3: Vor ``set_relation`` ``omit_if_existing``-Check gegen DataStore.
  - Gate-3-Fix (Phase 2.1): zusätzlich lokales ``inserted``-Set in
    ``_materialize_tuples``; fängt Intra-Call-Duplikate, die Nemo bei
    Mehrfach-Ableitung desselben Tupels liefert und die der Stand-zu-
    Loop-Beginn-Check nicht sieht.
  - mod_context_uri über ``core.uri_context(...)`` (V5).
  - V1 (Qualifier-Delegation) weiterhin vertagt — ``_apply_qualifiers`` no-op.

Bekannte Limitation:
  Rückkopplung Nemo↔Python erfolgt über den V4-Loop in
  ``ruleengine.apply_semantic_rules`` (nicht hier).
"""

import ast
import csv
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


# Mirror of ``exporter.LITERAL_PREFIX``. Imported lazily inside the helper to
# avoid a hard import-time dependency between the two modules.
_LITERAL_PREFIX = "LIT:"


def _decode_object_cell(ds, obj_cell):
    """Return the Python object the Nemo cell ``obj_cell`` refers to.

    Two branches:
      * URI cell → ``ds.get_entity_by_uri`` (Item or Relation).
      * ``LIT:<repr>`` cell → decode via :func:`ast.literal_eval` so a
        delegated rule can produce literal-objects (e.g. ``True``, ``1``,
        ``"hello"``).  The prefix matches :func:`exporter.encode_literal`.

    Raises ``UnknownURIError`` (entity branch) or ``ValueError`` (literal
    branch) on failure — both are caught by the caller, which skips the
    triple and logs at DEBUG.
    """
    if isinstance(obj_cell, str) and obj_cell.startswith(_LITERAL_PREFIX):
        payload = obj_cell[len(_LITERAL_PREFIX):]
        try:
            return ast.literal_eval(payload)
        except (ValueError, SyntaxError) as ex:
            raise ValueError(
                f"Cannot decode literal token {obj_cell!r}: {ex}"
            ) from ex
    return ds.get_entity_by_uri(obj_cell)


def _nemo_available() -> bool:
    """True wenn das Nemo-Binary (PYIRK_NEMO_BIN oder /home/user/bin/nmo) existiert."""
    bin_path = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")
    return os.path.exists(bin_path)


def _split_rules_by_nemo_delegation(rules):
    """Teilt *rules* in (delegated, remaining) auf.

    delegated  = Regeln mit Kategorie 'direct' oder 'transitive'
    remaining  = alle anderen (python_only, SPARQL, OR-Subscope usw.)

    Gibt ([], rules) zurück wenn keine delegierbaren Regeln gefunden werden.
    """
    from pyirk import core
    from pyirk.nemobridge import classify_rules

    try:
        clfs = classify_rules(core.ds)
    except Exception as ex:
        logger.debug("classify_rules fehlgeschlagen: %s", ex)
        return [], list(rules)

    delegatable_keys = {
        c.rule_short_key for c in clfs if c.category in ("direct", "transitive")
    }

    delegated = []
    remaining = []
    for rule in rules:
        if hasattr(rule, "short_key") and rule.short_key in delegatable_keys:
            delegated.append(rule)
        else:
            remaining.append(rule)

    return delegated, remaining


def _apply_via_nemo(
    delegated_rules, mod_context_uri, *, out_stms=None, inserted_uris=None,
):
    """Führt den Nemo-Delegationspfad aus.

    Pipeline: ``export_datastore`` → ``generate_rls`` → ``nmo`` →
    ``output_fact.csv`` (ternäres ``fact(subj_uri, pred_uri, obj_uri)``) →
    Auflösung jeder Spalte per ``ds.get_entity_by_uri`` →
    ``subj.set_relation(rel, obj)`` (V2.1 + V3 + V5).

    Designvorgaben:
      * V2.1 (Phase 2.1) — Datenterme sind volle URIs. Alle drei Spalten
        von ``output_fact.csv`` werden direkt per URI aufgelöst; kein
        short_key-Pfad mehr → kollisionsfest über Module hinweg (Gate 1).
      * V3 — ``omit_if_existing``-Spiegel des nativen Konklusions-Pfads
        (ruleengine.py): Tupel, die bereits Statements sind, werden nicht
        erneut eingefügt.
      * Gate-3-Fix (Phase 2.1) — zusätzliches ``inserted``-Set in
        ``_materialize_tuples`` deduplifiziert Nemo-Mehrfachausgaben
        desselben Tupels innerhalb eines Aufrufs.
      * V5 — Kontextwrap via ``core.uri_context(mod_context_uri)``.

    :param delegated_rules:   Liste delegierbarer Regelobjekte (nur für Log)
    :param mod_context_uri:   Kontext-URI für neue Statements; None ⇒ es muss
                              bereits ein aktiver Modul-Kontext gesetzt sein
                              (Aufrufer-Verantwortung, wie im nativen Pfad).
    :param out_stms:          Optionale Liste, die — wenn übergeben — pro neu
                              erzeugtem Statement um genau jenes Statement-Objekt
                              ergänzt wird. Plumbing-Hook für
                              ``ruleengine.apply_semantic_rules``.
    :param inserted_uris:     Optionales ``set`` von ``(subj_uri, pred_uri,
                              obj_uri)``-Tripeln, das Cross-V4-Iteration
                              durchgereicht werden kann, damit der Gate-3-
                              Dedup über mehrere ``_apply_via_nemo``-Calls
                              innerhalb derselben Fixpoint-Schleife hinweg
                              wirkt. Default ``None`` → lokaler Set in
                              ``_materialize_tuples`` (Backward-Compat).
    :return int:              Anzahl tatsächlich eingefügter neuer Statements.
    """
    from pyirk import core
    from pyirk.nemobridge import export_datastore, generate_rls

    nmo_bin = os.environ.get("PYIRK_NEMO_BIN", "/home/user/bin/nmo")

    with tempfile.TemporaryDirectory(prefix="pyirk_nemo_p4_") as tmp_dir:
        # 1) EDB exportieren
        out_dir = os.path.join(tmp_dir, "out")
        os.makedirs(out_dir)

        try:
            export_datastore(core.ds, tmp_dir)
        except Exception as ex:
            raise RuntimeError(f"export_datastore fehlgeschlagen: {ex}") from ex

        # 2) RLS-Datei erzeugen — beschraenkt auf die tatsaechlich vom Aufrufer
        # angeforderten delegierbaren Regeln; sonst wuerde Nemo auch alle
        # anderen direct/transitive-Regeln auswerten, deren Konklusionen der
        # native Pfad in diesem Aufruf NICHT erzeugen wuerde (verfaelschte
        # Aequivalenz im Einzelregel-Test, siehe H5-Extension Phase 1).
        delegated_keys = {
            getattr(r, "short_key", None) for r in delegated_rules
        }
        delegated_keys.discard(None)
        rls_content = generate_rls(core.ds, restrict_to=delegated_keys)
        rls_path = os.path.join(tmp_dir, "rules.rls")
        with open(rls_path, "w", encoding="utf-8") as fh:
            fh.write(rls_content)

        # 3) Nemo-Lauf
        cmd = [
            nmo_bin,
            "--export-dir", out_dir,
            "--import-dir", tmp_dir,
            "--overwrite-results",
            rls_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(
                f"nmo exit {proc.returncode}: {proc.stderr[:500]}"
            )

        # 4) Output-CSV parsen — ternäres (subj_uri, pred_uri, obj_uri)
        nemo_tuples = _parse_nemo_outputs(out_dir)
        logger.debug(
            "Nemo lieferte %d Tupel für %d delegierte Regeln",
            len(nemo_tuples), len(delegated_rules),
        )

        # 5) Tupel → Statements (V2.1 + V3 + Gate-3-Fix + V5)
        return _materialize_tuples(
            core.ds, nemo_tuples, mod_context_uri,
            out_stms=out_stms, inserted=inserted_uris,
        )


def _materialize_tuples(
    ds, nemo_tuples, mod_context_uri, *, out_stms=None, inserted=None,
):
    """Schreibt Nemo-Output-Tupel als neue Statements zurück in *ds*.

    Erwartet Tupel der Form ``(subj_uri, pred_uri, obj_uri)``. Jede Spalte
    wird direkt per ``ds.get_entity_by_uri`` aufgelöst.

    V3 (DataStore-Stand zu Loop-Beginn): vor ``set_relation`` denselben
    Check wie im nativen Konklusions-Pfad (ruleengine.py): ``if obj not in
    subj.get_relations(rel.uri, return_obj=True): subj.set_relation(...)``.

    Gate-3-Fix (Intra-Call-Dedup, Phase 2.1): ein ``inserted``-Set fängt
    Tupel ab, die Nemo innerhalb desselben Laufs mehrfach ableitet; der
    V3-Check sieht sie sonst nicht (DataStore-Stand wurde erst durch
    ``set_relation`` aktualisiert, aber Iteration läuft weiter über die
    nicht-dedupifizierte Liste — und ``nemo_tuples`` ist u. U. auch eine
    Liste, kein Set). Wird ``inserted`` vom Aufrufer übergeben, lebt der
    Dedup-State über mehrere ``_apply_via_nemo``-Calls hinweg (z. B.
    Cross-V4-Iteration im Fixpoint-Loop von ``apply_semantic_rules``);
    Default ``None`` legt einen lokalen Set für Backward-Compat an.

    V5: ``uri_context(mod_context_uri)``-Wrapper spiegelt
    ``RuleApplicator.apply`` (ruleengine.py) 1:1.

    :return int: Anzahl tatsächlich neu eingefügter Statements.
    """
    from pyirk import core

    if inserted is None:
        inserted = set()  # Gate-3-Fix: (subj_uri, pred_uri, obj_uri)

    def _do() -> int:
        n_new = 0
        for triple in nemo_tuples:
            if len(triple) != 3:
                continue
            subj_uri, pred_uri, obj_uri = triple

            # Gate-3-Fix: Intra-Call-Dedup vor jeder Auflösung
            key = (subj_uri, pred_uri, obj_uri)
            if key in inserted:
                continue

            try:
                subj = ds.get_entity_by_uri(subj_uri)
                rel = ds.get_entity_by_uri(pred_uri)
                obj = _decode_object_cell(ds, obj_uri)
            except Exception as ex:
                logger.debug(
                    "skip nemo tuple (%s,%s,%s): URI/literal resolution failed: %s",
                    subj_uri, pred_uri, obj_uri, ex,
                )
                continue

            # V3 — omit_if_existing-Spiegel des nativen Pfads
            if obj in subj.get_relations(rel.uri, return_obj=True):
                continue

            new_stm = subj.set_relation(rel, obj)
            inserted.add(key)
            # V1 (Phase-2 vertagt): Qualifier-Reifikation kommt später hier rein.
            _apply_qualifiers(new_stm)
            if out_stms is not None:
                out_stms.append(new_stm)
            n_new += 1
        return n_new

    if mod_context_uri is None:
        return _do()
    core.aux.ensure_valid_baseuri(mod_context_uri)
    with core.uri_context(mod_context_uri):
        return _do()


def _apply_qualifiers(new_stm):
    """V1-Hook (Phase-2 vertagt): Qualifier an *new_stm* hängen.

    Aktuell no-op — spiegelt das native ``# TODO: add qualifiers`` in
    ``ruleengine.py`` (~Z. 716) wider. Eine spätere Phase ergänzt hier die
    Qualifier-Reifikation gegen ``stmts.csv`` / ``quals_<R>.csv``. Bis dahin
    bleibt die Funktion bewusst leer; das Vorhalten als eigene Funktion sorgt
    dafür, dass die spätere Aktivierung eine isolierte Ergänzung ist (kein
    Umbau des Mapping-Schritts).
    """
    return None


def _parse_nemo_outputs(export_dir):
    """Liest ``output_fact.csv`` aus *export_dir* → Set ternärer URI-Tupel.

    Erwartet das ternäre ``fact``-Modell (Phase 2.1): genau eine
    Output-Datei, drei Spalten ``(subj_uri, pred_uri, obj_uri)``.

    Nemo serialisiert String-Werte mit umschließenden Anführungszeichen, die
    NACH CSV-Entescaping als literale doppelte Anführungszeichen am Anfang/
    Ende jeder Zelle stehen bleiben (Nemo schreibt die Zelle z. B. als
    `\"\"\"value\"\"\"`, nach csv.reader steht `"value"` mit echten ``"`` als
    erstem und letztem Zeichen). Diese werden hier entfernt, damit die Werte
    in ``ds.get_entity_by_uri`` passen.
    """
    def _strip_q(cell: str) -> str:
        if len(cell) >= 2 and cell[0] == '"' and cell[-1] == '"':
            return cell[1:-1]
        return cell

    nemo_set = set()
    if not os.path.isdir(export_dir):
        return nemo_set
    fpath = os.path.join(export_dir, "output_fact.csv")
    if not os.path.isfile(fpath):
        return nemo_set
    with open(fpath, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if len(row) >= 3:
                nemo_set.add((_strip_q(row[0]), _strip_q(row[1]), _strip_q(row[2])))
    return nemo_set
