"""
PrefixShortCut helper extracted from :mod:`pyirk.core`.

The class defined here is import-time safe: it accesses ``ds`` lazily via the
``_core`` module object, whose attributes are only read at call time.
"""

from __future__ import annotations

from pyirk.auxiliary import UnknownPrefixError

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the method bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = [
    "PrefixShortCut",
]


class PrefixShortCut:
    def __getattribute__(self, prefix_name: str) -> object:
        if prefix_name not in _core.ds.uri_prefix_mapping.b:
            raise UnknownPrefixError(prefix_name)

        uri = _core.ds.uri_prefix_mapping.b[prefix_name]
        mod = _core.ds.uri_mod_dict[uri]
        return mod
