"""
Command line interface for erk package
"""
import os
import argparse
from . import core, erkloader, rdfstack
from . import visualization
from . import reportgenerator
from . import auxiliary as aux
from . import settings

from ipydex import IPS, activate_ips_on_exception

activate_ips_on_exception()


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputfile",
        help=f"input file",
        nargs="?",
        default=None,
    )

    parser.add_argument("--new-keys", help=f"generate new key", default=None, action="store_true")

    parser.add_argument(
        "-l",
        "--load-mod",
        help=f"load module from path with prefix. You might want to provide the `-rwd` flag",
        nargs=2,
        default=None,
        metavar="MOD_PATH",
    )

    # background: by default erk-module paths are specified wrt the path of the pyerk.core python module
    # (and thus not wrt the current working dir)
    parser.add_argument(
        "-rwd",
        "--relative-to-workdir",
        help=f"specifies that the module path is interpreted relative to working dir (not the modules install path)",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--nk",
        help=f"number of keys",
        type=int,
        default=30,
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
        help="generate report for entity",
        metavar="uri",
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
        help="start an interactive session (with the specified module loaded)",
        action="store_true",
    )

    parser.add_argument("--dbg", help=f"start debug routine", default=None, action="store_true")

    args = parser.parse_args()

    if args.dbg:
        debug()
        exit()

    if args.load_mod is not None:

        rtwd = args.relative_to_workdir
        path, prefix = args.load_mod
        loaded_mod = process_mod(path=path, prefix=prefix, relative_to_workdir=rtwd)
    else:
        loaded_mod = None
        prefix = None

    if args.interactive_session:
        interactive_seesion(loaded_mod, prefix)
        exit()

    # typical calls to generate new keys:

    # with path relative to the module (not current working dir)
    # pyerk --load-mod ../../../erk-data/ocse/control_theory1.py ocse --new-keys --nk 100

    # with true relative path
    # pyerk --new-keys 30 --load-mod ../knowledge-base/rules/rules1.py rl -rwd
    if args.new_keys:
        if not args.load_mod:
            print(aux.byellow("No module loaded. There might be key clashes. Use `--load-mod` to prevent this."))
        core.print_new_keys(args.nk, loaded_mod)

    elif args.inputfile is not None:
        core.script_main(args.inputfile)
    elif args.generate_report:
        reportgenerator.generate_report()
    elif args.parse_ackrep_data:

        # TODO @Julius
        raise NotImplementedError("This functionality was removed")
        # ackrep_parser.load_ackrep_entities(args.parse_ackrep_data)
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
    else:
        print("nothing to do, see option `--help` for more info")


def process_mod(path: str, prefix: str, relative_to_workdir: bool = False) -> erkloader.ModuleType:

    smart_relative = not relative_to_workdir
    mod1 = erkloader.load_mod_from_path(path, prefix=prefix, smart_relative=smart_relative)

    # perform sanity check
    # rdfstack.check_all_relation_types()
    return mod1


def debug():
    ERK_ROOT_DIR = aux.get_erk_root_dir()
    TEST_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "ocse", "control_theory1.py")
    mod1 = erkloader.load_mod_from_path(TEST_DATA_PATH, prefix="ct")
    ds = core.ds
    ds.rdfgraph = rdfstack.create_rdf_triples()
    qsrc = rdfstack.get_sparql_example_query2()
    res = ds.rdfgraph.query(qsrc)
    z = aux.apply_func_to_table_cells(rdfstack.convert_from_rdf_to_pyerk, res)
    IPS()


def interactive_seesion(loaded_mod, prefix):
    """
    Start an interactive IPython session where the (optinally) loaded mod is available under its prefix name.
    """
    import pyerk as p
    if loaded_mod is not None and prefix is not None:
        locals()[prefix] = loaded_mod

    IPS()
