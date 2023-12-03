#!/usr/bin/env python3

import asyncio
import argparse
import logging
import json

from termcolor import colored

import nms

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)


def parse_args():
    parser = argparse.ArgumentParser("Load No Man's Sky wiki page")
    parser.add_argument("item", type=str, help="Item name")  # TODO Array
    parser.add_argument(
        "-v",
        "--log-level",
        type=str,
        choices=LOG_LEVELS.keys(),
        default="INFO",
        help="Log level",
    )

    return parser.parse_args()


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nms.Wiki() as wiki:
        item = await wiki.get_item(args.item)
        if item is None:
            print(f"No item {args.item} found")
            return
        print(json.dumps(item, cls=nms.JSONEncoder))


if __name__ == "__main__":
    asyncio.run(main())
