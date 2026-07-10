"""Tokenfree aggregation helpers for the FNL-vs-direct dry-run output.

Operates on event-record dicts produced by the mock dry-run harness (see
``latex_bulk_dry_run.py``). The event-type vocabulary mirrors the events
emitted by :func:`pyirk.authoring.import_one_statement` -- ``retrieval``,
``fork``, ``validation_fail``, ``key_remap``, ``nonascii``,
``scope_reopen``, ``timeout``, ``ok`` (plus ``gave_up`` / ``malformed`` /
``append_fail`` / ``fork_pending`` as observed). Unknown / absent event
types are counted as zero, not invented.

The module is pure: no I/O, no network, no PRNG, no clock.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List, Mapping


_TRACKED_COUNT_EVENTS = (
    "ok",
    "validation_fail",
    "timeout",
    "nonascii",
    "fork",
    "key_remap",
    "scope_reopen",
    "malformed",
    "append_fail",
    "gave_up",
    "fork_pending",
    "retrieval",
)


def _empty_aggregate() -> dict:
    base = {
        "n_snippets": 0,
        "validity_rate": 0.0,
        "fork_rate": 0.0,
        "retry_rate": 0.0,
        "ok_count": 0,
        "validation_fail_count": 0,
        "timeout_count": 0,
        "nonascii_count": 0,
        "fork_count": 0,
        "per_type_validity": {},
        "per_type_counts": {},
        "per_snippet": [],
    }
    return base


def aggregate_events(records: Iterable[Mapping]) -> dict:
    """Aggregate a list of per-snippet event-records into a metrics dict.

    Each record is a dict with at least ``snippet_id``, ``type``,
    ``outcome`` (string; ``ok`` means a successful round-trip), and
    ``events`` (a list of event-dicts each with an ``event`` key).
    """
    records = list(records)
    out = _empty_aggregate()
    n = len(records)
    if n == 0:
        return out

    event_counts: Counter = Counter()
    per_type_total: Counter = Counter()
    per_type_ok: Counter = Counter()
    fork_records = 0
    retry_records = 0
    per_snippet: List[dict] = []

    for rec in records:
        events = list(rec.get("events", []) or [])
        outcome = rec.get("outcome")
        type_tag = rec.get("type", "unknown")
        per_type_total[type_tag] += 1
        had_fail = False
        had_fork = False
        attempts: set = set()
        for ev in events:
            kind = ev.get("event")
            if kind in _TRACKED_COUNT_EVENTS:
                event_counts[kind] += 1
            if kind == "validation_fail":
                had_fail = True
            elif kind == "fork":
                had_fork = True
            attempt = ev.get("attempt")
            if attempt is not None:
                attempts.add(attempt)
        if outcome == "ok":
            per_type_ok[type_tag] += 1
        if had_fork:
            fork_records += 1
        # a retry happened either when more than one attempt-numbered event
        # appears, or when a validation_fail / timeout / fork was followed by
        # any further attempt at all
        if len(attempts) > 1 or had_fail:
            retry_records += 1
        per_snippet.append(
            {
                "snippet_id": rec.get("snippet_id"),
                "corpus": rec.get("corpus"),
                "type": type_tag,
                "outcome": outcome,
                "n_events": len(events),
                "had_validation_fail": had_fail,
                "had_fork": had_fork,
            }
        )

    out["n_snippets"] = n
    out["ok_count"] = event_counts.get("ok", 0)
    out["validation_fail_count"] = event_counts.get("validation_fail", 0)
    out["timeout_count"] = event_counts.get("timeout", 0)
    out["nonascii_count"] = event_counts.get("nonascii", 0)
    out["fork_count"] = event_counts.get("fork", 0)
    n_ok_records = sum(1 for r in records if r.get("outcome") == "ok")
    out["validity_rate"] = n_ok_records / n
    out["fork_rate"] = fork_records / n
    out["retry_rate"] = retry_records / n
    out["per_type_validity"] = {
        t: (per_type_ok[t] / per_type_total[t]) if per_type_total[t] else 0.0
        for t in sorted(per_type_total)
    }
    out["per_type_counts"] = {t: per_type_total[t] for t in sorted(per_type_total)}
    out["per_snippet"] = per_snippet
    return out


def summarize_by_corpus(records: Iterable[Mapping], selection: Mapping) -> dict:
    """Bucket records by corpus name and aggregate each bucket separately.

    ``selection`` is the parsed ``snippet_selection.json`` dict; its
    ``corpora`` keys define the corpora to surface (so an empty bucket still
    appears in the output as the zero-aggregate, which keeps downstream
    tabulation stable).
    """
    records = list(records)
    out: dict = {}
    corpora_keys = list((selection or {}).get("corpora", {}).keys())
    seen = set(corpora_keys)
    for c in corpora_keys:
        subset = [r for r in records if r.get("corpus") == c]
        out[c] = aggregate_events(subset)
    # any corpus that appears in records but not in selection still gets
    # surfaced; otherwise data could silently fall through
    extra = sorted({r.get("corpus") for r in records if r.get("corpus") not in seen and r.get("corpus") is not None})
    for c in extra:
        subset = [r for r in records if r.get("corpus") == c]
        out[c] = aggregate_events(subset)
    return out
