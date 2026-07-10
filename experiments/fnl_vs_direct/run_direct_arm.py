"""Direct-arm runner for the FNL-vs-direct experiment: real Opus calls.

Drives the LaTeX adapter's segmentation layer over the gold corpora in
``corpus_gold__gitignore__/`` and routes every snippet through
:func:`pyirk.authoring.latex.import_snippet`, which in turn calls Claude
(here: Opus) via the substrate's ``propose_via_claude``. Per-snippet event
records are appended (one JSONL line at a time) to ``stats.jsonl`` in the
output directory; the bootstrapped per-corpus pyirk modules live next to
that file at ``out_dir/{corpus}/direct_arm.py``.

CLI::

    python -m experiments.fnl_vs_direct.run_direct_arm \\
        [--corpus nichtlinear|bernstein|both] [--limit N] \\
        [--out-dir PATH] [--resume] [--model MODELID]

Resume: existing ``stats.jsonl`` lines are read on startup; already-seen
``(corpus, snippet_id)`` pairs are skipped silently so a re-run is
idempotent (no duplicate lines, no double-applied snippet code).

Smoke-first: when no ``stats.jsonl`` exists yet AND no ``--limit`` was
given, the runner processes 2 snippets per corpus first, prints a short
diagnosis, and -- if all four smoke snippets failed -- aborts with a
non-zero exit code and a diagnostic on stderr. The orchestrator can act on
that signal before spending Opus tokens on a doomed full run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

# Make sure the in-repo src/ wins over any editable install when this is run
# as a script (``python -m experiments.fnl_vs_direct.run_direct_arm``).
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import pyirk  # noqa: E402
from pyirk import authoring as _substrate  # noqa: E402
from pyirk.authoring import (  # noqa: E402
    Session,
    bootstrap_working_module,
    fork_policy_first,
)
from pyirk.authoring.latex import (  # noqa: E402
    find_snippet,
    import_snippet,
    parse_snippets,
)


DEFAULT_MODEL = "claude-opus-4-7"
SELECTION_FILE = _THIS_DIR / "snippet_selection.json"
DEFAULT_OUT_DIR = _THIS_DIR / "run_out"
DEFAULT_OCSE_PATH = _PROJECT_ROOT / "tests" / "test_data" / "ocse_subset" / "math1.py"

CORPUS_TEX: Dict[str, Path] = {
    "nichtlinear": _THIS_DIR / "corpus_gold__gitignore__" / "nichtlinear" / "kapitel2.tex",
    "bernstein": _THIS_DIR / "corpus_gold__gitignore__" / "bernstein" / "chunk_full_source.tex",
}


_SID_NUM_RE = re.compile(r"^(\d+)(.*)$")


def _snippet_sort_key(snippet_id: str) -> tuple:
    """Natural sort: numeric prefix first, then alphabetic suffix."""
    m = _SID_NUM_RE.match(snippet_id)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, snippet_id)


# ---------------------------------------------------------------------------
# Monkey-patch: inject the Opus model id into propose_via_claude calls that
# do NOT pass an explicit model (the substrate's ``import_one_statement`` is
# one such caller).

_PATCH_SENTINEL = object()


def apply_opus_patch(model_id: str) -> None:
    """Replace ``pyirk.authoring.propose_via_claude`` with a wrapper that
    defaults the ``model`` kwarg to ``model_id`` when the caller omitted it.

    Idempotent: repeat calls re-patch over the SAME original function (the
    first patch stores ``__opus_orig__`` on the wrapper), so the model id
    can be updated mid-process without stacking wrappers.
    """
    current = _substrate.propose_via_claude
    original = getattr(current, "__opus_orig__", current)

    def wrapper(prompt, timeout=600, model=_PATCH_SENTINEL):
        effective = model_id if model is _PATCH_SENTINEL else model
        return original(prompt, timeout=timeout, model=effective)

    wrapper.__opus_orig__ = original
    wrapper.__opus_model__ = model_id
    _substrate.propose_via_claude = wrapper


# ---------------------------------------------------------------------------
# Monkey-patch: workaround for the hardcoded ``_validate`` prefix in
# ``pyirk.authoring.validate_module`` -- without this, the second corpus
# always trips on ``InvalidPrefixError: prefix '_validate' was already
# registered`` because the prefix from the previous corpus's validate
# survives in ``pyirk.ds.uri_prefix_mapping.b``.

_VALIDATE_PREFIX = "_validate"


def apply_validate_prefix_patch() -> None:
    """Replace ``pyirk.authoring.validate_module`` with a wrapper that releases
    any stale ``_validate`` prefix registration before delegating to the
    original validator.

    Idempotent: a second call is a no-op (the wrapper carries a
    ``__validate_patched__`` marker).
    """
    current = _substrate.validate_module
    if getattr(current, "__validate_patched__", False):
        return
    original = current

    def wrapper(path):
        existing_uri = pyirk.ds.uri_prefix_mapping.b.get(_VALIDATE_PREFIX)
        if existing_uri is not None:
            try:
                pyirk.unload_mod(existing_uri, strict=False)
            except Exception:
                # best-effort cleanup; fall through to the original validator
                # so its own error reporting wins.
                pass
        return original(path)

    wrapper.__validate_patched__ = True
    wrapper.__validate_orig__ = original
    _substrate.validate_module = wrapper


# ---------------------------------------------------------------------------
# Selection + resume

def load_selection(path: Path = SELECTION_FILE) -> dict:
    with path.open() as fp:
        return json.load(fp)


def load_already_done(stats_path: Path) -> Set[Tuple[str, str]]:
    """Return the set of ``(corpus, snippet_id)`` pairs already recorded.

    Tolerates a missing file or a partially-corrupt trailing line (the
    append-and-die failure mode); each well-formed line contributes one pair.
    """
    done: Set[Tuple[str, str]] = set()
    if not stats_path.exists():
        return done
    for line in stats_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        corpus = obj.get("corpus")
        sid = obj.get("snippet_id")
        if corpus and sid is not None:
            done.add((corpus, str(sid)))
    return done


def collect_planned(selection: dict, corpora: List[str], limit: int) -> List[Tuple[str, str, str]]:
    """Return the deterministically sorted ``(corpus, snippet_id, type)`` triples.

    ``--limit`` is applied PER CORPUS (analogous to the mock runner), not
    globally, so a 4-snippet smoke run covers 2-per-corpus the same way.
    """
    planned: List[Tuple[str, str, str]] = []
    for corpus in corpora:
        entries = list(selection["corpora"].get(corpus, []))
        entries_sorted = sorted(entries, key=lambda e: _snippet_sort_key(e["snippet_id"]))
        if limit and limit > 0:
            entries_sorted = entries_sorted[:limit]
        for entry in entries_sorted:
            planned.append((corpus, entry["snippet_id"], entry.get("type", "unknown")))
    return planned


# ---------------------------------------------------------------------------
# Per-corpus session + working module bootstrap

def bootstrap_corpus(out_dir: Path, corpus: str, ocse_path: Path) -> Tuple[Session, Path]:
    """Create (or reuse) the per-corpus working module and return a fresh Session.

    Idempotency: if the module file already exists (resume case), reuse it.
    A fresh ``Session`` is created either way; the module's dependencies are
    re-executed on first ``import_snippet`` validation pass.
    """
    module_path = out_dir / corpus / "direct_arm.py"
    uri = f"irk:/auto_import_direct_arm_{corpus}"
    if not module_path.exists():
        bootstrap_working_module(module_path, uri=uri, ocse_path=str(ocse_path))

    session = Session(working_module_path=module_path, working_module_prefix="")
    session.load_dependency(str(ocse_path), prefix="ma")
    return session, module_path


# ---------------------------------------------------------------------------
# Per-snippet execution

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_stats(stats_path: Path, record: dict) -> None:
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open("a") as fp:
        fp.write(json.dumps(record, sort_keys=True) + "\n")


def _outcome_from_events(events: List[dict], default_ok: bool) -> Tuple[bool, str]:
    """Reduce per-attempt events to ``(ok, outcome_label)``.

    Mirrors the substrate's own terminal-event semantics: a trailing ``ok``
    event means success; ``gave_up`` / ``fork_pending`` / ``runner_exception``
    are failures; missing snippet is recorded as ``missing``.
    """
    for ev in reversed(events):
        et = ev.get("event")
        if et == "ok":
            return True, "ok"
        if et == "gave_up":
            return False, "gave_up"
        if et == "fork_pending":
            return False, "fork_pending"
        if et == "runner_exception":
            return False, "runner_exception"
        if et == "missing":
            return False, "missing"
    return default_ok, "ok" if default_ok else "fail"


def process_snippet(
    *,
    session: Session,
    working_module_path: Path,
    snippet_text_provider: Callable[[], "object"],
    corpus: str,
    snippet_id: str,
    snippet_type: str,
    stats_path: Path,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """Run a single snippet end-to-end, append exactly one JSONL line.

    Returns the record that was appended -- useful for the in-process smoke
    aggregation. ``snippet_text_provider`` is a thunk so missing snippets
    can be reported without forcing the .tex parse on the caller's side.
    """
    events: List[dict] = []
    started_at = _now_iso()
    snippet_text_length = 0
    ok = False

    try:
        snippet = snippet_text_provider()
        if snippet is None:
            events.append({"event": "missing"})
        else:
            snippet_text_length = len(snippet.text)
            ok = import_snippet(
                snippet,
                session=session,
                working_module_path=working_module_path,
                source_url=str(working_module_path),
                ask_user=fork_policy_first,
                on_progress=on_progress,
                events=events,
            )
    except _substrate.ForkPending as fp:
        # fork_policy_first never raises ForkPending, but keep this branch
        # for symmetry with the substrate's documented contract.
        events.append({"event": "fork_pending", "question": fp.question})
        ok = False
    except Exception as exc:  # noqa: BLE001 -- one bad snippet must not kill the run
        events.append({"event": "runner_exception", "message": str(exc)[:500]})
        ok = False

    final_ok, _ = _outcome_from_events(events, default_ok=ok)
    record = {
        "corpus": corpus,
        "snippet_id": snippet_id,
        "type": snippet_type,
        "ok": final_ok,
        "events": events,
        "snippet_text_length": snippet_text_length,
        "started_at": started_at,
        "finished_at": _now_iso(),
    }
    append_stats(stats_path, record)
    return record


# ---------------------------------------------------------------------------
# Runner / smoke / orchestration


def _emit(msg: str) -> None:
    print(msg, flush=True)


def _load_corpus_snippets_cache(corpora: List[str]) -> Dict[str, list]:
    """Parse each corpus's .tex once and return the snippet list per corpus."""
    cache: Dict[str, list] = {}
    for corpus in corpora:
        tex_path = CORPUS_TEX.get(corpus)
        if tex_path is None or not tex_path.exists():
            _emit(f"WARN: corpus tex not available for {corpus!r} ({tex_path}); skipping")
            cache[corpus] = []
            continue
        cache[corpus] = parse_snippets(tex_path.read_text())
    return cache


