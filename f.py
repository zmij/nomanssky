#!/usr/bin/env python3

import asyncio
import argparse
import logging

from enum import Enum

import nomanssky

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)


def parse_args():
    parser = argparse.ArgumentParser("Load No Man's Sky wiki page")
    parser.add_argument(
        "items",
        type=str,
        nargs="+",
        help="No Man's Sky item to show",
    )
    parser.add_argument(
        "-v",
        "--log-level",
        type=str,
        choices=LOG_LEVELS.keys(),
        default="INFO",
        help="Log level",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=1,
        help="Formula depth",
    )
    parser.add_argument(
        "-c", "--cheapest", action="store_true", help="Highlight cheapest formula"
    )
    parser.add_argument(
        "-n",
        "--component-count",
        type=int,
        default=0,
        help="Formula component count (default 0 means any)",
    )
    parser.add_argument(
        "-t",
        "--type",
        default="any",
        choices=nomanssky.enum_values(nomanssky.FormulaTypeFilter),
        help="Filter formulas by type",
    )
    parser.add_argument(
        "-o",
        "--order",
        default="DFS",
        choices=nomanssky.enum_names(nomanssky.WalkOrder),
        help="Graph walk order",
    )
    parser.add_argument(
        "-j",
        "--use-emoji",
        action="store_true",
        help="Use emoji for formula types",
    )
    parser.add_argument(
        "-l",
        "--formula_number",
        type=int,
        default=0,
        help="Number of formulas to pick (option for debugging)",
    )
    parser.add_argument(
        "-f",
        "--formula",
        type=str,
        default=None,
        help="Formula's repr (option for debugging)",
    )

    return parser.parse_args()


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nomanssky.Wiki() as wiki:
        items = await wiki.get_items(args.items)
        source_formulas = [f for i in items if i is not None for f in i.source_formulas]

        if not source_formulas:
            print(f"No formulas to make {items}")
            exit(1)
        else:
            if args.formula is not None:
                source_formulas = [
                    f for f in source_formulas if f.__repr__() == args.formula
                ]
                if not source_formulas:
                    print(f"Formula {args.formula} not found")
                    exit(1)
            elif args.formula_number > 0:
                source_formulas = source_formulas[0 : args.formula_number]
                print(source_formulas)
            count_filter = nomanssky.component_count_filter(args.component_count)
            type_tilter = nomanssky.formula_type_filter(
                nomanssky.FormulaTypeFilter(args.type)
            )

            vis = nomanssky.FormulaTreePrinter(
                wiki,
                filter=nomanssky.combine_predicates(count_filter, type_tilter),
                max_distance=args.depth,
                use_type_emoji=args.use_emoji,
            )
            await nomanssky.walk_graph(
                source_formulas,
                vis,
                walk_order=nomanssky.enum_by_name(nomanssky.WalkOrder, args.order),
            )


if __name__ == "__main__":
    asyncio.run(main())
