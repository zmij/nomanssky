import ui

from .._loggable import Loggable
from ._table_datasource import SegmentedDataSource, TableViewDelegate

from .._bom import BOM


class BomDataSource(Loggable, SegmentedDataSource, TableViewDelegate):
    def __init__(self) -> None:
        super().__init__()
        self._bom: BOM = None
        self._avoided = []
        self._multiple = 1
        self.avoid_added = None
        self.avoid_deleted = None

    @property
    def bom(self) -> BOM:
        return self._bom

    @bom.setter
    def bom(self, value: BOM):
        self._bom = value

    @property
    def avoided(self) -> list[str]:
        return self._avoided

    @avoided.setter
    def avoided(self, value: list[str]) -> None:
        self._avoided = value

    def tableview_number_of_sections(self, tableview: ui.TableView) -> int:
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

    def tableview_number_of_rows(self, tableview: ui.TableView, section: int) -> int:
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

    def tableview_title_for_header(self, tableview: ui.TableView, section: int) -> str:
        if section == 0:
            return "Required Materials"
        elif section == 1:
            return "Process"
        elif section == 2:
            return "Required Refineries"
        elif section == 3:
            return "Avoided Materials"
        return "Unexpected Section"

    def tableview_can_delete(
        self, tableview: ui.TableView, section: int, row: int
    ) -> bool:
        """
        Deleting in required materials section adds item to avoided materials
        Deleting in avoided materials section removes the item from avoided materials
        """
        if section == 0:
            return True
        elif section == 3:
            return True
        return False

    def tableview_title_for_delete_button(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        if section == 0:
            return "Avoid"
        elif section == 3:
            return "Use"
        return "This is unexpected"

    def tableview_delete(self, tableview: ui.TableView, section: int, row: int) -> None:
        if section == 0:
            ingredient = self._bom.ingredients[row]
            self.log_info(f"Avoid {ingredient}")
            if self.avoid_added:
                item = self._bom.components[ingredient.name]
                self.avoid_added(item)
        elif section == 3:
            item = self._avoided[row]
            self.log_info(f"Don't avoid {item}")
            if self.avoid_deleted:
                self.avoid_deleted(item)

    def tableview_did_select(self, tableview, section, row) -> None:
        return super().tableview_did_select(tableview, section, row)
