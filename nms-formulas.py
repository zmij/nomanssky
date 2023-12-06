import pythonista

if not pythonista.in_pythonista():
    raise Exception(f"This script is intended to be run in Pythonista application")

import ui
import asyncio
import logging
import os

from typing import Any
from enum import IntEnum

import nomanssky as nms

LOG_LEVELS = logging._nameToLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)

ITEM_CLASSES = [
    nms.Class.Resource,
    nms.Class.Tradeable,
    nms.Class.Consumable,
    nms.Class.Product,
    nms.Class.Tech,
    nms.Class.Plant,
    nms.Class.Component,
]

GLYPH_FONT = "NMS Glyphs"
FANCY_FONT = "GeosansLight-NMS"

EMPTY_IMAGE = "image_32"
BACK_ARROW = "ios7_arrow_back_24"
FORWARD_ARROW = "ios7_arrow_forward_24"

UNITS_IMAGE = "assets/currency.units.png"


class TableViewDataSource:
    def make_cell(
        self, text: str, style="default", font_size: int = 20
    ) -> ui.TableViewCell:
        cell = ui.TableViewCell(style=style)
        cell.text_label.font = (FANCY_FONT, font_size)
        if text:
            cell.text_label.text = text
        return cell

    """
    TableView DataSource
    """

    def tableview_number_of_sections(self, tableview) -> int:
        # Return the number of sections (defaults to 1)
        ...

    def tableview_number_of_rows(self, tableview, section) -> int:
        # Return the number of rows in the section
        ...

    def tableview_cell_for_row(self, tableview, section, row) -> ui.TableViewCell:
        # Create and return a cell for the given section/row
        ...

    def tableview_can_delete(self, tableview, section, row) -> bool:
        # Return True if the user should be able to delete the given row.
        return False

    def tableview_can_move(self, tableview, section, row) -> bool:
        # Return True if a reordering control should be shown for the given row (in editing mode).
        return False

    def tableview_delete(self, tableview, section, row) -> None:
        # Called when the user confirms deletion of the given row.
        ...

    def tableview_move_row(
        self, tableview, from_section, from_row, to_section, to_row
    ) -> None:
        # Called when the user moves a row with the reordering control (in editing mode).
        ...


class SegmentedDataSource(TableViewDataSource):
    def tableview_title_for_header(self, tableview, section) -> str:
        # Return a title for the given section.
        # If this is not implemented, no section headers will be shown.
        ...


class TableViewDelegate:
    def tableview_did_select(self, tableview, section, row) -> None:
        # Called when a row was selected.
        ...

    def tableview_did_deselect(self, tableview, section, row) -> None:
        # Called when a row was de-selected (in multiple selection mode).
        ...

    def tableview_title_for_delete_button(self, tableview, section, row) -> None:
        # Return the title for the 'swipe-to-***' button.
        ...


class BaseDataSource(nms.Loggable, TableViewDataSource, TableViewDelegate):
    def __init__(self) -> None:
        super().__init__()
        self._items = []
        self.action = None

    def __getitem__(self, key: int) -> nms.Item:
        return self._items[key]

    def sort_items(self, items: list[Any]) -> list[Any]:
        """
        For overloading
        """
        return items

    def after_set_items(self) -> None:
        """
        For overloading
        """
        ...

    @property
    def items(self) -> list[Any]:
        return self._items

    @items.setter
    def items(self, items: list[Any]) -> None:
        self._items = self.sort_items(items)
        self.after_set_items()

    @property
    def empty(self) -> bool:
        return not self._items

    """
    TableView DataSource
    """

    def tableview_number_of_sections(self, tableview):
        return 1

    def tableview_number_of_rows(self, tableview, section):
        return len(self._items)

    def tableview_cell_for_row(self, tableview, section, row):
        cell = self.make_cell(str(self[row]))
        return cell

    def tableview_can_delete(self, tableview, section, row):
        return False

    def tableview_can_move(self, tableview, section, row):
        return False

    """
    TableView delegate
    """

    def tableview_did_select(self, tableview, section, row):
        # Called when a row was selected.
        self.log_info(f"{self[row]} selected")
        if self.action:
            self.action(self[row])


class ItemDataSource(BaseDataSource):
    def __init__(self) -> None:
        super().__init__()

    def sort_items(self, items: list[Any]) -> list[Any]:
        return sorted(items, key=lambda s: s.name)

    def tableview_cell_for_row(self, tableview, section, row):
        item = self._items[row]
        cell = self.make_cell(item.name_with_symbol)
        if item.image:
            cell.image_view.load_from_url(item.image)
        return cell


