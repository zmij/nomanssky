import aiohttp
import asyncio
import sqlite3
import datetime

from typing import Optional, Type, Dict, Tuple, List, Set, Any, Iterable
from types import TracebackType

from easysqlite import Database, Field as DBField

from ._loggable import Loggable
from ._page_parser import PageParser
from ._items import Item, ItemFormulaLink
from ._formula import Formula


class Wiki(Loggable):
    WIKI_BASE = "https://nomanssky.fandom.com/wiki/"

    DB_CLASSES = [Item, ItemFormulaLink, Formula]

    _session: aiohttp.ClientSession
    _items: Dict[str, Item]
    _db: Database

    def __init__(self, db_name: str = "data/nms.sqlite") -> None:
        super().__init__()
        self._session = None
        self._items = {}
        self._db = Database(db_name, self.setup_db)
        self._req_made = 0

    def setup_db(self, conn: sqlite3.Connection) -> None:
        self.log_debug("Setup database")
        for cls in Wiki.DB_CLASSES:
            conn.execute(cls._create_ddl())

    def drop_tables(self) -> None:
        self.log_warning(f"Dropping tables in {self._db.dbname_}")
        conn = self._db.connection()
        for cls in Wiki.DB_CLASSES:
            conn.execute(cls._drop_ddl())
        conn.commit()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def parse_page(self, page: str) -> Tuple[Item, List[str]]:
        url = f"{Wiki.WIKI_BASE}{page}"
        self.log_debug(f"Get wiki item {page} ({url})")
        parser = PageParser(self.session, f"{url}")
        self._req_made += 1
        return await parser.parse()

    async def get_item(self, item_id: str, return_in_db: bool = False) -> Item:
        in_db = False
        if item_id not in self._items:
            # First try the database
            items = self.load_entities(Item, id=item_id)
            if items:
                self.log_none(f"Item {item_id} found in database")
                item = items[0]
                in_db = True
                # TODO check item is stale
            else:
                self.log_info(f"Item {item_id} not found in database")
                item, _ = await self.parse_page(item_id)
                if item is None:
                    self.log_warning(f"Item {item_id} not found")
                else:
                    self.store_to_db(item)
            self._items[item_id] = item
        else:
            self.log_none(f"Item {item_id} found in cache")
        if return_in_db:
            return self._items[item_id], in_db
        return self._items[item_id]

    async def search_item(self, search_string: str) -> List[Item]:
        search_expr = f"%{search_string}%"
        expr = (
            DBField("lower(id)").like(search_expr)
            | DBField("lower(name)").like(search_expr)
            | ((DBField("symbol") != None) & DBField("lower(symbol)").like(search_expr))
        )
        return self.load_entities(Item, expr)

    async def get_items(self, items_ids: Iterable[str]) -> List[Item]:
        tasks = [asyncio.create_task(self.get_item(id)) for id in items_ids]
        items = await asyncio.gather(*tasks)
        return [x for x in items if x is not None]

    async def evaluate_formula(self, formula: Formula) -> Tuple[Formula, float, float]:
        ingredients = await self.get_items([i.name for i in formula.ingredients])
        ingredient_map = {i.id: i for i in ingredients}
        total = sum([i.qty * ingredient_map[i.name].value for i in formula.ingredients])
        per_item = total / formula.result.qty
        return formula, total, per_item

    async def find_cheapest_formula(self, item: Item) -> Tuple[Formula, float]:
        if not item.source_formulas:
            return None, None, None
        tasks = [
            asyncio.create_task(self.evaluate_formula(f)) for f in item.source_formulas
        ]
        evaluations = await asyncio.gather(*tasks)
        evaluations.sort(key=lambda t: t[2])
        return evaluations[0]

    async def check_can_be_made_of(self, tgt: Item, src: Item) -> bool:
        ...

    async def check_formula_contains(
        self, formula: Formula, item: Item, seen: Set[Formula] = set()
    ) -> bool:
        if formula.has_ingredient(item.id):
            return True
        return False

    def store_to_db(self, entity: Any, commit: bool = True) -> None:
        conn = self._db.connection()
        entity.store(conn)
        if commit:
            conn.commit()

    def load_entities(self, cls: type, *args, **kwargs) -> List[Any]:
        conn = self._db.connection()
        return cls.load(conn, self.load_entities, *args, **kwargs)

    async def __aenter__(self) -> "Wiki":
        self._session_start = datetime.datetime.now()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        elapsed = datetime.datetime.now() - self._session_start
        self.log_info(
            f"Session took {elapsed}. Made {self._req_made} requests to Wiki."
        )
        if self._session is not None:
            await self._session.close()
