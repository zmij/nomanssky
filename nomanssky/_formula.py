import asyncio
import json
import logging

import math
from enum import Enum, IntEnum, auto
from typing import Awaitable, Callable, Iterable, Iterator, List, Set, Any, Tuple
from datetime import timedelta

from easysqlite import StoredField, stored_class

from ._attributes import Class
from ._loggable import Loggable
from ._json import JSONDecoder, JSONEncoder
from ._utils import int_digest
from ._formats import (
    format_spec_tokeniser,
    format_expression_parser,
    TokeniserState,
    ExpressionToken,
    format_attrib_action,
    format_list_attrib_action,
    format_literal_action,
)


class CompareResult(IntEnum):
    Less = -1
    Equal = 0
    More = 1

    def __invert__(self) -> "CompareResult":
        if self == CompareResult.Less:
            return CompareResult.More
        elif self == CompareResult.More:
            return CompareResult.Less
        return self


class Ingredient(JSONDecoder):
    name: str
    qty: int

    def __init__(self, name: str, qty: int) -> None:
        self.name = name
        self.qty = qty

    def __str__(self) -> str:
        return self.__format__("%n x%q")
        # return f"{self.name} x{self.qty}"

    def __repr__(self) -> str:
        return f"{self.name} x{self.qty}"

    def __format__(self, __format_spec: str) -> str:
        """
        Format specs:

        %nn ingredient name lowercase
        %NN ingredient name uppercase
        %q ingredient qty
        Default format = '%n x%q'
        """
        if not __format_spec:
            __format_spec = "%n x%q"
        ret = ""
        for action in _ingredient_format_parser(__format_spec):
            ret += action(self)
        return ret

    def digest(self) -> int:
        return int_digest(self)

    def __to_json__(self) -> Any:
        return [self.name, self.qty]

    def __mul__(self, rhs) -> "Ingredient":
        if not isinstance(rhs, int):
            return self
        return Ingredient(self.name, self.qty * rhs)

    def __lt__(self, rhs: "Ingredient") -> bool:
        if rhs is None:
            return False
        if not isinstance(rhs, Ingredient):
            raise NotImplementedError(
                f"Comparison between {self.__class__.__name__} and {rhs.__class__.__name__} is not implemented"
            )
        if self.name < rhs.name:
            return True
        if self.name > rhs.name:
            return False
        # Equal names
        return self.qty < rhs.qty

    @classmethod
    def __from_json__(cls, o: "Ingredient", data: Tuple[str, int]) -> "Ingredient":
        o.name = data[0]
        o.qty = data[1]
        return o


class IngredientListCompare(IntEnum):
    LongerLess = 0
    LongerMore = 1


