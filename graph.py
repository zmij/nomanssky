#!/usr/bin/env python3

import asyncio
import argparse
import logging
import os

import pyvis.network

from typing import Set

import nms

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)

FORMULA_NODE_COLORS = {
    nms.FormulaType.CRAFT: "#dcd23d",
    nms.FormulaType.REFINING: "#623295",
}
FORMULA_EDGE_COLORS = {
    nms.FormulaType.CRAFT: "#45431f",
    nms.FormulaType.REFINING: "#392351",
}
NODE_CLASS_COLORS = {
    nms.Class.Resource: "#38b5b0",
    nms.Class.Tradeable: "#40b53a",
}
DEFAULT_NODE_COLOR = "#e05048"
EDGE_COLORS = {
    nms.FormulaType.CRAFT: "#742c28",
    nms.FormulaType.REFINING: "#245e21",
    nms.FormulaType.COOK: "#194745",
    nms.FormulaType.REPAIR: "#e0a748",
}


def get_node_color(logger: logging.Logger, cls: nms.Class) -> str:
    if cls in NODE_CLASS_COLORS:
        return NODE_CLASS_COLORS[cls]
    logger.info(f"No color defined for {cls.value}")
    return DEFAULT_NODE_COLOR


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
        default=2,
        help="Formula depth",
    )

    return parser.parse_args()


class GraphBuilder(nms.Loggable):
    ...


async def add_nodes(
    logger: logging.Logger,
    wiki: nms.Wiki,
    net: pyvis.network.Network,
    item: nms.Item,
    seen_nodes: Set[nms.Item],
    depth: int,
) -> None:
    if item is None or item in seen_nodes:
        return
    logger.info(f"Add {item.name} {item.cls.name} node")
    seen_nodes.add(item)
    net.add_node(
        item.id,
        label=item.id,
        shape="circularImage",
        image=item.image,
        color=get_node_color(logger, item.cls),
    )
    adjascent = item.source_items - seen_nodes
    adjascent_items = await wiki.get_items(adjascent)
    if depth > 0:
        tasks = [
            asyncio.create_task(add_nodes(logger, wiki, net, i, seen_nodes, depth - 1))
            for i in adjascent_items
        ]
        await asyncio.gather(*tasks)
    else:
        for i in adjascent_items:
            net.add_node(
                i.id,
                label=i.name,
                shape="circularImage",
                image=i.image,
                color=get_node_color(logger, i.cls),
            )

        seen_nodes |= set(adjascent_items)


async def build_formula_edges(
    logger: logging.Logger,
    wiki: nms.Wiki,
    net: pyvis.network.Network,
    seen_nodes: Set[nms.Item],
):
    seen_ids = set([x.id for x in seen_nodes])
    node_id = 0
    for item in seen_nodes:
        for f in item.source_formulas:
            source_ids = set([i.name for i in f.ingredients]) & seen_ids
            if not source_ids:
                # sources haven't been loaded, skip
                logger.info(f"Skip formula for {item.id} ({f.ingredients})")
                continue
            if len(source_ids) != len(f.ingredients):
                logger.info(f"Skip formula for {item.id} ({f.ingredients})")
                continue
            source_items = set(await wiki.get_items(source_ids))
            net.add_node(
                node_id,
                label=None,
                shape="circularImage",
                image=item.image,
                color=FORMULA_NODE_COLORS[f.type],
                title=f"{f!r}",
                size=10,
            )
            net.add_edge(
                node_id,
                item.id,
                color=EDGE_COLORS[f.type],
                title=f"{item.name} x{f.result.qty}",
            )
            for i in f.ingredients:
                net.add_edge(i.name, node_id, title=f"{i.name} x{i.qty}")
            # net.add_edges([(i.id, node_id) for i in source_items])
            node_id += 1


async def build_edges(
    logger: logging.Logger,
    wiki: nms.Wiki,
    net: pyvis.network.Network,
    seen_nodes: Set[nms.Item],
) -> None:
    seen_ids = set([x.id for x in seen_nodes])
    node_id = 0
    for item in seen_nodes:
        for f in item.source_formulas:
            source_ids = set([i.name for i in f.ingredients]) & seen_ids
            if not source_ids:
                # sources haven't been loaded, skip
                logger.info(f"Skip formula for {item.id} ({f.ingredients})")
                continue
            if len(source_ids) != len(f.ingredients):
                logger.info(f"Skip formula for {item.id} ({f.ingredients})")
                continue
            for i in f.ingredients:
                net.add_edge(i.name, item.id, title=f"{f!r}", color=EDGE_COLORS[f.type])


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    logger = logging.getLogger("Graph")
    async with nms.Wiki() as wiki:
        seen_nodes = set()
        item = await wiki.get_item(args.item)
        if not item.source_formulas:
            print(f"No formulas to make {item.name}")
        else:
            net = pyvis.network.Network(
                directed=True, bgcolor="#222222", font_color="white", height="100%"
            )

            items = await wiki.get_items(item.source_items)
            await add_nodes(logger, wiki, net, item, seen_nodes, args.depth)
            print(seen_nodes)
            # await build_formula_edges(logger, wiki, net, seen_nodes)
            await build_edges(logger, wiki, net, seen_nodes)

            net.toggle_physics(True)
            net.show_buttons(filter_="physics")
            #             net.set_options(
            #                 """
            # const options = {
            #   "physics": {
            #     "forceAtlas2Based": {
            #       "springLength": 100
            #     },
            #     "minVelocity": 0.75,
            #     "solver": "forceAtlas2Based"
            #   }
            # }            """
            #             )
            net.show(f"{item.id}.html", notebook=False)
            print(f"file://{os.getcwd()}/{item.id}.html")


if __name__ == "__main__":
    asyncio.run(main())
