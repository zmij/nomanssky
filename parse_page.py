#!/usr/bin/env python3

import asyncio
import argparse
import logging
import json


LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)

import nms


def parse_args():
    parser = argparse.ArgumentParser("Load No Man's Sky wiki page")
    parser.add_argument("page", type=str, help="Page name")  # TODO Array
    parser.add_argument(
        "-v",
        "--log-level",
        type=str,
        choices=LOG_LEVELS.keys(),
        default="INFO",
        help="Log level",
    )

    return parser.parse_args()


def dump_item(item: nms.Item) -> None:
    print(item.name)
    for k, v in item.__dict__.items():
        if k.startswith("_"):  # or k.endswith("_"):
            continue
        if isinstance(v, type(item.log_debug)):
            continue
        print(f"{k} = {v}")


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nms.Wiki() as wiki:
        item, _ = await wiki.parse_page(args.page)
        if item is None:
            print(f"No item {args.page} found")
            return
        print(json.dumps(item, cls=nms.JSONEncoder))
        wiki.store_to_db(item)


if __name__ == "__main__":
    asyncio.run(main())
