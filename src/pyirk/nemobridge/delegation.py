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
import functools
import logging
import os
import re
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)


# Mirror of ``exporter.LITERAL_PREFIX``. Imported lazily inside the helper to
# avoid a hard import-time dependency between the two modules.
_LITERAL_PREFIX = "LIT:"


_TRUTHY_TOKENS = ("1", "true", "yes", "on")
_FALSY_TOKENS = ("0", "false", "no", "off", "")


def _coerce_flag(value) -> "bool | None":
    """Interpret a config/env value as an on/off flag.

    Returns ``True``/``False`` for a recognised token, or ``None`` if the
    value is absent (``None``) or unrecognised (caller decides the default).
    A genuine ``bool`` (e.g. from a TOML ``delegation = true``) passes through.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in _TRUTHY_TOKENS:
        return True
    if token in _FALSY_TOKENS:
        return False
    return None


def delegation_enabled() -> bool:
    """Whether the Nemo-delegation path should be used.

    Resolution order (first decisive wins):
      1. ``PYIRK_NEMO_DELEGATION`` env var — an explicit truthy/falsy token
         decides in BOTH directions (so ``=0`` disables even if the config
         enables it). An unrecognised value is ignored, not treated as on.
      2. pyirk config ``[nemo] delegation`` (``p.CONF``) — lets a user opt in
         persistently without setting the env var on every invocation.
      3. Default: ``False`` (delegation stays opt-in; the native Python engine
         is the shipped default).

    Note: this only expresses *intent*. The hook still verifies that an
    ``nmo`` binary is available and version-compatible before delegating,
    and falls back silently otherwise.
    """
    env_flag = _coerce_flag(os.environ.get("PYIRK_NEMO_DELEGATION"))
    if env_flag is not None:
        return env_flag

    try:
        import pyirk as p
        cfg_flag = _coerce_flag(p.CONF.get("nemo", {}).get("delegation"))
        if cfg_flag is not None:
            return cfg_flag
    except Exception:
        pass

    return False

# ── Deployment-Robustheit (H5 Deployment) ────────────────────────────────────
# Modul-State für idempotente Logs/Warnings — pro Prozess genau einmal.
# Tests setzen diese Flags via monkeypatch zurück.
# Generic per-user last-resort location (resolves to /home/user/bin/nmo on the
# VPS where the H5 gates were validated).
_LEGACY_DEFAULT_NMO_BIN = os.path.expanduser("~/bin/nmo")
_resolver_logged: bool = False
_warned_no_binary: bool = False
_warned_nmo_failed: bool = False
_warned_version_mismatch: bool = False

# Validierte Nemo-Version: 0.10.x. Politik (vgl. Bericht):
#   patch (0.10.y) → ok, kein Warning
#   minor (0.11.z) → ein Warning, Delegation trotzdem versuchen
#   major (1.x)    → ein Warning, Fallback
#   unparseable    → ein Warning, Fallback
_EXPECTED_NMO_MAJOR = 0
_EXPECTED_NMO_MINOR = 10
_NMO_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _resolve_nmo_bin() -> "str | None":
    """Resolve the path of the ``nmo`` binary.

    Order:
      1. ``PYIRK_NEMO_BIN`` env var, if set AND the path exists.
      2. ``shutil.which("nmo")`` — first hit on PATH.
      3. ``~/bin/nmo`` (expanded per user) — legacy default, if it exists.
      4. ``None`` — no binary available.

    Logs the chosen source on ``logger.info`` exactly once per process
    (or until the module-level ``_resolver_logged`` flag is reset, which
    is intended for tests only).
    """
    global _resolver_logged

    env_val = os.environ.get("PYIRK_NEMO_BIN")
    if env_val and os.path.exists(env_val):
        bin_path, source = env_val, "PYIRK_NEMO_BIN"
    else:
        which_val = shutil.which("nmo")
        if which_val:
            bin_path, source = which_val, "shutil.which"
        elif os.path.exists(_LEGACY_DEFAULT_NMO_BIN):
            bin_path, source = _LEGACY_DEFAULT_NMO_BIN, "default"
        else:
            bin_path, source = None, "none"

    if not _resolver_logged:
        if bin_path is None:
            logger.info(
                "nmo binary resolution: no candidate found "
                "(PYIRK_NEMO_BIN, PATH, %s all empty)",
                _LEGACY_DEFAULT_NMO_BIN,
            )
        else:
            logger.info("nmo binary resolved via %s: %s", source, bin_path)
        _resolver_logged = True

    return bin_path


def _warn_no_binary_once() -> None:
    """Emit the ``no nmo binary`` warning at most once per process."""
    global _warned_no_binary
    if not _warned_no_binary:
        logger.warning(
            "PYIRK_NEMO_DELEGATION is set but no nmo binary could be located "
            "(checked PYIRK_NEMO_BIN, shutil.which('nmo'), %s). "
            "Falling back to the native Python engine.",
            _LEGACY_DEFAULT_NMO_BIN,
        )
        _warned_no_binary = True


def mark_nmo_failed_warned(exc: "BaseException | None" = None) -> None:
    """Emit the ``Nemo delegation failed at runtime`` warning at most once per
    process. Exported for the ruleengine hook so the ``_apply_via_nemo``
    exception path stays idempotent across calls."""
    global _warned_nmo_failed
    if not _warned_nmo_failed:
        if exc is not None:
            logger.warning(
                "Nemo delegation failed at runtime (%s); falling back to the "
                "native Python engine. Further occurrences are suppressed.",
                exc,
            )
        else:
            logger.warning(
                "Nemo delegation failed at runtime; falling back to the "
                "native Python engine. Further occurrences are suppressed."
            )
        _warned_nmo_failed = True


@functools.lru_cache(maxsize=1)
def _check_nmo_version(nmo_bin: str) -> bool:
    """Validate the installed nmo binary's version against the supported range.

    Cached (``functools.lru_cache(maxsize=1)``) per ``nmo_bin`` path — the
    subprocess only runs once per process unless tests clear the cache.

    Policy:
      * Matches the expected ``0.10.y`` series → return ``True``, no warning.
      * Minor mismatch (e.g. ``0.11.z``) → emit one warning, return ``True``
        (delegation is attempted; protocol differences may still cause a
        runtime failure, which is caught by the hook).
      * Major mismatch (e.g. ``1.x.y``) → emit one warning, return ``False``
        (fall back to the native engine — major bumps reliably break the RLS
        codegen/CLI contract).
      * Unparseable / subprocess failure → emit one warning, return ``False``.
    """
    global _warned_version_mismatch

    try:
        proc = subprocess.run(
            [nmo_bin, "--version"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as ex:  # noqa: BLE001 — subprocess can raise many things
        if not _warned_version_mismatch:
            logger.warning(
                "Could not invoke `%s --version` (%s); falling back to the "
                "native Python engine.", nmo_bin, ex,
            )
            _warned_version_mismatch = True
        return False

    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = _NMO_VERSION_RE.search(blob)
    if not m or proc.returncode != 0:
        if not _warned_version_mismatch:
            logger.warning(
                "Could not parse nmo version from `%s --version` (rc=%s, "
                "output=%r); falling back to the native Python engine.",
                nmo_bin, proc.returncode, blob[:200],
            )
            _warned_version_mismatch = True
        return False

    major, minor, patch = (int(x) for x in m.groups())
    if major != _EXPECTED_NMO_MAJOR:
        if not _warned_version_mismatch:
            logger.warning(
                "nmo version %d.%d.%d differs from the validated %d.%d.x "
                "series by MAJOR; falling back to the native Python engine.",
                major, minor, patch,
                _EXPECTED_NMO_MAJOR, _EXPECTED_NMO_MINOR,
            )
            _warned_version_mismatch = True
        return False
    if minor != _EXPECTED_NMO_MINOR:
        if not _warned_version_mismatch:
            logger.warning(
                "nmo version %d.%d.%d differs from the validated %d.%d.x "
                "series by MINOR; attempting delegation anyway.",
                major, minor, patch,
                _EXPECTED_NMO_MAJOR, _EXPECTED_NMO_MINOR,
            )
            _warned_version_mismatch = True
        return True
    return True


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
    """True wenn ein Nemo-Binary via :func:`_resolve_nmo_bin` gefunden wird.

    Wenn keines vorhanden ist, wird **einmal pro Prozess** eine Warnung
    emittiert; der Caller (Ruleengine-Hook) fällt anschließend still auf den
    nativen Python-Pfad zurück.
    """
    bin_path = _resolve_nmo_bin()
    if bin_path is None:
        _warn_no_binary_once()
        return False
    return True


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

    nmo_bin = _resolve_nmo_bin()
    if nmo_bin is None:
        raise RuntimeError("nmo binary not available — caller must check first")

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
