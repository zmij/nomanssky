import pythonista

if not pythonista.in_pythonista():
    raise Exception(f"This script is intended to be run in Pythonista application")

import ui
import clipboard

from console import hud_alert

from typing import List, Iterable, Tuple
from enum import Enum, IntEnum

from nomanssky import GalacticCoords, CoordinateSpace
from nomanssky._coords import _CodeState as CodeState, _BoosterCodeState


GLYPH_FONT = "NMS Glyphs"
FANCY_FONT = "GeosansLight-NMS"
SCANNER_ID = "HUKYA"


class EditMode(IntEnum):
    PortalGlyph = 0
    PortalHex = 1
    Galactic = 2

    @property
    def portal_mode(self) -> bool:
        return self != EditMode.Galactic


MAX_CODE_LENGTH = {
    EditMode.PortalGlyph: 12,
    EditMode.PortalHex: 12,
    EditMode.Galactic: 4 * 4 + 3,
}

START_EDIT = {
    EditMode.PortalGlyph: 0,
    EditMode.PortalHex: 0,
    EditMode.Galactic: len(SCANNER_ID) + 2,
}


class DisplayMode(IntEnum):
    Dec = 0
    Hex = 1


MODE_FONTS = {
    EditMode.PortalGlyph: GLYPH_FONT,
    EditMode.PortalHex: FANCY_FONT,
    EditMode.Galactic: FANCY_FONT,
}

COLOUR_GOOD = "#39B339"
COLOUR_BAD = "#E04848"
COLOUR_INCOMPLETE = "#FF9E4E"
COLOUR_EMPTY = "#37B4B4"

STATE_COLOURS = {
    CodeState.Empty: COLOUR_EMPTY,
    CodeState.Incomplete: COLOUR_INCOMPLETE,
    CodeState.Complete: COLOUR_GOOD,
    CodeState.Invalid: COLOUR_BAD,
}


