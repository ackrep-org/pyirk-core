"""LaTeX source adapter for ``pyirk.authoring``.

Fetches a LaTeX source file, segments it at ``\\snippet{ID}`` markers, and
drives each snippet body through the generic import loop. Snippet IDs are
alphanumeric (e.g. ``"3"``, ``"17i"``) -- filtering of suffix-tagged
``ignored`` snippets is the caller's responsibility, not the adapter's.
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
class LatexSnippet:
    snippet_id: str  # alphanumeric, e.g. "3" or "17i"
    text: str  # verbatim LaTeX body between this marker and the next
    raw: str  # entire slice including the leading marker


def fetch_latex_source(url_or_path: str) -> str:
    """Fetch ``.tex`` source from an http(s) URL or a local path."""
    if url_or_path.startswith(("http://", "https://")):
        with urllib.request.urlopen(url_or_path) as r:  # noqa: S310
            return r.read().decode("utf-8")
    return Path(url_or_path).read_text()


_SNIPPET_RE = re.compile(r"\\snippet\{(?P<id>[A-Za-z0-9]+)\}")


def parse_snippets(source: str) -> List[LatexSnippet]:
    """Segment a LaTeX source string at ``\\snippet{ID}`` markers.

    Each snippet's body is everything from the end of its marker up to (but
    not including) the next ``\\snippet{...}`` marker, or end-of-file for the
    last snippet. Content before the first marker is discarded.
    """
    matches = list(_SNIPPET_RE.finditer(source))
    out: List[LatexSnippet] = []
    for i, m in enumerate(matches):
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        raw_end = body_end
        out.append(
            LatexSnippet(
                snippet_id=m.group("id"),
                text=source[body_start:body_end],
                raw=source[m.start():raw_end],
            )
        )
    return out


def find_snippet(snippets: List[LatexSnippet], snippet_id: str) -> Optional[LatexSnippet]:
    for s in snippets:
        if s.snippet_id == snippet_id:
            return s
    return None


def import_snippet(
    snippet: LatexSnippet,
    session: Session,
    working_module_path: Path,
    source_url: str = "",
    ask_user: Callable[[str, list], str] = ask_user_via_stdin,
    on_progress: Optional[Callable[[str], None]] = None,
    events: Optional[list] = None,
) -> bool:
    """Drive one LaTeX snippet through the generic import loop."""
    source_info = f"LaTeX: {snippet.snippet_id}"
    if source_url:
        source_info += f" ({source_url})"

    ok, _ = import_one_statement(
        session=session,
        theorem_text=snippet.text,
        source_info=source_info,
        working_module_path=working_module_path,
        ask_user=ask_user,
        extra_query_text=snippet.text,
        on_progress=on_progress,
        events=events,
    )
    return ok
