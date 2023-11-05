"""
Command line interface for erk package
"""
import os
import argparse
from pathlib import Path
import re

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


from . import core, erkloader, rdfstack
from . import visualization
from . import reportgenerator
from . import auxiliary as aux
from . import settings
from . import release

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


def create_parser():
    """
    Returns the parser object which is then evaluated in  main(). This is neccessary for sphinx to automatically
    generate the cli docs.
    """

    parser = argparse.ArgumentParser(description="command line interface to ERK (emergent representation of knowledge)")
    parser.add_argument(
        "inputfile",
        help="input file",
        nargs="?",
        default=None,
    )

    parser.add_argument(
        "-nk",
        "--new-keys",
        help="generate new keys",
        default=None,
        type=int,
        metavar="NUMBER_OF_NEW_KEYS",
    )

    parser.add_argument(
        "-l",
        "--load-mod",
        help="load module (.py file) from path with prefix.",
        nargs=2,
        default=None,
        metavar=("MOD_PATH", "PREFIX"),
    )

    parser.add_argument(
        "-lp",
        "--load-package",
        help="load erk package (represented by erkpackage.tomle file)",
        default=None,
        metavar=("PACKAGE_TOML_PATH"),
    )

    # background: in earlier versions default erk-module paths were specified wrt the path of the
    # pyerk.core python module (and thus not wrt the current working dir).
    # This flag served to switch to "real" paths (interpreted wrt the current working directory)
    # This behavior is now deprecated
    parser.add_argument(
        "-rwd",
        "--relative-to-workdir",
        help=(
            "DEPRECATED; "
            "specifies that the module path is interpreted relative to working dir (not the modules install path)"
        ),
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "-pad",
        "--parse-ackrep-data",
        help="parse ackrep data repository, create items and relations. specify path to ackrep_data base dir \
            (.../ackrep_data)",
        metavar="path",
    )

    parser.add_argument(
        "-grp",
        "--generate-report",
        help="generate report based on configuration file (e.g. reportconf.toml)",
        metavar="reportconf-path",
    )

    parser.add_argument(
        "-vis",
        "--visualize",
        help="create a visualization for the entity",
        metavar="uri",
    )

    parser.add_argument(
        "-i",
        "--interactive-session",
        help="start an interactive session (with the specified module/package loaded)",
        action="store_true",
    )

    parser.add_argument(
        "-dj",
        "--start-django",
        help="start the django server from the current directory",
        action="store_true",
    )

    parser.add_argument(
        "-djs",
        "--start-django-shell",
        help="start the django shell from the current directory (mainly useful for development)",
        action="store_true",
    )

    parser.add_argument(
        "-ac",
        "--create-autocomplete-candidates",
        help="create a file with autocomplete candidates in the current workdir",
        action="store_true",
    )

    parser.add_argument(
        "-ik",
        "--insert-keys-for-placeholders",
        help="replace `_newitemkey_ = ` with appropriate short keys",
        metavar="path_to_mod"
    )

    parser.add_argument("--dbg", help="start debug routine", default=None, action="store_true")

    parser.add_argument(
        "--version",
        help="print the version and exit",
        action="store_true",
    )

    return parser


