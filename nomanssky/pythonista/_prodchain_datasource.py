import ui
import asyncio
from functools import cmp_to_key
from typing import Callable

from .._wiki import Wiki
from .._formula import (
    ProductionChain,
    ProductionStage,
    Ingredient,
    ChainCompareType,
    make_prod_chain_compare,
)
from .._items import Item
from ._base_datasource import BaseDataSource
from ._constants import COLOUR_OK, COLOUR_NOK, COLOUR_BAD

ProductionStageCallback = Callable[[ProductionChain, ProductionStage, int], None]


class ProdChainDataSource(BaseDataSource[ProductionChain, Item]):
    def __init__(self, wiki: Wiki) -> None:
        super().__init__()
        self.stage_action: ProductionStageCallback = None
        self._wiki = wiki
        self._by_id = wiki.item_cache
        self._cmp = make_prod_chain_compare(
            [ChainCompareType.Length, ChainCompareType.Input, ChainCompareType.Output]
        )

    def sort_items(self, items: list[ProductionChain]) -> list[ProductionChain]:
        return sorted(items, key=cmp_to_key(self._cmp), reverse=True)

    def after_set_items(self) -> None:
        return super().after_set_items()

    def tableview_number_of_sections(self, tableview: ui.TableView) -> int:
        return len(self._items)

    def tableview_number_of_rows(self, tableview: ui.TableView, section: int) -> int:
        chain = self[section]
        return len(chain) + len(chain.input)

    def tableview_title_for_header(self, tableview: ui.TableView, section: int) -> str:
        chain = self[section]
        return ", ".join([self.format_ingredient(i) for i in chain.profit])

    def tableview_can_delete(
        self, tableview: ui.TableView, section: int, row: int
    ) -> bool:
        chain = self[section]
        if row < len(chain.input):
            return True
        return False

    def tableview_title_for_delete_button(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        chain = self[section]
        if row < len(chain.input):
            ing = chain.input[row]
            item = None
            if ing.name in self._by_id:
                item = self._by_id[ing.name]
            return f"Avoid {item and item.name_with_symbol or ing.name}"
        return "Unexpected"

    def tableview_cell_for_row(
        self, tableview: ui.TableView, section: int, row: int
    ) -> ui.TableViewCell:
        chain = self[section]
        if chain.has_losses:
            colour = COLOUR_BAD
        elif chain.has_profit:
            colour = COLOUR_OK
        else:
            colour = COLOUR_NOK
        if row < len(chain.input):
            # Cell for input item
            ing = chain.input[row]
            item = None
            if ing.name in self._by_id:
                item = self._by_id[ing.name]
            cell = self.make_cell(
                item and item.name_with_symbol or ing.name,
                detail_text=f"x{ing.qty}",
                style="value1",
                text_colour=colour,
            )
            if item and item.image:
                cell.image_view.load_from_url(item.image)
            return cell
        else:
            # Cell for stage
            stage_no = row - len(chain.input)
            stage = chain[stage_no]
            text = f"{stage_no + 1}. " + " + ".join(
                [self.format_ingredient(i) for i in stage.ingredients]
            )
            detail_text = "Output: " + " + ".join(
                [self.format_ingredient(i) for i in stage.results]
            )
            cell = self.make_cell(
                text, detail_text=detail_text, style="subtitle", text_colour=colour
            )
            return cell

    def tableview_did_select(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        self.log_info(f"Selected secton {section} row {row}")
        chain = self[section]
        if row < len(chain.input):
            # Item action
            ing = chain.input[row]
            if ing.name in self._by_id:
                self.do_action(self._by_id[ing.name])
            else:
                self.log_warning(f"{ing.name} not found in cache")
        else:
            # Stage action
            if self.stage_action:
                stage_no = row - len(chain.input)
                self.stage_action(chain, chain[stage_no], stage_no)

    def tableview_delete(self, tableview: ui.TableView, section: int, row) -> None:
        chain = self[section]
        if row < len(chain.input):
            ing = chain.input[row]
            item = None
            if ing.name in self._by_id:
                item = self._by_id[ing.name]
            self.log_info(f"Avoid {item and item.name_with_symbol or ing.name}")
            # TODO Call action

    def format_ingredient(self, ing: Ingredient) -> str:
        if ing.name in self._by_id:
            res = self._by_id[ing.name].name_with_symbol
        else:
            res = ing.name
        res += f" x{ing.qty}"
        return res
