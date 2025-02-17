"""
Command line interface for irk package
"""

import os
import argparse
from pathlib import Path
import re
from typing import Tuple
import ast
import inspect

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


from . import core, irkloader, rdfstack
from . import visualization
from . import reportgenerator
from . import auxiliary as aux
from . import settings
from . import release

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


def create_parser():
    """
    Returns the parser object which is then evaluated in  main(). This is necessary for sphinx to automatically
    generate the cli docs.
    """

    parser = argparse.ArgumentParser(
        description="command line interface to IRK (imperative representation of knowledge)"
    )
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
        help="load irk package (represented by irkpackage.toml file)",
        default=None,
        metavar=("PACKAGE_TOML_PATH"),
    )

    # background: in earlier versions default irk-module paths were specified wrt the path of the
    # pyirk.core python module (and thus not wrt the current working dir).
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
        metavar="path_to_mod",
    )

    parser.add_argument(
        "-utd",
        "--update-test-data",
        help="create a subset of the irkpackage (e.g. OCSE) and store it in the `test_data` dir of pyirk-core",
        metavar="path_to_irk_package",
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
    # pyirk --new-keys 30 --load-mod ../knowledge-base/rules/rules1.py rl
    # short version: pyirk -nk 100 -l rules1.py rl
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
            entity = core.ds.get_entity_by_key_str(key)
            uri = entity.uri
        else:
            uri = key
        aux.ensure_valid_uri(uri)
        visualization.visualize_entity(uri, write_tmp_files=True)
    elif args.start_django:
        try:
            import pyirkdjango.core
        except ImportError:
            print(aux.bred("Error:"), "the module pyirkdjango seems not to be installed.")
            # exit(10)
            raise
        pyirkdjango.core.start_django()
    elif args.start_django_shell:
        try:
            import pyirkdjango.core
        except ImportError:
            print(aux.bred("Error:"), "the module pyirkdjango seems not to be installed.")
            # exit(10)
            raise
        pyirkdjango.core.start_django_shell()
    elif args.insert_keys_for_placeholders:
        insert_keys_for_placeholders(args.insert_keys_for_placeholders)
    elif args.update_test_data:
        update_test_data(args.update_test_data)
    else:
        print("nothing to do, see option `--help` for more info")


def process_package(pkg_path: str) -> Tuple[irkloader.ModuleType, str]:
    if os.path.isdir(pkg_path):
        pkg_path = os.path.join(pkg_path, "irkpackage.toml")

    with open(pkg_path, "rb") as fp:
        irk_conf_dict = tomllib.load(fp)
    main_rel_path = irk_conf_dict["main_module"]
    main_module_prefix = irk_conf_dict["main_module_prefix"]
    main_mod_path = Path(pkg_path).parent.joinpath(main_rel_path).as_posix()

    mod = irkloader.load_mod_from_path(modpath=main_mod_path, prefix=main_module_prefix)
    return mod, main_module_prefix


def process_mod(path: str, prefix: str, relative_to_workdir: bool = False) -> irkloader.ModuleType:
    if not relative_to_workdir:
        msg = "using mod paths which are not relative to workdir is deprecated since pyirk version 0.6.0"
        raise DeprecationWarning(msg)

    smart_relative = None
    mod1 = irkloader.load_mod_from_path(path, prefix=prefix, smart_relative=smart_relative)

    # perform sanity check
    # rdfstack.check_all_relation_types()
    return mod1


def debug():
    """
    Debug function for development of core and script modules.
    To interactively examine modules (builtin and others) use `--interactive-session`
    """

    IRK_ROOT_DIR = aux.get_irk_root_dir()
    TEST_DATA_PATH = os.path.join(IRK_ROOT_DIR, "irk-data", "ocse", "control_theory1.py")
    mod1 = irkloader.load_mod_from_path(TEST_DATA_PATH, prefix="ct")  # noqa
    ds = core.ds
    ds.rdfgraph = rdfstack.create_rdf_triples()
    qsrc = rdfstack.get_sparql_example_query2()
    res = ds.rdfgraph.query(qsrc)
    z = aux.apply_func_to_table_cells(rdfstack.convert_from_rdf_to_pyirk, res)  # noqa
    IPS()


def create_auto_complete_file():
    lines = []

    default_pkg_fname = "irkpackage.toml"
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

    # create a module which excludes everything between `start_tag` and `end_tag`
    tmp_txt = re.sub(pattern=pattern, repl="", string=old_txt, flags=re.DOTALL)
    assert start_tag not in tmp_txt
    assert end_tag not in tmp_txt
    assert placeholder not in tmp_txt

    tmp_modpath = tempfile.mktemp(prefix=f"{fname[:-3]}_tmp_", suffix=".py", dir=".")

    with open(tmp_modpath, "w") as fp:
        fp.write(tmp_txt)

    # load this temporary module
    loaded_mod = process_mod(path=tmp_modpath, prefix="mod", relative_to_workdir=True)

    # generate keys for the new items
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

    replace_dummy_entities_by_label(modpath)


def replace_dummy_entities_by_label(modpath):
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
        if entity is None:
            print(f"could not find entity for label: {label}")
            continue
        new_expr = f'{entity.short_key}["{label}"]'
        txt = txt.replace(full_expr, new_expr)

    with open(modpath, "w") as fp:
        fp.write(txt)


def update_test_data(pkg_path):
    """
    Background: see devdocs
    """
    import glob

    mod, prefix = process_package(pkg_path)
    mod_cont = path_to_ast_container(inspect.getfile(mod))

    test_data_root = core.aux.get_irk_path("pyirk-core-test_data")
    target_dir = os.path.join(test_data_root, "ocse_subset")
    template_dir = os.path.join(target_dir, "templates")

    template_files = glob.glob(os.path.join(template_dir, "*__template.py"))
    for template_path in template_files:
        rendered_template_txt = process_template(template_path)
        fname = os.path.split(template_path)[-1].replace("__template", "")
        target_path = os.path.join(target_dir, fname)
        with open(target_path, "w") as fp:
            fp.write(rendered_template_txt)
            print(f"File written: {target_path}")


def process_template(template_path):

    templ_ast_cont = path_to_ast_container(template_path)

    # extract the uri-line
    uri_line = templ_ast_cont.line_data["__URI__"]
    tmp_locals = {}
    exec(uri_line, {}, tmp_locals)
    uri = tmp_locals["__URI__"]

    original_mod_path = inspect.getfile(core.ds.uri_mod_dict[uri])

    mod_ast_cont = path_to_ast_container(original_mod_path)

    insert_key_lines = templ_ast_cont.line_data["insert_entities"].strip().split("\n")
    assert insert_key_lines[0].strip() == "insert_entities = ["
    assert insert_key_lines[-1].strip() == "]"

    insert_key_lines = insert_key_lines[1:-1]

    lines_to_insert = []

    for line in insert_key_lines:
        line = line.strip().strip(",")
        if not line:
            continue
        elif line.startswith("#"):
            continue
        elif line.startswith("raw__"):
            # handle raw lines
            lines_to_insert.append(line[len("raw__") :])
            lines_to_insert.append("\n" * 3)
            continue
        elif line.startswith("with__"):
            # handle context managers
            short_key = line
        elif line.startswith("def__"):
            short_key = line[len("def__") :]
        elif line.startswith("class__"):
            short_key = line[len("class__") :]
        else:
            # assume pyirk entity
            short_key = core.process_key_str(line, check=False).short_key

        original_content = mod_ast_cont.line_data[short_key]
        if not isinstance(original_content, str) or original_content == "":
            short_template_path, fname = os.path.split(template_path)
            short_template_path = os.path.split(short_template_path)[-1]
            short_template_path = os.path.join(short_template_path, fname)
            msg = (
                f"could not find associated data for short_key {short_key} while processing "
                f"template line `{line}` in template {short_template_path}."
            )
            raise KeyError(msg)
        lines_to_insert.append(original_content)
        lines_to_insert.append("\n")

    new_insert_txt = "".join(lines_to_insert)

    rendered_template = templ_ast_cont.txt.replace(
        templ_ast_cont.line_data["insert_entities"], new_insert_txt
    )
    return rendered_template


def path_to_ast_container(mod_path: str) -> core.aux.Container:

    with open(mod_path) as fp:
        lines = fp.readlines()

    txt = "".join(lines)
    c = core.aux.Container(ast=ast.parse(txt), lines=lines, line_data={}, txt=txt)

    for elt in c.ast.body:
        if isinstance(elt, ast.Assign):
            name = elt.targets[0].id
        elif isinstance(elt, (ast.FunctionDef, ast.ClassDef)):
            name = elt.name
        elif isinstance(elt, ast.With):
            first_line = lines[elt.lineno - 1]
            # assume form like `with I9907.scope("setting") as cm:`
            idx = first_line.index(" as ")
            # create name string like `with__I9907.scope("setting")`
            name = f"with__{first_line[len('with '):idx]}"
        else:
            continue

        assert isinstance(name, str)

        # subtract 1 because the line numbers are human-oriented (1-indexed)
        src_txt = "".join(lines[elt.lineno - 1 : elt.end_lineno])
        c.line_data[name] = src_txt

    return c


def get_lines_for_short_key(short_key: str) -> str:
    pass


def interactive_session(loaded_mod, prefix):
    """
    Start an interactive IPython session where the (optionally) loaded mod is available under its prefix name.
    Also: prepare interactive pyirk-module -- a namespace for experimentally creating entities.
    """
    import pyirk as p  # noqa

    __URI__ = "irk:/_interactive"

    keymanager = p.KeyManager()
    p.register_mod(__URI__, keymanager, check_uri=False)

    print("to create entities in this interactive scope use `p.start_mod(__URI__)`")

    if loaded_mod is not None and prefix is not None:
        locals()[prefix] = loaded_mod

    IPS()
