"""
Command line interface for irk package
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
import re
import types
from typing import Tuple
import ast
import inspect
from textwrap import dedent
from addict import Addict as Container

try:
    # this will be part of standard library for python >= 3.11
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

import platformdirs


from . import core, irkloader, rdfstack
from . import settings
from . import visualization
from . import reportgenerator
from . import auxiliary as aux

from . import release

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


def create_parser():
    """
    Returns the parser object which is then evaluated in  main(). This is necessary for sphinx to
    automatically generate the cli docs.
    """

    if os.path.isfile(settings.config_file):
        _cfg_status = "exists"
    else:
        _cfg_status = "not present — create it with --bootstrap-config"
    config_epilog = f"config file: {settings.config_file}\n  ({_cfg_status})"

    parser = argparse.ArgumentParser(
        description="command line interface to IRK (imperative representation of knowledge)",
        epilog=config_epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "-ee",
        "--export-entities",
        help="generate text file with all entities for embedding",
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

    parser.add_argument(
        "--bootstrap-config",
        help="create an empty config.toml file in the user config directory",
        action="store_true",
    )

    parser.add_argument(
        "--ci-mode",
        help="indicate that pyirk (e.g. --bootstrap-config) is run on CI",
        action="store_true",
    )

    parser.add_argument(
        "--refactor-entity-label",
        help="change main label of entity in source file of loaded module. "
        "Recommended: Apply ony to clean git repo.",
        nargs=2,
        metavar=("key", "new label"),
    )

    # --- authoring / Lean import ------------------------------------------------
    parser.add_argument(
        "--import-lean",
        help="import theorem(s) from a Lean source file (local path or http(s) URL) "
        "into a pyirk content module via the authoring substrate",
        metavar="PATH_OR_URL",
        default=None,
    )
    parser.add_argument(
        "--target",
        help="target pyirk content module (.py file) to append the imported theorem(s) to; "
        "auto-bootstrapped if missing (requires --working-uri)",
        metavar="MODULE_PY",
        default=None,
    )

    theorem_group = parser.add_mutually_exclusive_group()
    theorem_group.add_argument(
        "--theorem",
        help="name of a single theorem (as it appears in the Lean source) to import",
        metavar="NAME",
        default=None,
    )
    theorem_group.add_argument(
        "--all",
        help="import every theorem parsed from the Lean source (fail-fast)",
        dest="all_theorems",
        action="store_true",
    )

    ocse_group = parser.add_mutually_exclusive_group()
    ocse_group.add_argument(
        "--ocse-uri",
        help="OCSE math module identified by its IRK URI (path looked up via pyirk config)",
        metavar="IRK_URI",
        default=None,
    )
    ocse_group.add_argument(
        "--ocse-path",
        help="OCSE math module identified by an on-disk filesystem path",
        metavar="FS_PATH",
        default=None,
    )

    parser.add_argument(
        "--working-uri",
        help="URI for the working content module; required if --target does not yet exist",
        metavar="URI",
        default=None,
    )
    parser.add_argument(
        "--source-url",
        help="optional source URL recorded as R9999 reference for imported theorems "
        "(auto-derived if --import-lean is an http(s) URL)",
        metavar="URL",
        default=None,
    )
    parser.add_argument(
        "--fork-policy",
        help="how to answer FORK questions: 'ask' = interactively on stdin (default), "
        "'first' = always pick the first option (for unattended bulk runs; choice is "
        "recorded), 'skip' = do not decide, mark the theorem as fork-pending and continue",
        choices=["ask", "first", "skip"],
        default="ask",
    )
    parser.add_argument(
        "--stats-jsonl",
        help="append one JSON line per processed theorem (attempts, forks, validation "
        "failures, outcome) to this file -- the metrics basis for bulk runs",
        metavar="PATH",
        default=None,
    )
    parser.add_argument(
        "--keep-going",
        help="with --all: continue with the next theorem after a failed import instead "
        "of stopping (failures are still reported in the exit code and --stats-jsonl)",
        action="store_true",
    )
    parser.add_argument(
        "--resume",
        help="with --all and --stats-jsonl: skip theorems that already have a record in "
        "the stats file (any outcome). Makes interrupted bulk runs idempotently "
        "re-runnable: just repeat the same command until everything is processed",
        action="store_true",
    )
    parser.add_argument(
        "--limit",
        help="with --all: only consider the first N parsed theorems. Applied before "
        "--resume filtering, so 'the first N of the corpus' stays stable across "
        "repeated resumed invocations",
        metavar="N",
        type=int,
        default=0,
    )

    return parser


def main():
    args = create_parser().parse_args()

    if args.dbg:
        debug()
        exit()

    if args.import_lean:
        sys.exit(import_lean(args))

    if args.refactor_entity_label:
        from . import refactor_tools as rt

        assert args.inputfile is not None
        assert len(args.refactor_entity_label) == 2
        rt.change_entity_label(*args.refactor_entity_label, args.inputfile)
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
    elif export_path := args.export_entities:
        core.export_entities(export_path)
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
            import pyirkdjango.core  # type: ignore
        except ImportError:
            print(aux.bred("Error:"), "the module pyirkdjango seems not to be installed.")
            # exit(10)
            raise
        pyirkdjango.core.start_django()
    elif args.start_django_shell:
        try:
            import pyirkdjango.core  # type: ignore
        except ImportError:
            print(aux.bred("Error:"), "the module pyirkdjango seems not to be installed.")
            # exit(10)
            raise
        pyirkdjango.core.start_django_shell()
    elif args.insert_keys_for_placeholders:
        insert_keys_for_placeholders(args.insert_keys_for_placeholders)
    elif args.update_test_data:
        update_test_data(args.update_test_data)
    elif args.bootstrap_config:
        bootstrap_config(args.ci_mode)
    else:
        print("nothing to do, see option `--help` for more info")


def _resolve_ocse_path(args) -> str:
    """Resolve --ocse-path | --ocse-uri to a concrete on-disk path.

    NOTE: --ocse-uri requires that the pyirk config (config.toml) declares the
    matching ``[package.X]`` entry; otherwise the lookup fails. Tests should
    prefer --ocse-path.
    """
    if args.ocse_path:
        return os.path.abspath(args.ocse_path)
    if not aux.STATES.available_modules_detected:
        aux.load_module_configs_from_general_config()
    try:
        return aux.AVAILABLE_MODULES[args.ocse_uri]
    except KeyError as exc:
        raise SystemExit(
            f"could not resolve --ocse-uri {args.ocse_uri!r}: not in pyirk config "
            f"(known URIs: {sorted(aux.AVAILABLE_MODULES)})"
        ) from exc


def import_lean(args) -> int:
    """Driver for ``pyirk --import-lean ...``. Returns a process exit code."""
    from .authoring import (
        ForkPending,
        Session,
        ask_user_via_stdin,
        bootstrap_working_module,
        fork_policy_first,
        fork_policy_skip,
    )
    from .authoring.lean import (
        fetch_lean_source,
        find_theorem,
        import_theorem,
        parse_theorems,
    )

    # 1. mutual-exclusion / required-one validation
    if not args.target:
        print("error: --target is required with --import-lean", file=sys.stderr)
        return 2
    if bool(args.theorem) == bool(args.all_theorems):
        print(
            "error: exactly one of --theorem NAME or --all must be given",
            file=sys.stderr,
        )
        return 2
    if bool(args.ocse_uri) == bool(args.ocse_path):
        print(
            "error: exactly one of --ocse-uri URI or --ocse-path PATH must be given",
            file=sys.stderr,
        )
        return 2

    # 2. resolve OCSE
    try:
        ocse_path = _resolve_ocse_path(args)
    except SystemExit as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # 3. bootstrap target if missing
    target_path = Path(args.target).resolve()
    if not target_path.exists():
        if not args.working_uri:
            print(
                f"error: target module {target_path} does not exist and --working-uri "
                f"was not provided to auto-bootstrap it",
                file=sys.stderr,
            )
            return 2
        bootstrap_working_module(target_path, args.working_uri, ocse_path)
        print(f"bootstrapped working module: {target_path}")

    # 4. build Session and load OCSE under prefix `ma`
    session = Session(working_module_path=target_path, working_module_prefix="")
    session.load_dependency(ocse_path, prefix="ma")

    # 5. fetch + parse Lean source
    source_text = fetch_lean_source(args.import_lean)
    theorems = parse_theorems(source_text)
    if not theorems:
        print(
            f"error: no theorems parsed from {args.import_lean}",
            file=sys.stderr,
        )
        return 1

    # 6. determine source_url
    if args.source_url:
        source_url = args.source_url
    elif args.import_lean.startswith(("http://", "https://")):
        source_url = args.import_lean
    else:
        source_url = ""

    # 7. dispatch single vs --all
    if args.theorem:
        thm = find_theorem(theorems, args.theorem)
        if thm is None:
            print(
                f"error: theorem {args.theorem!r} not found in {args.import_lean} "
                f"(parsed {len(theorems)} theorems)",
                file=sys.stderr,
            )
            return 1
        targets = [thm]
    else:
        targets = theorems
        limit = getattr(args, "limit", 0)
        if limit:
            targets = targets[:limit]
            print(f"--limit: considering the first {len(targets)} of {len(theorems)} theorems")

    # 8. resolve the FORK policy into an ask_user callback
    fork_policy = getattr(args, "fork_policy", "ask")
    ask_user = {
        "ask": ask_user_via_stdin,
        "first": fork_policy_first,
        "skip": fork_policy_skip,
    }[fork_policy]

    stats_path = getattr(args, "stats_jsonl", None)
    keep_going = getattr(args, "keep_going", False)

    if getattr(args, "resume", False):
        if not (stats_path and args.all_theorems):
            print("error: --resume requires --all and --stats-jsonl", file=sys.stderr)
            return 2
        done_keys = set()
        if os.path.exists(stats_path):
            with open(stats_path) as fp:
                for line in fp:
                    if line.strip():
                        rec = json.loads(line)
                        done_keys.add((rec.get("namespace", ""), rec["theorem"]))
        if done_keys:
            before = len(targets)
            targets = [t for t in targets if (t.namespace, t.name) not in done_keys]
            print(f"--resume: skipping {before - len(targets)} already-recorded theorems")

    def write_stats(record: dict):
        if not stats_path:
            return
        with open(stats_path, "a") as fp:
            fp.write(json.dumps(record) + "\n")

    failures = 0
    fork_pending = 0
    for thm in targets:
        print(f"importing theorem: {thm.namespace}.{thm.name}")
        events: list = []
        t0 = time.time()
        record = {"theorem": thm.name, "namespace": thm.namespace}
        try:
            ok = import_theorem(
                thm,
                session=session,
                working_module_path=target_path,
                source_url=source_url,
                ask_user=ask_user,
                on_progress=print,
                events=events,
            )
        except ForkPending as fp_exc:
            fork_pending += 1
            print(f"theorem {thm.namespace}.{thm.name}: FORK pending (skipped per --fork-policy skip)")
            record.update(
                outcome="fork_pending",
                fork_question=fp_exc.question,
                fork_options=list(fp_exc.options),
            )
            _finalize_stats_record(record, events, t0)
            write_stats(record)
            continue
        except Exception as exc:
            print(
                f"theorem {thm.namespace}.{thm.name}: import raised {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            failures += 1
            record.update(outcome="error", error=f"{type(exc).__name__}: {exc}"[:300])
            _finalize_stats_record(record, events, t0)
            write_stats(record)
            if keep_going:
                continue
            break

        record.update(outcome="ok" if ok else "failed")
        _finalize_stats_record(record, events, t0)
        write_stats(record)
        if not ok:
            print(
                f"theorem {thm.namespace}.{thm.name}: import failed (see prior output)",
                file=sys.stderr,
            )
            failures += 1
            if not keep_going:
                break

    if fork_pending:
        print(f"{fork_pending} theorem(s) skipped as fork-pending")
    return 0 if failures == 0 else 1


def _finalize_stats_record(record: dict, events: list, t0: float) -> None:
    """Derive aggregate counters from the per-attempt event list."""
    record["duration_s"] = round(time.time() - t0, 2)
    record["n_forks"] = sum(1 for e in events if e["event"] == "fork")
    record["n_validation_fails"] = sum(1 for e in events if e["event"] == "validation_fail")
    record["n_malformed"] = sum(1 for e in events if e["event"] == "malformed")
    record["n_key_remaps"] = sum(1 for e in events if e["event"] == "key_remap")
    record["n_nonascii"] = sum(1 for e in events if e["event"] == "nonascii")
    record["n_scope_reopens"] = sum(1 for e in events if e["event"] == "scope_reopen")
    record["n_timeouts"] = sum(1 for e in events if e["event"] == "timeout")
    # every event except synthetic non-call events corresponds to one claude call
    record["n_claude_calls"] = sum(1 for e in events if e["event"] not in ("gave_up", "key_remap"))
    costs = [e["cost_usd"] for e in events if e.get("cost_usd") is not None]
    record["cost_usd"] = round(sum(costs), 4) if costs else None
    record["events"] = events


def process_package(pkg_path: str) -> Tuple[types.ModuleType, str]:
    if os.path.isdir(pkg_path):
        pkg_path = os.path.join(pkg_path, "irkpackage.toml")

    with open(pkg_path, "rb") as fp:
        irk_conf_dict = tomllib.load(fp)
    main_rel_path = irk_conf_dict["main_module"]
    main_module_prefix = irk_conf_dict["main_module_prefix"]
    main_mod_path = Path(pkg_path).parent.joinpath(main_rel_path).as_posix()

    mod = irkloader.load_mod_from_path(modpath=main_mod_path, prefix=main_module_prefix)
    return mod, main_module_prefix


def process_mod(path: str, prefix: str, relative_to_workdir: bool = False) -> types.ModuleType:
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
    with open(fname, "w", encoding="utf-8") as fp:
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
    pattern = re.compile(r"""(p.I000\[['"](.*?)['"]\])""")

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

    # Walk the ``insert_entities = [...]`` list via AST so that multi-line
    # entries (e.g. a long ``raw__I...set_relation(...)`` call) are kept as
    # one entry instead of being split by newlines.
    insert_assign = None
    for elt in templ_ast_cont.ast.body:
        if (
            isinstance(elt, ast.Assign)
            and elt.targets
            and isinstance(elt.targets[0], ast.Name)
            and elt.targets[0].id == "insert_entities"
        ):
            insert_assign = elt
            break
    assert insert_assign is not None, "template must contain `insert_entities = [...]`"

    entry_texts = []
    for item in insert_assign.value.elts:
        src = "".join(templ_ast_cont.lines[item.lineno - 1 : item.end_lineno])
        # trim a trailing comma (if present) and surrounding whitespace
        entry_texts.append(src.rstrip().rstrip(",").strip())

    short_template_path, fname = os.path.split(template_path)
    short_template_path = os.path.split(short_template_path)[-1]
    short_template_path = os.path.join(short_template_path, fname)

    lines_to_insert = []

    for line in entry_texts:
        if not line:
            continue
        if line.startswith("raw__"):
            # handle raw lines (verbatim insertion; may span multiple lines)
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

        original_content = mod_ast_cont.line_data.get(short_key, "")
        if not isinstance(original_content, str) or original_content == "":
            # Skip stale references (entity removed/renamed upstream) with a
            # warning instead of aborting the whole regeneration. This keeps
            # the subset usable while the template catches up.
            print(
                f"WARNING [{short_template_path}]: could not find associated "
                f"data for short_key {short_key} (template line `{line}`); "
                f"skipping this entry.",
                file=sys.stderr,
            )
            continue
        lines_to_insert.append(original_content)
        lines_to_insert.append("\n")

    new_insert_txt = "".join(lines_to_insert)

    rendered_template = templ_ast_cont.txt.replace(
        templ_ast_cont.line_data["insert_entities"], new_insert_txt
    )
    return rendered_template


def path_to_ast_container(mod_path: str) -> Container:

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


def bootstrap_config(ci_mode: bool = False):
    """
    Create an empty config.toml file in the user config directory.
    """
    config_dir = platformdirs.user_config_dir("pyirk")
    os.makedirs(config_dir, exist_ok=True)

    config_path = os.path.join(config_dir, "config.toml")

    if ci_mode:
        initial_content = aux.get_initial_config_content_for_ci()
    else:
        initial_content = dedent(
            """
        # PyIRK configuration file

        # example:
        # [package.ocse]
        # path = "/home/username/irk-data/ocse"

        # Optional: delegate a curated subset of rules to the Nemo datalog
        # engine for a large speedup on rule-heavy knowledge bases. This is
        # OFF by default; uncomment the two lines below to enable it
        # persistently for your installation. Requires the `nmo` binary on
        # PATH (or via PYIRK_NEMO_BIN); the native engine stays the reference
        # and the automatic fallback when nmo is absent.
        # Background, requirements and limitations — see the documentation:
        #   https://pyirk-core.readthedocs.io  ->  How-to  ->  Nemo delegation
        # [nemo]
        # delegation = true

        """
        )

    if os.path.exists(config_path):
        print(f"Config file already exists at: {config_path}")
        return

    with open(config_path, "w") as f:
        f.write(initial_content)

    print(f"Empty config file created at: {config_path}")


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
