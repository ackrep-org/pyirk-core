import importlib.util
import sys


def load_mod_from_path(modpath: str, modname=None):
    if modname is None:
        raise NotImplementedError

    spec = importlib.util.spec_from_file_location(modname, modpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["module.name"] = mod
    spec.loader.exec_module(mod)

    return mod
