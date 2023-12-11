#!/usr/bin/env python3

import asyncio
import argparse
import logging

from math import lcm
from typing import Any, Callable, Coroutine
from functools import cmp_to_key

import nomanssky as nms
from nomanssky.ansicolour import highlight_8bit as hl, Colour8Bit as cl
from nomanssky.symbols import Symbols

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
        nargs="*",
        help="No Man's Sky items research",
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
        "-o",
        "--order",
        default="DFS",
        choices=nms.enum_names(nms.WalkOrder),
        help="Graph walk order",
    )

    return parser.parse_args()


class CycleBuilder(nms.FormulaVisitor):
    def __init__(self, wiki: nms.Wiki, *, debug_traversal: bool = False) -> None:
        super().__init__(wiki)
        self._current_stack = nms.LIFO()
        self._color_gen = nms._formula_printer.cycle_8bit_colors()
        self._colors = dict[int, cl]()
        self.detected_cycles = dict[str, list[nms.ProductionChain]]()
        self._debug_traversal = debug_traversal
        self.inspected_nodes = 0

    def get_color(self, distance: int) -> cl:
        if distance not in self._colors:
            self._colors[distance] = next(self._color_gen)
        return self._colors[distance]

    async def examine_node(self, node: nms.Formula, distance: int) -> None:
        await super().examine_node(node, distance)
        if self._debug_traversal:
            self.print_traversal(node, distance, ">>>")
        self._current_stack.push(node)

    async def finish_node(self, node: nms.Formula, distance: int) -> None:
        await super().finish_node(node, distance)
        if self._debug_traversal:
            self.print_traversal(node, distance, "<<<")
        self._current_stack.pop()
        self.inspected_nodes += 1

    def print_traversal(self, node: nms.Formula, distance: int, sybmol: str) -> None:
        offset = " " * distance
        cl = self.get_color(distance)
        print(hl(f"{offset}{sybmol} {node!r}", fg=cl))

    async def tree_edge(self, source: nms.Formula, target: nms.Formula) -> None:
        await super().tree_edge(source, target)
        trace = self.backtrack_to(target)
        if trace:
            trace_str = " <- ".join(f.result.name for f in trace)
            cl = self.get_color(-1)
            print(hl(f"tree {trace_str}", fg=cl))

    async def back_edge(self, source: nms.Formula, target: nms.Formula) -> None:
        await super().back_edge(source, target)
        trace = self.backtrack_to(target)
        chain = nms.ProductionChain.from_formula_chain(*trace)
        # Force estimation cache
        value = await chain.estimate_value(self._wiki.get_items)
        if chain.has_profit or len(chain) < 5:
            await chain.estimate_time(
                self._wiki.get_items,
                refinery_limit={nms.RefinerySize.Medium: 1, nms.RefinerySize.Big: 1},
            )

        if target.result.name not in self.detected_cycles:
            self.detected_cycles[target.result.name] = list[nms.ProductionChain]()

        self.detected_cycles[target.result.name].append(chain)

        if self._debug_traversal:
            multiplied = []
            x = 1
            for tt in trace:
                if multiplied:
                    out = multiplied[-1].result.qty
                    inp = tt[multiplied[-1].result.name].qty
                    k = lcm(out, inp)
                    x = k // inp

                mf = tt * x
                multiplied.append(mf)

            trace_str = " -> ".join(f"`{f:'('%ing')'=%res}`" for f in multiplied)
            pos_cl = self.get_color(-2)
            neg_cl = self.get_color(-4)
            print(hl(trace_str, fg=pos_cl))

            trace_str = " ".join(f"'{f!r}'" for f in trace)
            print(hl(trace_str, fg=pos_cl))

            cl = chain.has_losses and neg_cl or pos_cl
            print(
                hl(
                    f"{chain} cost: {value.costs:.2f} value {value.value:.2f} diff {value.profit:.2f}",
                    fg=(cl, "bright"),
                )
            )

    async def fwd_or_cross_edge(self, source: nms.Formula, target: nms.Formula) -> None:
        await super().fwd_or_cross_edge(source, target)
        trace = self.backtrack_to(target)
        if trace:
            trace_str = " -> ".join(f.result.name for f in trace)
            cl = self.get_color(-3)
            print(hl(f"cross {trace_str}", fg=cl))

    def backtrack_to(self, node: nms.Formula) -> None:
        condition = lambda s: s == node
        return self.backtrack(condition)

    def backtrack(self, condition: Callable[[Any], bool]) -> list[nms.Formula]:
        trace = list[nms.Formula]()
        backup = nms.LIFO()
        while not self._current_stack.empty:
            item = self._current_stack.pop()
            trace.append(item)
            backup.push(item)
            if condition(item):
                break

        # Restore stack
        self._current_stack.add(backup)

        if not condition(trace[-1]):
            return []

        return trace


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nms.Wiki() as wiki:
        if not args.items:
            items = await wiki.search_item()
        else:
            items = await wiki.get_items(args.items)

        wiki.log_info(f"Found {len(items)} items")
        source_formulas = [f for i in items if i is not None for f in i.source_formulas]
        wiki.log_info(f"Found {len(source_formulas)} source formulas")

        if not source_formulas:
            print(f"No formulas to make {items}")
            exit(1)
        else:
            vis = CycleBuilder(wiki, debug_traversal=True)
            await nms.walk_graph(
                source_formulas,
                vis,
                walk_order=nms.enum_by_name(nms.WalkOrder, args.order),
            )
            cycle_count = 0
            wiki.log_info(f"Inspected {vis.inspected_nodes} nodes")
            for name, cycles in vis.detected_cycles.items():
                cl = vis.get_color(name)
                print(hl(name, fg=(cl, "bright")))
                cycles = sorted(
                    cycles,
                    key=cmp_to_key(
                        nms.make_prod_chain_compare(
                            [
                                nms.ChainCompareType.Value,
                                nms.ChainCompareType.Output,
                                nms.ChainCompareType.Length,
                                nms.ChainCompareType.Time,
                                nms.ChainCompareType.Input,
                            ]
                        )
                    ),
                )
                for c in cycles:
                    cycle_count += 1
                    fg = (cl, "dim")
                    if c.has_profit and c.estimated_values.profit > 0:
                        fg = (cl,)
                    pl = c.production_line
                    prod = (
                        pl
                        and (
                            f"Big: {pl.big.actual_pool_size}/{pl.big.max_time}, "
                            + f"Medium: {pl.medium.actual_pool_size}/{pl.medium.max_time}, "
                            + f"Craft: {pl.craft.max_len}/{pl.craft.max_time}"
                        )
                        or "Not estimated"
                    )
                    print(
                        hl(
                            f"{c}\n\t{c.estimated_values.profit:+.1f}{Symbols.UNITS} total time {c.estimated_time} {prod}",
                            fg=fg,
                        )
                    )
            print(f"{cycle_count} cycles detected")


if __name__ == "__main__":
    asyncio.run(main())
