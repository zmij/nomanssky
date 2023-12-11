import ui

from ._base_datasource import BaseDataSource
from .._items import Item


class ItemDataSource(BaseDataSource[Item, Item]):
    def __init__(self) -> None:
        super().__init__()

    def sort_items(self, items: list[Item]) -> list[Item]:
        return sorted(items, key=lambda s: s.name)

    def tableview_cell_for_row(self, tableview: ui.TableView, section: int, row: int):
        item = self._items[row]
        cell = self.make_cell(item.name_with_symbol)
        if item.image:
            cell.image_view.load_from_url(item.image)
        return cell
