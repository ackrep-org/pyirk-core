"""
Inspection-/context-/module-lifecycle helpers extracted from :mod:`pyirk.core`.

The symbols defined here are import-time safe: none of them needs any
module-global of ``core`` while this module is being imported. Symbols that use
``core`` module-globals (``ds``, the uri-stacks ``_uri_stack`` /
``_search_uri_stack`` etc.) at *call* time access them module-qualified via the
``_core`` module object, whose attributes are only read once the functions are
actually called. This keeps the import monodirectional: ``core`` imports this
module (early), this module only binds the (partially loaded) ``core`` module
object plus the already-loaded ``keymanager`` submodule.

Note: the module-level bindings ``_uri_stack = []`` and
``_search_uri_stack = []`` intentionally remain in :mod:`pyirk.core` (they are
the single source of truth for the active/search uri stacks). They are accessed
here lazily as ``_core._uri_stack`` / ``_core._search_uri_stack``.
"""

import inspect
import os
import types
from typing import Union

from pyirk import auxiliary as aux
from pyirk import settings

# KeyManager is used in an annotation of `register_mod`, which is evaluated at
# import time -> needs to be a real direct import. The keymanager submodule is
# fully loaded before this module is imported by `core`.
from pyirk._core.keymanager import KeyManager

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the function bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = [
    "get_caller_frame",
    "get_key_str_by_inspection",
    "get_mod_name_by_inspection",
    "get_mod_id_list_by_inspection",
    "Context",
    "abstract_uri_context",
    "uri_context",
    "search_uri_context",
    "get_active_mod_uri",
    "register_mod",
    "start_mod",
    "end_mod",
]


def get_caller_frame(upcount: int) -> types.FrameType:
    # get the topmost frame
    frame = inspect.currentframe()
    # + 1 because the we have to leave this frame first
    i = upcount + 1
    while True:
        if frame.f_back is None:
            break
        frame = frame.f_back
        i -= 1
        if i == 0:
            break

    return frame


def get_key_str_by_inspection(upcount=1) -> str:
    """
    Retrieve the name of an entity from a code line like
      `cm.new_var(M=p.instance_of(I9904["matrix"]))`

    :param upcount:     int; how many frames to go up
    :return:
    """

    # get the topmost frame
    frame = get_caller_frame(upcount=upcount + 1)

    # this is strongly inspired by sympy.var
    try:
        fi = inspect.getframeinfo(frame)
        code_context = fi.code_context
    finally:
        # we should explicitly break cyclic dependencies as stated in inspect
        # doc
        del frame

    # !! TODO: parsing the assignment should be more robust (correct parsing of logical lines)
    # assume that there is at least one `=` in the line
    lhs, rhs = code_context[0].split("=")[:2]
    res: str = lhs.split("(")[-1].strip()
    assert res.isidentifier()
    return res


# TODO: remove obsolete this obsolete function
def get_mod_name_by_inspection(upcount=1):
    """
    :param upcount:     int; how many frames to go up
    :return:
    """

    frame = get_caller_frame(upcount=upcount + 1)

    mod_id = frame.f_globals.get("__MOD_ID__")
    return mod_id


def get_mod_id_list_by_inspection(upcount=2) -> list:
    """
    :param upcount:     int; how many frames to go up at beginning
                        upcount=2 (default) means: start int the caller frame. Example: fnc1()->fnc2()->fnc3()
                        where fnc3 is this function, called by fnc2, which itself is called by fnc1 (the caller)
    :return:            list of mod_id-objects (type str)
    """

    # get start frame
    frame = inspect.currentframe()
    i = upcount
    while True:
        assert frame.f_back is not None
        frame = frame.f_back
        i -= 1
        if i == 0:
            break

    # now `frame` is our start frame where we begin to look for __MOD_ID__
    res = [None]
    while True:
        mod_id = frame.f_globals.get("__URI__")
        if mod_id is not None:
            res.append(mod_id)
        frame = frame.f_back
        if frame is None:
            break

    return res


# TODO: obsolete?
class Context:
    """
    Container class for context definitions
    """

    def __init__(self, *args, **kwargs):
        pass


class abstract_uri_context:
    def __init__(self, uri_stack: list, uri: str, prefix: str = None):
        self.uri_stack = uri_stack
        self.uri = uri
        self.prefix = prefix

    def __enter__(self):
        """
        implicitly called in the head of the with statement
        :return:
        """
        self.uri_stack.append(self.uri)

        if self.prefix:
            _core.ds.uri_prefix_mapping.add_pair(self.uri, self.prefix)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this is the place to handle exceptions

        res = self.uri_stack.pop()
        assert res == self.uri
        if self.prefix:
            _core.ds.uri_prefix_mapping.remove_pair(self.uri, self.prefix)


class uri_context(abstract_uri_context):
    """
    Context manager for creating entities with a given uri
    """

    def __init__(self, uri: str, prefix: str = None):
        super().__init__(_core._uri_stack, uri, prefix)


class search_uri_context(abstract_uri_context):
    """
    uri Context manager for searching for entities with a given key
    """

    def __init__(self, uri: str, prefix: str = None):
        super().__init__(_core._search_uri_stack, uri, prefix)


def get_active_mod_uri(strict: bool = True) -> Union[str, None]:
    try:
        res = _core._uri_stack[-1]
    except IndexError:
        msg = (
            "Unexpected: empty uri_stack. Be sure to use uri_context manager or similar technique "
            "when creating entities"
        )
        if strict:
            raise aux.EmptyURIStackError(msg)
        else:
            return None
    return res


def register_mod(uri: str, keymanager: KeyManager = None, check_uri=True, prefix=None):
    frame = get_caller_frame(upcount=1)
    path = os.path.abspath(frame.f_globals["__file__"])
    if check_uri:
        if not frame.f_globals.get("__URI__", None) == uri:
            raise AssertionError()
    if uri != settings.BUILTINS_URI:
        # the builtin module is an exception because it should not be unloaded

        if uri in _core.ds.mod_path_mapping.a:
            msg = f"URI '{uri}' was already registered by {_core.ds.mod_path_mapping.a[uri]}."
            raise aux.InvalidURIError(msg)

        _core.ds.mod_path_mapping.add_pair(key_a=uri, key_b=path)

    if keymanager is None:
        # there are use cases (e.g. in stafo where the key manager is created before the module is registered)
        # -> we want to reuse that key manager
        if uri in _core.ds.uri_keymanager_dict:
            keymanager = _core.ds.uri_keymanager_dict[uri]
        else:
            keymanager = KeyManager()
    # all modules should have their own key manager
    _core.ds.uri_keymanager_dict[uri] = keymanager

    # currently this is only used from within unittests as they create test data on the fly and
    # not use irkloader for every tiny item
    if prefix:
        _core.ds.uri_prefix_mapping.add_pair(key_a=uri, key_b=prefix)


def start_mod(uri):
    """
    Register the uri for the _uri_stack.

    Note: between start_mod and end_mod no it is not allowed to load other irk modules

    :param uri:
    :return:
    """
    assert len(_core._uri_stack) == 0, f"Non-empty uri_stack: {_core._uri_stack}"
    _core._uri_stack.append(uri)


def end_mod():
    _core._uri_stack.pop()
    assert len(_core._uri_stack) == 0
