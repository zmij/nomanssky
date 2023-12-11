import ui

from .._wiki import Wiki
from ._base_view import BaseView
from ._formula_datasource import FormulaDataSource


class FormulaPopup(BaseView):
    VIEW_NAME = "table-view"

    @classmethod
    def load_view(view_class) -> "FormulaPopup":
        return super().load_view()

    def __init__(self) -> None:
        super().__init__()
        self._formulas: FormulaDataSource = None

    @property
    def formulas(self) -> FormulaDataSource:
        return self._formulas

    @formulas.setter
    def formulas(self, value: FormulaDataSource) -> None:
        self._formulas = value
        self.table_view.data_source = self._formulas
        self.table_view.delegate = self._formulas
        self.table_view.reload_data()

    @property
    def table_view(self) -> ui.TableView:
        return self["the_table"]
