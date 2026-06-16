"""Lean (mathlib4) source adapter for ``pyirk.authoring``.

Fetches a Lean source file, extracts theorem *statements* (proofs are
explicitly dropped), and drives them through the generic import loop.
"""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from . import (
    Session,
    ask_user_via_stdin,
    import_one_statement,
)


@dataclass
class LeanTheorem:
    name: str
    namespace: str
    docstring: str  # the ``/-- ... -/`` immediately before the theorem (if any)
    statement: str  # full type signature, i.e. everything between ``theorem`` and ``:=``/``by``
    raw: str  # raw source slice for reference


def fetch_lean_source(url_or_path: str) -> str:
    """Fetch ``.lean`` source from an http(s) URL or a local path."""
    if url_or_path.startswith(("http://", "https://")):
        # mathlib4_docs URLs and raw GitHub URLs both work
        with urllib.request.urlopen(url_or_path) as r:  # noqa: S310
            return r.read().decode("utf-8")
    return Path(url_or_path).read_text()


# matches a theorem or lemma at start-of-line, optionally preceded by a
# ``/-- ... -/`` docstring also at start-of-line, immediately before. The body
# extends up to the start of the proof (``:=`` or ``by``). ``^`` anchors are
# essential -- without them, the regex matches ``theorem`` inside URLs / block
# comments and the lazy ``rest`` engulfs subsequent real theorems up to the
# next ``:=``. ``lemma`` is mathlib's predominant keyword (many files contain
# no ``theorem`` at all, e.g. Analysis/ODE/Transform.lean); both are
# semantically identical in Lean 4 / mathlib.
# The ``doc`` group must not skip over a ``-/``: with a plain lazy ``.*?``
# (DOTALL) a docstring belonging to e.g. a ``def`` backtracks across its own
# ``-/`` and stretches to the next ``-/`` that *is* followed by a theorem,
# silently engulfing every theorem in between (observed on
# LinearAlgebra/Trace.lean: 14 of 35 declarations parsed).
_THEOREM_RE = re.compile(
    r"(?:^/--[ \t]*(?P<doc>(?:(?!-/).)*?)[ \t]*-/[ \t]*\n)?"
    r"^(?:theorem|lemma)[ \t]+(?P<name>\S+)[ \t]*(?P<rest>.*?)(?=[ \t]*:=|[ \t]*\n[ \t]*by\b|\nend\b)",
    re.DOTALL | re.MULTILINE,
)
_NAMESPACE_RE = re.compile(r"^[ \t]*namespace[ \t]+(\S+)", re.MULTILINE)


def parse_theorems(source: str) -> List[LeanTheorem]:
    """Extract theorem statements from a Lean source string.

    Each theorem is attributed to the most recent ``namespace X`` declaration
    that precedes it in the source, so multi-namespace files (the common case
    in mathlib) attribute theorems correctly.
    """
    # collect (offset, namespace) pairs in source order
    namespace_changes = [(m.start(), m.group(1)) for m in _NAMESPACE_RE.finditer(source)]

    def namespace_at(offset: int) -> str:
        current = ""
        for start, name in namespace_changes:
            if start > offset:
                break
            current = name
        return current

    out: List[LeanTheorem] = []
    for m in _THEOREM_RE.finditer(source):
        name = m.group("name")
        rest = (m.group("rest") or "").strip()
        statement = f"theorem {name} {rest}".rstrip()
        docstring = (m.group("doc") or "").strip()
        out.append(
            LeanTheorem(
                name=name,
                namespace=namespace_at(m.start()),
                docstring=docstring,
                statement=statement,
                raw=m.group(0),
            )
        )
    return out


def find_theorem(theorems: List[LeanTheorem], name: str) -> Optional[LeanTheorem]:
    for t in theorems:
        if t.name == name:
            return t
    return None


def import_theorem(
    theorem: LeanTheorem,
    session: Session,
    working_module_path: Path,
    source_url: str = "",
    ask_user: Callable[[str, list], str] = ask_user_via_stdin,
    on_progress: Optional[Callable[[str], None]] = None,
    events: Optional[list] = None,
) -> bool:
    """Drive one Lean theorem through the generic import loop."""
    source_info = f"Lean / mathlib4: {theorem.namespace}.{theorem.name}"
    if source_url:
        source_info += f" ({source_url})"
    theorem_text = theorem.statement
    if theorem.docstring:
        theorem_text = f"/-- {theorem.docstring} -/\n{theorem_text}"

    ok, _ = import_one_statement(
        session=session,
        theorem_text=theorem_text,
        source_info=source_info,
        working_module_path=working_module_path,
        ask_user=ask_user,
        extra_query_text=theorem.docstring,
        on_progress=on_progress,
        events=events,
    )
    return ok
