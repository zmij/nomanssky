#!/usr/bin/env python3

import argparse
import sys

from nomanssky import GalacticCoords


def parse_args():
    parser = argparse.ArgumentParser(
        "No Man's Sky portal to signal booster coordinates converter"
    )
    parser.add_argument(
        "portal_code",
        type=str,
        metavar="<PORTAL CODE>",
        help="Portal glyph code in hexademical form.\n"
        + "It is a 12-length hexademical string that looks like 00380256EC6B.\n"
        + "The code can be converted from glyphs here https://nmsportals.github.io",
    )
    parser.add_argument(
        "-b",
        "--booster",
        type=str,
        default=None,  # "HUKYA",
        metavar="<SCANNER ID>",
        help="Scanner ID",
    )
    parser.add_argument(
        "-s",
        "--separator",
        type=str,
        default=":",
        help="Output field separator. NOTE: `|` should be quoted when passing to command line",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    try:
        coords = GalacticCoords.from_portal_code(args.portal_code)
        print(coords.booster_code(alpha=args.booster, sep=args.separator))
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    main()
