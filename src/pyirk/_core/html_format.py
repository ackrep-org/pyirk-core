"""
HTML-formatting helpers extracted from :mod:`pyirk.core`.

PEP 563 (``from __future__ import annotations``) is active so that all
forward-reference annotations (``Entity``, etc.) become lazy strings rather
than immediately evaluated names.
"""

from __future__ import annotations

from urllib.parse import quote


__all__ = ["format_entity_html"]


def format_entity_html(e: Entity):
    short_txt = f'<span class="entity">{e.R1}</span>'
    detailed_txt = f'<span class="entity">{e.short_key}["{e.R1}"]</span>'

    return f'<span class="js-toggle" data-short-txt="{quote(short_txt)}" data-detailed-txt="{quote(detailed_txt)}">{short_txt}</span>'
