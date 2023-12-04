#!/usr/bin/env python3

import argparse
import sys

from nomanssky import GalacticCoords


def parse_args():
    parser = argparse.ArgumentParser(
        "No Man's Sky booster to galactic coordinates converter"
    )
    parser.add_argument(
        "codes",
        type=str,
        nargs="*",
        metavar="<CODE>",
        help="Signal booster or portal code",
    )

    return parser.parse_args()


def arg_input(args):
    for v in args:
        yield v


def stdin_input():
    for line in sys.stdin:
        yield line.rstrip()


def main():
    args = parse_args()
    try:
        input = arg_input(args.codes)
        if not args.codes or args.codes[0] == "-":
            # Read from stdin
            input = stdin_input()
        for code in input:
            coords = GalacticCoords(code)
            print(coords.xyz)
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    main()
