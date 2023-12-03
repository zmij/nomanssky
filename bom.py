#!/usr/bin/env python3

import asyncio
import argparse
import logging
import datetime

from typing import Any, Coroutine, Set, Dict, List, Callable, Iterable, Tuple
from math import lcm

import nms
from nms.ansicolour import highlight_8bit as hl

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


class _FormulaNode:
    def __init__(self, formula: nms.Formula, dependencies: List[Any] = []) -> None:
        self.formula = formula
        self.dependencies: List[_FormulaNode] = dependencies


class BOM:
    """
    Bill Of Materials for creating an item

    Consists of FormulaIngredient objects, can multiply by a number or sum with another BOM.
    Has a total value
    """

    ingredients: List[nms.Ingredient]
    components: Dict[str, nms.Item]

    def __init__(
        self,
        result: nms.Item,
        ingredients: List[nms.Ingredient],
        components: Dict[str, nms.Item],
        result_qty: int,
        formulas: _FormulaNode,
        avoid: bool,
        prefer_craft: bool,
    ) -> None:
        self.result = result
        self.ingredients = sorted(ingredients, key=lambda i: i.name)
        self.components = components
        self.max_rarity = max([c.rarity for c in components.values()])
        self.output_qty = result_qty
        self.total = sum([components[i.name].value * i.qty for i in ingredients])
        self.per_item = self.total / result_qty
        self.formula_tree = formulas
        self._avoid = avoid
        self._prefer_craft = prefer_craft

    def __str__(self) -> str:
        ing_strs = [
            f"({self.components[i.name].symbol_or_id} x{i.qty})"
            for i in self.ingredients
        ]
        return (
            f"{self.result.symbol_or_id} {self.output_qty}x{self.result.value}"
            + " = "
            + " + ".join(ing_strs)
            + f" ∑ = {self.total} ({self.output_qty}x{self.per_item:.1f}) ({self.max_rarity.value})"
        )

    def __repr__(self) -> str:
        ing_strs = [
            f"({self.components[i.name].symbol_or_id} x{i.qty})"
            for i in self.ingredients
        ]
        return f"{self.result.symbol_or_id} = " + " + ".join(ing_strs)

    def __mul__(self, other) -> "BOM":
        if not isinstance(other, int):
            return self
        return BOM(
            self.result,
            [i * other for i in self.ingredients],
            self.components,
            self.output_qty * other,
            self.formula_tree,
            self._avoid,
            self._prefer_craft,
        )

    def __lt__(self, other) -> bool:
        if self.__class__ == other.__class__:
            if self._avoid == other._avoid:
                if self.process_type == other.process_type:
                    if self.max_rarity == other.max_rarity:
                        return self.total < other.total
                    elif self.max_rarity < other.max_rarity:
                        return True
                    return False
                elif self.process_type == nms.FormulaType.CRAFT:
                    return self._prefer_craft
                return not self._prefer_craft
            elif self._avoid:
                return False
            return True
        raise NotImplementedError()

    def __getitem__(self, item_id: str) -> int:
        if not item_id in self.components:
            return 0
        for ing in self.ingredients:
            if ing.name == item_id:
                return ing.qty
        return 0

    @property
    def name(self) -> str:
        return self.result.id

    @property
    def process_type(self) -> nms.FormulaType:
        return self.formula_tree.formula.type

    @classmethod
    async def make_bom(
        cls,
        wiki: nms.Wiki,
        result: nms.Item,
        formula: nms.Formula,
        global_boms: Dict[str, Any],
        avoid: Set[str],
        prefer_craft: bool,
    ) -> "BOM":
        ingredient_boms = [
            global_boms[i.name] for i in formula.ingredients if i.name in global_boms
        ]
        if ingredient_boms:
            return cls.combine_boms(
                result, formula, ingredient_boms, global_boms, avoid, prefer_craft
            )
        sources = await wiki.get_items(formula.source_ids())
        components = {i.id: i for i in sources}
        avoid = components.keys() & avoid and True or False
        return cls(
            result,
            formula.ingredients,
            components,
            formula.result.qty,
            _FormulaNode(formula),
            avoid,
            prefer_craft,
        )

    @classmethod
    def combine_boms(
        cls,
        result: nms.Item,
        formula: nms.Formula,
        boms: List["BOM"],
        global_boms: Dict[str, Any],
        avoid: Set[str],
        prefer_craft: bool,
    ) -> "BOM":
        def _select_bom(name: str, local_boms: Dict[str, BOM]) -> BOM:
            local_bom = None
            global_bom = None
            if name in local_boms:
                local_bom = local_boms[name]
            if name in global_boms:
                global_bom = global_boms[name]
            if local_bom is not None and global_bom is not None:
                if local_bom < global_bom:
                    return local_bom
                return global_bom
            if local_bom is not None:
                return local_bom
            return global_bom

        # Sort boms per component
        bom_per_component: Dict[str, List[BOM]] = dict()
        for bom in boms:
            if bom.name not in bom_per_component:
                bom_per_component[bom.name] = list()
            bom_per_component[bom.name].append(bom)

        # Now sort them
        for name, bom in bom_per_component.items():
            bom.sort()

        # Select best bom
        best_boms = {name: bom[0] for name, bom in bom_per_component.items() if bom}

        # Calculate coefficients ouf output
        new_output = formula.result.qty
        output_lcm = new_output
        for ing in formula.ingredients:
            bom = _select_bom(ing.name, best_boms)
            if not bom:
                continue
            if ing.name not in best_boms:
                best_boms[ing.name] = bom
            ing_lcm = lcm(ing.qty, bom.output_qty)
            output_lcm = lcm(ing_lcm // ing.qty, output_lcm)

        if new_output != output_lcm:
            new_output = output_lcm // new_output

        # Apply coefficient to BOMs
        k_output = new_output // formula.result.qty
        for ing in formula.ingredients:
            bom = _select_bom(ing.name, best_boms)
            if not bom:
                continue
            ing_lcm = lcm(ing.qty * k_output, bom.output_qty)
            if ing_lcm != bom.output_qty:
                best_boms[ing.name] = bom * (ing_lcm // bom.output_qty)

        # Merge boms
        new_components = {}
        for bom in best_boms.values():
            new_components = new_components | {
                k: v for k, v in bom.components.items() if k not in best_boms
            }

        new_counts = {}
        for key in new_components.keys():
            new_counts[key] = sum([b[key] for b in best_boms.values()])

        new_ingredients = [nms.Ingredient(k, v) for k, v in new_counts.items()]
        avoid = new_components.keys() & avoid and True or False
        new_bom = BOM(
            result,
            new_ingredients,
            new_components,
            new_output,
            _FormulaNode(
                formula,
                [
                    b.formula_tree
                    for b in best_boms.values()
                    if b.formula_tree.formula != formula
                ],
            ),
            avoid,
            prefer_craft,
        )
        return new_bom


class BOMCounter(nms.NodeVisitor[BOM], nms.Loggable):
    def __init__(self, boms: Dict[str, BOM]) -> None:
        super().__init__()
        self.boms = boms
        self.process_count: Dict[str, int] = {}

    async def get_adjacent(
        self, node: BOM, direction: nms.WalkDirection, distance: int
    ) -> Set[BOM]:
        return {
            self.boms[dep.formula.result.name] for dep in node.formula_tree.dependencies
        }

    async def discover_node(self, node: BOM, distance: int) -> None:
        self.process_count[node.name] = 1

    async def tree_edge(self, source: BOM, target: BOM) -> None:
        self.process_count[target.name] += 1

    async def back_edge(self, source: BOM, target: BOM) -> None:
        self.process_count[target.name] += 1

    async def fwd_or_cross_edge(self, source: BOM, target: BOM) -> None:
        self.process_count[target.name] += 1


class BOMPrinter(nms.NodeVisitor[BOM], nms.Loggable):
    def __init__(
        self,
        boms: Dict[str, BOM],
        counts: Dict[str, int],
        print_formula: Callable[[nms.Item, nms.Formula, str], None],
        get_color: Callable[[nms.Formula], Any],
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
            nms.FormulaType.REFINING: 0,
            nms.FormulaType.CRAFT: 0,
            nms.FormulaType.COOK: 0,
        }
        self._multiple = multiple

    async def get_adjacent(
        self, node: BOM, direction: nms.WalkDirection, distance: int
    ) -> Set[BOM]:
        return {
            self.boms[dep.formula.result.name] for dep in node.formula_tree.dependencies
        }

    async def finish_node(self, node: BOM, distance: int) -> None:
        formula = node.formula_tree.formula
        count = self.counts[node.name] * node.output_qty * self._multiple
        color = self.get_color(formula)
        refine_time = ""
        if formula.type == nms.FormulaType.REFINING:
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


class BOMBuilder(nms.FormulaTreePrinter):
    def __init__(
        self, wiki: nms.Wiki, avoid: Iterable[str], prefer_craft: bool
    ) -> None:
        super().__init__(wiki)
        self._bom_stack = nms.LIFO[List[BOM]]()
        self.best_boms: Dict[str, BOM] = {}
        self.avod = set(avoid)
        self.prefer_craft = prefer_craft

    def filter(self, formula: nms.Formula, result: nms.Item) -> bool:
        return result.cls != nms.Class.Resource

    async def examine_node(self, formula: nms.Formula, distance: int) -> None:
        self.log_debug(f"Examine {formula.result.name} distance {distance}")

        result = await self._wiki.get_item(formula.result.name)
        if result.cls == nms.Class.Resource:
            return
        self._bom_stack.push(list())
        await self.print_formula(result, formula, " " * distance * 3)

    async def finish_node(self, formula: nms.Formula, distance: int) -> None:
        result = await self._wiki.get_item(formula.result.name)
        if result.cls == nms.Class.Resource:
            return

        self.log_debug(
            f"Finish {formula.result.name} distance {distance} stack size {len(self._bom_stack)}"
        )

        boms = self._bom_stack.pop()
        if not boms:
            bom = await BOM.make_bom(
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
            bom = BOM.combine_boms(
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

    def print_totals(self, bom: BOM, formula: nms.Formula, distance: int) -> None:
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
        await nms.walk_graph([bom], vis)

        hlprint("=" * 80, fg=color)
        hlprint("Process", fg=(color, "bright"))
        vis = BOMPrinter(
            self.best_boms,
            vis.process_count,
            self.print_formula,
            self.get_color,
            multiple=multiple,
        )
        await nms.walk_graph([bom], vis)
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
            f"{vis.steps[nms.FormulaType.CRAFT] * multiple} taps for crafting", fg=color
        )


async def main():
    args = parse_args()
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    async with nms.Wiki() as wiki:
        item = await wiki.get_item(args.item)
        if not item:
            print(f"Item not found")
            exit(1)
        vis = BOMBuilder(wiki, avoid=args.avoid, prefer_craft=args.prefer_craft)
        await nms.walk_graph(
            item.source_formulas,
            vis,
            walk_order=nms.WalkOrder.DFS,
            log=wiki.log_debug,
        )
        await vis.print_bom(args.item, multiple=args.multiple)


if __name__ == "__main__":
    asyncio.run(main())
