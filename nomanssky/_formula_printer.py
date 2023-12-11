from typing import Callable, Set, Any, Iterable, Dict, List
from enum import Enum


from .ansicolour import highlight_8bit as hl, Colour8Bit
from ._attributes import Class
from ._items import Item
from ._formula import Formula, FormulaType
from ._loggable import Loggable
from ._wiki import Wiki
from ._item_graph import FormulaVisitor, WalkDirection

from .symbols import *

FormulaPredicate = Callable[[Formula, Item], bool]

_TREE_COLORS = ["green", "red", "blue", "yellow", "magenta", "cyan"]
_TREE_BRANCH = "├─"
_TREE_LAST_BRANCH = "└─"


def cycle_colors():
    index = 0
    while True:
        yield _TREE_COLORS[index]
        index += 1
        if index == len(_TREE_COLORS):
            index = 0


def cycle_8bit_colors():
    index = 21
    while True:
        yield Colour8Bit(index)
        index += 1
        if index == 232:
            index = 20


def component_count_filter(cn: int) -> FormulaPredicate:
    if cn == 0:
        return None

    def filter(r: Item, f: Formula) -> bool:
        return len(f.ingredients) == cn

    return filter


class FormulaTypeFilter(Enum):
    ANY = "any"
    REFINE = "refine"
    CRAFT = "craft"
    COOK = "cook"


_FILTER_TO_FORMULA_TYPE = {
    FormulaTypeFilter.REFINE: FormulaType.REFINING,
    FormulaTypeFilter.CRAFT: FormulaType.CRAFT,
    FormulaTypeFilter.COOK: FormulaType.COOK,
}


def item_class_filter(c: Class) -> FormulaPredicate:
    def filter(f: Formula, r: Item) -> bool:
        return r.cls == c

    return filter


def formula_type_filter(t: FormulaTypeFilter) -> FormulaPredicate:
    if t == FormulaTypeFilter.ANY:
        return None

    to_find = _FILTER_TO_FORMULA_TYPE[t]

    def filter(f: Formula, r: Item) -> bool:
        return f.type == to_find

    return filter


def combine_predicates(*args) -> FormulaPredicate:
    not_empty = [f for f in args if f is not None]
    if not not_empty:
        return None

    def filter(f: Formula, r: Item) -> bool:
        for p in not_empty:
            if not p(f, r):
                return False
        return True

    return filter


def not_(p: FormulaPredicate) -> FormulaPredicate:
    def filter(f: Formula, r: Item) -> bool:
        return not p(f, r)


class FormulaPrinter(Loggable):
    def __init__(
        self,
        wiki: Wiki,
        *,
        find_cheapest: bool = False,
        filter: FormulaPredicate = None,
    ) -> None:
        super().__init__()
        self.wiki = wiki
        self.color_gen = cycle_8bit_colors()
        self.find_cheapest = find_cheapest
        self.filter = filter

    async def print_item_formulas(
        self,
        item: Item,
        depth: int,
        seen_formulas: Set[Formula],
        offset: str = "",
    ) -> None:
        new_formulas = seen_formulas | set(item.source_formulas)
        color = next(self.color_gen)

        cheapest_formula = None
        if self.find_cheapest:
            cheapest_formula, _, _ = await self.wiki.find_cheapest_formula(item)

        for f in item.source_formulas:
            if f in seen_formulas:
                continue
            seen_formulas.add(f)
            if self.filter is not None and not self.filter(f):
                continue
            _, formula_cost, per_item = await self.wiki.evaluate_formula(f)
            item_cost = item.value * f.result.qty
            cost_color = formula_cost < item_cost and "cyan" or "red"
            attrs = "bright"
            if cheapest_formula and cheapest_formula != f:
                attrs = None
            time = ""
            if f.time is not None:
                time = f" {f.time:.2f} sec/unit"
            signs = ""
            if await self.wiki.check_formula_contains(f, item):
                signs = " " + Symbols.RECYCLE.value
            print(
                self.format_item(
                    item,
                    f.result.qty,
                    color,
                    attrs=attrs,
                    offset=offset,
                    item_decorator=f.type.value + " ",
                )
                + " "
                + hl(
                    f"{item_cost} {formula_cost} ({item.value} {per_item:.1f} pi)",
                    fg=cost_color,
                )
                + time
                + signs
            )

            last_idx = len(f.ingredients) - 1
            for i, ing in enumerate(f.ingredients):
                child = await self.wiki.get_item(ing.name)
                last_item = i == last_idx
                tb = hl(last_item and _TREE_LAST_BRANCH or _TREE_BRANCH, fg=color)
                print(
                    f"{offset} {tb} {self.format_item(child, ing.qty, color)} {ing.qty * child.value}"
                )
                if depth > 0:
                    await self.print_item_formulas(
                        child,
                        depth - 1,
                        new_formulas,
                        offset + (last_item and "    " or hl(" │  ", fg=color)),
                    )
        seen_formulas = new_formulas

    def format_item(
        self,
        item: Item,
        qty: int,
        color: Any,
        *,
        attrs: Any = None,
        offset: str = "",
        item_decorator: str = "",
    ) -> str:
        name_fg = attrs and (color, attrs) or (color,)

        return (
            offset
            + hl(f"{item_decorator}{item.id}", fg=name_fg)
            + " "
            + hl(f"{item.cls.value} {item.rarity.value}", fg=(color, "dim"))
            + f" x{qty}"
        )