class IngredientList(Loggable):
    def __init__(self, *items: Iterable[Ingredient]) -> None:
        self._by_id = dict[str, Ingredient]()
        self._sorted: list[Ingredient] = None
        for i in items:
            self[i.name] = i * 1

    def __repr__(self) -> str:
        return str(self.items)

    def __to_json__(self) -> Any:
        return self.items

    def __iter__(self) -> Iterator[Ingredient]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self._by_id)

    def __getitem__(self, key: str | int | Ingredient) -> Ingredient:
        if isinstance(key, int):
            return self.items[key]
        if isinstance(key, Ingredient):
            if key.name in self._by_id:
                return self._by_id[key.name]
        elif key in self._by_id:
            return self._by_id[key]
        raise KeyError(f"No ingredient {key}")

    def __setitem__(self, key: str, value: Ingredient) -> None:
        self._by_id[key] = value * 1

    def __contains__(self, key: int | str | Ingredient) -> bool:
        if isinstance(key, int):
            return key < len(self)
        if isinstance(key, Ingredient):
            return key.name in self._by_id
        return key in self._by_id

    def __mul__(self, rhs: int) -> "IngredientList":
        new_ingredients = [i * rhs for i in self._by_id.values()]
        return IngredientList(*new_ingredients)

    def __add__(self, rhs: "IngredientList") -> "IngredientList":
        copy = IngredientList(*self.items)
        copy.append_list(rhs)
        return copy

    def __sub__(self, rhs: "IngredientList") -> "IngredientList":
        copy = IngredientList(*self.items)
        copy.deduct_list(rhs)
        return copy

    def __lt__(self, rhs: "IngredientList") -> bool:
        """
        The order is:
        Lexicographically compare items
        identical items -- compare quantities
        longer lists are more
        """
        return self.compare(rhs, IngredientListCompare.LongerMore) == CompareResult.Less

    def compare(
        self, rhs: "Ingredient", strategy: IngredientListCompare
    ) -> CompareResult:
        """
        Less igredients is "better"
        If common part is identical, lenght comparison is determined by strateby
        """
        min_len = min(len(self), len(rhs))
        for idx in range(0, min_len):
            lhs_item = self[idx]
            rhs_item = rhs[idx]
            if lhs_item < rhs_item:
                return CompareResult.Less
            if lhs_item > rhs_item:
                return CompareResult.More

        res = CompareResult.Equal
        if len(self) < len(rhs):
            res = CompareResult.Less
        elif len(self) > len(rhs):
            res = CompareResult.More

        if strategy == IngredientListCompare.LongerLess:
            return ~res
        return res

    def clear(self) -> None:
        self._by_id.clear()
        self._sorted = None

    def append(self, item: Ingredient) -> None:
        if item.name in self:
            self[item.name].qty += item.qty
        else:
            self[item.name] = item * 1
            self._sorted = None

    def append_list(self, items: Iterable[Ingredient]) -> None:
        for item in items:
            if item in self:
                self[item.name].qty += item.qty
            else:
                self[item.name] = item * 1
                self._sorted = None

    def deduct_list(self, items: Iterable[Ingredient]) -> None:
        for item in items:
            if item in self:
                self[item.name].qty -= item.qty

    def find_if(self, condition: Callable[[Ingredient], bool]) -> list[Ingredient]:
        return list([i for i in self.items if condition(i)])

    def remove_if(self, condition: Callable[[Ingredient], bool]) -> None:
        new_items = [i for i in self.items if not condition(i)]
        self.clear()
        self.append_list(new_items)

    async def estimate_value(
        self, get_items: Callable[[list[str]], Awaitable[Any]]
    ) -> float:
        # TODO cache maybe
        items = await get_items(self.item_ids)
        by_id = {i.id: i.value for i in items if i is not None}
        value = 0
        for ing in self:
            if ing.name in by_id:
                value += by_id[ing.name] * ing.qty
            else:
                self.log_warning(f"There is no value for {ing.name}")
        return value

    @property
    def items(self) -> list[Ingredient]:
        if self._sorted is None:
            self._sorted = sorted(self._by_id.values(), key=lambda v: v.name)
        return self._sorted

    @property
    def item_ids(self) -> list[str]:
        return [x.name for x in self.items]


class FormulaType(Enum):
    CRAFT = "{C}"
    REFINING = "{R}"
    REPAIR = "{M}"
    COOK = "{K}"

    def compare(self, other) -> int:
        if self.__class__ == other.__class__:
            items = [m for m in self.__class__.__members__.values()]
            self_idx = items.index(self)
            other_idx = items.index(other)
            if self_idx < other_idx:
                return -1
            elif self_idx > other_idx:
                return 1
            return 0
        raise NotImplementedError()

    def __lt__(self, other) -> bool:
        return self.compare(other) < 0

    def __le__(self, other) -> bool:
        return self.compare(other) <= 0

    def __gt__(self, other) -> bool:
        return self.compare(other) > 0

    def __ge__(self, other) -> bool:
        return self.compare(other) >= 0


class RefinerySize(IntEnum):
    Craft = -1
    Medium = 2
    Big = 3


