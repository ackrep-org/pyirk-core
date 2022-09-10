import importlib.util
import sys
import os
import pyerk

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


# noinspection PyProtectedMember
def load_mod_from_path(modpath: str, modname=None, allow_reload=True, omit_reload=False):
    if modname is None:
        raise NotImplementedError

    modpath = os.path.abspath(modpath)
    old_mod_uri = pyerk.ds.mod_path_mapping.b.get(modpath)

    if omit_reload and old_mod_uri:
        return

    if allow_reload and old_mod_uri:
        pyerk.unload_mod(old_mod_uri)

    spec = importlib.util.spec_from_file_location(modname, modpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["module.name"] = mod

    old_len = len(pyerk.core._uri_stack)
    try:
        # noinspection PyUnresolvedReferences
        spec.loader.exec_module(mod)
    except Exception:
        if len(pyerk.core._uri_stack) > old_len:
            # deactivate the failed module (because execution did not reach end_mod())
            failed_mod_uri = pyerk.core._uri_stack.pop()

            # remove all added entities
            pyerk.unload_mod(failed_mod_uri)
        raise

    if len(pyerk.core._uri_stack) > old_len:

        failed_mod_uri = pyerk.core._uri_stack.pop()

        msg = (
            f"The module {failed_mod_uri} was not properly ended. Ensure that pyerk.end_mod() is called after "
            "the last PyERK-statement."
        )

        raise pyerk.PyERKError(msg)

    return mod