class FormulaTreePrinter(FormulaVisitor):
    _TREE_BRANCH = " ├─ "
    _TREE_LAST_BRANCH = " └─ "
    _FORMULA_TYPE_SYMBOLS = {
        FormulaType.CRAFT: Symbols.HAMMER,
        FormulaType.REFINING: Symbols.TEST_TUBE,
        FormulaType.COOK: Symbols.THERMOMETER,
        FormulaType.REPAIR: Symbols.SPANNER,
    }

    def __init__(
        self,
        wiki: Wiki,
        filter: FormulaPredicate = None,
        max_distance: int = None,
        use_type_emoji: bool = False,
    ) -> None:
        super().__init__(wiki)
        self._color_gen = cycle_8bit_colors()
        self._formula_colors: Dict[Formula, Any] = {}
        self._max_distance = max_distance
        self._filter = filter
        self._use_type_emoji = use_type_emoji

    def get_color(self, node: Formula) -> Any:
        if node not in self._formula_colors:
            self._formula_colors[node] = next(self._color_gen)
        return self._formula_colors[node]

    def filter(self, formula: Formula, result: Item) -> bool:
        if self._filter:
            return self._filter(formula, result)
        return True

    async def get_adjacent(
        self, formula: Formula, direction: WalkDirection, distance: int
    ) -> Set:
        if self._max_distance is not None and distance >= self._max_distance:
            return {}

        result = await self._wiki.get_item(formula.result.name)
        if not self.filter(formula, result):
            return {}

        return await super().get_adjacent(formula, direction, distance)

    async def examine_node(self, formula: Formula, distance: int) -> None:
        await super().examine_node(formula, distance)

        result = await self._wiki.get_item(formula.result.name)

        if not self.filter(formula, result):
            return

        await self.print_formula(result, formula, " " * distance * 3)

    async def print_formula(self, result: Item, formula: Formula, offset: str) -> None:
        color = self.get_color(formula)
        deco = ""
        if formula.is_replentishing:
            deco = f" {Symbols.RECYCLE}"
        type_sym = (
            self._use_type_emoji
            and f" {FormulaTreePrinter._FORMULA_TYPE_SYMBOLS[formula.type]}"
            or formula.type.value
        )
        print(
            offset
            + hl(f"{type_sym} ", fg=color)
            + self.format_item(result, formula.result.qty, color)
            + deco
        )
        last_idx = len(formula.ingredients) - 1
        for i, ing in enumerate(formula.ingredients):
            item = await self._wiki.get_item(ing.name)
            branch = (
                i == last_idx
                and FormulaTreePrinter._TREE_LAST_BRANCH
                or FormulaTreePrinter._TREE_BRANCH
            )
            print(
                offset + hl(branch, fg=color) + self.format_item(item, ing.qty, color)
            )

    def format_item(self, item: Item, qty: int, color: Any) -> str:
        return (
            hl(f"{item.id} ", fg=color)
            + hl(
                f"{item.value} ({item.rarity.value}) {item.cls.value}",
                fg=(color, "dim"),
            )
            + hl(f" x{qty}", fg=color)
        )