@stored_class(
    table_name="formulas",
    id_fields=["id"],
    store_fn_name="store",
    load_fn_name="load",
    log_level=logging.DEBUG,
    verbose=True,
)
class Formula(Loggable, JSONDecoder):
    _LONG_FORMAT = (
        "%type %res(%n x%q) <- %ing(' + '%n x%q)%process(' ('%pname %ptime' sec/unit)')"
    )
    _SHORT_FORMAT = "%res(%n)=%type'('%ing(', '%n)')'"
    _PRODUCTION_STAGE_FORMAT = "'('%ing(', ')')' -> '('%res')'"

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

    def __init__(
        self,
        *,
        result: Ingredient = None,
        ingredients: Iterable[Ingredient] = [],
        type=FormulaType.CRAFT,
        process: str = None,
        time: float = None,
    ) -> None:
        super().__init__()
        self.result = result
        self.ingredients = IngredientList(*ingredients)
        self.type = type
        self.process = process
        self.time = time
        self._is_replentishing = None

    def __lt__(self, rhs: "Formula") -> bool:
        if self.result is not None:
            if self.result < rhs.result:
                return True
        elif rhs.result is not None:
            return False

        if self.type < rhs.type:
            return True
        elif self.type > rhs.type:
            return False

        if self.ingredients < rhs.ingredients:
            return True
        return False

    def __mul__(self, other) -> "Formula":
        if not isinstance(other, int):
            return self
        return Formula(
            result=self.result * other,
            ingredients=[x * other for x in self.ingredients],
            type=self.type,
            process=self.process,
            time=self.time and self.time * other or None,
        )

    def __add__(self, other) -> "ProductionStage":
        return ProductionStage(self, other)

    def __getitem__(self, key: str) -> Ingredient:
        """
        Get ingredient by name
        """
        for i in self.ingredients:
            if i.name == key:
                return i
        raise KeyError(f"There is no ingredient `{key!r}` in `{self!r}`")

    def __str__(self) -> str:
        return f"{{:{Formula._LONG_FORMAT}}}".format(self)

    def __repr__(self) -> str:
        formula = (
            f"{self.result.name} x{self.result.qty}={self.type.value}("
            + ", ".join([i.name for i in self.ingredients])
            + ")"
        )
        return formula

    def __format__(self, __format_spec: str) -> str:
        """
        Format specs:
        %type formula type
        %res result, defalt ingredient format specs
        %res(<ingredient format specs>)
        %ing ingredient list, default ingredient format specs, join string = " + "
        %ing('<join string>'<ingredient format specs>)
        %process - format process if not none
        args for %process: %pname and %ptime
        """
        if __format_spec == "short":
            __format_spec = Formula._SHORT_FORMAT
        elif __format_spec == "stage":
            __format_spec = Formula._PRODUCTION_STAGE_FORMAT
        if __format_spec:
            ret = ""
            # TODO Cache format results
            for action in _formula_format_parser(__format_spec):
                ret += action(self)
            return ret
        return super().__format__(__format_spec)

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
        o.ingredients = IngredientList(
            *(Ingredient.from_json(x) for x in data["ingredients"])
        )
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

    def estimate_time(
        self, max_output_batch: int, craft_time: float = 0.5
    ) -> tuple[timedelta, timedelta, int, RefinerySize]:
        """
        Estimate time required to produce result.qty of items

        max_output_batch - size of output slot in a refinery.
                           Ignored for crafted formulas, craft is serial only

        returns total time, max time per batch, number of batches, type of refinery required
        """
        if self.type == FormulaType.REPAIR:
            return timedelta(), timedelta(), 0, RefinerySize.Craft
        if self.type == FormulaType.CRAFT:
            return (
                timedelta(seconds=self.result.qty * craft_time),
                timedelta(seconds=self.result.qty * craft_time),
                1,
                RefinerySize.Craft,
            )
        exec_count = self.result.qty / max_output_batch
        batch_count = math.ceil(exec_count)
        unit_time = self.time / self.result.qty
        total_time = self.time

        max_batch_time = (
            self.result.qty > max_output_batch
            and max_output_batch * unit_time
            or self.time
        )

        return (
            timedelta(seconds=total_time),
            timedelta(seconds=max_batch_time),
            batch_count,
            self.refinery_size,
        )

    @property
    def refinery_size(self) -> RefinerySize:
        if self.type in [FormulaType.REPAIR, FormulaType.CRAFT]:
            return RefinerySize.Craft
        if len(self.ingredients) > 2:
            return RefinerySize.Big
        return RefinerySize.Medium

    @property
    def is_replentishing(self) -> bool:
        if not hasattr(self, "_is_replentishing") or self._is_replentishing is None:
            if self.result is None:
                self._is_replentishing = False
            self._is_replentishing = self.result.name in self.source_ids()
        return self._is_replentishing


# TODO Move the refinery stuff to another file
def refiner_output_batch(item_class: Class) -> int:
    # TODO game mode
    if item_class == Class.Resource:
        return 4095
    # TODO other item classes
    return 10


