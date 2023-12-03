#!/usr/bin/env python3

import aiohttp
import asyncio
import argparse
import logging

import nomanssky

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)

WIKI_BASE = "https://nomanssky.fandom.com/wiki/"


def parse_args():
    parser = argparse.ArgumentParser("Load No Man's Sky wiki page")
    parser.add_argument("page", type=str, help="Page name")  # TODO Array

    return parser.parse_args()


async def main():
    args = parse_args()

    async with aiohttp.ClientSession() as session:
        url = f"{WIKI_BASE}{args.page}"
        parser = nomanssky.PageParser(session, url)
        doc = await parser.content()
        print(doc.prettify())


if __name__ == "__main__":
    asyncio.run(main())
