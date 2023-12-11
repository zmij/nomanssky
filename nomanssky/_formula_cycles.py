from typing import Callable, Any, Iterable

from ._item_graph import FormulaVisitor, WalkOrder, walk_graph
from ._wiki import Wiki
from ._utils import LIFO
from ._formula import Formula, ProductionChain


class CycleDetector(FormulaVisitor):
    def __init__(self, wiki: Wiki, db_only: bool = False) -> None:
        super().__init__(wiki, db_only=db_only)
        self._current_stack = LIFO()
        self.detected_cycles = dict[str, list[ProductionChain]]()
        self.inspected_nodes = 0
        self.cycle_count = 0

    async def examine_node(self, node: Formula, distance: int) -> None:
        await super().examine_node(node, distance)
        self._current_stack.push(node)

    async def finish_node(self, node: Formula, distance: int) -> None:
        await super().finish_node(node, distance)
        self._current_stack.pop()
        self.inspected_nodes += 1

    async def tree_edge(self, source: Formula, target: Formula) -> None:
        await super().tree_edge(source, target)

    async def back_edge(self, source: Formula, target: Formula) -> None:
        await super().back_edge(source, target)
        trace = self.backtrack_to(target)
        if trace:
            self.cycle_count += 1
            chain = ProductionChain.from_formula_chain(*trace)

            if target.result.name not in self.detected_cycles:
                self.detected_cycles[target.result.name] = list[ProductionChain]()

            self.detected_cycles[target.result.name].append(chain)

    async def fwd_or_cross_edge(self, source: Formula, target: Formula) -> None:
        await super().fwd_or_cross_edge(source, target)

    def backtrack_to(self, node: Formula) -> None:
        condition = lambda s: s == node
        return self.backtrack(condition)

    def backtrack(self, condition: Callable[[Formula], bool]) -> list[Formula]:
        trace = list[Formula]()
        backup = LIFO()
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


async def detect_formula_cycles(
    wiki: Wiki, start_from: Iterable[Formula], db_only: bool = False
):
    vis = CycleDetector(wiki, db_only=db_only)
    await walk_graph(start_from, vis, walk_order=WalkOrder.DFS)
    return vis