class RefineryJob(Loggable):
    def __init__(self, formula: Formula, time: timedelta, batch: int) -> None:
        super().__init__()
        self.formula = formula
        self.time = time
        self.batch = batch


class RefineryJobQueue(Loggable):
    def __init__(self) -> None:
        self._jobs = list[RefineryJob]()
        self._total_time = timedelta(seconds=0)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} len({self.jobs})/{self.total_time}>"

    def __len__(self) -> int:
        return len(self._jobs)

    @property
    def jobs(self) -> list[RefineryJob]:
        return self._jobs

    @property
    def total_time(self) -> timedelta:
        return self._total_time

    def add_job(self, job: RefineryJob) -> None:
        self._total_time += job.time
        self._jobs.append(job)


class RefineryPool(Loggable):
    def __init__(self, size: int = 1) -> None:
        super().__init__()
        self._pool_size = size
        self._queues = list[RefineryJobQueue]()
        self._max_time = timedelta(seconds=0)
        self._max_len = 0

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.actual_pool_size}/{self.pool_size}>"

    @property
    def unlimited(self) -> bool:
        return self._pool_size is None

    @property
    def pool_size(self) -> int:
        return self._pool_size

    @property
    def actual_pool_size(self) -> int:
        return len(self._queues)

    @property
    def max_time(self) -> timedelta:
        return self._max_time

    @property
    def max_len(self) -> int:
        return self._max_len

    def _get_next_queue(self) -> RefineryJobQueue:
        if self.unlimited:
            self._queues.append(RefineryJobQueue())
            return self._queues[-1]
        # TODO May be smarter?
        if self.actual_pool_size < self.pool_size:
            self._queues.append(RefineryJobQueue())
            return self._queues[-1]
        # Select queue with shortest time
        self._queues = sorted(self._queues, key=lambda s: s.total_time)
        return self._queues[0]

    def add_job(self, job: RefineryJob) -> None:
        queue = self._get_next_queue()
        queue.add_job(job)
        if queue.total_time > self._max_time:
            self._max_time = queue.total_time
        if len(queue) > self._max_len:
            self._max_len = len(queue)

    @classmethod
    def make_pool(
        cls, refinery_size: RefinerySize, limit: dict[RefinerySize, int]
    ) -> "RefineryPool":
        queue_limit = (
            (limit and refinery_size in limit) and limit[refinery_size] or None
        )
        return cls(queue_limit)

    @classmethod
    def make_pools(
        cls, refinery_limit: dict[RefinerySize, int]
    ) -> dict[RefinerySize, "RefineryPool"]:
        return {
            RefinerySize.Medium: cls.make_pool(RefinerySize.Medium, refinery_limit),
            RefinerySize.Big: cls.make_pool(RefinerySize.Big, refinery_limit),
            RefinerySize.Craft: cls(1),
        }


class ProductionLine(Loggable):
    """
    A set of refinery pools, for big and medium refineries,
    and a "RefineryPool" for craft
    """

    def __init__(
        self,
        refinery_limit: dict[RefinerySize, int] = {
            RefinerySize.Medium: 3,
            RefinerySize.Big: 2,
        },
    ) -> None:
        super().__init__()
        self._pools = RefineryPool.make_pools(refinery_limit)

    @property
    def max_time(self):
        by_time = sorted(self._pools.values(), key=lambda s: s.max_time, reverse=True)
        return by_time[0].max_time

    @property
    def big(self) -> RefineryPool:
        return self._pools[RefinerySize.Big]

    @property
    def medium(self) -> RefineryPool:
        return self._pools[RefinerySize.Medium]

    @property
    def craft(self) -> RefineryPool:
        return self._pools[RefinerySize.Craft]

    def __getitem__(self, key: RefinerySize) -> RefineryPool:
        return self._pools[key]


