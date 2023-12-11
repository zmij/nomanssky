import ui
import asyncio

from enum import IntEnum

from .._items import Item
from .._wiki import Wiki
from .._bom import BOM, build_bom

from ._base_view import BaseView
from ._bom_datasource import BomDataSource
from ._constants import FANCY_FONT


class BomCalculationMode(IntEnum):
    PreferRefining = 0
    PreferCraft = 1


class BOMView(BaseView):
    VIEW_NAME = "bom-view"

    def __init__(self) -> None:
        super().__init__()
        self._wiki = None
        self._mode = BomCalculationMode.PreferRefining
        self._boms = dict[str, BOM]()
        self._bom_ds = BomDataSource()

    def did_load(self) -> None:
        self.total_label.font = (FANCY_FONT, 18)
        self.multiple_label.font = (FANCY_FONT, 18)

        self.prefer_mode_switch.action = self.mode_switched
        self.multiple_slider.action = self.multiple_changed
        self._bom_ds.avoid_added = self.avoid_added
        self._bom_ds.avoid_deleted = self.avoid_deleted

        self.table_view.data_source = self._bom_ds
        self.table_view.delegate = self._bom_ds

    # Subview properties
    @property
    def table_view(self) -> ui.TableView:
        return self["bom_view"]

    @property
    def total_label(self) -> ui.Label:
        return self["total_cost"]

    @property
    def multiple_slider(self) -> ui.Slider:
        return self["multiplication_slider"]

    @property
    def multiple_label(self) -> ui.Label:
        return self["multiple_label"]

    @property
    def prefer_mode_switch(self) -> ui.SegmentedControl:
        return self["prefer_mode_switch"]

    # Actions
    def mode_switched(self, sender: ui.SegmentedControl) -> None:
        # Recalc required
        self.log_info(f"Slider value changed to {sender.selected_index}")

    def multiple_changed(self, sender: ui.Slider) -> None:
        # Redraw only needed, no recalc required
        new_multiple = 1 + int(99 * sender.value)
        self.log_info(f"Slider value changed to {sender.value} {new_multiple}")
        self.multiple = new_multiple

    def avoid_added(self, item: Item) -> None:
        # Recalc required
        ...

    def avoid_deleted(self, item_id: str) -> None:
        # Recalc required
        ...

    # Logic
    @property
    def wiki(self) -> Wiki:
        return self._wiki

    @wiki.setter
    def wiki(self, value: Wiki) -> None:
        self._wiki = value
        # self._source_formulas = FormulaDataSource(self._wiki)
        # self._source_formulas.action = self.item_selected
        # self._target_formulas = FormulaDataSource(self._wiki)
        # self._target_formulas.action = self.item_selected

        self.update_state()

    @property
    def item(self) -> Item:
        return self._item

    @item.setter
    def item(self, value: Item) -> None:
        self._item = value
        if self._item:
            self.calculate_bom()
        else:
            self._bom_ds.bom = None
        self.update_state()

    @property
    def bom(self) -> BOM:
        return self._bom_ds.bom

    @property
    def multiple(self) -> int:
        return self._bom_ds._multiple

    @multiple.setter
    def multiple(self, value: int) -> None:
        if value > 0 and value != self._bom_ds._multiple:
            self._bom_ds._multiple = value
            self.multiple_label.text = f"x{value}"

    def update_state(self) -> None:
        self.table_view.reload_data()

    def calculate_bom(self) -> None:
        # TODO Check cache
        bom = asyncio.run(
            build_bom(self._wiki, self._item, [], prefer_craft=False, db_only=True)
        )
        self._bom_ds.bom = bom

    @classmethod
    def load_view(cls) -> "BOMView":
        return super().load_view()