def _run_batch(
    *,
    planned: List[Tuple[str, str, str]],
    snippets_cache: Dict[str, list],
    sessions: Dict[str, Tuple[Session, Path]],
    stats_path: Path,
    label: str,
) -> List[dict]:
    """Iterate ``planned`` and process each snippet. Returns the record list."""
    records: List[dict] = []
    n = len(planned)
    for i, (corpus, snippet_id, snippet_type) in enumerate(planned, start=1):
        _emit(f"[{label} {i}/{n}] corpus={corpus} snippet_id={snippet_id} type={snippet_type}")
        session, module_path = sessions[corpus]
        snippet_list = snippets_cache[corpus]

        def _provider(sid=snippet_id, slist=snippet_list):
            return find_snippet(slist, sid)

        rec = process_snippet(
            session=session,
            working_module_path=module_path,
            snippet_text_provider=_provider,
            corpus=corpus,
            snippet_id=snippet_id,
            snippet_type=snippet_type,
            stats_path=stats_path,
            on_progress=lambda m, sid=snippet_id: _emit(f"    .. {sid}: {m}"),
        )
        records.append(rec)
        ok_marker = "OK " if rec["ok"] else "FAIL"
        _emit(f"    -> {ok_marker} events={len(rec['events'])}")
    return records


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", choices=["nichtlinear", "bernstein", "both"], default="both")
    ap.add_argument("--limit", type=int, default=0,
                    help="if > 0, process at most N snippets PER CORPUS")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--resume", action="store_true",
                    help="skip snippets already recorded in stats.jsonl (always on; "
                         "the flag also suppresses the smoke-first preflight)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Claude CLI model id (default: {DEFAULT_MODEL})")
    ap.add_argument("--ocse-path", type=Path, default=DEFAULT_OCSE_PATH,
                    help="path to the ocse math module loaded as the 'ma' dependency")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    cli = parse_args(argv)
    apply_opus_patch(cli.model)
    apply_validate_prefix_patch()

    if not cli.ocse_path.exists():
        print(f"ERROR: OCSE path does not exist: {cli.ocse_path}", file=sys.stderr)
        return 2

    selection = load_selection()
    corpora = ["nichtlinear", "bernstein"] if cli.corpus == "both" else [cli.corpus]

    cli.out_dir.mkdir(parents=True, exist_ok=True)
    stats_path = cli.out_dir / "stats.jsonl"

    snippets_cache = _load_corpus_snippets_cache(corpora)
    sessions: Dict[str, Tuple[Session, Path]] = {}
    for corpus in corpora:
        if not CORPUS_TEX.get(corpus, Path("/nonexistent")).exists():
            continue
        sessions[corpus] = bootstrap_corpus(cli.out_dir, corpus, cli.ocse_path)

    already_done = load_already_done(stats_path)
    _emit(f"DIRECT-ARM model={cli.model} out_dir={cli.out_dir} corpora={corpora} "
          f"already_done={len(already_done)}")

    planned_all = collect_planned(selection, corpora, cli.limit)
    planned = [p for p in planned_all if (p[0], p[1]) not in already_done
               and p[0] in sessions]

    if not planned:
        _emit("DIRECT-ARM: nothing to do (all selected snippets already processed).")
        return 0

    # Smoke-first preflight: only on truly fresh starts.
    smoke_eligible = (not already_done) and (cli.limit == 0) and (not cli.resume)
    if smoke_eligible:
        smoke_planned: List[Tuple[str, str, str]] = []
        for corpus in corpora:
            in_corpus = [p for p in planned if p[0] == corpus][:2]
            smoke_planned.extend(in_corpus)
        _emit(f"DIRECT-ARM SMOKE: running {len(smoke_planned)} snippet(s) ({corpora}, 2 each)")
        smoke_records = _run_batch(
            planned=smoke_planned,
            snippets_cache=snippets_cache,
            sessions=sessions,
            stats_path=stats_path,
            label="smoke",
        )
        smoke_ok = sum(1 for r in smoke_records if r["ok"])
        ok_rate = smoke_ok / len(smoke_records) if smoke_records else 0.0
        _emit(f"DIRECT-ARM SMOKE: ok={smoke_ok}/{len(smoke_records)} (ok_rate={ok_rate:.2f})")
        if ok_rate == 0.0:
            print(
                "DIRECT-ARM SMOKE FAILED: ok_rate=0 -- all smoke snippets failed.\n"
                "Likely causes: claude CLI missing or unauthorised, OCSE retrieval "
                "empty, prompt/model mismatch. See events in stats.jsonl.",
                file=sys.stderr,
            )
            return 3
        # remove smoke entries from main batch (they're now in stats.jsonl)
        smoke_keys = {(r["corpus"], r["snippet_id"]) for r in smoke_records}
        planned = [p for p in planned if (p[0], p[1]) not in smoke_keys]

    if planned:
        _emit(f"DIRECT-ARM MAIN: running {len(planned)} remaining snippet(s)")
        main_records = _run_batch(
            planned=planned,
            snippets_cache=snippets_cache,
            sessions=sessions,
            stats_path=stats_path,
            label="main",
        )
        main_ok = sum(1 for r in main_records if r["ok"])
        _emit(f"DIRECT-ARM MAIN: ok={main_ok}/{len(main_records)}")

    # final tally over the fresh stats.jsonl
    final_done = load_already_done(stats_path)
    _emit(f"DIRECT-ARM DONE: stats.jsonl now has {len(final_done)} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
