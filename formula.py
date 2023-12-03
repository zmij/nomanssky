#!/usr/bin/env python3

import asyncio
import argparse
import logging

from enum import Enum

from typing import Set, Callable

import nomanssky

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)

TREE_BRANCH = "├"
TREE_LAST_BRANCH = "└"


class FormulaTypeFilter(Enum):
    ANY = "any"
    REFINE = "refine"
    CRAFT = "craft"
    COOK = "cook"


FILTER_TO_FORMULA_TYPE = {
    FormulaTypeFilter.REFINE: nomanssky.FormulaType.REFINING,
    FormulaTypeFilter.CRAFT: nomanssky.FormulaType.CRAFT,
    FormulaTypeFilter.COOK: nomanssky.FormulaType.COOK,
}

# FormulaPredicate = Callable[[nms.Formula], bool]


def parse_args():
    parser = argparse.ArgumentParser("Load No Man's Sky wiki page")
    parser.add_argument(
        "item", type=str, help="No Man's Sky item to show"
    )  # TODO Array
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
        choices=nomanssky.enum_values(FormulaTypeFilter),
        help="Filter formulas by type",
    )

    return parser.parse_args()


def component_count_filter(cn: int) -> nomanssky.FormulaPredicate:
    if cn == 0:
        return None

    def filter(f: nomanssky.Formula) -> bool:
        return len(f.ingredients) == cn

    return filter


def formula_type_filter(t: FormulaTypeFilter) -> nomanssky.FormulaPredicate:
    if t == FormulaTypeFilter.ANY:
        return None

    to_find = FILTER_TO_FORMULA_TYPE[t]

    def filter(f: nomanssky.Formula) -> bool:
        return f.type == to_find

    return filter


def combine_predicates(*args) -> nomanssky.FormulaPredicate:
    not_empty = [f for f in args if f is not None]
    if not not_empty:
        return None

    def filter(f: nomanssky.Formula) -> bool:
        for p in not_empty:
            if not p(f):
                return False
        return True

    return filter


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nomanssky.Wiki() as wiki:
        seen_formulas = set()
        item = await wiki.get_item(args.item)
        if not item.source_formulas:
            print(f"No formulas to make {item.name}")
        else:
            count_filter = component_count_filter(args.component_count)
            type_tilter = formula_type_filter(FormulaTypeFilter(args.type))

            printer = nomanssky.FormulaPrinter(
                wiki,
                find_cheapest=args.cheapest,
                filter=combine_predicates(count_filter, type_tilter),
            )
            await printer.print_item_formulas(item, args.depth, seen_formulas)


if __name__ == "__main__":
    asyncio.run(main())
