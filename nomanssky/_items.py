import datetime
import sqlite3
import logging

from typing import Any, List, Set, Callable

from enum import Enum

from easysqlite import StoredField, stored_class

from ._loggable import Loggable
from ._attributes import Type, Rarity, Class
from ._infobox import Infobox
from ._formula import Formula, FormulaType
from ._utils import enum_by_name, int_digest
from ._json import JSONDecoder


@stored_class(
    table_name="items",
    id_fields=["id"],
    store_fn_name="store",
    load_fn_name="load",
    log_level=logging.DEBUG,
    verbose=True,
)
class Item(Loggable, JSONDecoder):
    id = StoredField[str](not_null=True, primary_key=True)
    name = StoredField[str](not_null=True, unique=True)
    symbol = StoredField[str]()
    utime = StoredField[datetime.datetime](not_null=True)
    cls = StoredField[Class](to_db=lambda v: v.value, from_db=Class)
    type = StoredField[Type](
        to_db=lambda v: v is not None and v.name or None,
        from_db=lambda s: enum_by_name(Type, s),
    )
    rarity = StoredField[Rarity](to_db=lambda v: v.value, from_db=Rarity)
    category = StoredField[str]()
    image = StoredField[str]()
    total_value = StoredField[float]()
    blueprint_value = StoredField[float]()

    source_formulas: List[Formula]
    formulas: List[Formula]
    repair_formula: Formula

    linked_items: Set[str]
    source_items: Set[str]

    def __init__(
        self, *, url: str, cls: Class, infobox: Infobox, formulas: List[Formula]
    ) -> None:
        super().__init__()
        self.rarity = Rarity.UNKNOWN
        self.utime = datetime.datetime.now()

        for k, v in infobox.__dict__.items():
            setattr(self, k, v)
        self.id = url.split("/")[-1]
        self.cls = cls

        self.source_formulas = []
        self.formulas = []
        self.repair_formula = None

        self.linked_items = set()
        self.source_items = set()
        self.target_items = set()

        for f in formulas:
            if f.type == FormulaType.REPAIR:
                self.repair_formula = f
            else:
                if self.cls == Class.Consumable:
                    f.type = FormulaType.COOK
                if f.result.name == self.name or f.result.name == self.id:
                    self.source_formulas.append(f)
                else:
                    self.formulas.append(f)
        self.build_linked_items()

    @property
    def has_symbol(self) -> bool:
        return hasattr(self, "symbol") and self.symbol is not None

    @property
    def symbol_or_id(self) -> str:
        if self.has_symbol:
            return self.symbol
        return self.id

    @property
    def value(self) -> float:
        if hasattr(self, "blueprint_value") and self.blueprint_value is not None:
            return self.blueprint_value
        elif hasattr(self, "total_value") and self.total_value is not None:
            return self.total_value
        return 0.0

    @property
    def name_with_symbol(self) -> str:
        if self.has_symbol:
            return f"{self.name} ({self.symbol})"
        return self.name

    @value.setter
    def value(self, value: float) -> None:
        ...

    def __str__(self) -> str:
        val = f"{self.cls.value} {{{self.id}}} {self.name}"
        if self.has_symbol:
            val = val + f" ({self.symbol})"
        return f"<{val}>"

    def __repr__(self) -> str:
        val = f"{self.cls.value} {{{self.id}}} {self.name}"
        if self.has_symbol:
            val = val + f" ({self.symbol})"
        return f"<{self.type}: {val}>"

    def __to_json__(self) -> Any:
        return {
            "id": self.id,
            "name": self.name,
            "symbol": self.symbol,
            "utime": f"{self.utime}",
            "cls": self.cls.value,
            "type": self.type and self.type.name or None,
            "rarity": self.rarity and self.rarity.value or None,
            "category": self.category,
            "image": self.image,
            "value": self.value,
            "source_formulas": self.source_formulas,
            "formulas": self.formulas,
        }

    @classmethod
    def __from_json__(cls, o: "Item", data: Any) -> "Item":
        for k in ["id", "name", "symbol", "category", "image", "value"]:
            setattr(o, k, data[k])
        o.utime = datetime.datetime.fromisoformat(data["utime"])
        o.cls = Class(data["cls"])
        o.type = enum_by_name(Type, data["type"])
        o.rarity = Rarity(data["rarity"])
        o.source_formulas = [Formula.from_json(d) for d in data["source_formulas"]]
        if "formulas" in data:
            o.formulas = [Formula.from_json(d) for d in data["formulas"]]

        return o

    def digest(self) -> int:
        return int_digest(self)

    def on_store(self, conn: sqlite3.Connection) -> None:
        self.log_debug(f"Store item {self.name} dependent stuff")
        links = [
            ItemFormulaLink(self.id, f.digest(), ItemFormulaType.TARGET)
            for f in self.source_formulas
        ] + [
            ItemFormulaLink(self.id, f.digest(), ItemFormulaType.SOURCE)
            for f in self.formulas
        ]
        for l in links:
            l.store(conn)
        for f in self.source_formulas + self.formulas:
            f.store(conn)
        # TODO Store maintenance formula

    def on_load(
        self,
        conn: sqlite3.Connection,
        load_fn: Callable[[Any, Any], List[Any]],
        *args,
    ) -> None:
        if load_fn:
            links: List[ItemFormulaLink] = ItemFormulaLink.load(conn, item_id=self.id)
            self.source_formulas = []
            self.formulas = []
            self.repair_formula = None
            for l in links:
                formulas: List[Formula] = load_fn(Formula, id=l.formula_id)
                for f in formulas:
                    if l.direction == ItemFormulaType.TARGET:
                        self.source_formulas.append(f)
                    else:
                        self.formulas.append(f)
            # TODO Load maintenance formula
            self.repair_formula = None
            self.build_linked_items()
        else:
            self.log_warning(
                f"Load function not supplied to load {self.name} dependencies"
            )

    def build_linked_items(self) -> None:
        self.linked_items = set(
            [
                i.name
                for f in self.source_formulas + self.formulas + [self.repair_formula]
                if f is not None
                for i in f.ingredients + [f.result]
                if i is not None and i.name != self.id
            ]
        )
        self.source_items = set(
            [
                i.name
                for f in self.source_formulas
                for i in f.ingredients
                if i is not None and i.name != self.id
            ]
        )
        self.target_items = self.linked_items - self.source_items


class ItemFormulaType(Enum):
    SOURCE = "src"
    TARGET = "tgt"


@stored_class(
    table_name="item_formulas",
    id_fields=["item_id", "formula_id"],
    store_fn_name="store",
    load_fn_name="load",
    log_level=logging.DEBUG,
    verbose=True,
)
class ItemFormulaLink:
    item_id = StoredField[str](primary_key=True)
    formula_id = StoredField[int](primary_key=True)
    direction = StoredField[ItemFormulaType]()

    def __init__(
        self, item_id: str, formula_id: int, direction: ItemFormulaType
    ) -> None:
        self.item_id = item_id
        self.formula_id = formula_id
        self.direction = direction

    def __repr__(self) -> str:
        return f"<link: {self.item_id} {self.formula_id} {self.direction.value}>"
