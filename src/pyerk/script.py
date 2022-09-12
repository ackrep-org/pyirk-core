"""
Command line interface for erk package
"""
import os
import argparse
from ipydex import IPS, activate_ips_on_exception
from . import core, erkloader, rdfstack, auxiliary as aux
from . import ackrep_parser

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
        "--load-mod",
        help=f"load module",
        default=None,
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

    parser.add_argument("--dbg", help=f"start debug routine", default=None, action="store_true")

    args = parser.parse_args()

    if args.dbg:
        debug()
        exit()

    if args.load_mod is not None:
        process_mod(path=args.load_mod)

    # typical call: pyerk --new-key --load-mod ../erk-data/control-theory/control_theory1.py --nk 100
    if args.new_keys:
        if not args.load_mod:
            print(aux.byellow("No module loaded. There might be key clashes. Use `--load-mod` to prevent this."))
        core.print_new_keys(args.nk)

    elif args.inputfile is not None:
        core.script_main(args.inputfile)
    elif args.parse_ackrep_data:
        ackrep_parser.parse_ackrep(args.parse_ackrep_data)
    else:
        print("nothing to do, see option `--help` for more info")


def process_mod(path):
    mod1 = erkloader.load_mod_from_path(path, modname="kbase")
    rdfstack.check_all_relation_types()


def debug():
    ERK_ROOT_DIR = aux.get_erk_root_dir()
    TEST_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "control-theory", "control_theory1.py")
    mod1 = erkloader.load_mod_from_path(TEST_DATA_PATH, prefix="ct")
    ackrep_parser.parse_ackrep()
    ds = core.ds
    ds.rdfgraph = rdfstack.create_rdf_triples()
    qsrc = rdfstack.get_sparql_example_query2()
    res = ds.rdfgraph.query(qsrc)
    z = aux.apply_func_to_table_cells(rdfstack.convert_from_rdf_to_pyerk, res)
    IPS()
