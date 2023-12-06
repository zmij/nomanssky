#!/usr/bin/env python3

import asyncio
import argparse
import logging
import datetime

from typing import Any, Coroutine, Set, Dict, List, Callable, Iterable, Tuple
from math import lcm

import nomanssky
from nomanssky.ansicolour import highlight_8bit as hl

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)


def hlprint(text: str, *args, **kwargs):
    print(hl(text, **kwargs))


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
        "-a",
        "--avoid",
        nargs="+",
        default=[],
        help="Avoid using resources",
    )
    parser.add_argument(
        "-c",
        "--prefer-craft",
        action="store_true",
        help="Prefer craft operations",
    )
    parser.add_argument(
        "-x",
        "--multiple",
        type=int,
        default=1,
        help="Make BOM for multiple items",
    )

    return parser.parse_args()


class BOMCounter(nomanssky.NodeVisitor[nomanssky.BOM], nomanssky.Loggable):
    def __init__(self, boms: Dict[str, nomanssky.BOM]) -> None:
        super().__init__()
        self.boms = boms
        self.process_count: Dict[str, int] = {}

    async def get_adjacent(
        self, node: nomanssky.BOM, direction: nomanssky.WalkDirection, distance: int
    ) -> Set[nomanssky.BOM]:
        return {
            self.boms[dep.formula.result.name] for dep in node.formula_tree.dependencies
        }

    async def discover_node(self, node: nomanssky.BOM, distance: int) -> None:
        self.process_count[node.name] = 1

    async def tree_edge(self, source: nomanssky.BOM, target: nomanssky.BOM) -> None:
        self.process_count[target.name] += 1

    async def back_edge(self, source: nomanssky.BOM, target: nomanssky.BOM) -> None:
        self.process_count[target.name] += 1

    async def fwd_or_cross_edge(
        self, source: nomanssky.BOM, target: nomanssky.BOM
    ) -> None:
        self.process_count[target.name] += 1


class BOMPrinter(nomanssky.NodeVisitor[nomanssky.BOM], nomanssky.Loggable):
    def __init__(
        self,
        boms: Dict[str, nomanssky.BOM],
        counts: Dict[str, int],
        print_formula: Callable[[nomanssky.Item, nomanssky.Formula, str], None],
        get_color: Callable[[nomanssky.Formula], Any],
        multiple: int = 1,
    ) -> None:
        super().__init__()
        self.boms = boms
        self.counts = counts
        self.print_formula = print_formula
        self.get_color = get_color
        self.refineries = {"medium": 0, "big": 0}
        self.refine_time = 0
        self.max_refine_time = 0
        self.refinery_allocations: List[Tuple[str, str]] = []
        self.steps = {
            nomanssky.FormulaType.REFINING: 0,
            nomanssky.FormulaType.CRAFT: 0,
            nomanssky.FormulaType.COOK: 0,
        }
        self._multiple = multiple

    async def get_adjacent(
        self, node: nomanssky.BOM, direction: nomanssky.WalkDirection, distance: int
    ) -> Set[nomanssky.BOM]:
        return {
            self.boms[dep.formula.result.name] for dep in node.formula_tree.dependencies
        }

    async def finish_node(self, node: nomanssky.BOM, distance: int) -> None:
        formula = node.formula_tree.formula
        count = self.counts[node.name] * node.output_qty * self._multiple
        color = self.get_color(formula)
        refine_time = ""
        if formula.type == nomanssky.FormulaType.REFINING:
            ref_size = len(formula.ingredients) < 3 and "medium" or "big"
            self.refineries[ref_size] += 1
            if formula.time is not None:
                t = formula.time * count
                refine_time = f" refine time {t} secs"
                self.refine_time += t
                if t > self.max_refine_time:
                    self.max_refine_time = t
            self.refinery_allocations.append((str(node.formula_tree.formula), ref_size))

        self.steps[formula.type] += 1
        hlprint(f"{node.name} x{count}{refine_time}", fg=color)
        await self.print_formula(node.result, formula, "")


