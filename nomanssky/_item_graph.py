from enum import Enum
import logging
from typing import Dict, Set, Iterable, Generic, TypeVar, Callable, Any

from ._wiki import Wiki
from ._items import Item
from ._formula import Formula
from ._utils import FIFO, LIFO
from ._loggable import Loggable


class WalkDirection(Enum):
    SOURCE = 0  # Walk to source nodes
    TARGET = 1  # Walk to target nodes


class WalkOrder(Enum):
    DFS = 0
    BFS = 1


_WALK_CONTAINERS = {WalkOrder.DFS: LIFO, WalkOrder.BFS: FIFO}


class _NodeColor(Enum):
    WHITE = None  # Not visited
    GRAY = 1  # In process
    BLACK = 2  # Done


T = TypeVar("T")
U = TypeVar("U")


class NodeVisitor(Generic[T]):
    async def get_adjacent(
        self, node: T, direction: WalkDirection, distance: int
    ) -> Set[T]:
        return {}

    @property
    def edges(self) -> bool:
        """
        Visitor returns edges together with items
        """
        return False

    async def discover_node(self, node: T, distance: int) -> None:
        ...

    async def examine_node(self, node: T, distance: int) -> None:
        ...

    async def finish_node(self, node: T, distance: int) -> None:
        ...

    async def tree_edge(self, source: T, target: T) -> None:
        ...

    async def back_edge(self, source: T, target: T) -> None:
        ...

    async def fwd_or_cross_edge(self, source: T, target: T) -> None:
        ...


class _NodeContainer(Generic[T, U]):
    class _Node(Generic[T, U]):
        def __init__(self, item: T, *, edge: U = None, distance: int) -> None:
            self.item = item
            self.distance = distance
            self.edge = edge

        def __repr__(self) -> str:
            return f"<{self.__class__.__name__}: {self.item!r}>"

    class _NodeFinish(Generic[T]):
        def __init__(self, item: T, distance: int) -> None:
            self.item = item
            self.distance = distance

        def __repr__(self) -> str:
            return f"<{self.__class__.__name__}: {self.item!r}>"

    def __init__(self, walk_order: WalkOrder, log: Callable[[str], None]) -> None:
        super().__init__()
        self._order = walk_order
        self._queue = _WALK_CONTAINERS[walk_order][_NodeContainer._Node[T, U]]()
        self._colors: Dict[T, _NodeColor] = {}
        self.log = log

    def __iter__(self) -> T:
        for e in self._queue:
            if isinstance(e, _NodeContainer._NodeFinish):
                yield e, e.distance
            else:
                yield e.item, e.distance

    def __len__(self):
        return len(self._queue)

    def __contains__(self, key: T) -> bool:
        return key in self._colors

    def __getitem__(self, key: T) -> _NodeColor:
        if key in self._colors:
            return self._colors[key]
        return _NodeColor.WHITE

    def __setitem__(self, key: T, value: _NodeColor) -> None:
        self._colors[key] = value

    async def add(
        self,
        items: Iterable[T],
        visitor: NodeVisitor[T],
        distance: int = 0,
        source: T = None,
    ) -> None:
        if source is not None and self._order == WalkOrder.DFS:
            self._queue.push(_NodeContainer._NodeFinish(source, distance - 1))
        for item in items:
            if not item in self:
                await visitor.discover_node(item, distance=distance)
                self._queue.push(_NodeContainer._Node(item, distance=distance))
                self._colors[item] = _NodeColor.WHITE
            elif self[item] == _NodeColor.WHITE:
                # Tree edge
                self.log(f"Tree edge {item}")
                await visitor.tree_edge(source, item)
            elif self[item] == _NodeColor.GRAY:
                # Back edge
                self.log(f"Back edge {item}")
                await visitor.back_edge(source, item)
            elif self[item] == _NodeColor.BLACK:
                # Forward or cross edge
                self.log(f"Forward or cross edge {item}")
                await visitor.fwd_or_cross_edge(source, item)
        if source is not None and self._order == WalkOrder.BFS:
            self._queue.push(_NodeContainer._NodeFinish(source, distance - 1))

    async def add_edges(
        self,
        items: Iterable[T],
        visitor: NodeVisitor[T],
        distance: int = 0,
        source: T = None,
    ) -> None:
        if source is not None and self._order == WalkOrder.DFS:
            self._queue.push(_NodeContainer._NodeFinish(source, distance - 1))
        for item, edge in items:
            if not item in self:
                await visitor.discover_node(item, edge=edge, distance=distance)
                self._queue.push(
                    _NodeContainer._Node(item, edge=edge, distance=distance)
                )
                self._colors[item] = _NodeColor.WHITE
            elif self[item] == _NodeColor.WHITE:
                # Tree edge
                self.log(f"Tree edge {item}")
                await visitor.tree_edge(source, item, edge)
            elif self[item] == _NodeColor.GRAY:
                # Back edge
                self.log(f"Back edge {item}")
                await visitor.back_edge(source, item, edge)
            elif self[item] == _NodeColor.BLACK:
                # Forward or cross edge
                self.log(f"Forward or cross edge {item}")
                await visitor.fwd_or_cross_edge(source, item, edge)
        if source is not None and self._order == WalkOrder.BFS:
            self._queue.push(_NodeContainer._NodeFinish(source, distance - 1))


