import aiohttp
import bs4
import re

from enum import Enum
from typing import Any, Dict, List, Tuple

from ._loggable import Loggable
from ._attributes import Class, get_class
from ._items import Item
from ._formula import Ingredient, Formula, FormulaType
from ._infobox import Infobox

__all__ = ["PageParser"]


def class_name_filter(cls: str):
    def filter(tag: bs4.Tag):
        return tag.has_attr("class") and cls in tag.get("class")

    return filter


def wiki_links(tag: bs4.Tag):
    return (
        tag.name == "a"
        and tag.has_attr("href")
        and tag.get("href").startswith("/wiki/")
    )


def match_text(tag: bs4.Tag):
    return isinstance(tag, bs4.NavigableString)


CUT_ARGS_RE = re.compile("(\?.*$)?")
IS_A_RE = re.compile(".*is\s+an?\s+([^.]+)\.")
QTY_RE = re.compile("x(\d+)")
REFINE_PROCESS_RE = re.compile('"([^"]+)"\s*,\s*(\d+(?:\.\d+)?)\s+sec./unit\s+([^)]+)')


def _get_item(tag: bs4.Tag) -> str:
    return tag.get("href").replace("/wiki/", "")


class IngredientParseState(Enum):
    EXPECT_INGREDIENT = 0
    EXPECT_RESULT = 1
    EXPECT_PROCESS = 2
    DONE = 3


class PageParser(Loggable):
    session: aiohttp.ClientSession
    url: str
    doc: bs4.BeautifulSoup

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
    ) -> None:
        super().__init__()
        self.session = session
        self.url = url
        self._real_url = None
        self.doc = None

    async def ensure_download(self) -> bs4.BeautifulSoup:
        if self.doc is None:
            async with self.session.get(self.url) as resp:
                html = await resp.text()
                self._real_url = resp.real_url
                self.doc = bs4.BeautifulSoup(html)
        return self.doc

    async def content(self) -> bs4.Tag:
        doc = await self.ensure_download()
        return doc.find(id="content")

    async def parse(self, data: bs4.Tag = None) -> Tuple[Item, List[str]]:
        content = data or await self.content()
        if content is None:
            self.log_error(f"{self.url} page doesn't contain a `content` element")
            return None

        item = self.extract_item_info(content)
        links = PageParser.extract_links(content, wiki_links)

        return item, links

    def extract_item_info(self, tag: bs4.Tag) -> Any:
        itags = tag.find_all(class_name_filter("infoboxtable"))

        if not itags:
            return None

        ibox = Infobox(itags[0])
        self.log_debug(f"Found {ibox}")

        # Now go from the last infobox down
        t = PageParser.next_tag(itags[0], tag_name="p")
        # Expect item class here
        cls = PageParser.get_is_a(t)
        self.log_debug(f"{ibox.name} is a {cls}")
        # Now search recepies
        ul = PageParser.next_tag(t, tag_name="ul")
        formulas = []
        while ul:
            items = ul.find_all("li")
            for li in items:
                formula = self.parse_formula(li)
                if formula is None:
                    continue

                formulas.append(formula)

            ul = PageParser.next_tag(ul, tag_name="ul")
        return Item(url=str(self._real_url), cls=cls, infobox=ibox, formulas=formulas)

    def parse_formula(self, tag: bs4.Tag) -> Any:
        # Check this item is a formula
        if not tag.find(class_name_filter("selflink")):
            return None

        formula = Formula()
        tag_filter = class_name_filter("itemlink")
        a = tag.find(tag_filter)
        state = IngredientParseState.EXPECT_INGREDIENT
        while a is not None:
            a, item, next_state = self.get_ingredient(a)
            if item:
                if state == IngredientParseState.EXPECT_INGREDIENT:
                    formula.ingredients.append(item)
                elif state == IngredientParseState.EXPECT_RESULT:
                    formula.result = item
                else:
                    self.log_warning(f"Parsed ingredient {item} in state {state.name}")

            state = next_state
            if state == IngredientParseState.DONE:
                break
            if state == IngredientParseState.EXPECT_PROCESS:
                formula.type = FormulaType.REFINING
                break
            if a is not None:
                a = a.find_next(tag_filter)

        if state == IngredientParseState.DONE and formula.result is None:
            formula.type = FormulaType.REPAIR

        if a is not None:
            next = a.next_sibling
            tail = PageParser.till_end_of_node(next)
            m = REFINE_PROCESS_RE.search(tail)
            if m:
                formula.type = FormulaType.REFINING
                formula.process = m.group(1)
                formula.time = float(m.group(2))

        if (
            formula.result is not None or formula.type == FormulaType.REPAIR
        ) and formula.ingredients:
            if len(formula.ingredients) > 3:
                self.log_warning(f"{formula} has more than 3 ingredients")
            else:
                self.log_debug(f"{formula}")
            return formula
        else:
            self.log_debug(f"### faulty formula {formula}")

        return None

    def get_ingredient(
        self, tag: bs4.Tag
    ) -> Tuple[bs4.Tag, Ingredient, IngredientParseState]:
        item = " ".join([s for s in tag.stripped_strings])  # _get_item(tag)
        if tag.parent.name == "a":
            item = _get_item(tag.parent)
        else:
            item = item.replace(" ", "_")
        # Go up until in the list item
        while tag.parent is not None and tag.parent.name != "li":
            tag = tag.parent
        # Go forward until quantity found
        tag = tag.next_sibling
        while tag is not None:
            if isinstance(tag, bs4.NavigableString):
                val = str(tag).strip()
                if val.startswith("x") or val == "--":
                    break
            tag = tag.next_sibling
        if str(tag).strip() == "--":
            return tag, None, IngredientParseState.EXPECT_INGREDIENT
        str_val = str(tag).strip()
        qty = 1
        m = QTY_RE.search(str_val)
        if m:
            qty = int(m.group(1))
        state = IngredientParseState.DONE
        if str_val.endswith("+"):
            state = IngredientParseState.EXPECT_INGREDIENT
        elif str_val.endswith("→"):
            state = IngredientParseState.EXPECT_RESULT
        elif str_val.endswith("("):
            state = IngredientParseState.EXPECT_PROCESS
        self.log_debug(f"{item} X{qty} `{tag}` {state.name}")
        return tag, Ingredient(item, qty), state

    @staticmethod
    def till_end_of_node(tag: bs4.Tag) -> str:
        strings = []
        while tag is not None:
            strings = strings + [s for s in tag.stripped_strings]
            tag = tag.next_sibling
        return " ".join(strings)

    @staticmethod
    def get_is_a(tag: bs4.Tag) -> Class:
        m = IS_A_RE.match(str(tag.contents[-1]))
        if m:
            return get_class(m.group(1))
        return Class.UNKNOWN

    @staticmethod
    def next_tag(tag: bs4.Tag, *, tag_name: str = None) -> bs4.Tag:
        t = tag.next_sibling
        while t is not None and (
            not isinstance(t, bs4.Tag)
            or (tag_name is None)
            or (tag_name is not None and t.name != tag_name)
        ):
            t = t.next_sibling
        return t

    @staticmethod
    def extract_links(tag: bs4.Tag, filter: Any = "a") -> List[str]:
        links = set([CUT_ARGS_RE.sub("", e.get("href")) for e in tag.find_all(filter)])
        links = list(links)
        links.sort()
        return links