class BOMBuilder(nomanssky.FormulaTreePrinter):
    def __init__(
        self, wiki: nomanssky.Wiki, avoid: Iterable[str], prefer_craft: bool
    ) -> None:
        super().__init__(wiki)
        self._bom_stack = nomanssky.LIFO[List[nomanssky.BOM]]()
        self.best_boms: Dict[str, nomanssky.BOM] = {}
        self.avod = set(avoid)
        self.prefer_craft = prefer_craft

    def filter(self, formula: nomanssky.Formula, result: nomanssky.Item) -> bool:
        return result.cls != nomanssky.Class.Resource

    async def examine_node(self, formula: nomanssky.Formula, distance: int) -> None:
        self.log_debug(f"Examine {formula.result.name} distance {distance}")

        result = await self._wiki.get_item(formula.result.name)
        if result.cls == nomanssky.Class.Resource:
            return
        self._bom_stack.push(list())
        await self.print_formula(result, formula, " " * distance * 3)

    async def finish_node(self, formula: nomanssky.Formula, distance: int) -> None:
        result = await self._wiki.get_item(formula.result.name)
        if result.cls == nomanssky.Class.Resource:
            return

        self.log_debug(
            f"Finish {formula.result.name} distance {distance} stack size {len(self._bom_stack)}"
        )

        boms = self._bom_stack.pop()
        if not boms:
            bom = await nomanssky.BOM.make_bom(
                self._wiki,
                result,
                formula,
                self.best_boms,
                self.avod,
                self.prefer_craft,
            )
            boms = [bom]
        else:
            # Sum boms by component
            bom = nomanssky.BOM.combine_boms(
                result, formula, boms, self.best_boms, self.avod, self.prefer_craft
            )

        if not self._bom_stack.empty:
            self._bom_stack.top().append(bom)

        if result.id in self.best_boms:
            if bom < self.best_boms[result.id]:
                self.best_boms[result.id] = bom
        else:
            self.best_boms[result.id] = bom

        self.print_totals(bom, formula, distance)

    def print_totals(
        self, bom: nomanssky.BOM, formula: nomanssky.Formula, distance: int
    ) -> None:
        color = self.get_color(formula)
        off = " " * distance * 3
        print(
            hl(
                f"{off}{bom}",
                fg=color,
            )
        )

    async def print_bom(self, name: str, multiple: int = 1) -> None:
        if name not in self.best_boms:
            hlprint(f"No bom for {name} found")
            return
        bom = self.best_boms[name]
        color = self.get_color(bom.formula_tree.formula)
        hlprint("=" * 80, fg=color)
        hlprint(
            f"BOM for {bom.result.id} value {bom.result.value} (cost per item {bom.per_item}) x{bom.output_qty * multiple}",
            fg=(color, "bright"),
        )
        if self.avod:
            hlprint("Avoiding " + ", ".join([x for x in self.avod]), fg=(color, "em"))
        if self.prefer_craft:
            hlprint("Craft operations in priority", fg=(color, "em"))
        # First goes the raw material count
        for ing in bom.ingredients:
            print(
                hl(f"  {ing.name:20s}", fg=(color, "em"))
                + hl(f" x{ing.qty * multiple}", fg=color)
            )

        vis = BOMCounter(self.best_boms)
        await nomanssky.walk_graph([bom], vis)

        hlprint("=" * 80, fg=color)
        hlprint("Process", fg=(color, "bright"))
        vis = BOMPrinter(
            self.best_boms,
            vis.process_count,
            self.print_formula,
            self.get_color,
            multiple=multiple,
        )
        await nomanssky.walk_graph([bom], vis)
        hlprint("=" * 80, fg=color)
        hlprint(f"Total steps {sum([v for v in vis.steps.values()])}", fg=color)
        for k, v in vis.steps.items():
            if not v:
                continue
            print(hl(f"{k.value}: ", fg=(color, "em")) + hl(str(v), fg=color))
        if vis.refinery_allocations:
            print(
                hl("Refinery allocations:\n  ", fg=(color, "bright"))
                + hl(
                    "\n  ".join(
                        [f"{x[1]} {x[0]}" for x in sorted(vis.refinery_allocations)]
                    ),
                    fg=(color, "em"),
                )
            )
        hlprint(
            f"Total refineries {sum([v for v in vis.refineries.values()])}",
            fg=(color, "bright"),
        )
        for k, v in vis.refineries.items():
            if not v:
                continue
            print(hl(f"{k:8s}: ", fg=(color, "em")) + hl(str(v), fg=color))
        if vis.refine_time > 0:
            max_refine_time = datetime.timedelta(seconds=vis.max_refine_time)
            total_refine_time = datetime.timedelta(seconds=vis.refine_time)
            hlprint(f"Max refine time {max_refine_time}", fg=color)
            hlprint(f"Total refine time {total_refine_time}", fg=color)
        hlprint(
            f"{vis.steps[nomanssky.FormulaType.CRAFT] * multiple} taps for crafting",
            fg=color,
        )


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nomanssky.Wiki() as wiki:
        item = await wiki.get_item(args.item)
        if not item:
            print(f"Item not found")
            exit(1)
        vis = BOMBuilder(wiki, avoid=args.avoid, prefer_craft=args.prefer_craft)
        await nomanssky.walk_graph(
            item.source_formulas,
            vis,
            walk_order=nomanssky.WalkOrder.DFS,
            log=wiki.log_debug,
        )
        await vis.print_bom(args.item, multiple=args.multiple)


if __name__ == "__main__":
    asyncio.run(main())