def main():
    args = create_parser().parse_args()

    if args.dbg:
        debug()
        exit()

    if args.version:
        print(release.__version__)
        exit()

    if args.load_mod is not None and args.load_package is not None:
        print(aux.byellow("The options to load a module and to load a package are mutually exclusive"))
        exit()

    if args.load_mod is not None:
        path, prefix = args.load_mod
        loaded_mod = process_mod(path=path, prefix=prefix, relative_to_workdir=True)
    elif args.load_package is not None:
        loaded_mod, prefix = process_package(args.load_package)
    else:
        loaded_mod = None
        prefix = None

    if args.interactive_session:
        interactive_session(loaded_mod, prefix)
        exit()

    if args.create_autocomplete_candidates:
        create_auto_complete_file()
        exit()

    # typical calls to generate new keys:
    # pyerk --new-keys 30 --load-mod ../knowledge-base/rules/rules1.py rl
    # short version: pyerk -nk 100 -l rules1.py rl
    if args.new_keys:
        if not args.load_mod:
            print(aux.byellow("No module loaded. Nothing to do."))
            exit()
        core.print_new_keys(args.new_keys, loaded_mod)

    elif args.inputfile is not None:
        core.script_main(args.inputfile)
    elif reportconf_path := args.generate_report:
        reportgenerator.generate_report(reportconf_path)
    elif key := args.visualize:
        if key == "__all__":
            visualization.visualize_all_entities(write_tmp_files=True)
            return

        if not aux.ensure_valid_uri(key, strict=False):
            uri = aux.make_uri(settings.BUILTINS_URI, key)
        else:
            uri = key
        aux.ensure_valid_uri(uri)
        visualization.visualize_entity(uri, write_tmp_files=True)
    elif args.start_django:
        try:
            import pyerkdjango.core
        except ImportError:
            print(aux.bred("Error:"), "the module pyerkdjango seems not to be installed.")
            # exit(10)
            raise
        pyerkdjango.core.start_django()
    elif args.start_django_shell:
        try:
            import pyerkdjango.core
        except ImportError:
            print(aux.bred("Error:"), "the module pyerkdjango seems not to be installed.")
            # exit(10)
            raise
        pyerkdjango.core.start_django_shell()
    elif args.insert_keys_for_placeholders:
        insert_keys_for_placeholders(args.insert_keys_for_placeholders)
    else:
        print("nothing to do, see option `--help` for more info")


def process_package(pkg_path: str) -> erkloader.ModuleType:
    if os.path.isdir(pkg_path):
        pkg_path = os.path.join(pkg_path, "erkpackage.toml")

    with open(pkg_path, "rb") as fp:
        erk_conf_dict = tomllib.load(fp)
    ocse_main_rel_path = erk_conf_dict["main_module"]
    main_module_prefix = erk_conf_dict["main_module_prefix"]
    ocse_main_mod_path = Path(pkg_path).parent.joinpath(ocse_main_rel_path).as_posix()

    mod = erkloader.load_mod_from_path(modpath=ocse_main_mod_path, prefix=main_module_prefix)
    return mod, main_module_prefix


def process_mod(path: str, prefix: str, relative_to_workdir: bool = False) -> erkloader.ModuleType:
    if not relative_to_workdir:
        msg = "using mod paths which are not relative to workdir is deprecated since pyerk version 0.6.0"
        raise DeprecationWarning(msg)

    smart_relative = None
    mod1 = erkloader.load_mod_from_path(path, prefix=prefix, smart_relative=smart_relative)

    # perform sanity check
    # rdfstack.check_all_relation_types()
    return mod1


def debug():
    """
    Debug function for development of core and script modules.
    To interactively examine modules (builtin and others) use `--interactive-session`
    """

    ERK_ROOT_DIR = aux.get_erk_root_dir()
    TEST_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "ocse", "control_theory1.py")
    mod1 = erkloader.load_mod_from_path(TEST_DATA_PATH, prefix="ct")  # noqa
    ds = core.ds
    ds.rdfgraph = rdfstack.create_rdf_triples()
    qsrc = rdfstack.get_sparql_example_query2()
    res = ds.rdfgraph.query(qsrc)
    z = aux.apply_func_to_table_cells(rdfstack.convert_from_rdf_to_pyerk, res)  # noqa
    IPS()


def create_auto_complete_file():
    lines = []

    default_pkg_fname = "erkpackage.toml"
    if len(core.ds.uri_mod_dict) == 0:
        if os.path.exists(default_pkg_fname):
            print(f"Loading {default_pkg_fname}")
            process_package(default_pkg_fname)

    for uri, entity in core.ds.items.items():
        if "Ia" in entity.short_key:
            # this is an automatically created item -> omit
            continue

        lines.append(f'{entity.short_key}["{entity.R1__has_label}"]\n')
        label_str = core.ilk2nlk(entity.R1__has_label)
        lines.append(f"{entity.short_key}__{label_str}\n")

    for uri, entity in core.ds.relations.items():
        label_str = core.ilk2nlk(entity.R1__has_label)
        lines.append(f"{entity.short_key}__{label_str}\n")
        lines.append(f'{entity.short_key}["{entity.R1__has_label}"]\n')

    fname = ".ac_candidates.txt"
    fpath = os.path.abspath(os.path.join("./", fname))
    with open(fname, "w") as fp:
        fp.writelines(lines)

    print(f"File written: {fpath}")


