"""
pyirk.nemobridge.delegation — Hilfsfunktionen für den PYIRK_NEMO_DELEGATION-Pfad.

Wird von ruleengine.apply_semantic_rules() aufgerufen, wenn das Feature-Flag
PYIRK_NEMO_DELEGATION gesetzt ist.

Aktueller Stand (Phase 1):
  - _nemo_available(), _split_rules_by_nemo_delegation() sind vollständig.
  - _apply_via_nemo() führt Export → RLS-Codegen → nmo-Run aus, aber das
    Mapping CSV → core.Statement ist NICHT implementiert (Phase-2-TODO).
    Es wird NotImplementedError geworfen, der im aufrufenden try/except
    den stillen Python-Fallback auslöst.

Bekannte Limitation:
  Rückkopplung zwischen Nemo-Block und Python-Block ist nicht umgesetzt.
  Nemo läuft einmal bis Fixpunkt seiner Teilmenge; python_only-Ergebnisse,
  die delegierbare Regeln erneut triggern würden, werden ignoriert.
  → offen für Phase 2.
"""

import csv
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


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


def _apply_via_nemo(delegated_rules, mod_context_uri):
    """Führt den Nemo-Delegationspfad aus.

    Pipeline: export_datastore → generate_rls → nmo → parse CSVs
    → create_statement für jeden neuen Tupel.

    Phase-1-Status: Export, RLS-Codegen und nmo-Aufruf sind implementiert.
    Das Mapping CSV-Tupel → core.Statement ist als Phase-2-TODO markiert
    (raise NotImplementedError), der den stillen Fallback im Aufrufer auslöst.

    :param delegated_rules:   Liste delegierbarer Regelobjekte (nur für Log)
    :param mod_context_uri:   Kontext-URI für neue Statements
    :raises NotImplementedError: immer (Phase-2-TODO für CSV→Statement-Mapping)
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

        # 2) RLS-Datei erzeugen
        rls_content = generate_rls(core.ds)
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

        # 4) Output-CSVs parsen — Tupel sammeln
        nemo_tuples = _parse_nemo_outputs(out_dir)
        logger.debug(
            "Nemo lieferte %d Tupel für %d delegierte Regeln",
            len(nemo_tuples), len(delegated_rules),
        )

        # 5) CSV → core.Statement mapping
        # TODO Phase 2: Für jeden Tupel (s_key, p_key, o_key) aus nemo_tuples:
        #   - Entitäten per core.ds.get_entity_by_key_str() auflösen
        #   - Duplikat-Check per p.qf_prevent_duplicate_stms()
        #   - Statement per subj.set_relation(rel, obj, ...) erzeugen
        # Qualifier-Reifikation, Prädikat-Auflösung und Kontext-URI-Handling
        # erfordern tiefergehende Kenntnis der Statement-Erzeugungslogik.
        raise NotImplementedError(
            "P4 mapping deferred to Phase 2: CSV→core.Statement conversion not yet implemented"
        )


def _parse_nemo_outputs(export_dir):
    """Liest alle output_*.csv aus *export_dir* → Set kanonischer 3-Tupel."""
    nemo_set = set()
    if not os.path.isdir(export_dir):
        return nemo_set
    for fname in sorted(os.listdir(export_dir)):
        if not (fname.startswith("output_") and fname.endswith(".csv")):
            continue
        fpath = os.path.join(export_dir, fname)
        if fname == "output_trans.csv":
            with open(fpath, newline="", encoding="utf-8") as fh:
                for row in csv.reader(fh):
                    if len(row) >= 3:
                        nemo_set.add((row[0], row[1], row[2]))
        else:
            pred_key = fname[len("output_"):-len(".csv")]
            with open(fpath, newline="", encoding="utf-8") as fh:
                for row in csv.reader(fh):
                    if len(row) >= 2:
                        nemo_set.add((row[0], pred_key, row[1]))
    return nemo_set
