import ui
import asyncio

from enum import IntEnum

from .._items import Item
from .._wiki import Wiki
from .._formula import ProductionChain, ProductionStage
from .._formula_cycles import detect_formula_cycles
from ..symbols import Symbols

from ._constants import FANCY_FONT, UNITS_IMAGE
from ._base_view import BaseView
from ._bom_view import BOMView
from ._base_datasource import BaseDataSource
from ._formula_datasource import FormulaDataSource
from ._prodchain_datasource import ProdChainDataSource
from ._formula_popup import FormulaPopup


class ItemView(BaseView):
    VIEW_NAME = "item-view"
    """
    Top view for item formulas
    States: source formulas, BOM, target formulas and a web view for wiki page
    """

    @classmethod
    def load_view(view_class) -> "ItemView":
        return super().load_view()

    class ViewState(IntEnum):
        Source = 0
        Target = 1
        BOM = 2
        Wiki = 3

    def __init__(self) -> None:
        super().__init__()
        self._wiki = None
        self._item = None
        self._source_formulas = None
        self._target_formulas = None
        self._prod_chains = None
        self._page_requested = False
        self._bom_view = None
        self.action = None

    def _make_bom_view(self) -> None:
        self._bom_view = BOMView.load_view()
        self._bom_view.wiki = self._wiki
        self._bom_view.x = self.formulas_view.x
        self._bom_view.y = self.formulas_view.y
        self._bom_view.width = self.formulas_view.width
        self._bom_view.height = self.formulas_view.height
        self._bom_view.flex = "WH"
        self._bom_view.hidden = True
        self.add_subview(self._bom_view)

    def did_load(self) -> None:
        self.log_info("View loaded")

        self.item_name_label.font = (FANCY_FONT, 24)

        self.value_label.font = (FANCY_FONT, 18)
        self.currency_image.load_from_url(UNITS_IMAGE)

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

    def item_selected(self, item: Item) -> None:
        if self.action:
            self.action(item)

    def production_stage_selected(
        self, chain: ProductionChain, stage: ProductionStage, stage_no: int
    ) -> None:
        self.log_info(f"{chain} stage {stage_no} selected")
        view = FormulaPopup.load_view()

        def _action(item: Item) -> None:
            view.close()
            self.item_selected(item)

        formulas = FormulaDataSource(self._wiki)
        formulas.items = stage.formulas
        formulas.action = _action

        view.name = f"Stage {stage_no + 1}"
        view.width = self.formulas_view.width
        view.formulas = formulas
        view.present("sheet")

    # Logic
    @property
    def wiki(self) -> Wiki:
        return self._wiki

    @wiki.setter
    def wiki(self, value: Wiki) -> None:
        self._wiki = value
        self._source_formulas = FormulaDataSource(self._wiki)
        self._source_formulas.action = self.item_selected
        self._target_formulas = FormulaDataSource(self._wiki)
        self._target_formulas.action = self.item_selected
        self._prod_chains = ProdChainDataSource(self._wiki)
        self._prod_chains.action = self.item_selected
        self._prod_chains.stage_action = self.production_stage_selected
        # TODO Actions

        self.update_state()

    @property
    def item(self) -> Item:
        return self._item

    @item.setter
    def item(self, value: Item) -> None:
        self._item = value
        if self._item:
            label = self._item.name.upper()
            if self._item.has_symbol:
                label += f" ({self._item.symbol})"
            self.item_name_label.text = label
            if self._item.image:
                self.item_image.load_from_url(self._item.image)

            self.value_label.text = f"{self._item.value}{Symbols.UNITS}"

            self._source_formulas.items = self._item.source_formulas
            self._target_formulas.items = self._item.formulas

            cycles = asyncio.run(
                detect_formula_cycles(
                    self._wiki, self._item.source_formulas, db_only=True
                )
            )
            if self._item.id in cycles.detected_cycles:
                self._prod_chains.items = cycles.detected_cycles[self._item.id]
            else:
                self._prod_chains.items = []

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
        elif state == ItemView.ViewState.BOM:
            self._set_data_source(self._prod_chains)
        elif state == ItemView.ViewState.Wiki:
            if not self._page_requested:
                self.webview.load_url(Wiki.WIKI_BASE + self._item.id)
                self._page_requested = True

        if state == ItemView.ViewState.Wiki:
            self.webview.bring_to_front()
            self.webview.hidden = False
        else:
            self.webview.hidden = True
            self.webview.send_to_back()

        # if state == ItemView.ViewState.BOM:
        #     self._bom_view.hidden = False
        #     self._bom_view.bring_to_front()
        # else:
        #     self._bom_view.hidden = True
        #     self._bom_view.send_to_back()
        self.value_label.hidden = self._item is None

    def _set_data_source(self, source: BaseDataSource) -> None:
        self.formulas_view.data_source = source
        self.formulas_view.delegate = source
        self.formulas_view.reload_data()
        self.formulas_view.hidden = source.empty
        self.no_way_label.hidden = not source.empty