def insert_keys_for_placeholders(modpath):
    """
    Motivation:
    When mass-inserting entities, it is easier to use a placeholder instead of unique short_key.
    This function replaces these placeholders with adequate unique short keys.
    """

    with open(modpath) as fp:
        old_txt = fp.read()

    # first write backup
    fname = os.path.split(modpath)[-1]
    import tempfile
    import shutil
    backup_path = os.path.join(tempfile.mkdtemp(), fname)

    shutil.copy(modpath, backup_path)
    print(f"Backup: {backup_path}")

    start_tag = r"#\s*?<new_entities>"
    end_tag = r"#\s*?</new_entities>"

    placeholder = "_newitemkey_ = "
    key_count = old_txt.count(f"\n{placeholder}")

    pattern = f"{start_tag}.*?{end_tag}"
    tmp_txt = re.sub(pattern=pattern, repl="", string=old_txt, flags=re.DOTALL)
    assert start_tag not in tmp_txt
    assert end_tag not in tmp_txt
    assert placeholder not in tmp_txt

    tmp_modpath = tempfile.mktemp(prefix=f"{fname[:-3]}_tmp_", suffix=".py", dir=".")

    with open(tmp_modpath, "w") as fp:
        fp.write(tmp_txt)

    # load this temporary module
    loaded_mod = process_mod(path=tmp_modpath, prefix="mod", relative_to_workdir=True)
    item_keys = [core.generate_new_key("I", mod_uri=loaded_mod.__URI__) for i in range(key_count)]

    old_lines = old_txt.split("\n")

    # replace the respective lines in the original module
    new_lines = []
    for line in old_lines:
        if line.startswith(placeholder):
            key = item_keys.pop()
            new_line = line.replace(placeholder, f"{key} = ")
        else:
            new_line = line
        new_lines.append(new_line)

    txt = "\n".join(new_lines)
    with open(modpath, "w") as fp:
        fp.write(txt)
        if not txt.endswith("\n"):
            fp.write("\n")

    print(f"File (over)written {modpath}")
    with open(modpath, "w") as fp:
        fp.write(txt)

    core.unload_mod(loaded_mod.__URI__)
    os.unlink(tmp_modpath)

    replace_dummy_enties_by_label(modpath)


def replace_dummy_enties_by_label(modpath):
    """
    load the module, additionally load its source, replace entities like I000["some label"] with
    real entities like I7654["some label"].
    """

    loaded_mod = process_mod(path=modpath, prefix="mod", relative_to_workdir=True)
    pattern = re.compile("""(p.I000\[['"](.*?)['"]\])""")

    with open(modpath) as fp:
        txt = fp.read()

    matches = list(pattern.finditer(txt))
    for match in matches:
        full_expr = match.group(1)  # the whole string like `p.I000["foo bar"]`
        label = match.group(2)  # only the label string "foo bar"
        entity = core.ds.get_item_by_label(label)
        new_expr = f'{entity.short_key}["{label}"]'
        txt = txt.replace(full_expr, new_expr)


    with open(modpath, "w") as fp:
        fp.write(txt)


def interactive_session(loaded_mod, prefix):
    """
    Start an interactive IPython session where the (optinally) loaded mod is available under its prefix name.
    Also: perepare interactive pyerk-module -- a namespacew for experimentally creating entities.
    """
    import pyerk as p  # noqa

    __URI__ = "erk:/_interactive"

    keymanager = p.KeyManager()
    p.register_mod(__URI__, keymanager, check_uri=False)

    print("to create entities in this interactive scope use `p.start_mod(__URI__)`")

    if loaded_mod is not None and prefix is not None:
        locals()[prefix] = loaded_mod

    IPS()
