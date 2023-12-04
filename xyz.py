#!/usr/bin/env python3

import argparse
import sys

from nomanssky import GalacticCoords


def parse_args():
    parser = argparse.ArgumentParser(
        "No Man's Sky booster to galactic coordinates converter"
    )
    parser.add_argument(
        "code",
        type=str,
        metavar="<CODE>",
        help="Signal booster or portal code",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    try:
        coords = GalacticCoords(code=args.code)
        print(coords.xyz)
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    main()
