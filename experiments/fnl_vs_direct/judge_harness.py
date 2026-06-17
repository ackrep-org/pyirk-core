"""LLM-as-judge harness for the ``fnl_vs_direct`` experiment.

Compares a ``direct-pyirk`` candidate against the gold material per snippet
and asks the judge for a fixed-scale verdict (``equivalent`` / ``partial`` /
``wrong``) plus a short justification, returned as structured JSON.

Two corpora:

* Corpus A (``nichtlinear``): the prompt carries both ``fnl_gold`` and
  ``pyirk_gold_block`` (the snippet's slice of the gold pyirk module).
* Corpus B (``bernstein``): the prompt carries only ``fnl_gold``.

The harness ships two judge clients:

* :class:`MockJudgeClient` -- deterministic, rule-based, tokenfree.  All
  tests run against this stand-in.
* :class:`OpusJudgeClient` -- skeleton that wires up to ``anthropic`` /
  ``claude-opus-4-7`` with ``response_format=json``.  Constructible in
  every environment; ``.judge(req)`` raises a clear ``RuntimeError`` up
  front when ``ANTHROPIC_API_KEY`` is missing or the SDK is not
  installed, so a Phase-7 live run cannot crash halfway through.

Outputs are written as JSONL via :func:`judge_all`, append-resume-safe:
existing ``(corpus, snippet_id)`` records are skipped on re-runs.

CLI::

    python -m experiments.fnl_vs_direct.judge_harness \\
        --selection PATH --direct-dir PATH --gold-fnl-dir PATH \\
        [--gold-pyirk PATH] --latex-dir PATH \\
        --client mock|opus --out PATH \\
        [--limit N] [--corpus nichtlinear|bernstein|both]

``--client mock`` is strictly tokenfree.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Protocol


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = """You are an expert mathematical-content judge for the
``pyirk`` formal-knowledge framework.  Given a small LaTeX snippet, one or
two gold encodings, and a candidate ``direct-pyirk`` encoding, decide
whether the candidate encodes the **same mathematics** as the gold.

Snippet id: {snippet_id}
Corpus: {corpus}

LaTeX source (verbatim):
{latex_source}

Formalized natural-language gold (FNL):
{fnl_gold}
{pyirk_gold_block}
Candidate direct-pyirk encoding:
{direct_pyirk}

Task: decide whether ``direct-pyirk`` encodes the same mathematics as the
gold material.  Use a fixed three-level scale:

* ``equivalent`` -- same items, same relations, same logical content
  modulo cosmetic differences (key allocation, label wording).
* ``partial``    -- core content matches but at least one item, relation,
  or logical link is missing, extra, or off; the encoding is on the
  right track but not faithful.
* ``wrong``      -- the candidate encodes different mathematics, contradicts
  the gold, or is too underspecified to count.

Respond with **exactly one** JSON object matching this schema and nothing
else (no prose, no fenced code block):

{{
  "snippet_id": "{snippet_id}",
  "corpus": "{corpus}",
  "verdict": "equivalent" | "partial" | "wrong",
  "confidence": <float between 0.0 and 1.0>,
  "reason": "<one to three sentences>",
  "differences": ["<short bullet>", "..."]
}}
"""


PYIRK_GOLD_SECTION_TEMPLATE = """
Gold pyirk module (snippet slice):
{pyirk_gold_block}
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class JudgeRequest:
    snippet_id: str
    corpus: str
    latex_source: str
    fnl_gold: str
    pyirk_gold_block: Optional[str]  # None for corpus B
    direct_pyirk: str


@dataclass
class JudgeResult:
    snippet_id: str
    corpus: str
    verdict: str  # one of "equivalent", "partial", "wrong"
    confidence: float
    reason: str
    differences: List[str] = field(default_factory=list)
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "snippet_id": self.snippet_id,
            "corpus": self.corpus,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reason": self.reason,
            "differences": list(self.differences),
            "raw_response": self.raw_response,
        }


