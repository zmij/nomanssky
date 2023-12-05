import hashlib

from enum import Enum
from typing import List, Generic, TypeVar, Any, Iterable
from collections import deque

_PRIME = 2_147_483_647


def enum_values(cls: type(Enum)) -> List[str]:
    return [e.value for e in cls.__members__.values()]


def enum_names(cls: type(Enum)) -> List[str]:
    return [e.name for e in cls.__members__.values()]


def enum_by_name(cls: type(Enum), name: str) -> Enum:
    for e in cls.__members__.values():
        if e.name == name:
            return e
    return None


def digest(*args) -> bytes:
    h = hashlib.sha1(usedforsecurity=False)
    for arg in args:
        h.update(repr(arg).encode("utf-8"))
    return h.digest()


def int_digest(*args) -> bytes:
    d = digest(*args)
    return int.from_bytes(d, byteorder="big") % _PRIME


T = TypeVar("T")


class _DequeWrapper(Generic[T]):
    _elements: deque[T]

    def __init__(self) -> None:
        super().__init__()
        self._elements = deque[T]()

    def __len__(self) -> int:
        return len(self._elements)

    def __iter__(self):
        while len(self._elements):
            yield self.pop()

    @property
    def empty(self) -> bool:
        return len(self._elements) == 0

    def top(self) -> T:
        e = self.pop()
        self.push(e)
        return e

    def push(self, element: T) -> None:
        self._elements.append(element)

    def add(self, items: Iterable[T]) -> None:
        for e in items:
            self.push(e)

    def pop(self) -> T:
        ...


class FIFO(_DequeWrapper[T]):
    """A FIFO adapter for container"""

    def pop(self) -> T:
        return self._elements.popleft()


class LIFO(_DequeWrapper[T]):
    """A LIFO adapter for container"""

    def pop(self) -> T:
        return self._elements.pop()


if __name__ == "__main__":
    q = FIFO()
    q.push(1)
    q.add([2, 3, 4])
    for e in q:
        print(e)
    q = LIFO()
    q.push(1)
    q.add([2, 3, 4])
    for e in q:
        print(e)
