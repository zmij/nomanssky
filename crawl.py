#!/usr/bin/env python3

import asyncio
import argparse
import logging

from typing import Set

import nomanssky

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-10s - %(levelname)-7s - %(message)s",
)


def print_missing_enum_values(cls):
    if hasattr(cls, "seen_missing"):
        print(f"Missing {cls.__name__} values:")
        for k, v in cls.seen_missing.items():
            print(f"\t`{k}` : {v} times")
    else:
        print(f"No missing values in {cls.__name__}")


def parse_args():
    parser = argparse.ArgumentParser("Load No Man's Sky wiki page")
    parser.add_argument("page", type=str, help="Item name")  # TODO Array
    parser.add_argument(
        "-v",
        "--log-level",
        type=str,
        choices=LOG_LEVELS.keys(),
        default="INFO",
        help="Log level",
    )
    parser.add_argument(
        "-c",
        "--missing-classes",
        action="store_true",
        help="Output missing Class enum values",
    )
    parser.add_argument(
        "-t",
        "--missing-types",
        action="store_true",
        help="Output missing Type enum values",
    )
    parser.add_argument(
        "-r",
        "--missing-rarities",
        action="store_true",
        help="Output missing Rarity enum values",
    )

    return parser.parse_args()


class VisitStat:
    def __init__(self) -> None:
        self.items = 0
        self.repeated = 0
        self.in_db = 0


async def visit_item(
    logger: logging.Logger,
    wiki: nomanssky.Wiki,
    item: str,
    visited: Set[str],
    to_visit: Set[str],
    stats: VisitStat,
):
    if item in visited:
        logger.warning(f"{item} is alredy marked visited")
        stats.repeated += 1
        return
    stats.items += 1
    visited.add(item)
    item, in_db = await wiki.get_item(item, return_in_db=True)
    if in_db:
        stats.in_db += 1
    if item:
        to_visit |= item.linked_items - visited
        if not in_db:
            logger.info(f"Parsed {item}")


async def main():
    logger = logging.getLogger("Crawler")
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    stats = VisitStat()
    try:
        async with nomanssky.Wiki() as wiki:
            to_visit: set[str] = set([args.page])
            visited = set()

            while to_visit:
                next_visit: set[str] = set()
                logger.info(f"Run {len(to_visit)} tasks")
                tasks = [
                    asyncio.create_task(
                        visit_item(logger, wiki, p, visited, next_visit, stats)
                    )
                    for p in to_visit
                ]
                await asyncio.gather(*tasks)

                to_visit = next_visit

    except asyncio.exceptions.CancelledError:
        ...
    except KeyboardInterrupt:
        ...

    print(
        f"Visited items: {stats.items}\nRepeated requests: {stats.repeated}\nFound in db: {stats.in_db}"
    )

    if args.missing_classes:
        print_missing_enum_values(nomanssky.Class)
    if args.missing_types:
        print_missing_enum_values(nomanssky.Type)
    if args.missing_rarities:
        print_missing_enum_values(nomanssky.Rarity)


if __name__ == "__main__":
    asyncio.run(main())