VALID_VERDICTS = ("equivalent", "partial", "wrong")


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def build_prompt(req: JudgeRequest) -> str:
    """Fill the template for a request; the pyirk-gold section is omitted
    for corpus B (no empty header left behind).
    """
    if req.pyirk_gold_block is None:
        pyirk_block = ""
    else:
        pyirk_block = PYIRK_GOLD_SECTION_TEMPLATE.format(
            pyirk_gold_block=req.pyirk_gold_block
        )
    return JUDGE_PROMPT_TEMPLATE.format(
        snippet_id=req.snippet_id,
        corpus=req.corpus,
        latex_source=req.latex_source,
        fnl_gold=req.fnl_gold,
        pyirk_gold_block=pyirk_block,
        direct_pyirk=req.direct_pyirk,
    )


# ---------------------------------------------------------------------------
# JudgeClient protocol + implementations
# ---------------------------------------------------------------------------


class JudgeClient(Protocol):
    def judge(self, req: JudgeRequest) -> JudgeResult: ...


def _ast_label_set(source: str) -> List[str]:
    """Collect R1 labels from top-level ``p.create_item(...)`` calls.

    Pure, deterministic, no execution; mirrors the very lightweight
    structural diff used by the rule-based mock judge.  Returns an
    unsorted list (label may repeat); callers normalise as needed.
    """
    labels: List[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return labels
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        call = stmt.value
        if not isinstance(call, ast.Call):
            continue
        for kw in call.keywords:
            if kw.arg is None:
                continue
            parts = kw.arg.split("__")
            if not parts or parts[0] != "R1":
                continue
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                labels.append(kw.value.value.strip().lower())
    return labels


def _normalised(text: str) -> str:
    return " ".join(text.split()).strip().lower()


class MockJudgeClient:
    """Deterministic rule-based judge.

    Rules (in order):

    1. If ``direct_pyirk`` is byte-identical to ``fnl_gold`` (or to
       ``pyirk_gold_block`` when present), verdict is ``equivalent``.
    2. Otherwise compute the symmetric difference of the R1-label
       multisets between gold and direct.  If the diff is empty,
       verdict is ``equivalent``.  More than 3 differences -> ``wrong``.
       Anything in between -> ``partial``.

    No RNG, no clock, no network.  Identical input -> identical output.
    """

    def judge(self, req: JudgeRequest) -> JudgeResult:
        if req.pyirk_gold_block is not None:
            gold_text = req.pyirk_gold_block
        else:
            gold_text = req.fnl_gold

        if _normalised(req.direct_pyirk) == _normalised(gold_text):
            return JudgeResult(
                snippet_id=req.snippet_id,
                corpus=req.corpus,
                verdict="equivalent",
                confidence=1.0,
                reason="Mock: candidate text is identical to the gold reference.",
                differences=[],
                raw_response="mock:identical",
            )

        gold_labels = sorted(_ast_label_set(gold_text))
        direct_labels = sorted(_ast_label_set(req.direct_pyirk))
        missing = [l for l in gold_labels if l not in direct_labels]
        extra = [l for l in direct_labels if l not in gold_labels]
        diffs = [f"missing: {l}" for l in missing] + [f"extra: {l}" for l in extra]

        if not diffs:
            verdict = "equivalent"
            confidence = 0.9
            reason = "Mock: gold and direct have the same R1-label set."
        elif len(diffs) > 3:
            verdict = "wrong"
            confidence = 0.9
            reason = f"Mock: label diff has {len(diffs)} entries (> 3)."
        else:
            verdict = "partial"
            confidence = 0.7
            reason = f"Mock: label diff has {len(diffs)} entries (<= 3)."

        return JudgeResult(
            snippet_id=req.snippet_id,
            corpus=req.corpus,
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            differences=diffs,
            raw_response=f"mock:diff:{len(diffs)}",
        )


OPUS_MODEL_ID = "claude-opus-4-7"


class OpusJudgeClient:
    """Skeleton client for the live Opus judge.

    Construction is always safe (no network, no env access).  The actual
    call inside :meth:`judge` checks ``ANTHROPIC_API_KEY`` and that the
    ``anthropic`` SDK is importable **before** any network attempt, and
    raises a clear :class:`RuntimeError` otherwise.  Phase 7 instantiates
    this client and calls ``.judge``; this file does not call it.
    """

    def __init__(self, model: str = OPUS_MODEL_ID, max_tokens: int = 1024):
        self.model = model
        self.max_tokens = max_tokens

    def judge(self, req: JudgeRequest) -> JudgeResult:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OpusJudgeClient.judge: ANTHROPIC_API_KEY is not set; "
                "refusing to make an LLM call. Set the env var or run "
                "with --client mock for tokenfree mode."
            )
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "OpusJudgeClient.judge: the `anthropic` SDK is not "
                "installed in this environment; install it before running "
                "the live judge."
            ) from exc

        client = anthropic.Anthropic(api_key=api_key)
        prompt = build_prompt(req)
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # anthropic SDK >= 0.21 returns a structured Message with .content
        # as a list of TextBlock; we concatenate the text payloads.
        text_parts = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                text_parts.append(text)
        raw_text = "".join(text_parts).strip()
        return _parse_judge_json(raw_text, req)