class ProductionStage(Loggable):
    def __init__(self, *formulas) -> None:
        self.results = IngredientList()
        self.ingredients = IngredientList()
        self._ingredients_by_id = dict[str, Ingredient]()

        self.formulas = formulas
        self._calc_formulas()

    def _calc_formulas(self):
        for f in self.formulas:
            self._add_result(f.result)
            self._add_ingredients(f.ingredients)

    def __repr__(self) -> str:
        formula = (
            "("
            + ", ".join([str(i) for i in self.ingredients])
            + ") -> ("
            + ", ".join([str(i) for i in self.results])
            + ")"
        )
        return formula

    def __add__(self, other) -> "ProductionStage":
        if isinstance(other, Formula):
            return ProductionStage(other, *self.formulas)
        if isinstance(other, ProductionStage):
            return ProductionStage(*self.formulas, *other.formulas)

        raise NotImplementedError(
            f"Adding {other.__class__.__name__} to {self.__class__.__name__} is not implemented"
        )

    def __mul__(self, rhs: int) -> "ProductionStage":
        return ProductionStage(*(x * rhs for x in self.formulas))

    def _add_result(self, ingredient: Ingredient) -> None:
        self.results.append(ingredient)

    def _add_ingredients(self, ingredients: Iterable[Ingredient]) -> None:
        self.ingredients.append_list(ingredients)

    def deduct_input(self, ingredients: list[Ingredient]) -> None:
        self.ingredients.deduct_list(ingredients)

    def __getitem__(self, key: str) -> Ingredient:
        return self.ingredients[key]

    def __setitem__(self, key: str, value: Ingredient) -> None:
        self.ingredients[key] = value * 1

    def __contains__(self, key: str | Ingredient) -> bool:
        return key in self.ingredients

    def multiply(self, value: int) -> bool:
        self.formulas = [f * value for f in self.formulas]
        self.results.clear()
        self.ingredients.clear()
        self._calc_formulas()

    async def estimate_time(
        self,
        get_items: Callable[[list[str]], Awaitable[Any]],
        craft_time: float = 0.5,
        # If undefined, there is no limit
        # RefinerySize.Inapplicable is ignored
        # Default value is the limit of refineries per region
        refinery_limit: dict[RefinerySize, int] = {
            RefinerySize.Medium: 3,
            RefinerySize.Big: 2,
        },
        pools: ProductionLine = None,
    ) -> timedelta:
        """
        Estimate each formula's time and try to parallelize the work in pools

        The most pessimistic estimate will be when the limit is 1 each refinery
        """
        # TODO Run all estimations in parallel
        # tasks = []
        # TODO replace with function returning batch sizes for ids
        result_items = await get_items(self.results.item_ids)
        by_id = {i.id: i for i in result_items}
        if not pools:
            pools = ProductionLine(refinery_limit)
        for f in self.formulas:
            res = by_id[f.result.name]
            batch_size = refiner_output_batch(res.cls)
            (
                total_time,
                batch_time,
                batch_count,
                refinery_size,
            ) = f.estimate_time(batch_size, craft_time=craft_time)

            if refinery_size != RefinerySize.Craft:
                pool = pools[refinery_size]
                # TODO Optimize for big batches
                for b in range(0, batch_count):
                    # TODO correct time and size for last batch
                    pool.add_job(RefineryJob(f, batch_time, batch_size))
            else:
                # Craft time
                pools[refinery_size].add_job(RefineryJob(f, total_time, f.result.qty))

        return pools.max_time


class ProductionValue:
    def __init__(self, cost: float, value: float) -> None:
        self.costs = cost
        self.value = value

    @property
    def profit(self) -> float:
        return self.value - self.costs

    def __lt__(self, rhs: "ProductionValue") -> bool:
        if rhs is None:
            return False
        if self.profit < rhs.profit:
            return True
        if self.profit > rhs.profit:
            return False
        return self.value < rhs.value


class ChainCompareType(IntEnum):
    Length = auto()
    Value = auto()
    Output = auto()
    Input = auto()
    Time = auto()


