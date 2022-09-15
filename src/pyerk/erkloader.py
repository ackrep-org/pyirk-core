import importlib.util
import sys
import os
import pyerk

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


# noinspection PyProtectedMember
def load_mod_from_path(modpath: str, prefix: str, modname=None, allow_reload=True, omit_reload=False):
    """

    :param modpath:         file system path for the module to be loaded
    :param prefix:          prefix which can be used to replace the URI for convenice
    :param modname:
    :param allow_reload:
    :param omit_reload:
    :return:
    """
    if modname is None:
        if modpath.endswith(".py"):
            modname = os.path.split(modpath)[-1][:-3]  # take the filename but without '.py' at the end
            assert len(modname) > 0
        else:
            msg = "`modpath` is unexpected. In such situations an explicit modname is mandatory."
            raise NotImplementedError(msg)

    modpath = os.path.abspath(modpath)
    old_mod_uri = pyerk.ds.mod_path_mapping.b.get(modpath)

    if omit_reload and old_mod_uri:
        mod = pyerk.ds.uri_mod_dict[old_mod_uri]
        mod.__fresh_load__ = False
        return mod

    if allow_reload and old_mod_uri:
        pyerk.unload_mod(old_mod_uri)

    spec = importlib.util.spec_from_file_location(modname, modpath)
    mod = importlib.util.module_from_spec(spec)

    assert modname not in sys.modules
    sys.modules[modname] = mod

    old_len = len(pyerk.core._uri_stack)
    try:
        # noinspection PyUnresolvedReferences
        spec.loader.exec_module(mod)
    except Exception:
        if len(pyerk.core._uri_stack) > old_len:
            # deactivate the failed module (because execution did not reach end_mod())
            failed_mod_uri = pyerk.core._uri_stack.pop()

            # remove all added entities, but tolerate errors (due to incomplete loading)
            pyerk.unload_mod(failed_mod_uri, strict=False)
        raise

    if len(pyerk.core._uri_stack) > old_len:

        failed_mod_uri = pyerk.core._uri_stack.pop()

        msg = (
            f"The module {failed_mod_uri} was not properly ended. Ensure that pyerk.end_mod() is called after "
            "the last PyERK-statement."
        )

        raise pyerk.PyERKError(msg)

    mod_uri = getattr(mod, "__URI__")
    if mod_uri is None:
        msg = f"The module from path {modpath} could not be loaded. No valid `__URI__` attribute found."
        raise pyerk.PyERKError(msg)

    pyerk.aux.ensure_valid_baseuri(mod_uri)
    pyerk.ds.uri_prefix_mapping.add_pair(mod_uri, prefix)

    pyerk.ds.uri_mod_dict[mod_uri] = mod

    # the modnames are needed to keep sys.modules in sync
    pyerk.ds.modnames[mod_uri] = modname

    mod.__fresh_load__ = True
    return mod
