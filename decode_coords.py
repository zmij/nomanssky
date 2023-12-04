#!/usr/bin/env python3

import argparse
import sys

from nomanssky import GalacticCoords, CoordinateSpace, enum_by_name
from nomanssky.ansicolour import Colour8Bit as cl, Options as opts, CLEAR as clear


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
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        default="dec",
        choices=["dec", "hex"],
        help="Output format, decimal or hexademic",
    )
    parser.add_argument(
        "-s",
        "--space",
        type=str,
        default="portal",
        choices=["portal", "galactic"],
        help="Coordinate space for X, Y and Z data",
    )

    return parser.parse_args()


def arg_input(args):
    for v in args:
        yield v


def stdin_input():
    for line in sys.stdin:
        yield line.rstrip()


def print_any(val: int, name: str, colour: cl):
    print(f"{colour}{name}: {colour + 'bright'}{val}{clear}")


def print_hex(val: int, name: str, colour: cl):
    if val is None:
        print(f"{colour}{name}: {colour + 'bright'}{val}{clear}")
    else:
        print(f"{colour}{name}: {colour + 'bright'}0x{val:X}{clear}")


def print_info(coords: GalacticCoords, format: str) -> None:
    if format == "hex":
        print_fn = print_hex
    else:
        print_fn = print_any

    print_any(coords.portal_code, "Portal code", cl.RED)
    print_any(coords.galactic_coords, "Galactic coords", cl.RED)
    print_any(coords.xyz, "XYZ", cl.RED)
    print_any(coords.coordinate_space.name, "Coord space", cl.GREEN)

    print_fn(coords.x, "X", cl.GREEN)
    print_fn(coords.y, "Y", cl.GREEN)
    print_fn(coords.z, "Z", cl.GREEN)
    print_fn(coords.star_system, "Star system", cl.BLUE)
    print_fn(coords.planet, "Planet", cl.BLUE)


def main():
    args = parse_args()
    try:
        input = arg_input(args.codes)
        if not args.codes or args.codes[0] == "-":
            # Read from stdin
            input = stdin_input()
        for code in input:
            coords = GalacticCoords(
                code, coordinate_space=enum_by_name(CoordinateSpace, args.space.title())
            )
            print_info(coords, args.format)
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    main()
