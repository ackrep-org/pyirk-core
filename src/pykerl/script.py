"""
Command line interface for pykerl package
"""

import argparse
from ipydex import IPS, activate_ips_on_exception
from . import core

activate_ips_on_exception()


def main():


    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputfile", help=f"input file", default=None,
    )

    args = parser.parse_args()

    if args.inputfile is not None:
        core.script_main(args.inputfile)
    else:
        print("nothing to do, see option `--help` for more info")