def _parse_judge_json(raw_text: str, req: JudgeRequest) -> JudgeResult:
    """Parse a JSON object from the model's response.

    Tolerates ```json fenced code blocks but expects a single JSON object.
    Raises :class:`RuntimeError` on shape violations; the caller decides
    whether to retry or to record the failure.
    """
    text = raw_text.strip()
    fence = re.match(r"^```(?:json)?\s*\n(.*?)```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"OpusJudgeClient.judge: response is not valid JSON: {exc}"
        )
    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise RuntimeError(
            f"OpusJudgeClient.judge: verdict {verdict!r} not in {VALID_VERDICTS}"
        )
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return JudgeResult(
        snippet_id=str(payload.get("snippet_id", req.snippet_id)),
        corpus=str(payload.get("corpus", req.corpus)),
        verdict=verdict,
        confidence=confidence,
        reason=str(payload.get("reason", "")),
        differences=[str(d) for d in payload.get("differences", []) or []],
        raw_response=raw_text,
    )


# ---------------------------------------------------------------------------
# JSONL writer with resume-safety
# ---------------------------------------------------------------------------


def _existing_keys(out_path: Path) -> set:
    keys: set = set()
    if not out_path.exists():
        return keys
    with out_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            corpus = rec.get("corpus")
            sid = rec.get("snippet_id")
            if corpus is not None and sid is not None:
                keys.add((str(corpus), str(sid)))
    return keys


