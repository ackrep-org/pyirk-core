"""
Module-lifecycle / entity-unlinking helpers extracted from :mod:`pyirk.core`.

The symbols defined here are import-time safe: none of them needs any
module-global of ``core`` while this module is being imported (their parameter
and return annotations use only builtins / stdlib types). Symbols that use
``core`` module-globals (``ds``, the core classes ``Statement`` / ``Relation``
etc.) at *call* time access them module-qualified via the ``_core`` module
object, whose attributes are only read once the functions are actually called.
This keeps the import monodirectional: ``core`` imports this module (early),
this module only binds the (partially loaded) ``core`` module object.

Note: ``replace_and_unlink_entity`` intentionally stays in :mod:`pyirk.core`
because its parameter annotations reference the core class ``Entity`` (which is
evaluated at import time and is not yet defined when this module is imported).
It calls ``_unlink_entity`` via the facade re-export.
"""

import sys
from typing import List

from pyirk import auxiliary as aux

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the function bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = [
    "unload_mod",
    "_unlink_entity",
]


def unload_mod(mod_uri: str, strict=True) -> None:
    """
    Delete all references to entities coming from a module with `mod_id`

    :param mod_uri: str; uri of the module, see its __URI__ attribute
    :param strict:  boolean; raise Exception if module seems be not loaded

    :return:        list of released keys
    """

    # TODO: This might to check dependencies in the future

    entity_uris: List[str] = _core.ds.entities_created_in_mod.pop(mod_uri, [])
    stm_dict = _core.ds.stms_created_in_mod.pop(mod_uri, {})

    if strict and (not entity_uris and not stm_dict):
        msg = f"Seems like neither entities nor statements from {mod_uri} have been loaded. This is unexpected."
        raise KeyError(msg)

    for uri in entity_uris:
        _unlink_entity(uri)
        assert uri not in _core.ds.relation_statements.keys()

    intersection_set = set(entity_uris).intersection(_core.ds.relation_statements.keys())

    msg = "Unexpectedly some of the entity keys are still present"
    assert len(intersection_set) == 0, msg

    for uri, stm in stm_dict.items():
        stm: _core.Statement
        assert isinstance(stm, _core.Statement)
        stm.unlink()

    try:
        _core.ds.mod_path_mapping.remove_pair(key_a=mod_uri)
    except KeyError:
        if strict:
            raise
        else:
            pass

    aux.clean_dict(_core.ds.statements)
    aux.clean_dict(_core.ds.inv_statements)

    try:
        _core.ds.uri_keymanager_dict.pop(mod_uri)
    except KeyError:
        if strict:
            raise

    try:
        _core.ds.uri_mod_dict.pop(mod_uri)
    except KeyError:
        if strict:
            raise

    _core.ds.uri_prefix_mapping.remove_pair(mod_uri, strict=strict)

    if modname := _core.ds.modnames.get(mod_uri):
        sys.modules.pop(modname)

    # Relations from the unloaded module are gone; cached attribute-name resolutions
    # that pointed to them would now return stale URIs.
    _core._attr_name_cache.clear()


def _unlink_entity(uri: str, remove_from_mod=False) -> None:
    """
    Remove the occurrence of this the respective entity from all relevant data structures

    :param uri:     entity uri
    :return:        None
    """
    assert isinstance(uri, str)
    aux.ensure_valid_uri(uri)
    entity: _core.Entity = _core.ds.get_entity_by_uri(uri)
    r1 = getattr(entity, "R1", "<unknown entity>")
    entity._label_after_unlink = f"!!unlinked: {r1}"
    entity._unlinked = True
    _core.ds.unlinked_entities[uri] = entity

    if remove_from_mod:
        mod_uri = uri.split("#")[0]
        mod_entities = _core.ds.entities_created_in_mod[mod_uri]

        # TODO: this could be speed up by using a dict instead of a list for mod_entities
        mod_entities.remove(uri)

    res1 = _core.ds.items.pop(uri, None)
    res2 = _core.ds.relations.pop(uri, None)

    if res1 is None and res2 is None:
        msg = f"No entity with key {uri} could be found. This is unexpected."
        raise KeyError(msg)

    # now delete the relation edges from the data structures
    re_dict = _core.ds.statements.pop(entity.uri, {})
    inv_re_dict = _core.ds.inv_statements.pop(entity.uri, {})

    # in case res1 is a scope-item we delete all corresponding relation edges, otherwise nothing happens
    scope_rels = _core.ds.scope_statements.pop(uri, [])

    re_list = list(scope_rels)

    # create a item-list of all Statements instances where `ek` is involved either as subject or object
    re_item_list = list(re_dict.items()) + list(inv_re_dict.items())

    for rel_uri, local_re_list in re_item_list:
        # rel_uri: uri of the relation (like "pyirk/foo#R1234")
        # re_list: list of Statement instances
        re_list.extend(local_re_list)

    if isinstance(entity, _core.Relation):
        tmp = _core.ds.relation_statements.pop(uri, [])
        re_list.extend(tmp)

    # now iterate over all Statement instances
    for stm in re_list:
        stm: _core.Statement
        stm.unlink(uri)

    # during unlinking of the Statements the default dicts might have been recreating some keys -> pop again
    # TODO: obsolete because we clean up the defaultdicts anyway
    _core.ds.statements.pop(entity.uri, None)
    _core.ds.inv_statements.pop(entity.uri, None)