class ProductionChain(Loggable):
    def __init__(self, *stages: Iterable[ProductionStage]) -> None:
        super().__init__()
        self._stages = list[ProductionStage]()
        for stage in stages:
            self.append(stage)
        self._input = None
        self._profit = None
        self._value_estimation: ProductionValue = None
        self._time_estimation: timedelta = None
        self._production_line: ProductionLine = None

    def __str__(self) -> str:
        if self.empty:
            return "Empty production chain"
        sign = self.has_losses and "--" or "++"
        res = (
            f"{len(self)} steps ("
            + ", ".join([str(i) for i in self.input])
            + ") -> ("
            + ", ".join([str(i) for i in self.output])
            + f") {sign}["
            + ", ".join([str(i) for i in self.profit])
            + "]"
        )
        return res

    def __repr__(self) -> str:
        if self.empty:
            return f"<{self.__class__.__name__} empty"
        res = (
            f"<{self.__class__.__name__} {len(self._stages)} stages result "
            + ", ".join([str(r) for r in self.last_stage.results])
            + ">"
        )
        return res

    def __len__(self) -> int:
        return len(self._stages)

    def __getitem__(self, key: int) -> ProductionStage:
        return self._stages[key]

    def compare(
        self,
        rhs: "ProductionChain",
        compare_order: list[ChainCompareType] = [
            ChainCompareType.Length,
            ChainCompareType.Output,
            ChainCompareType.Input,
        ],
    ) -> CompareResult:
        """
        The order is:
        from most losses to biggest output

        """
        if not isinstance(rhs, ProductionChain):
            raise NotImplementedError(
                f"Comparison between {self.__class__.__name__} and {rhs.__class__.__name__} is not implemented"
            )

        def _cmp_length() -> CompareResult:
            if len(self) < len(rhs):
                return CompareResult.More
            if len(self) > len(rhs):
                return CompareResult.Less
            return CompareResult.Equal

        def _cmp_value() -> CompareResult:
            lhs_value = self._value_estimation
            rhs_value = rhs._value_estimation
            if lhs_value is not None:
                if lhs_value < rhs_value:
                    return CompareResult.Less
                if lhs_value > rhs_value:
                    return CompareResult.More
            elif rhs_value is not None:
                return CompareResult.More
            return CompareResult.Equal

        def _cmp_time() -> CompareResult:
            lhs_time = self._time_estimation
            rhs_time = rhs._time_estimation
            if lhs_time is not None and rhs_time is not None:
                if lhs_time < rhs_time:
                    return CompareResult.Less
                if lhs_time > rhs_time:
                    return CompareResult.More
            elif lhs_time is not None:
                return CompareResult.Less
            elif rhs_time is not None:
                return CompareResult.More
            return CompareResult.Equal

        def _cmp_output() -> CompareResult:
            return self.output.compare(
                rhs.output, strategy=IngredientListCompare.LongerMore
            )

        def _cmp_input() -> CompareResult:
            return self.input.compare(
                rhs.input, strategy=IngredientListCompare.LongerLess
            )

        comparisons = {
            ChainCompareType.Length: _cmp_length,
            ChainCompareType.Value: _cmp_value,
            ChainCompareType.Output: _cmp_output,
            ChainCompareType.Input: _cmp_input,
            ChainCompareType.Time: _cmp_time,
        }

        # 0. empty chains are the least
        if self.empty:
            if rhs.empty:
                # Equal
                return CompareResult.Equal
            return CompareResult.Less
        if rhs.empty:
            return CompareResult.More

        for ct in compare_order:
            cmp = comparisons[ct]()
            if cmp != CompareResult.Equal:
                return cmp
        return cmp

    @property
    def empty(self) -> bool:
        return len(self._stages) == 0

    @property
    def stages(self) -> list[ProductionStage]:
        return self._stages

    @property
    def fist_stage(self) -> ProductionStage:
        if self._stages:
            return self._stages[0]
        return None

    @property
    def last_stage(self) -> ProductionStage:
        if self._stages:
            return self._stages[-1]
        return None

    @property
    def output(self) -> IngredientList:
        last_stage = self.last_stage
        if last_stage:
            return last_stage.results
        return IngredientList()

    @property
    def input(self) -> IngredientList:
        if self.empty:
            return IngredientList()
        if self._input is None:
            input = self.fist_stage.ingredients * 1
            for idx in range(1, len(self._stages)):
                input.append_list(self._stages[idx].ingredients)
                input.deduct_list(self._stages[idx - 1].results)
            input.remove_if(lambda i: i.qty == 0)
            self._input = input
        return self._input

    @property
    def profit(self) -> IngredientList:
        if self._profit is None:
            self._profit = self.output - self.input
        return self._profit

    @property
    def has_losses(self) -> bool:
        losses = self.profit.find_if(lambda s: s.qty < 0)
        if losses:
            return True
        return False

    @property
    def has_profit(self) -> bool:
        profit = self.profit.find_if(lambda s: s.qty > 0)
        if profit:
            return True
        return False

    def _invalidate_caches(self) -> None:
        self._input = None
        self._profit = None
        self._value_estimation = None
        self._time_estimation = None

    def append(self, stage: ProductionStage) -> None:
        """
        Append a stage to the end of chain

        Multiply this stage with LCM of last stage output
        """
        last_stage = self.last_stage
        if last_stage:
            for res in last_stage.results:
                if res in stage:
                    lcm_ = math.lcm(res.qty, stage[res].qty)
                    k_out = lcm_ // stage[res].qty
                    k_in = lcm_ // res.qty
                    self.log_debug(f"Append back K input = {k_in} K output = {k_out}")
                    if k_out != 1:
                        stage = stage * k_out
                    if k_in != 1:
                        # Multiply all down
                        for s in self._stages:
                            s.multiply(k_in)
        self._stages.append(stage)
        self._invalidate_caches()

    def append_front(self, stage: ProductionStage) -> None:
        """
        Append a stage to the front of chain

        Multiply this stage with LCM of last stage output
        """
        first_stage = self.fist_stage
        if first_stage:
            for res in stage.results:
                if res in first_stage:
                    lcm_ = math.lcm(res.qty, first_stage[res].qty)
                    k_out = lcm_ // first_stage[res].qty
                    k_in = lcm_ // res.qty
                    self.log_debug(f"Append front K input = {k_in} K output = {k_out}")
                    if k_out != 1:
                        # Multiply all down
                        for s in self._stages:
                            s.multiply(k_out)
                    if k_in != 1:
                        # Multiply all down
                        stage.multiply(k_in)
            self._stages = [stage] + self._stages
        else:
            self._stages = [stage]
        self._invalidate_caches()

    async def estimate_value(
        self, get_items: Callable[[list[str]], Awaitable[Any]]
    ) -> ProductionValue:
        if not self._value_estimation:
            costs = await self.input.estimate_value(get_items)
            value = await self.output.estimate_value(get_items)
            self._value_estimation = ProductionValue(costs, value)

        return self._value_estimation

    async def estimate_time(
        self,
        get_items: Callable[[list[str]], Awaitable[Any]],
        craft_time: float = 0.5,
        # If undefined, there is no limit
        # RefinerySize.Inapplicable is ignored
        # Default value is the limit of refineries per region
        refinery_limit: dict[RefinerySize, int] = {
            RefinerySize.Medium: 3,
            RefinerySize.Big: 2,
        },
        pools: ProductionLine = None,
        reset_estimation: bool = False,
    ) -> timedelta:
        if reset_estimation:
            self._time_estimation = None
            self._production_line = None
        if self._time_estimation:
            return self._time_estimation

        estimation = timedelta(seconds=0)
        if not pools:
            pools = ProductionLine(refinery_limit)
        for stage in self._stages:
            stage_time = await stage.estimate_time(
                get_items=get_items,
                craft_time=craft_time,
                refinery_limit=refinery_limit,
                pools=pools,
            )
            self.log_info(f"Stage {stage} estimation {stage_time}")
            estimation += stage_time

        self._time_estimation = estimation
        self._production_line = pools
        return self._time_estimation

    @property
    def estimated_values(self) -> ProductionValue:
        return self._value_estimation

    @property
    def estimated_time(self) -> timedelta:
        return self._time_estimation

    @property
    def production_line(self) -> ProductionLine:
        return self._production_line

    @classmethod
    def from_formula_chain(cls, *formulas: Iterable[Formula]) -> "ProductionChain":
        return ProductionChain(*(ProductionStage(f) for f in formulas))


