"""LaTeX source adapter for ``pyirk.authoring``.

Fetches a LaTeX source file, segments it at ``\\snippet{ID}`` markers, and
drives each snippet body through the generic import loop. Snippet IDs are
alphanumeric (e.g. ``"3"``, ``"17i"``) -- filtering of suffix-tagged
``ignored`` snippets is the caller's responsibility, not the adapter's.
"""

from __future__ import annotations

import contextlib
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, List, Optional

from .. import authoring as _substrate
from . import (
    Session,
    ask_user_via_stdin,
    import_one_statement,
)


# ---------------------------------------------------------------------------
# Math-tuned prompt header
#
# Mathematical-textbook snippets (corpora ``nichtlinear`` / ``bernstein``) are
# dominated by class declarations, notation introductions, operator and
# instance definitions -- NOT by typed Lean theorem statements. The Lean-tuned
# ``PROMPT_HEADER`` in ``pyirk.authoring`` shows a Pythagorean iff theorem as
# its only worked example; that pushes the LLM toward the I17/I15 three-scope
# pattern even when the snippet just introduces a set class or fixes a LaTeX
# symbol. ``LATEX_PROMPT_HEADER`` replaces the worked example with a math-book
# passage covering (a) a subclass declaration reusing a builtin class,
# (b) a binary operator with explicit domain/range AND LaTeX notation via
# ``R24__has_LaTeX_string``, and (c) a named instance with its symbol. The
# iff/implies pattern is still mentioned in the idiom list so propositional
# snippets (e.g. Bernstein 14/15 equivalence statements) remain encodable.

