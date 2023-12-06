from typing import Any, Iterable
from math import lcm

from ._loggable import Loggable
from ._attributes import Class
from ._formula import Ingredient, Formula, FormulaType
from ._items import Item
from ._wiki import Wiki
from ._item_graph import NodeVisitor, FormulaVisitor, walk_graph, WalkDirection
from ._utils import LIFO


class _FormulaNode:
    def __init__(self, formula: Formula, dependencies: list[Any] = []) -> None:
        self.formula = formula
        self.dependencies: list[_FormulaNode] = dependencies


class BOM:
    """
    Bill Of Materials for creating an item

    Consists of FormulaIngredient objects, can multiply by a number or sum with another BOM.
    Has a total value
    """

    ingredients: list[Ingredient]
    components: dict[str, Item]

    def __init__(
        self,
        result: Item,
        ingredients: list[Ingredient],
        components: dict[str, Item],
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
        self.process: list[tuple[Formula, int]] = []
        self.refinery_allocations: list[tuple[str, str]] = []
        self.avoided_items: set[str] = set()

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
                elif self.process_type == FormulaType.CRAFT:
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
    def process_type(self) -> FormulaType:
        return self.formula_tree.formula.type

    @classmethod
    async def make_bom(
        cls,
        wiki: Wiki,
        result: Item,
        formula: Formula,
        global_boms: dict[str, Any],
        avoid: set[str],
        prefer_craft: bool,
        db_only: bool = False,
    ) -> "BOM":
        ingredient_boms = [
            global_boms[i.name] for i in formula.ingredients if i.name in global_boms
        ]
        if ingredient_boms:
            return cls.combine_boms(
                result, formula, ingredient_boms, global_boms, avoid, prefer_craft
            )
        sources = await wiki.get_items(formula.source_ids(), db_only=db_only)
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
        result: Item,
        formula: Formula,
        boms: list["BOM"],
        global_boms: dict[str, Any],
        avoid: set[str],
        prefer_craft: bool,
    ) -> "BOM":
        def _select_bom(name: str, local_boms: dict[str, BOM]) -> BOM:
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
        bom_per_component: dict[str, list[BOM]] = dict()
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

        new_ingredients = [Ingredient(k, v) for k, v in new_counts.items()]
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


class BOMCounter(NodeVisitor[BOM], Loggable):
    def __init__(self, boms: dict[str, BOM]) -> None:
        super().__init__()
        self.boms = boms
        self.process_count: dict[str, int] = {}

    async def get_adjacent(
        self, node: BOM, direction: WalkDirection, distance: int
    ) -> set[BOM]:
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


class BOMSorter(NodeVisitor[BOM], Loggable):
    def __init__(
        self,
        boms: dict[str, BOM],
        counts: dict[str, int],
        multiple: int = 1,
    ) -> None:
        super().__init__()
        self.boms = boms
        self.counts = counts
        self.refineries = {"medium": 0, "big": 0}
        self.refine_time = 0
        self.max_refine_time = 0
        self.refinery_allocations: list[tuple[str, str]] = []
        self.steps = {
            FormulaType.REFINING: 0,
            FormulaType.CRAFT: 0,
            FormulaType.COOK: 0,
        }
        self._multiple = multiple
        self.topo_sorted = list[tuple(Formula, int)] = []

    async def get_adjacent(
        self, node: BOM, direction: WalkDirection, distance: int
    ) -> set[BOM]:
        return {
            self.boms[dep.formula.result.name] for dep in node.formula_tree.dependencies
        }

    async def finish_node(self, node: BOM, distance: int) -> None:
        formula = node.formula_tree.formula
        count = self.counts[node.name] * node.output_qty * self._multiple
        if formula.type == FormulaType.REFINING:
            ref_size = len(formula.ingredients) < 3 and "medium" or "big"
            self.refineries[ref_size] += 1
            if formula.time is not None:
                t = formula.time * count
                self.refine_time += t
                if t > self.max_refine_time:
                    self.max_refine_time = t
            self.refinery_allocations.append((str(node.formula_tree.formula), ref_size))

        self.steps[formula.type] += 1
        self.topo_sorted.append((formula, count))


class SilentBomBuilder(FormulaVisitor):
    def __init__(
        self,
        wiki: Wiki,
        avoid: Iterable[str],
        prefer_craft: bool,
        db_only: bool = False,
    ) -> None:
        super().__init__(wiki)
        self._bom_stack = LIFO[list[BOM]]()
        self.best_boms: dict[str, BOM] = {}
        self.avoid = set(avoid)
        self.prefer_craft = prefer_craft
        self._db_only = db_only

    def filter(self, formula: Formula, result: Item) -> bool:
        return result.cls != Class.Resource

    async def examine_node(self, formula: Formula, distance: int) -> None:
        self.log_debug(f"Examine {formula.result.name} distance {distance}")

        result = await self._wiki.get_item(formula.result.name, db_only=self._db_only)
        if result.cls == Class.Resource:
            return
        self._bom_stack.push(list())

    async def finish_node(self, formula: Formula, distance: int) -> None:
        result = await self._wiki.get_item(formula.result.name, db_only=self._db_only)
        if result.cls == Class.Resource:
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
                self.avoid,
                self.prefer_craft,
                self._db_only,
            )
            boms = [bom]
        else:
            # Sum boms by component
            bom = BOM.combine_boms(
                result, formula, boms, self.best_boms, self.avoid, self.prefer_craft
            )

        if not self._bom_stack.empty:
            self._bom_stack.top().append(bom)

        if result.id in self.best_boms:
            if bom < self.best_boms[result.id]:
                self.best_boms[result.id] = bom
        else:
            self.best_boms[result.id] = bom

    async def sort_and_count(self, name: str, multiple: int = 1) -> BOM:
        if name not in self.best_boms:
            self.log_warning(f"No bom for {name} found")
            return None
        bom = self.best_boms[name]

        vis = BOMCounter(self.best_boms)
        await walk_graph([bom], vis)

        vis = BOMSorter(
            self.best_boms,
            vis.process_count,
            multiple=multiple,
        )
        await walk_graph([bom], vis)
        bom.process = vis.topo_sorted
        bom.refinery_allocations = vis.refinery_allocations
        bom.avoided_items = self.avoid
        return bom


async def build_bom(
    wiki: Wiki,
    item: Item,
    avoid: Iterable[str],
    prefer_craft: bool = False,
    db_only: bool = False,
) -> BOM:
    vis = SilentBomBuilder(wiki, avoid, prefer_craft, db_only)
    await walk_graph(item.source_formulas, vis, log=wiki.log_debug)
    return await vis.sort_and_count(item.id)
