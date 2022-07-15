import importlib.util
import sys
import os
import pyerk

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


def load_mod_from_path(modpath: str, modname=None, allow_reload=True, omit_reload=False):
    if modname is None:
        raise NotImplementedError

    modpath = os.path.abspath(modpath)
    old_mod_id = pyerk.ds.mod_path_mapping.b.get(modpath)

    if omit_reload and old_mod_id:
        return

    if allow_reload and old_mod_id:
        pyerk.unload_mod(old_mod_id)

    pyerk.core.available_key_numbers = pyerk.generate_key_numbers()

    spec = importlib.util.spec_from_file_location(modname, modpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["module.name"] = mod
    # noinspection PyUnresolvedReferences
    spec.loader.exec_module(mod)

    return mod