def judge_all(
    client: JudgeClient,
    requests: Iterable[JudgeRequest],
    out_path: os.PathLike,
) -> List[JudgeResult]:
    """Run the judge over ``requests``, appending JSONL to ``out_path``.

    Resume-safe: existing records with the same ``(corpus, snippet_id)``
    key are skipped (not re-judged).  Returns the list of results actually
    produced in **this** call (not the cached ones from earlier runs).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _existing_keys(out_path)
    produced: List[JudgeResult] = []
    with out_path.open("a", encoding="utf-8") as fp:
        for req in requests:
            key = (str(req.corpus), str(req.snippet_id))
            if key in seen:
                continue
            result = client.judge(req)
            fp.write(json.dumps(result.to_dict(), sort_keys=True) + "\n")
            fp.flush()
            seen.add(key)
            produced.append(result)
    return produced


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


_SID_NUM_RE = re.compile(r"^(\d+)(.*)$")


def _snippet_sort_key(snippet_id: str) -> tuple:
    m = _SID_NUM_RE.match(snippet_id)
    if m:
        return (0, int(m.group(1)), m.group(2))
    return (1, snippet_id)


def _build_client(name: str) -> JudgeClient:
    if name == "mock":
        return MockJudgeClient()
    if name == "opus":
        return OpusJudgeClient()
    raise ValueError(f"unknown client {name!r} (expected 'mock' or 'opus')")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_optional(path: Optional[Path]) -> str:
    if path is None or not path.exists():
        return ""
    return _read_text(path)


def _extract_pyirk_gold_block(gold_pyirk_path: Optional[Path], snippet_id: str) -> Optional[str]:
    """Return the substring of the gold pyirk module belonging to ``snippet_id``.

    Uses the same ``snippet(<id>)`` marker convention as the structural
    diff: text from the marker line up to (but not including) the next
    ``snippet(...)`` marker.  Returns ``None`` if no gold file is given
    or no marker matches.
    """
    if gold_pyirk_path is None or not gold_pyirk_path.exists():
        return None
    src = _read_text(gold_pyirk_path)
    pattern = re.compile(
        r'R1__has_label\s*=\s*"snippet\(([^)]+)\)"',
    )
    matches = list(pattern.finditer(src))
    starts: dict = {}
    for m in matches:
        starts.setdefault(m.group(1), []).append(m.start())
    if snippet_id not in starts:
        return None
    start = starts[snippet_id][0]
    # find next snippet marker after `start`
    next_starts = [m.start() for m in matches if m.start() > start]
    end = next_starts[0] if next_starts else len(src)
    line_start = src.rfind("\n", 0, start) + 1
    return src[line_start:end].rstrip()


def _build_requests_for_corpus(
    *,
    corpus: str,
    selection: dict,
    direct_dir: Path,
    gold_fnl_dir: Path,
    gold_pyirk_path: Optional[Path],
    latex_dir: Optional[Path],
    limit: int,
) -> List[JudgeRequest]:
    entries = list(selection.get("corpora", {}).get(corpus, []))
    entries.sort(key=lambda e: _snippet_sort_key(str(e["snippet_id"])))
    if limit and limit > 0:
        entries = entries[:limit]
    requests: List[JudgeRequest] = []
    for entry in entries:
        sid = str(entry["snippet_id"])
        direct_path = direct_dir / f"{corpus}_{sid}.py"
        if not direct_path.exists():
            # missing direct -> empty source so judge can still see absence
            direct_text = ""
        else:
            direct_text = _read_text(direct_path)
        fnl_path = gold_fnl_dir / f"{corpus}_{sid}.md"
        fnl_text = _read_optional(fnl_path) if fnl_path.exists() else str(
            entry.get("fnl_excerpt", "")
        )
        latex_text = ""
        if latex_dir is not None:
            latex_path = latex_dir / f"{corpus}_{sid}.tex"
            latex_text = _read_optional(latex_path)
        pyirk_block = (
            _extract_pyirk_gold_block(gold_pyirk_path, sid)
            if corpus == "nichtlinear"
            else None
        )
        requests.append(
            JudgeRequest(
                snippet_id=sid,
                corpus=corpus,
                latex_source=latex_text,
                fnl_gold=fnl_text,
                pyirk_gold_block=pyirk_block,
                direct_pyirk=direct_text,
            )
        )
    return requests


def _parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection", required=True, type=Path)
    ap.add_argument("--direct-dir", required=True, type=Path)
    ap.add_argument("--gold-fnl-dir", required=True, type=Path)
    ap.add_argument("--gold-pyirk", type=Path, default=None,
                    help="path to the corpus-A gold pyirk module (nichtlinear only)")
    ap.add_argument("--latex-dir", type=Path, default=None,
                    help="optional directory with <corpus>_<id>.tex sources")
    ap.add_argument("--client", choices=["mock", "opus"], default="mock")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--corpus",
        choices=["nichtlinear", "bernstein", "both"],
        default="both",
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    cli = _parse_args(argv)
    selection = json.loads(cli.selection.read_text(encoding="utf-8"))
    corpora = ["nichtlinear", "bernstein"] if cli.corpus == "both" else [cli.corpus]

    client = _build_client(cli.client)

    requests: List[JudgeRequest] = []
    for corpus in corpora:
        requests.extend(
            _build_requests_for_corpus(
                corpus=corpus,
                selection=selection,
                direct_dir=cli.direct_dir,
                gold_fnl_dir=cli.gold_fnl_dir,
                gold_pyirk_path=cli.gold_pyirk,
                latex_dir=cli.latex_dir,
                limit=cli.limit,
            )
        )

    produced = judge_all(client, requests, cli.out)
    print(
        f"JUDGE-HARNESS: client={cli.client} n_produced={len(produced)} "
        f"out={cli.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
