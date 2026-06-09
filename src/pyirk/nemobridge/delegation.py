"""
pyirk.nemobridge.delegation — Hilfsfunktionen für den PYIRK_NEMO_DELEGATION-Pfad.

Wird von ruleengine.apply_semantic_rules() aufgerufen, wenn das Feature-Flag
PYIRK_NEMO_DELEGATION gesetzt ist.

Aktueller Stand (Phase-2 P2):
  - _nemo_available(), _split_rules_by_nemo_delegation() sind vollständig.
  - _apply_via_nemo() führt Export → RLS-Codegen → nmo-Run → CSV→Statement-
    Mapping aus. Rückgabewert: Anzahl neu eingefügter Statements (für den
    Fixpunkt-Loop in Phase-2 P3).
  - Auflösung der Entitäten erfolgt strikt per URI über das vom Exporter
    geschriebene ``uri_index.csv`` (V2), nicht per nacktem short_key gegen das
    aktive Modul.
  - Einfügung idempotent via ``omit_if_existing``-Spiegelung (V3); nur echt
    neue Tupel werden Statements.
  - mod_context_uri wird wie im nativen Pfad über ``core.uri_context(...)``
    aktiv gehalten (V5).
  - Qualifier-Delegation ist Phase-2 vertagt (V1) — Hook ``_apply_qualifiers``
    ist als no-op-Stub vorhanden, damit eine künftige Phase die Qualifier-
    Reifikation lokal ergänzen kann, ohne den Mapping-Schritt umzubauen.

Bekannte Limitation:
  Rückkopplung zwischen Nemo-Block und Python-Block ist nicht umgesetzt.
  Nemo läuft einmal bis Fixpunkt seiner Teilmenge; python_only-Ergebnisse,
  die delegierbare Regeln erneut triggern würden, werden ignoriert.
  → offen für Phase-2 P3 (Fixpunkt-Loop in apply_semantic_rules).
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


def _apply_via_nemo(delegated_rules, mod_context_uri, *, out_stms=None):
    """Führt den Nemo-Delegationspfad aus.

    Pipeline: ``export_datastore`` → ``generate_rls`` → ``nmo`` → parse CSVs
    → für jedes Tupel ``subj.set_relation(rel, obj)`` (V2+V3+V5).

    Designvorgaben (verbindlich aus goal.md):
      * V2 — Jede Entity wird über ihre URI aufgelöst (``ds.get_entity_by_uri``);
        Quelle: ``uri_index.csv`` aus dem Export. Konklusionsrelationen, die
        zur Exportzeit noch keine Statements im DataStore hatten (z. B. R83
        gegen eine frische Test-KB), werden zusätzlich aus ``ds.relations``
        nachgeschlagen — strikt per URI, kollisionssichere Erweiterung lokal
        in dieser Funktion, keine short_key-Resolution gegen das aktive Modul.
      * V3 — Idempotente Einfügung: spiegelt das ``omit_if_existing``-Muster
        des nativen Konklusions-Pfads (ruleengine.py ~Z. 712-715). Nur Tupel,
        die noch nicht als Statement existieren, werden eingefügt.
      * V5 — Abgeleitete Statements bekommen denselben mod_context_uri wie der
        native Pfad. Mechanismus identisch zu ``RuleApplicator.apply``
        (ruleengine.py ~Z. 295-301): ``with core.uri_context(mod_context_uri):
        ... set_relation(...)``.

    :param delegated_rules:   Liste delegierbarer Regelobjekte (nur für Log)
    :param mod_context_uri:   Kontext-URI für neue Statements; None ⇒ es muss
                              bereits ein aktiver Modul-Kontext gesetzt sein
                              (Aufrufer-Verantwortung, wie im nativen Pfad).
    :param out_stms:          Optionale Liste, die — wenn übergeben — pro neu
                              erzeugtem Statement um genau jenes Statement-Objekt
                              ergänzt wird. Plumbing-Hook für
                              ``ruleengine.apply_semantic_rules``, damit die
                              Nemo-materialisierten Statements im
                              ``ReportingMultiRuleResult`` sichtbar bleiben.
                              Funktionaler Rückgabewert (int n_new) ist
                              unverändert.
    :return int:              Anzahl tatsächlich eingefügter neuer Statements
                              (für den Fixpunkt-Loop in P3).
    """
    from pyirk import core
    from pyirk.nemobridge import export_datastore, generate_rls
    from pyirk.nemobridge.exporter import load_uri_index

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

        # 5) CSV → core.Statement mapping (V2 + V3 + V5)
        uri_index = load_uri_index(tmp_dir)
        return _materialize_tuples(
            core.ds, nemo_tuples, uri_index, mod_context_uri, out_stms=out_stms,
        )


def _extend_uri_index_for_conclusion_relations(ds, uri_index):
    """Ergänzt *uri_index* um Relationen, die in den Statements nicht vorkamen.

    Hintergrund: ``export_datastore`` registriert eine URI nur, wenn die zugehörige
    Entity in einem exportierten Statement auftaucht. Konklusions-Relationen einer
    Regel (z. B. R83 in einer KB ohne vorbestehende R83-Statements) sind dadurch
    im URI-Index nicht enthalten — Nemo erzeugt aber Tupel mit eben diesen
    Relations-short_keys. Diese Funktion füllt solche Lücken aus ``ds.relations``
    auf, wobei bestehende Index-Einträge Vorrang haben (V2-konform: weiterhin
    URI-basierte Auflösung, kein short_key gegen das aktive Modul).

    Sicherheit gegen short_key-Kollisionen: ds.relations ist URI-keyed. Sollten
    zwei Relationen mit verschiedenem URI denselben short_key haben (in
    normalem pyirk-Betrieb unüblich, aber technisch denkbar bei Mehrfach-Modul-
    Loads), wird der short_key als ambig markiert und NICHT in den Index
    aufgenommen — der Mapping-Schritt skipt diese Tupel mit DEBUG-Log.
    """
    rel_by_sk = {}
    ambiguous = set()
    for uri, rel in ds.relations.items():
        sk = getattr(rel, "short_key", None)
        if sk is None:
            continue
        if sk in rel_by_sk and rel_by_sk[sk] != uri:
            ambiguous.add(sk)
            continue
        rel_by_sk[sk] = uri
    for sk, uri in rel_by_sk.items():
        if sk in ambiguous:
            continue
        uri_index.setdefault(sk, uri)


def _materialize_tuples(ds, nemo_tuples, uri_index, mod_context_uri, *, out_stms=None):
    """Schreibt Nemo-Output-Tupel als neue Statements zurück in *ds*.

    V2: Auflösung strikt per URI; fehlt der short_key im Index, wird das Tupel
    geräuschlos übersprungen (DEBUG-Log) — der äußere try/except im Aufrufer
    in ``ruleengine.apply_semantic_rules`` greift erst bei harten Exceptions.

    V3: Vor ``set_relation`` exakt der gleiche Check wie im nativen Pfad
    (ruleengine.py ~Z. 714): ``if obj not in subj.get_relations(rel.uri,
    return_obj=True): subj.set_relation(rel, obj)``.

    V5: ``uri_context(mod_context_uri)``-Wrapper spiegelt
    ``RuleApplicator.apply`` (ruleengine.py ~Z. 295-301) 1:1.

    :return int: Anzahl tatsächlich neu eingefügter Statements.
    """
    from pyirk import core

    # V2-Ergänzung: Konklusions-Relationen müssen NICHT zur Exportzeit als Statement
    # vorgekommen sein — fülle Lücken im URI-Index aus ds.relations auf.
    # (Lokal mutiert, da uri_index sowieso eine pro-Aufruf-Datei-Kopie ist.)
    _extend_uri_index_for_conclusion_relations(ds, uri_index)

    def _do() -> int:
        n_new = 0
        for triple in nemo_tuples:
            if len(triple) != 3:
                continue
            subj_key, pred_key, obj_key = triple

            subj_uri = uri_index.get(subj_key)
            pred_uri = uri_index.get(pred_key)
            obj_uri = uri_index.get(obj_key)
            if subj_uri is None or pred_uri is None or obj_uri is None:
                logger.debug(
                    "skip nemo tuple (%s,%s,%s): missing uri in index "
                    "(subj=%s pred=%s obj=%s)",
                    subj_key, pred_key, obj_key,
                    subj_uri is not None, pred_uri is not None, obj_uri is not None,
                )
                continue
            try:
                subj = ds.get_entity_by_uri(subj_uri)
                rel = ds.get_entity_by_uri(pred_uri)
                obj = ds.get_entity_by_uri(obj_uri)
            except Exception as ex:
                logger.debug(
                    "skip nemo tuple (%s,%s,%s): URI resolution failed: %s",
                    subj_key, pred_key, obj_key, ex,
                )
                continue

            # V3 — omit_if_existing-Spiegel des nativen Pfads (ruleengine.py ~Z. 714)
            if obj in subj.get_relations(rel.uri, return_obj=True):
                continue

            new_stm = subj.set_relation(rel, obj)
            # V1 (Phase-2 vertagt): Qualifier-Reifikation kommt später hier rein.
            _apply_qualifiers(new_stm)
            if out_stms is not None:
                out_stms.append(new_stm)
            n_new += 1
        return n_new

    # V5 — gleiche Kontext-Setzung wie RuleApplicator.apply (ruleengine.py ~Z. 295-301):
    # mod_context_uri=None ⇒ bestehender aktiver Modul-Kontext wird verwendet.
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
