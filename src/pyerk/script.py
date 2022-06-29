"""
Command line interface for erk package
"""

import argparse
from ipydex import IPS, activate_ips_on_exception
from . import core, erkloader

activate_ips_on_exception()


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputfile",
        help=f"input file",
        nargs="?",
        default=None,
    )

    parser.add_argument(
        "--new-key",
        help=f"generate new key",
        default=None,
        action="store_true"
    )

    parser.add_argument(
        "--load-mod",
        help=f"load module",
        default=None,
    )

    args = parser.parse_args()

    if args.new_key:
        core.print_new_key(args.inputfile)

    elif args.inputfile is not None:
        core.script_main(args.inputfile)
    elif args.load_mod is not None:
        process_mod(path=args.load_mod)
    else:
        print("nothing to do, see option `--help` for more info")


def process_mod(path):
    mod = erkloader.load_mod_from_path(path, modname="kbase")
    IPS()
