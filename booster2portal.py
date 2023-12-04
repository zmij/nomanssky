#!/usr/bin/env python3

import argparse
import sys

from nomanssky import GalacticCoords


def parse_args():
    parser = argparse.ArgumentParser(
        "No Man's Sky booster to galactic coordinates converter"
    )
    parser.add_argument(
        "booster_code",
        type=str,
        metavar="<BOOSTER CODE>",
        help="Signal booster code, can be obtained looking at the signal booster.\n"
        + "Looks like HUKYA:046A:0081:0D6D:0038, the first part may be omitted, then the value must start with a colon (:)",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    try:
        coords = GalacticCoords.from_booster_code(args.booster_code)
        print(coords.portal_code)
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    main()
