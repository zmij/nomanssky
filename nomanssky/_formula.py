import json
import hashlib
import logging

from enum import Enum
from typing import List, Set, Any, Tuple

from ._loggable import Loggable
from ._db_helpers import StoredField, stored_class
from ._json import JSONDecoder, JSONEncoder
from ._utils import int_digest


class Ingredient(JSONDecoder):
    name: str
    qty: int

    def __init__(self, name: str, qty: int) -> None:
        self.name = name
        self.qty = qty

    def __str__(self) -> str:
        return f"{self.name} x{self.qty}"

    def __repr__(self) -> str:
        return f"{self.name} x{self.qty}"

    def digest(self) -> int:
        return int_digest(self)

    def __to_json__(self) -> Any:
        return [self.name, self.qty]

    def __mul__(self, other) -> "Ingredient":
        if not isinstance(other, int):
            return self
        return Ingredient(self.name, self.qty * other)

    @classmethod
    def __from_json__(cls, o: "Ingredient", data: Tuple[str, int]) -> "Ingredient":
        o.name = data[0]
        o.qty = data[1]
        return o


class FormulaType(Enum):
    CRAFT = "{C}"
    REFINING = "{R}"
    REPAIR = "{M}"
    COOK = "{K}"


@stored_class(
    table_name="formulas",
    id_fields=["id"],
    store_fn_name="store",
    load_fn_name="load",
    log_level=logging.DEBUG,
    verbose=True,
)
class Formula(Loggable, JSONDecoder):
    id = StoredField[int](get=lambda s: s.digest(), primary_key=True)
    type = StoredField[FormulaType]()
    result = StoredField[Ingredient](
        store_as=str,
        to_db=lambda s: json.dumps(s, cls=JSONEncoder),
        from_db=lambda s: Ingredient.loads(s),
    )
    ingredients = StoredField[List[Ingredient]](
        store_as=str,
        to_db=lambda s: json.dumps(s, cls=JSONEncoder),
        from_db=lambda s: Ingredient.load_list(s),
    )
    process = StoredField[str]()
    time = StoredField[float]()

    def __init__(self) -> None:
        super().__init__()
        self.result = None
        self.ingredients = []
        self.type = FormulaType.CRAFT
        self.process = None
        self.time = None
        self._is_replentishing = None

    def __str__(self) -> str:
        formula = (
            self.type.value
            + " "
            + str(self.result)
            + " <- "
            + " + ".join([str(i) for i in self.ingredients])
        )
        if self.time is not None:
            formula = f"{formula} ({self.process} {self.time} sec/unit)"
        return formula

    def __repr__(self) -> str:
        formula = (
            f"{self.result.name}={self.type.value}("
            + ", ".join([i.name for i in self.ingredients])
            + ")"
        )
        return formula

    def __to_json__(self) -> Any:
        data = {
            "id": hash(self),
            "type": self.type.value,
            "result": self.result,
            "ingredients": self.ingredients,
        }
        if self.time is not None:
            data["process"] = self.process
            data["time"] = self.time

        return data

    @classmethod
    def __from_json__(cls, o: "Formula", data: Any) -> "Formula":
        o.type = FormulaType(data["type"])
        o.result = Ingredient.from_json(data["result"])
        o.ingredients = [Ingredient.from_json(x) for x in data["ingredients"]]
        if "time" in data:
            o.process = data["process"]
            o.time = data["time"]
        return o

    def digest(self) -> int:
        return int_digest(self)

    def get_item_ids(self) -> List[str]:
        return [self.result.name] + [i.name for i in self.ingredients]

    def source_ids(self) -> Set[str]:
        return set([i.name for i in self.ingredients])

    def target_ids(self) -> Set[str]:
        if self.result is None:
            return {}
        return {self.result.name}

    def has_ingredient(self, item_id: str) -> bool:
        return item_id in [i.name for i in self.ingredients]

    def has_any(self, items: Set[str]) -> bool:
        ingredient_ids = set([i.name for i in self.ingredients])
        if ingredient_ids & items:
            return True
        return False

    def has_all(self, items: Set[str]) -> bool:
        ingredient_ids = set([i.name for i in self.ingredients])
        if ingredient_ids & items == items:
            return True
        return False

    @property
    def is_replentishing(self) -> bool:
        if not hasattr(self, "_is_replentishing") or self._is_replentishing is None:
            if self.result is None:
                self._is_replentishing = False
            self._is_replentishing = self.result.name in self.source_ids()
        return self._is_replentishing