class GlyphCreator(ui.View):
    EMPTY_CODE = GalacticCoords("00380256EC6B")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._code = ""
        self._edit_mode = EditMode.PortalGlyph
        self._display_mode = DisplayMode.Dec
        self._parse_state = CodeState.Empty
        self._coords = GalacticCoords()

    def did_load(self) -> None:
        button_items = []
        bi = ui.ButtonItem(title="Close", action=self.close_tapped)
        button_items.append(bi)
        self.right_button_items = button_items

        self.set_font(self.glyph_buttons(), (GLYPH_FONT,))
        self.set_font(self.code_label, (GLYPH_FONT, 28))
        self.set_font([self.scanner_label, self.clear_button], (FANCY_FONT, 24))
        self.set_font(self.code_edit, (FANCY_FONT))

        self.set_font(
            [
                self.x_label,
                self.y_label,
                self.z_label,
                self.star_system_label,
                self.planet_label,
            ],
            (FANCY_FONT,),
        )

        for i, bn in enumerate(self.glyph_buttons()):
            bn.action = self.make_glyph_handler(i)

        self.code_edit.delegate = HexFilter(self)

        self.code_label.action = self.copy_label_tapped
        self.scanner_label.action = self.copy_label_tapped

        self.clear_button.action = self.clear_tapped
        self.del_button.action = self.del_tapped
        self.copy_button.action = self.copy_tapped
        self.mode_switch.action = self.edit_mode_switched
        self.display_mode.action = self.display_mode_switched

        # Force update labels
        self.code = ""

    def layout(self) -> None:
        # Distribute x y z labels
        self.distribute_horizontally(
            [self.x_label, self.y_label, self.z_label], right=self.display_mode.x
        )
        # Distribute labels for star system and planet
        self.distribute_horizontally([self.star_system_label, self.planet_label])

        # Distribute glyph buttons horizontally in packs by 4
        for i in range(0, 4):
            start = i * 4
            end = i * 4 + 4
            self.distribute_horizontally(self.glyph_buttons(range(start, end)))

        # Next distribute glyph buttons vertically in packs by 4
        for i in range(0, 4):
            self.distribute_vertically(
                self.glyph_buttons([i, i + 4, i + 8, i + 12]),
                top=self.mode_switch.y + self.mode_switch.height,
            )

        # Now resize edit mode switch
        self.mode_switch.width = (
            self.glyph_buttons([1])[0].x
            + self.glyph_buttons([1])[0].width
            - self.glyph_buttons([0])[0].x
        )

        # And align clear and del buttons nicely
        self.distribute_horizontally(
            [self.clear_button, self.del_button],
            left=self.mode_switch.x + self.mode_switch.width,
        )

    def distribute_horizontally(
        self,
        items: Iterable[ui.View],
        margins: int = 6,
        space: int = 6,
        left: int = None,
        right: int = None,
    ) -> None:
        if left is None:
            left = 0
        if right is None:
            right = self.width

        item_count = len(items)
        total_space = margins * 2 + space * (item_count - 1)
        item_width = (right - left - total_space) // item_count
        for idx, item in enumerate(items):
            offset = left + margins + idx * (item_width + space)
            item.x = offset
            item.width = item_width

    def distribute_vertically(
        self,
        items: Iterable[ui.View],
        margins: int = 6,
        space: int = 6,
        top: int = None,
        bottom: int = None,
    ) -> None:
        if top is None:
            top = 0
        if bottom is None:
            bottom = self.height

        item_count = len(items)
        total_space = margins * 2 + space * (item_count - 1)
        item_height = (bottom - top - total_space) // item_count
        for idx, item in enumerate(items):
            offset = top + margins + idx * (item_height + space)
            item.y = offset
            item.height = item_height

    @property
    def code_edit(self) -> ui.TextField:
        return self.subviews[0]

    @property
    def code_label(self) -> ui.Label:
        return self["code_label"]

    @property
    def scanner_label(self) -> ui.Label:
        return self["scanner_label"]

    @property
    def x_label(self) -> ui.Label:
        return self["x_label"]

    @property
    def y_label(self) -> ui.Label:
        return self["y_label"]

    @property
    def z_label(self) -> ui.Label:
        return self["z_label"]

    @property
    def star_system_label(self) -> ui.Label:
        return self["star_system_label"]

    @property
    def planet_label(self) -> ui.Label:
        return self["planet_label"]

    def glyph_buttons(self, r: Iterable[int] = None) -> List[ui.Button]:
        if r is None:
            r = range(0, 16)
        return [self[f"bn_{n:x}"] for n in r]

    @property
    def clear_button(self) -> ui.Button:
        return self["clear_button"]

    @property
    def del_button(self) -> ui.Button:
        return self["del_button"]

    @property
    def mode_switch(self) -> ui.SegmentedControl:
        return self["mode_switch"]

    @property
    def display_mode(self) -> ui.SegmentedControl:
        return self["display_mode"]

    @property
    def copy_button(self) -> ui.Button:
        return self["copy_button"]

    @property
    def code(self) -> str:
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        last_idx = -1
        if value:
            if self._edit_mode == EditMode.Galactic:
                # Insert colons into right places
                parts = value.split(":")
                if len(parts) < 4 and len(parts[-1]) == 4:
                    value += ":"
                _, self._parse_state, last_idx = GalacticCoords.from_booster_code(
                    value,
                    raise_if_invalid=False,
                    coords=self._coords,
                    start_state=_BoosterCodeState.x,
                )
            else:
                _, self._parse_state, last_idx = GalacticCoords.from_portal_code(
                    value, raise_if_invalid=False, coords=self._coords
                )
            # print(f"`{value}` -> {self._parse_state!r} {last_idx}")

        self._code = value[: last_idx + 1]
        if self._edit_mode == EditMode.Galactic:
            self.code_edit.text = f"{SCANNER_ID}:" + self._code
        else:
            self.code_edit.text = self._code

        if self._code:
            if self._edit_mode.portal_mode:
                self.update_display_coords(self._coords, portal_code=self._code)
            else:
                self.update_display_coords(self._coords, booster_code=self._code)
        else:
            self._parse_state = CodeState.Empty
            self.update_display_coords(GlyphCreator.EMPTY_CODE)

    def update_display_coords(
        self, coords: GalacticCoords, portal_code: str = None, booster_code=None
    ) -> None:
        self.code_label.title = portal_code and portal_code or coords.portal_code
        self.scanner_label.title = (
            booster_code
            and f"{SCANNER_ID}:{booster_code}"
            or coords.booster_code(alpha=SCANNER_ID)
        )
        self.x_label.text = self.format_coords("X", coords.x)
        self.y_label.text = self.format_coords("Y", coords.y)
        self.z_label.text = self.format_coords("Z", coords.z)
        self.star_system_label.text = self.format_coords(
            "STAR SYSTEM", coords.star_system
        )
        self.planet_label.text = self.format_coords("PLANET", coords.planet)

        self.set_text_colour(
            [
                self.code_label,
                self.scanner_label,
                self.x_label,
                self.y_label,
                self.z_label,
                self.star_system_label,
                self.planet_label,
            ],
            STATE_COLOURS[self._parse_state],
        )
        self.copy_button.enabled = self._parse_state == CodeState.Complete

    def format_coords(self, label: str, value: int) -> str:
        if self._display_mode == DisplayMode.Dec or value is None:
            return f"{label}: {value}"
        else:
            return f"{label}: 0x{value:X}"

    def set_text_colour(self, items: Iterable[ui.View], colour: str) -> None:
        for item in items:
            if isinstance(item, ui.Label):
                item.text_color = colour
            elif isinstance(item, ui.Button):
                item.tint_color = colour

    def set_font(
        self, items: Iterable[ui.View] | ui.View, font: Tuple[str, int]
    ) -> None:
        if len(font) == 2:

            def _set_font(item: ui.View):
                item.font = font

        else:

            def _set_font(item: ui.View):
                item.font = (font[0], item.font[1])

        if hasattr(items, "__iter__"):
            for item in items:
                _set_font(item)
        else:
            _set_font(items)

    def append_glyph(self, value: int) -> None:
        if self._parse_state != CodeState.Complete:
            self.code += f"{value:X}"

    def append_text(self, value: str) -> None:
        for c in value:
            try:
                g = int(c, 16)
                self.append_glyph(g)
            except:
                ...

    def clear_code(self) -> None:
        self.code = ""

    def del_glyph(self) -> None:
        if len(self._code) > 0:
            code = self.code
            if code[-1] == ":":
                code = code[:-2]
            else:
                code = code[:-1]
            self.code = code

    def remove_code_range(self, r: range) -> None:
        # TODO check edit mode
        edit_start = START_EDIT[self._edit_mode]
        delete_start = r[0]
        self.code = self.code[: r[0]] + self.code[r[1] :]

    def glyph_tapped(self, sender: ui.Button, number: int) -> None:
        self.append_glyph(number)

    def make_glyph_handler(self, val: int):
        def handler(sender):
            self.glyph_tapped(sender, val)

        return handler

    def clear_tapped(self, sender: ui.Button) -> None:
        self.clear_code()

    def del_tapped(self, sender: ui.Button) -> None:
        self.del_glyph()

    def edit_mode_switched(self, sender: ui.SegmentedControl) -> None:
        old_edit_mode = self._edit_mode
        self._edit_mode = EditMode(sender.selected_index)
        self.set_font(self.glyph_buttons(), (MODE_FONTS[self._edit_mode],))
        if old_edit_mode.portal_mode != self._edit_mode.portal_mode:
            if self._parse_state == CodeState.Complete:
                if self._edit_mode == EditMode.Galactic:
                    self.code = self._coords.galactic_coords
                else:
                    self.code = self._coords.portal_code
            else:
                self.clear_code()

    def display_mode_switched(self, sender: ui.SegmentedControl) -> None:
        self._display_mode = DisplayMode(sender.selected_index)
        # Force update labels
        self.code = self.code

    def copy_tapped(self, sender: ui.Button) -> None:
        clipboard.set(self.code_edit.text)
        hud_alert(f"{self.code_edit.text} copied")

    def copy_label_tapped(self, sender: ui.Button) -> None:
        if self._parse_state == CodeState.Complete:
            clipboard.set(sender.title)
            hud_alert(f"{sender.title} copied")

    def close_tapped(self, sender: ui.ButtonItem) -> None:
        self.close()


class HexFilter:
    def __init__(self, owner: GlyphCreator) -> None:
        self._owner = owner

    def textfield_should_begin_editing(self, textfield: ui.TextField) -> bool:
        return False

    def textfield_did_begin_editing(self, textfield: ui.TextField) -> None:
        ...

    def textfield_did_end_editing(self, textfield: ui.TextField) -> None:
        ...

    def textfield_should_return(self, textfield: ui.TextField) -> bool:
        textfield.end_editing()
        return True

    def textfield_should_change(
        self, textfield: ui.TextField, r: range, replacement: str
    ) -> bool:
        # if r[0] > 11:
        #     return False
        if replacement:
            self._owner.append_text(replacement)
        else:
            self._owner.remove_code_range(r)
        return False

    def textfield_did_change(self, textfield: ui.TextField) -> None:
        print(f"{textfield} did change")


def main():
    v = ui.load_view()
    v.name = "NMS Glyphs"

    v.present("panel")


if __name__ == "__main__":
    main()
