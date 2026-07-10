"""
Entity-operation helpers extracted from :mod:`pyirk.core`.

PEP 563 (``from __future__ import annotations``) is active so that all
forward-reference annotations (``Entity``, ``Item``, ``Statement``, etc.) become
lazy strings rather than immediately evaluated names.

The module only binds the (possibly partially loaded) ``core`` module object
and reads its attributes lazily at call time.
"""

from __future__ import annotations

from pyirk import auxiliary as aux

# Note: this import only binds the (possibly partially loaded) module object;
# its attributes are accessed lazily inside the function bodies (i.e. at call
# time, not import time).
from pyirk import core as _core


__all__ = ["replace_and_unlink_entity"]


def replace_and_unlink_entity(old_entity: Entity, new_entity: Entity):
    """
    Replace all statements where `old_entity` is subject or object with new relations where `new_entity` is sub or obj.
    For the "subject-case" only process those statements for which `new_entity` does not yet have any relations.
    Thus do not replace e.g. the R4__is_instance_of statement of `new_entity`.

    Then unlink `old_entity`.
    """

    res = _core.RuleResult()

    from pyirk import builtin_entities as bi

    # these predicates should not be replaced
    omit_uris = aux.uri_set(
        bi.R1["has label"], bi.R2["has description"], bi.R4["is instance of"], bi.R57["is placeholder"]
    )

    # ensure both entities exist (raise UnknownURIError otherwise):
    _core.ds.get_entity_by_uri(old_entity.uri)
    _core.ds.get_entity_by_uri(new_entity.uri)

    stm_dict1 = old_entity.get_inv_relations()  # where it is obj
    stm_dict2 = old_entity.get_relations()  # where it is subj

    _core._unlink_entity(old_entity.uri, remove_from_mod=True)
    res.unlinked_entities.append(old_entity)
    res.replacements.append((old_entity, new_entity))

    for relation_uri, stm_list in list(stm_dict1.items()) + list(stm_dict2.items()):
        for stm in stm_list:
            new_stm = None
            stm: Statement
            subject, predicate, obj = stm.relation_tuple
            if predicate.uri in omit_uris:
                continue
            subject: Item
            qlf = stm.qualifiers
            if obj == old_entity:
                # case1: old_entity was object, subject stays the same
                new_stm = subject.set_relation(predicate, new_entity, qualifiers=qlf, prevent_duplicate=True)
                res.add_statement(new_stm)
                continue
            else:
                # case2: old_entity was subject, subject must be new_entity
                assert subject == old_entity

                # prevent the creation of a duplicated statement
                existing_objs = new_entity.get_relations(predicate.uri, return_obj=True)
                if not obj in existing_objs:
                    # it is possible that predicate is functional and new_entity.predicate has a value
                    # different from obj. this is OK if one of them is a placeholder
                    if len(existing_objs) == 1 and predicate.R22__is_functional:
                        existing_obj = existing_objs[0]
                        if obj.R57__is_placeholder:
                            # ignore it -> continue with next statement
                            continue
                        elif not existing_obj.R57__is_placeholder and not obj.R57__is_placeholder:
                            msg = (
                                f"conflicting statement for functional predicate {predicate} and non-placeholder "
                                f"objects: {obj} (of old_entity)  and {existing_obj} of new_entity, while replacing"
                                f"{old_entity} (old) with {new_entity} (new)."
                            )
                            raise aux.FunctionalRelationError(msg)
                        else:
                            assert existing_obj.R57__is_placeholder and not obj.R57__is_placeholder
                            # replace the placeholder with the non-placeholder information
                            chgd_stm = new_entity.overwrite_statement(predicate.uri, obj, qualifiers=qlf)
                            res.changed_statements.append(chgd_stm)
                            continue
                    else:
                        # no replacement has to be made
                        new_stm = new_entity.set_relation(predicate, obj, qualifiers=qlf)
                        res.add_statement(new_stm)
                        continue
                else:
                    assert obj in existing_objs
                    # no new information available -> continue with next statement
                    continue

    return res