def prod_chain_compare(lhs: ProductionChain, rhs: ProductionChain) -> int:
    return lhs.compare(rhs).value


def make_prod_chain_compare(compare_order: list[ChainCompareType]):
    def _cmp(lhs: ProductionChain, rhs: ProductionChain):
        return lhs.compare(rhs, compare_order)

    return _cmp


"""
Nothing special after this point
"""


def _ingredient_format_parser(__format_spec: str):
    for token, state in format_spec_tokeniser(__format_spec):
        if state == TokeniserState.PctString:
            if token == "%q":
                yield format_attrib_action(
                    "qty", lambda s: s >= 0 and str(s) or f"({s})"
                )
                continue
            elif token == "%n":
                yield format_attrib_action("name")
                continue
            elif token == "%nn":
                yield format_attrib_action("name", lambda s: s.lower())
                continue
            elif token == "%NN":
                yield format_attrib_action("name", lambda s: s.upper())
                continue
            elif token == "%Nn":
                yield format_attrib_action("name", lambda s: s.title())
                continue
        yield format_literal_action(token)


class FormulaFormatState(IntEnum):
    Literal = auto()
    ResultArgs = auto()
    IngredientsArgs = auto()
    ProcessArgs = auto()


def _formula_format_parser(__format_spec: str):
    state = FormulaFormatState.Literal
    for exp_state, token in format_expression_parser(
        __format_spec, __valid_open_brackets="("
    ):
        if state != FormulaFormatState.Literal and exp_state != ExpressionToken.PctArgs:
            yield _format_formula_attr(state)
            state = FormulaFormatState.Literal

        if exp_state == ExpressionToken.PctString:
            if token == "%res":
                state = FormulaFormatState.ResultArgs
            elif token == "%ing":
                state = FormulaFormatState.IngredientsArgs
            elif token == "%process":
                state = FormulaFormatState.ProcessArgs
            elif token == "%type":
                yield format_attrib_action("type", lambda s: s.value)
                state = FormulaFormatState.Literal
            else:
                raise ValueError(f"Invalid format specifier for Formula {token}")

        elif exp_state == ExpressionToken.PctArgs:
            yield _format_formula_attr(state, token)
            state = FormulaFormatState.Literal
        elif (
            exp_state == ExpressionToken.Literal
            or exp_state == ExpressionToken.QuotedString
        ):
            yield format_literal_action(token)
            state = FormulaFormatState.Literal
    if state != FormulaFormatState.Literal:
        yield _format_formula_attr(state)


