import ui
from typing import Generic, TypeVar

from ._table_datasource import TableViewDataSource, TableViewDelegate
from .._loggable import Loggable

T = TypeVar("T")
U = TypeVar("U")


class BaseDataSource(Loggable, TableViewDataSource, TableViewDelegate, Generic[T, U]):
    def __init__(self) -> None:
        super().__init__()
        self._items = list[T]()
        self.action = None

    def __getitem__(self, key: int) -> T:
        return self._items[key]

    def sort_items(self, items: list[T]) -> list[T]:
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
    def items(self) -> list[T]:
        return self._items

    @items.setter
    def items(self, items: list[T]) -> None:
        self._items = self.sort_items(items)
        self.after_set_items()

    @property
    def empty(self) -> bool:
        return not self._items

    """
    TableView DataSource
    """

    def tableview_number_of_sections(self, tableview: ui.TableView) -> int:
        return 1

    def tableview_number_of_rows(self, tableview: ui.TableView, section: int) -> int:
        return len(self._items)

    def tableview_cell_for_row(
        self, tableview: ui.TableView, section: int, row: int
    ) -> ui.TableViewCell:
        cell = self.make_cell(str(self[row]))
        return cell

    def tableview_can_delete(
        self, tableview: ui.TableView, section: int, row: int
    ) -> bool:
        return False

    def tableview_can_move(
        self, tableview: ui.TableView, section: int, row: int
    ) -> bool:
        return False

    """
    TableView delegate
    """

    def tableview_did_select(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        # Called when a row was selected.
        self.log_info(f"{self[row]} selected")
        self.do_action(self[row])

    def do_action(self, item: U) -> None:
        if self.action:
            self.action(item)
