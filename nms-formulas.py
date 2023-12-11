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
from nomanssky.pythonista import (
    ItemDataSource,
    ItemView,
)

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

VIEWS_ROOT = "pyui-views"


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

        self._item_view = ItemView.load_view()
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