LATEX_PROMPT_HEADER = """You are mapping the *content* of a snippet from a mathematical
textbook (LaTeX source, in German or English) into a pyirk content module.
The snippet typically introduces a new class, fixes notation, declares an
operator/relation, names an instance, or states a proposition. Proofs are
out of scope. Reuse existing entities aggressively; only introduce a new
local item if no entity in the listings below matches the needed concept.

CRITICAL: your output is *appended* to a working module that is already
fully bootstrapped. The module already executes ``import pyirk as p``,
loads its dependencies (e.g. ``ma = p.irkloader.load_mod_from_path(...,
prefix="ma")``), and has called ``p.start_mod(__URI__)``. Do NOT include
``import pyirk``, ``load_mod_from_path``, ``KeyManager``, ``register_mod``,
``start_mod``, or ``end_mod`` in your code block. Produce ONLY the new
``create_item`` / ``create_relation`` / ``with ...scope(...) as st:`` blocks.

Canonical example: a short math-book passage introducing a subclass of an
existing set class, a binary operator on sets with its LaTeX notation, and
a named instance with its symbol. Treat this as the structure you must
follow for snippets that introduce classes / notation / operators /
instances. For snippets that state an "if and only if" or an implication,
follow the iff/implication pattern documented in the rules below.

```python
# A new subclass of an existing OCSE class. Reuse the builtin
# ``p.I13["mathematical set"]`` rather than inventing a fresh "set" item.
I999 = p.create_item(
    R1__has_label="bounded set",
    R2__has_description="A set whose elements admit a uniform bound.",
    R3__is_subclass_of=p.I13["mathematical set"],
)
# A binary operator with explicit domain/range AND LaTeX notation via R24.
# Use ``arg1`` / ``arg2`` as positional placeholders inside the LaTeX string,
# and a Python raw string so backslashes survive.
I1000 = p.create_item(
    R1__has_label="set intersection",
    R2__has_description="binary operator: intersection of two sets",
    R4__is_instance_of=p.I8["mathematical operation with arity 2"],
    R8__has_domain_of_argument_1=p.I13["mathematical set"],
    R9__has_domain_of_argument_2=p.I13["mathematical set"],
    R11__has_range_of_result=p.I13["mathematical set"],
    R24__has_LaTeX_string=r"$arg1 \\cap arg2$",
)
# A named instance with its LaTeX symbol.
I1001 = p.create_item(
    R1__has_label="empty set",
    R2__has_description="The set with no elements.",
    R4__is_instance_of=p.I13["mathematical set"],
    R24__has_LaTeX_string=r"$\\varnothing$",
)
```

Key idioms to copy from that example:
* Short keys MUST match ``IXXXX`` / ``RXXXX`` where XXXX is digits
  (e.g. ``I999``, ``R24``). Do NOT use descriptive Python names like
  ``I_bounded_set``; the key resolver will reject them.
* ``R3__is_subclass_of`` is the class-of-class relation.
  ``R4__is_instance_of`` is the member-of-class relation. Do not confuse.
* For NOTATION introductions (e.g. "we write $\\SX \\cap \\SY$"), attach the
  LaTeX form via ``R24__has_LaTeX_string=r"..."``. Use a raw string so
  backslashes are not interpreted. Refer to operator arguments by
  positional placeholders ``arg1``, ``arg2`` inside the LaTeX string.
* For CLASS / SUBCLASS introductions (e.g. "A set ... is *finite* if ...",
  "Der Vektorraum heisst beschraenkt, wenn ..."), use
  ``p.create_item(R1__has_label=..., R3__is_subclass_of=<parent>)``. When no
  more specific parent matches, reuse ``p.I13["mathematical set"]`` or the
  generic mathematical-object class.
* For OPERATORS, pick the arity item: unary = ``p.I7``, binary = ``p.I8``,
  ternary = ``p.I9``. Always set ``R8`` / (``R9``) / (``R10``) for the
  argument domains and ``R11`` for the result range.
* For named INSTANCES (a specific set, matrix, constant), use
  ``R4__is_instance_of=<class entity>`` and attach the symbol via
  ``R24__has_LaTeX_string``.
* Bilingual (German + English) labels are common in these corpora. Put the
  *English* label (or the one most likely to align with OCSE) in
  ``R1__has_label`` and inline the other language in ``R2__has_description``
  unless the dependency index advertises an alt-label relation.
* When the snippet states a PROPOSITION (if-and-only-if, implies), follow
  the substrate's iff/implication pattern: a fresh
  ``R4__is_instance_of=p.I17["equivalence proposition"]`` (or
  ``p.I15["implication proposition"]``) item with three scopes
  (``setting`` / ``premise`` / ``assertion``). Universally quantified
  variables go into ``setting`` via ``p.uq_instance_of(<type entity>)`` and
  equations via ``st.new_equation(lhs=..., rhs=...)``.
* For cross-module relations use the prefix attribute form, e.g.
  ``a.ma__R2495__has_length`` (NOT ``a.R2495__has_length``).
* Non-ASCII characters (math operators like ``\\cap``, German umlauts) are
  fine inside string literals and descriptions but MUST NOT appear in the
  code itself; use ASCII operators (``**``, ``+``, ``*``) for equations.
"""


@contextlib.contextmanager
def _swap_prompt_header(new_header: str) -> Iterator[None]:
    """Temporarily replace ``pyirk.authoring.PROMPT_HEADER`` for the duration
    of an :func:`import_one_statement` call.

    The substrate's ``build_import_prompt`` references the module-level
    ``PROMPT_HEADER`` by name at call time, so reassigning the attribute on
    the module propagates to the next prompt build. Restored on exit so other
    adapters (e.g. ``pyirk.authoring.lean``) keep seeing the Lean-tuned
    header.
    """
    saved = _substrate.PROMPT_HEADER
    _substrate.PROMPT_HEADER = new_header
    try:
        yield
    finally:
        _substrate.PROMPT_HEADER = saved


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
    """Drive one LaTeX snippet through the generic import loop.

    The substrate's :data:`pyirk.authoring.PROMPT_HEADER` is Lean-tuned (its
    worked example is a Pythagorean iff theorem). LaTeX-math snippets are
    dominated by class / notation / operator / instance declarations, so the
    adapter swaps in :data:`LATEX_PROMPT_HEADER` for the duration of the
    substrate call.
    """
    source_info = f"LaTeX: {snippet.snippet_id}"
    if source_url:
        source_info += f" ({source_url})"

    with _swap_prompt_header(LATEX_PROMPT_HEADER):
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
