import ui

from ._constants import FANCY_FONT


class TableViewDataSource:
    def make_cell(
        self,
        text: str,
        detail_text: str = None,
        style="default",
        font_size: int = 20,
        detail_font_size=16,
        text_colour: str = "black",
    ) -> ui.TableViewCell:
        cell = ui.TableViewCell(style=style)
        cell.text_label.font = (FANCY_FONT, font_size)
        cell.text_label.text_color = text_colour
        if text:
            cell.text_label.text = text
        if style != "default":
            cell.detail_text_label.font = (FANCY_FONT, detail_font_size)
            cell.detail_text_label.text_color = text_colour
            if detail_text:
                cell.detail_text_label.text = detail_text
        return cell

    """
    TableView DataSource
    """

    def tableview_number_of_sections(self, tableview: ui.TableView) -> int:
        # Return the number of sections (defaults to 1)
        ...

    def tableview_number_of_rows(self, tableview: ui.TableView, section: int) -> int:
        # Return the number of rows in the section
        ...

    def tableview_cell_for_row(
        self, tableview: ui.TableView, section: int, row: int
    ) -> ui.TableViewCell:
        # Create and return a cell for the given section/row
        ...

    def tableview_can_delete(self, tableview: ui.TableView, section: int, row) -> bool:
        # Return True if the user should be able to delete the given row.
        return False

    def tableview_can_move(self, tableview: ui.TableView, section: int, row) -> bool:
        # Return True if a reordering control should be shown for the given row (in editing mode).
        return False

    def tableview_delete(self, tableview: ui.TableView, section: int, row) -> None:
        # Called when the user confirms deletion of the given row.
        ...

    def tableview_move_row(
        self,
        tableview: ui.TableView,
        from_section: int,
        from_row: int,
        to_section: int,
        to_row: int,
    ) -> None:
        # Called when the user moves a row with the reordering control (in editing mode).
        ...


class SegmentedDataSource(TableViewDataSource):
    def tableview_title_for_header(self, tableview: ui.TableView, section: int) -> str:
        # Return a title for the given section.
        # If this is not implemented, no section headers will be shown.
        return f"{self.__class__.__name__} section {section}"


class TableViewDelegate:
    def tableview_did_select(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        # Called when a row was selected.
        ...

    def tableview_did_deselect(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        # Called when a row was de-selected (in multiple selection mode).
        ...

    def tableview_title_for_delete_button(
        self, tableview: ui.TableView, section: int, row: int
    ) -> None:
        # Return the title for the 'swipe-to-***' button.
        ...
