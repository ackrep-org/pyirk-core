import importlib.util
import sys
import os
import inspect
import pyerk
import pathlib
import functools
import addict


ModuleType = type(sys)


def preserve_cwd(function):
    """
    This is a decorator that ensures that the current working directory is unchanged during the function call.
    """

    @functools.wraps(function)
    def decorator(*args, **kwargs):
        cwd = os.getcwd()
        try:
            return function(*args, **kwargs)
        finally:
            os.chdir(cwd)

    return decorator


# noinspection PyProtectedMember
@preserve_cwd
def load_mod_from_path(
    modpath: str,
    prefix: str,
    modname=None,
    allow_reload=True,
    smart_relative=None,
    reuse_loaded=None,
) -> ModuleType:
    """

    :param modpath:         file system path for the module to be loaded
    :param prefix:          prefix which can be used to replace the URI for convenience
    :param modname:
    :param allow_reload:    flag; if False, an error is raised if the module was already loaded
    :param smart_relative:  flag; if True, relative paths are interpreted w.r.t. the calling module
                            (not w.r.t. current working path)
    :param reuse_loaded:    flag; if True and the module was already loaded before, then just use this
                            if False:: reload; if None use the default action from pyerk.ds
    :return:
    """

    reuse_loaded_original = pyerk.ds.reuse_loaded_module

    match reuse_loaded:
        case True:
            reuse_loaded__actual = True
            pyerk.ds.reuse_loaded_module = True
        case False:
            reuse_loaded__actual = False
            pyerk.ds.reuse_loaded_module = False
        case None:
            # use the (unchanged) default
            reuse_loaded__actual = pyerk.ds.reuse_loaded_module

    try:
        mod = _load_mod_from_path(modpath, prefix, modname, allow_reload, smart_relative, reuse_loaded__actual)
    except:
        if reuse_loaded is not None:
            # we had changed the default
            pyerk.ds.reuse_loaded_module = reuse_loaded_original
        raise

    if reuse_loaded is not None:
        # we had changed the default
        pyerk.ds.reuse_loaded_module = reuse_loaded_original
    return mod


def _load_mod_from_path(
    modpath: str,
    prefix: str,
    modname=None,
    allow_reload=True,
    smart_relative=None,
    reuse_loaded=False,
) -> ModuleType:
    """
    see docstring of load_mod_from_path
    """

    # save some data structures in order to reenable them if something goes wrong

    original_loaded_mod_uris = list(pyerk.ds.mod_path_mapping.a.keys())

    if smart_relative is not None:
        msg = "Using 'smart_relative' paths is deprecated since pyerk version 0.6.0. Please use real paths now."
        raise DeprecationWarning(msg)

    smart_relative = False

    if modname is None:
        if modpath.endswith(".py"):
            modname = os.path.split(modpath)[-1][:-3]  # take the filename but without '.py' at the end
            assert len(modname) > 0
        else:
            msg = "`modpath` is unexpected. In such situations an explicit modname is mandatory."
            raise NotImplementedError(msg)

    if smart_relative and not os.path.isabs(modpath):
        # the path is relative and should be interpreted w.r.t. the calling module
        caller_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe().f_back)))
        modpath = os.path.join(caller_dir, modpath)
    else:
        # the path is either absolute or should be interpreted w.r.t. current working directory
        modpath = os.path.abspath(modpath)

    old_mod_uri = pyerk.ds.mod_path_mapping.b.get(modpath)

    if old_mod_uri:
        if reuse_loaded:
            assert modname in sys.modules
            return sys.modules[modname]

        if allow_reload:
            pyerk.unload_mod(old_mod_uri)
        else:
            msg = f"Unintended attempt to reload module {old_mod_uri}"
            raise pyerk.aux.ModuleAlreadyLoadedError(msg)

    # the following code is newer and thus uses pathlib.Path
    # TODO: simplify the above code (after removing smart_relative)
    modpath = os.path.abspath(modpath)
    modpathfull = pathlib.Path(modpath)
    modpathdir = modpathfull.parent

    # change the working directory; this allows to load dependency modules which are specified in a module with
    # relative paths
    # this will be reverted at the end of the function due to decorator
    os.chdir(modpathdir)

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

        # ensure that the current module is not lurking in sys.modules
        sys.modules.pop(modname, None)
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

    if mod_uri in pyerk.ds.uri_prefix_mapping.a:
        _cleanup(mod_uri, modname, original_loaded_mod_uris)
        msg = f"While loading {modpath}: URI '{mod_uri}' was already registered."
        raise pyerk.aux.InvalidURIError(msg)

    if prefix in pyerk.ds.uri_prefix_mapping.b:
        _cleanup(mod_uri, modname, original_loaded_mod_uris)

        msg = f"While loading {modpath}: prefix '{prefix}' was already registered."
        raise pyerk.aux.InvalidPrefixError(msg)

    pyerk.ds.uri_prefix_mapping.add_pair(mod_uri, prefix)

    pyerk.ds.uri_mod_dict[mod_uri] = mod

    # the modnames are needed to keep sys.modules in sync
    pyerk.ds.modnames[mod_uri] = modname

    mod.__fresh_load__ = True
    return mod


def _cleanup(mod_uri, modname, original_loaded_mod_uris):
    """
    Clean up some data structures if something went wrong during module load. This helps to keep the tests independent.
    """

    pyerk.unload_mod(mod_uri, strict=False)
    sys.modules.pop(modname, None)

    # due to dependencies there might have been other modules loaded -> unload them
    modules_to_unload = [uri for uri in pyerk.ds.mod_path_mapping.a if uri not in original_loaded_mod_uris]

    for uri in modules_to_unload:
        pyerk.unload_mod(uri)
