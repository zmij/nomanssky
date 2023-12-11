import logging
import ui

from .._loggable import Loggable
from ._constants import VIEWS_ROOT


class BaseView(Loggable, ui.View):
    VIEW_NAME = None

    def __init__(self) -> None:
        super().__init__()

    def did_load(self) -> None:
        ...

    @classmethod
    def load_view(view_class) -> "BaseView":
        return ui.load_view(f"{VIEWS_ROOT}/{view_class.VIEW_NAME}")