async def walk_graph(
    start_from: Iterable[Any],
    visitor: NodeVisitor[Any],
    *,
    walk_order: WalkOrder = WalkOrder.DFS,
    walk_direction: WalkDirection = WalkDirection.SOURCE,
    log: Callable[[str], None] = lambda s: None,
):
    to_process = _NodeContainer[Any, Any](walk_order=walk_order, log=log)
    await to_process.add(start_from, visitor=visitor, distance=0)
    for item, distance in to_process:
        if isinstance(item, _NodeContainer[Any, Any]._NodeFinish):
            to_process[item.item] = _NodeColor.BLACK
            await visitor.finish_node(item.item, distance=distance)
            continue
        if to_process[item] != _NodeColor.WHITE:
            log(f"{item} is not white")
            continue
        to_process[item] = _NodeColor.GRAY
        await visitor.examine_node(item, distance=distance)
        adjascent = await visitor.get_adjacent(item, walk_direction, distance)
        if visitor.edges:
            await to_process.add_edges(
                adjascent, visitor, distance=distance + 1, source=item
            )
        else:
            await to_process.add(adjascent, visitor, distance=distance + 1, source=item)


class FormulaVisitor(NodeVisitor[Formula], Loggable):
    def __init__(self, wiki: Wiki, db_only: bool = False) -> None:
        super().__init__()
        self._wiki = wiki
        self._db_only = db_only
        self._walk_direction = None

    async def get_adjacent(
        self, node: Formula, direction: WalkDirection, distance: int
    ) -> Set[Formula]:
        if not self._walk_direction:
            self._walk_direction = direction
        get_formulas = None
        if direction == WalkDirection.SOURCE:
            get_formulas = lambda f: f.source_formulas
        else:
            get_formulas = lambda f: f.formulas
        adjacent_ids = (
            direction == WalkDirection.SOURCE and node.source_ids() or node.target_ids()
        )
        adjacent_items = await self._wiki.get_items(adjacent_ids, db_only=self._db_only)
        adjacent_items.sort(key=lambda s: s.id)
        return set([f for i in adjacent_items for f in get_formulas(i)])

    def _get_log_offset(self, distance) -> str:
        return "." * distance

    async def discover_node(self, node: Formula, distance: int) -> None:
        self.log_debug(
            self._get_log_offset(distance) + f"o_O {node!r} distance {distance}"
        )

    async def examine_node(self, node: Formula, distance: int) -> None:
        self.log_debug(
            self._get_log_offset(distance) + f">>> {node!r} distance {distance}"
        )

    async def finish_node(self, node: Formula, distance: int) -> None:
        self.log_debug(
            self._get_log_offset(distance) + f"<<< node {node!r} distance {distance}"
        )

    async def tree_edge(self, source: Formula, target: Formula) -> None:
        self.log_debug(f"Tree edge {source!r} {self.walk_arrow} {target!r}")

    async def back_edge(self, source: Formula, target: Formula) -> None:
        self.log_debug(f"Back edge {source!r} {self.walk_arrow} {target!r}")

    async def fwd_or_cross_edge(self, source: Formula, target: Formula) -> None:
        self.log_debug(f"Fwd or cross edge {source!r} {self.walk_arrow} {target!r}")

    @property
    def walk_arrow(self) -> str:
        if self._walk_direction == WalkDirection.SOURCE:
            return "<-"
        elif self._walk_direction == WalkDirection.TARGET:
            return "->"
        return "<->"


class ItemVisitor(NodeVisitor[Item], Loggable):
    def __init__(self, wiki: Wiki) -> None:
        super().__init__()
        self._wiki = wiki
        self._walk_direction = None

    async def get_adjacent(
        self, node: Formula, direction: WalkDirection, distance: int
    ) -> Set[Formula]:
        if not self._walk_direction:
            self._walk_direction = direction
        get_formulas = None
        if direction == WalkDirection.SOURCE:
            get_formulas = lambda f: f.source_formulas
        else:
            get_formulas = lambda f: f.formulas
        adjacent_ids = (
            direction == WalkDirection.SOURCE and node.source_ids() or node.target_ids()
        )
        adjacent_items = await self._wiki.get_items(adjacent_ids)
        return set([f for i in adjacent_items for f in get_formulas(i)])


__all__ = [
    "WalkDirection",
    "WalkOrder",
    "NodeVisitor",
    "FormulaVisitor",
    "walk_graph",
]