def _format_formula_attr(
    state: FormulaFormatState, format_args: list[tuple[ExpressionToken, Any]] = None
):
    if state == FormulaFormatState.ResultArgs:
        return _format_formula_result(format_args)
    elif state == FormulaFormatState.IngredientsArgs:
        return _format_formula_ingredients(format_args)
    elif state == FormulaFormatState.ProcessArgs:
        return _format_formula_porcess(format_args)
    return format_literal_action("oops")


def _format_formula_result(
    format_args: list[tuple[ExpressionToken, Any]] = None
) -> Callable[[Formula], str]:
    if not format_args:
        return format_attrib_action("result", lambda s: str(s))
    fmt_str = "{:" + "".join([x[1] for x in format_args]) + "}"
    return format_attrib_action("result", lambda s: fmt_str.format(s))


def _format_formula_ingredients(
    format_args: list[tuple[ExpressionToken, Any]] = None
) -> Callable[[Formula], str]:
    if not format_args:
        return format_list_attrib_action("ingredients", " + ", lambda s: str(s))
    start_idx = 0
    join_string = " + "
    if format_args[0][0] == ExpressionToken.QuotedString:
        join_string = format_args[0][1]
        start_idx = 1
    fmt_str = "{}"
    if len(format_args) > start_idx:
        fmt_str = "{:" + "".join([x[1] for x in format_args[start_idx:]]) + "}"
    return format_list_attrib_action(
        "ingredients", join_string, lambda s: fmt_str.format(s)
    )


def _format_formula_porcess(
    format_args: list[tuple[ExpressionToken, Any]] = None
) -> Callable[[Formula], str]:
    if not format_args:

        def default_format(f: Formula) -> str:
            if f.process is not None:
                return f"{f.process} {f.time:.2f}"
            return ""

        return default_format

    def action(f: Formula) -> str:
        ret = ""

        if f.process is not None:
            for arg_type, arg in format_args:
                if arg_type == ExpressionToken.PctString:
                    if arg == "%pname":
                        ret += f.process
                    elif arg == "%ptime":
                        ret += f"{f.time:.2f}"
                elif arg_type in [
                    ExpressionToken.Literal,
                    ExpressionToken.QuotedString,
                ]:
                    ret += arg

        return ret

    return action
