import ui
import asyncio
from datetime import timedelta

from .._wiki import Wiki
from .._formula import Formula, FormulaType, Ingredient
from .._items import Item
from ..symbols import Symbols
from ._base_datasource import BaseDataSource
from ._constants import FANCY_FONT, COLOUR_OK


class FormulaDataSource(BaseDataSource[Formula, Item]):
    def __init__(self, wiki: Wiki) -> None:
        super().__init__()
        self._wiki = wiki
        self._by_id = {}

    def sort_items(self, items: list[Formula]) -> list[Formula]:
        return sorted(items, key=lambda s: s.__repr__())

    def after_set_items(self) -> None:
        item_ids = [x for formula in self._items for x in formula.get_item_ids()]
        items = asyncio.run(self._wiki.get_items(item_ids, db_only=True))
        self._by_id = {i.id: i for i in items}

    def tableview_cell_for_row(self, tableview: ui.TableView, section: int, row: int):
        formula = self[section]
        ingredient = None
        if row == 0:
            ingredient = formula.result
        else:
            ingredient = formula.ingredients[row - 1]

        item = None
        if ingredient.name in self._by_id:
            item = self._by_id[ingredient.name]

        colour = row == 0 and COLOUR_OK or "black"

        cell = self.make_cell(
            item and item.name_with_symbol or ingredient.name,
            style="subtitle",
            text_colour=colour,
        )

        if item and item.image:
            cell.image_view.load_from_url(item.image)
        cell.detail_text_label.font = (FANCY_FONT, 16)
        if row == 0:
            cell.detail_text_label.text = (
                f"Result = x{ingredient.qty} " + self.format_process(formula)
            )
        else:
            cell.detail_text_label.text = f"x{ingredient.qty}"
        return cell

    def tableview_number_of_rows(self, tableview: ui.TableView, section: 1):
        return len(self[section].ingredients) + 1

    def tableview_number_of_sections(self, tableview: ui.TableView):
        return len(self._items)

    def tableview_title_for_header(self, tableview: ui.TableView, section: int):
        # Return a title for the given section.
        # If this is not implemented, no section headers will be shown.
        formula = self[section]
        return self.format_formula(formula)

    def tableview_did_select(self, tableview: ui.TableView, section: int, row: int):
        formula = self[section]
        ingredient = row == 0 and formula.result or formula.ingredients[row - 1]
        item = None
        if ingredient.name in self._by_id:
            item = self._by_id[ingredient.name]
        if item:
            self.log_info(f"{ingredient} selected")
            self.do_action(item)
        else:
            self.log_warning(f"{ingredient} item not found")

    def format_formula(self, formula: Formula) -> str:
        res = (
            self.format_ingredient(formula.result)
            + " = "
            + " + ".join([self.format_ingredient(i) for i in formula.ingredients])
        )

        if formula.is_replentishing:
            res += f" {Symbols.RECYCLE.value}"

        return res

    def format_process(self, formula: Formula) -> str:
        if formula.type == FormulaType.REFINING:
            time = self.format_timedelta(timedelta(seconds=formula.time))
            return f"refining '{formula.process}' takes {time}"
        elif formula.type == FormulaType.CRAFT:
            return f"craft"
        elif formula.type == FormulaType.COOK:
            time = self.format_timedelta(timedelta(seconds=formula.time))
            return f"cooking '{formula.process}' takes {time}"
        else:
            return "unexpected"

    def format_timedelta(self, time: timedelta) -> str:
        res = str(time)
        sp = res.split(".")
        if len(sp) > 1:
            sp[-1] = sp[-1].rstrip("0")
        res = ".".join(sp)
        return res

    def format_ingredient(self, item: Ingredient) -> str:
        if item.name in self._by_id:
            return self._by_id[item.name].name_with_symbol + f" x{item.qty}"
        self.log_warning(f"{item.name} not found :(")
        return item.name + f" x{item.qty}"