class FormulaDataSource(BaseDataSource):
    def __init__(self, wiki: nms.Wiki) -> None:
        super().__init__()
        self._wiki = wiki
        self._by_id = {}

    def sort_items(self, items: list[Any]) -> list[Any]:
        return sorted(items, key=lambda s: s.__repr__())

    def after_set_items(self) -> None:
        item_ids = [x for formula in self._items for x in formula.get_item_ids()]
        items = asyncio.run(self._wiki.get_items(item_ids, db_only=True))
        self._by_id = {i.id: i for i in items}

    def tableview_cell_for_row(self, tableview, section, row):
        formula = self[section]
        ingredient = None
        if row == 0:
            ingredient = formula.result
        else:
            ingredient = formula.ingredients[row - 1]

        item = None
        if ingredient.name in self._by_id:
            item = self._by_id[ingredient.name]

        cell = self.make_cell(
            item and item.name_with_symbol or ingredient.name, style="subtitle"
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

    def tableview_number_of_rows(self, tableview, section):
        return len(self[section].ingredients) + 1

    def tableview_number_of_sections(self, tableview):
        return len(self._items)

    def tableview_title_for_header(self, tableview, section):
        # Return a title for the given section.
        # If this is not implemented, no section headers will be shown.
        formula = self[section]
        return self.format_formula(formula)

    def tableview_did_select(self, tableview, section, row):
        formula = self[section]
        ingredient = row == 0 and formula.result or formula.ingredients[row - 1]
        item = None
        if ingredient.name in self._by_id:
            item = self._by_id[ingredient.name]
        if item:
            self.log_info(f"{ingredient} selected")
            if self.action:
                self.action(item)
        else:
            self.log_warning(f"{ingredient} item not found")

    def format_formula(self, formula: nms.Formula) -> str:
        res = (
            self.format_ingredient(formula.result)
            + " = "
            + " + ".join([self.format_ingredient(i) for i in formula.ingredients])
        )

        if formula.is_replentishing:
            res += f" {nms.symbols.Symbols.RECYCLE.value}"

        return res

    def format_process(self, formula: nms.Formula) -> str:
        if formula.type == nms.FormulaType.REFINING:
            return f"refining '{formula.process}' {formula.time} secs"
        elif formula.type == nms.FormulaType.CRAFT:
            return f"craft"
        elif formula.type == nms.FormulaType.COOK:
            return f"cooking '{formula.process}' {formula.time} secs"
        else:
            return "unexpected"

    def format_ingredient(self, item: nms.Ingredient) -> str:
        if item.name in self._by_id:
            return self._by_id[item.name].name_with_symbol + f" x{item.qty}"
        self.log_warning(f"{item.name} not found :(")
        return item.name + f" x{item.qty}"


class BomDataSource(SegmentedDataSource, TableViewDelegate):
    def __init__(self) -> None:
        super().__init__()
        self._bom: nms.BOM = None
        self._avoided = []
        self._multiple = 1

    @property
    def bom(self) -> nms.BOM:
        return self._bom

    @bom.setter
    def bom(self, value: nms.BOM):
        self._bom = value

    def tableview_number_of_sections(self, tableview) -> int:
        if self._bom is None:
            return 0
        """
        BOM view contains the following sections:
        * list of ingredients
        * topo-sorted funtions for progress
        * refinery allocations
        * avoided materials
        """
        return 4

    def tableview_number_of_rows(self, tableview, section) -> int:
        if self._bom is None:
            return 0
        if section == 0:
            return len(self._bom.ingredients)
        elif section == 1:
            return len(self._bom.process)
        elif section == 2:
            return len(self._bom.refinery_allocations)
        elif section == 3:
            return len(self._avoided)

    def tableview_title_for_header(self, tableview, section) -> str:
        if section == 0:
            return "Required Materials"
        elif section == 1:
            return "Process"
        elif section == 2:
            return "Required Refineries"
        elif section == 3:
            return "Avoided Materials"
        return "Unexpected Section"

    def tableview_can_delete(self, tableview, section, row) -> bool:
        """
        Deleting in required materials section adds item to avoided materials
        Deleting in avoided materials section removes the item from avoided materials
        """
        if section == 0:
            return True
        elif section == 3:
            return True
        return False

    def tableview_delete(self, tableview, section, row) -> None:
        if section == 0:
            ...
        elif section == 3:
            ...


class ItemControl(nms.Loggable, ui.View):
    def __init__(self) -> None:
        super().__init__()
        self._item: nms.Item = None

    def did_load(self) -> None:
        ...

    # Subview properties
    @property
    def name_label(self) -> ui.Label:
        ...

    @property
    def image_view(self) -> ui.Label:
        return self["image"]

    # Item property
    @property
    def item(self) -> nms.Item:
        return self._item

    @item.setter
    def item(self, value: nms.Item) -> None:
        self._item = value
        if self._item:
            self.name_label.text = self._item.name_with_symbol
            if self._item.image:
                self.image_view.load_from_url(self._item.image)
            else:
                self.image_view.image = ui.Image.named(EMPTY_IMAGE)


class ItemView(nms.Loggable, ui.View):
    """
    Top view for item formulas
    States: source formulas, BOM, target formulas and a web view for wiki page
    """

    class ViewState(IntEnum):
        Source = 0
        BOM = 1
        Target = 2
        Wiki = 3

    def __init__(self) -> None:
        super().__init__()
        self._wiki = None
        self._item = None
        self._source_formulas = None
        self._target_formulas = None
        self._page_requested = False
        self.action = None
        self._units_image = None

    def did_load(self) -> None:
        self.log_info("View loaded")
        self._units_image = ui.Image.load_from_url(UNITS_IMAGE)

        self.item_name_label.font = (FANCY_FONT, 24)

        self.value_label.font = (FANCY_FONT, 18)
        self.currency_image.image = self._units_image

        self.value_label.hidden = True
        self.currency_image.hidden = True

        self.no_way_label.font = (FANCY_FONT, 30)
        self.no_way_label.hidden = True
        self.state_control.action = self.state_switched

    # Subview properties
    @property
    def item_name_label(self) -> ui.Label:
        return self["item_name"]

    @property
    def value_label(self) -> ui.Label:
        return self["value_label"]

    @property
    def currency_image(self) -> ui.ImageView:
        return self["currency_image"]

    @property
    def item_image(self) -> ui.ImageView:
        return self["item_image"]

    @property
    def formulas_view(self) -> ui.TableView:
        return self["formulas_view"]

    @property
    def state_control(self) -> ui.SegmentedControl:
        return self["state_control"]

    @property
    def webview(self) -> ui.WebView:
        return self["webview"]

    @property
    def no_way_label(self) -> ui.Label:
        return self["no_way"]

    # Actions
    def state_switched(self, sender: ui.SegmentedControl) -> None:
        self.log_info(f"State switched {sender.selected_index}")
        self.update_state()

    def item_selected(self, item: nms.Item) -> None:
        if self.action:
            self.action(item)

    # Logic
    @property
    def wiki(self) -> nms.Wiki:
        return self._wiki

    @wiki.setter
    def wiki(self, value: nms.Wiki) -> None:
        self._wiki = value
        self._source_formulas = FormulaDataSource(self._wiki)
        self._source_formulas.action = self.item_selected
        self._target_formulas = FormulaDataSource(self._wiki)
        self._target_formulas.action = self.item_selected

        self.update_state()

    @property
    def item(self) -> nms.Item:
        return self._item

    @item.setter
    def item(self, value: nms.Item) -> None:
        self._item = value
        if self._item:
            label = self._item.name.upper()
            if self._item.has_symbol:
                label += f" ({self._item.symbol})"
            self.item_name_label.text = label
            if self._item.image:
                self.item_image.load_from_url(self._item.image)

            self._source_formulas.items = self._item.source_formulas
            self._target_formulas.items = self._item.formulas

            self._page_requested = False

            self.update_state()
        else:
            ...

    def update_state(self) -> None:
        self.value_label.hidden = self._item is not None
        self.currency_image.hidden = self._item is not None

        state = ItemView.ViewState(self.state_control.selected_index)
        if state == ItemView.ViewState.Source:
            # source
            self._set_data_source(self._source_formulas)
        elif state == ItemView.ViewState.Target:
            # target
            self._set_data_source(self._target_formulas)
        elif state == ItemView.ViewState.Wiki:
            if not self._page_requested:
                self.webview.load_url(nms.Wiki.WIKI_BASE + self._item.id)
                self._page_requested = True

        if state == ItemView.ViewState.Wiki:
            self.webview.bring_to_front()
            self.webview.hidden = False
        else:
            self.webview.hidden = True
            self.webview.send_to_back()

    def _set_data_source(self, source: BaseDataSource) -> None:
        self.formulas_view.data_source = source
        self.formulas_view.delegate = source
        self.formulas_view.reload_data()
        self.formulas_view.hidden = source.empty
        self.no_way_label.hidden = not source.empty


class ItemsView(nms.Loggable, ui.View):
    def __init__(self):
        super().__init__()
        self._wiki = nms.Wiki()
        self._data_source = ItemDataSource()
        self._data_source.action = self.item_selected
        self._item_view = None
        self._history_stack = nms.LIFO()
        self._future_stack = nms.LIFO()
        self._back_button = None
        self._forward_button = None

    def _make_nav_button(self, title, action, image_name) -> ui.ButtonItem:
        button = ui.ButtonItem(
            title=title, action=action, image=ui.Image.named(image_name)
        )
        button.enabled = False
        return button

    def did_load(self) -> None:
        self._back_button = self._make_nav_button("Back", self.back_tapped, BACK_ARROW)
        self._forward_button = self._make_nav_button(
            "Forward", self.forward_tapped, FORWARD_ARROW
        )

        self.left_button_items = [self._back_button, self._forward_button]

        self.name = "NMS Formula Viewer"
        self.log_info("View loaded")

        self._item_view = ui.load_view(f"pyui-views/item-view")
        self.item_panel.add_subview(self._item_view)
        self._item_view.flex = "WH"
        self._item_view.width = self.item_panel.width
        self._item_view.height = self.item_panel.height
        self._item_view.wiki = self._wiki
        self._item_view.action = self.item_selected

        self.class_select.segments = [x.value for x in ITEM_CLASSES]
        self.class_select.selected_index = 0

        self.items_table.font = (FANCY_FONT, 24)

        self.assign_actions()
        self.load_by_class()

    def assign_actions(self) -> None:
        self.search_button.action = self.search_tapped
        self.items_table.delete_enabled = False
        self.items_table.editing = False
        self.items_table.data_source = self._data_source
        self.items_table.delegate = self._data_source
        self.class_select.action = self.class_switched

    def layout(self) -> None:
        self.log_info("Layout called")

    # UI properties
    @property
    def search_button(self) -> ui.Button:
        return self["search_button"]

    @property
    def search_field(self) -> ui.TextField:
        return self["search_field"]

    @property
    def items_table(self) -> ui.TableView:
        return self["items_table"]

    @property
    def class_select(self) -> ui.SegmentedControl:
        return self["class_select"]

    @property
    def item_panel(self) -> ui.View:
        return self["item_panel"]

    # Logic properties
    @property
    def items(self) -> list[nms.Item]:
        return self._items

    @items.setter
    def items(self, value: list[nms.Item]) -> None:
        self._data_source.items = value
        self.items_table.reload_data()

    # Actions
    def search_tapped(self, sender: ui.Button) -> None:
        self.log_info("Search tapped")
        search_term = self.search_field.text
        if len(search_term) > 3:
            self.search(search_term)

    def item_selected(self, item: nms.Item) -> None:
        self.log_info(f"{item} selected")
        self.show_item(item)

    def class_switched(self, sender: ui.SegmentedControl) -> None:
        self.load_by_class(ITEM_CLASSES[sender.selected_index])

    def back_tapped(self, sender: ui.ButtonItem) -> None:
        self.go_back()

    def forward_tapped(self, sender: ui.ButtonItem) -> None:
        self.go_forward()

    # Logic
    def search(self, search_term: str) -> None:
        res = asyncio.run(self._wiki.search_item(search_term))
        for item in res:
            self.log_info(f"{item}")
        self.class_select.selected_index = -1
        self.items = res

    def load_by_class(self, cls: nms.Class = nms.Class.Resource) -> None:
        res = asyncio.run(self._wiki.search_item(cls=cls.value))
        self.items = res

    def show_item(self, item: nms.Item) -> None:
        if self._item_view.item == item:
            return

        if self._item_view.item:
            self._history_stack.push(self._item_view.item)
        self._item_view.item = item
        self._future_stack.clear()

        self.update_nav_buttons()

    def go_back(self) -> None:
        if not self._history_stack.empty:
            # Current item to future stack
            self._future_stack.push(self._item_view.item)

            item = self._history_stack.pop()
            self._item_view.item = item

            self.update_nav_buttons()

    def go_forward(self) -> None:
        if not self._future_stack.empty:
            # Current item to history stack
            self._history_stack.push(self._item_view.item)

            item = self._future_stack.pop()
            self._item_view.item = item

            self.update_nav_buttons()

    def update_nav_buttons(self) -> None:
        self._update_nav_button(self._back_button, self._history_stack, "Back")
        self._update_nav_button(self._forward_button, self._future_stack, "Forward")

    def _update_nav_button(
        self, button: ui.ButtonItem, stack: nms.LIFO, default_title: str
    ) -> None:
        button.enabled = not stack.empty
        if button.enabled:
            item = stack.top()
            button.title = item.name_with_symbol
        else:
            button.title = default_title


def main():
    logger = logging.getLogger("main")
    v = ui.load_view()
    v.present("fullscreen")


if __name__ == "__main__":
    logger = logging.getLogger("main")
    main()
