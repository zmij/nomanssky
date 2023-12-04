from enum import IntEnum, Enum
from collections import namedtuple
from typing import Any

from ._loggable import Loggable


class Glyphs(IntEnum):
    Sunset = 0x0
    Bird = 0x1
    Face = 0x2
    Diplo = 0x3
    Eclipse = 0x4
    Balloon = 0x5
    Boat = 0x6
    Bug = 0x7
    Dragonfly = 0x8
    Galaxy = 0x9
    Voxel = 0xA
    Fish = 0xB
    Tent = 0xC
    Rocket = 0xD
    Tree = 0xE
    Atlas = 0xF


class _BoosterCodeState(IntEnum):
    BoosterID = 0
    x = 1
    y = 2
    z = 3
    planet = 4
    star_system = 5
    DONE = 6
    INCOMPLETE = 100499
    ERROR = 100500

    def next(self) -> "_BoosterCodeState":
        return _BoosterCodeState(self.value + 1)


class _PortalCodeState(IntEnum):
    planet = 0
    star_system = 1
    y = 2
    z = 3
    x = 4
    DONE = 5
    INCOMPLETE = 100499
    ERROR = 100500

    def next(self) -> "_PortalCodeState":
        return _PortalCodeState(self.value + 1)


class _CodeState(IntEnum):
    Empty = 0
    Incomplete = 1
    Complete = 2
    Invalid = 3


def _y_galactic_to_portal(value: int) -> int:
    # TODO check range
    if value < 0x7F:
        return 0x81 + value
    return value - 0x7F


def _y_portal_to_galactic(value: int) -> int:
    if value > 0x80:
        return value - 0x81
    return value + 0x7F


def _xz_galactic_to_portal(value: int) -> int:
    # TODO check range
    if value < 0x7FF:
        return 0x801 + value
    return value - 0x7FF


def _xz_portal_to_galactic(value: int) -> int:
    if value > 0x800:
        return value - 0x801
    return value + 0x7FF


_NOOP = lambda s: s


_Conversions = namedtuple(
    "_Conversions",
    [
        "name",
        "y_to_galactic",  # Current coord space to galactic coord space
        "y_to_portal",  # Current coord space to portal coord space
        "y_from_galactic",  # Galactic coord space to local
        "y_from_portal",  # Portal coord space to local
        "xz_to_galactic",  # Current coord space to portal coord space
        "xz_to_portal",  # Current coord space to galactic coord space
        "xz_from_galactic",  # Galactic coord space to local
        "xz_from_portal",  # Portal coord space to local
    ],
    defaults=[
        None,
        _NOOP,
        _NOOP,
        _NOOP,
        _NOOP,
        _NOOP,
        _NOOP,
        _NOOP,
        _NOOP,
    ],
)


class CoordinateSpace(Enum):
    Galactic = _Conversions(
        name="Galactic",
        y_to_portal=_y_galactic_to_portal,
        y_from_portal=_y_portal_to_galactic,
        xz_to_portal=_xz_galactic_to_portal,
        xz_from_portal=_xz_portal_to_galactic,
    )
    Portal = _Conversions(
        name="Portal",
        y_to_galactic=_y_portal_to_galactic,
        y_from_galactic=_y_galactic_to_portal,
        xz_to_galactic=_xz_portal_to_galactic,
        xz_from_galactic=_xz_galactic_to_portal,
    )

    def y_to_galactic(self, value: int) -> int:
        return self.value.y_to_galactic(value)

    def y_from_galactic(self, value: int) -> int:
        return self.value.y_from_galactic(value)

    def y_to_portal(self, value: int) -> int:
        return self.value.y_to_portal(value)

    def y_from_portal(self, value: int) -> int:
        return self.value.y_from_portal(value)

    def xz_to_galactic(self, value: int) -> int:
        return self.value.xz_to_galactic(value)

    def xz_from_galactic(self, value: int) -> int:
        return self.value.xz_from_galactic(value)

    def xz_to_portal(self, value: int) -> int:
        return self.value.xz_to_portal(value)

    def xz_from_portal(self, value: int) -> int:
        return self.value.xz_from_portal(value)

    def from_portal(self, field: Any, value: int) -> int:
        if field.name == "y":
            return self.y_from_portal(value)
        if field.name == "x":
            return self.xz_from_portal(value)
        if field.name == "z":
            return self.xz_from_portal(value)
        return value

    def from_galactic(self, field: Any, value: int) -> int:
        if field.name == "y":
            return self.y_from_galactic(value)
        if field.name == "x":
            return self.xz_from_galactic(value)
        if field.name == "z":
            return self.xz_from_galactic(value)
        return value


_DEFAULT_COORD_SPACE = CoordinateSpace.Portal


class GalacticCoords(Loggable):
    """
    Galactic coords

    Stores x, y and z in the Portal coordinate system
    """

    planet: int
    star_system: int
    y: int
    z: int
    x: int
    c_space: CoordinateSpace

    def __init__(
        self,
        code: str = None,
        *,
        planet: int = None,
        star_system: int = None,
        y: int = None,
        x: int = None,
        z: int = None,
        sep: str = ":",
        coordinate_space: CoordinateSpace = _DEFAULT_COORD_SPACE,
    ) -> None:
        self.planet = planet
        self.star_system = star_system
        self.y = y
        self.x = x
        self.z = z
        self.c_space = coordinate_space
        if code:
            if sep != ":" or code.find(sep) >= 0:
                # Try parse booster string
                _, booster_state, _ = GalacticCoords.from_booster_code(
                    code,
                    coordinate_space=coordinate_space,
                    raise_if_invalid=False,
                    coords=self,
                    sep=sep,
                )
                if booster_state == _CodeState.Complete:
                    return
                # Retry parsing without booster id
                GalacticCoords.from_booster_code(
                    code,
                    coordinate_space=coordinate_space,
                    start_state=_BoosterCodeState.x,
                    coords=self,
                    sep=sep,
                    parse_entity="galatic coords",
                    complete_after=_BoosterCodeState.z,
                )
            else:
                GalacticCoords.from_portal_code(
                    code, coords=self, coordinate_space=coordinate_space
                )

    def __str__(self) -> str:
        return self.galactic_coords

    def __repr__(self) -> str:
        return f"<x: {self.x} y: {self.y} z: {self.z} system: {self.star_system} planet: {self.planet}>"

    def __format__(self, __format_spec: str) -> str:
        """
        Format specs:
        c = galactic coords (default)
        p = portal string
        b = booster string
        TODO other formats, e.g. x for lowercase hexes or d for decimals
        """
        if __format_spec == "c":
            return self.galactic_coords
        if __format_spec == "p":
            return self.portal_code
        elif __format_spec.startswith("b"):
            return self.booster_code(alpha=__format_spec[1:])
        return super().__format__(__format_spec)

    @property
    def coordinate_space(self) -> CoordinateSpace:
        return self.c_space.value

    @property
    def valid(self) -> bool:
        for a in ["x", "y", "z", "planet", "star_system"]:
            if not hasattr(self, a) or getattr(self, a) is None:
                return False
        return True

    @property
    def portal_code(self) -> str:
        return "".join(
            [
                f"{{:{fmt}}}".format(v or 0)
                for v, fmt in [
                    (self.planet, "1X"),
                    (self.star_system, "03X"),
                    (self.c_space.y_to_portal(self.y or 0), "02X"),
                    (self.c_space.xz_to_portal(self.z or 0), "03X"),
                    (self.c_space.xz_to_portal(self.x or 0), "03X"),
                ]
            ]
        )

    @property
    def galactic_coords(self) -> str:
        return self.booster_code(alpha=None)

    def booster_code(self, alpha: str = "HUKYA", sep: str = ":") -> str:
        return sep.join(
            [
                f"{{:{fmt}}}".format(v)
                for v, fmt in [
                    (alpha, "s"),
                    (self.c_space.xz_to_galactic(self.x or 0), "04X"),
                    (self.c_space.y_to_galactic(self.y or 0), "04X"),
                    (self.c_space.xz_to_galactic(self.z or 0), "04X"),
                    ((self.planet or 0) * 0x1000 + (self.star_system or 0), "04X"),
                ]
                if v is not None
            ]
        )

    @property
    def xyz(self):
        return ":".join(
            [
                "{:04X}".format(v)
                for v in [
                    self.c_space.xz_to_galactic(self.x or 0),
                    self.c_space.y_to_galactic(self.y or 0),
                    self.c_space.xz_to_galactic(self.z or 0),
                ]
            ]
        )

    @classmethod
    def from_booster_code(
        cls,
        code: str,
        coordinate_space: CoordinateSpace = _DEFAULT_COORD_SPACE,
        raise_if_invalid: bool = True,
        coords: "GalacticCoords" = None,
        start_state: _BoosterCodeState = _BoosterCodeState.BoosterID,
        sep: str = ":",
        complete_after: _BoosterCodeState = _BoosterCodeState.star_system,
        parse_entity: str = "booster code",
    ) -> "GalacticCoords":
        """
        Parse signal booster string

        Signal booster string format is NNNNN:XXXX:YYYY:ZZZZ:PSSS
        """
        parser = booster_string_parser(code, start_state=start_state, sep=sep)
        state = _CodeState.Empty
        if coords is None:
            coords = GalacticCoords(coordinate_space=coordinate_space)

        last_idx = -1
        prev_idx = -1
        for v, s, n in parser:
            prev_idx = last_idx
            last_idx = n
            if s == _BoosterCodeState.BoosterID:
                # Ignore the scanner id
                continue

            # print(f"{s!r} {v}")

            if s == _BoosterCodeState.ERROR:
                state = _CodeState.Invalid
                break

            if s == _BoosterCodeState.INCOMPLETE:
                state = _CodeState.Incomplete
                break

            if s >= complete_after:
                state = _CodeState.Complete
            else:
                state = _CodeState.Incomplete

            try:
                setattr(coords, s.name, coordinate_space.from_galactic(s, v))
            except Exception as e:
                # Restore last_idx
                last_idx = prev_idx
                state = _CodeState.Invalid
                cls.try_log_error(f"{e}")
                break
        if raise_if_invalid:
            if state != _CodeState.Complete:
                raise ValueError(
                    f"`{code}` is an {state.name.lower()} value for {parse_entity}"
                )
            return coords
        return coords, state, last_idx

    @classmethod
    def from_portal_code(
        cls,
        code: str,
        coordinate_space: CoordinateSpace = _DEFAULT_COORD_SPACE,
        raise_if_invalid: bool = True,
        coords: "GalacticCoords" = None,
    ) -> "GalacticCoords":
        """
        Parse portal code string

        Portal string format is PSSSYYZZZXXX
        """
        parser = portal_string_parser(code)
        state = _CodeState.Empty
        if not coords:
            coords = GalacticCoords(coordinate_space=coordinate_space)
        last_idx = -1
        for v, s, n in parser:
            if s == _PortalCodeState.ERROR:
                state = _CodeState.Invalid
                last_idx = n
                break
            if s == _PortalCodeState.x:
                state = _CodeState.Complete
            else:
                state = _CodeState.Incomplete

            try:
                setattr(coords, s.name, coordinate_space.from_portal(s, v))
                last_idx = n
            except Exception as e:
                state = _CodeState.Invalid
                cls.try_log_error(f"{e}")
                break
        if raise_if_invalid:
            if state != _CodeState.Complete:
                raise ValueError(
                    f"`{code}` is an {state.name.lower()} value for portal code"
                )
            return coords
        return coords, state, last_idx

    @classmethod
    def try_log_error(cls, message: str) -> None:
        logger = cls.get_class_logger()
        if logger:
            logger.error(message)


_BOOSTER_TOKEN_LENGTH = {
    _BoosterCodeState.x: 4,
    _BoosterCodeState.y: 4,
    _BoosterCodeState.z: 4,
    _BoosterCodeState.planet: 1,
    _BoosterCodeState.star_system: 3,
}

_PORTAL_TOKEN_LENGHT = {
    _PortalCodeState.planet: 1,
    _PortalCodeState.star_system: 3,
    _PortalCodeState.y: 2,
    _PortalCodeState.z: 3,
    _PortalCodeState.x: 3,
}


def _check_token_length(state: _BoosterCodeState, token: str) -> bool:
    if state == _BoosterCodeState.BoosterID:
        return True
    return len(token) == _BOOSTER_TOKEN_LENGTH[state]


def booster_string_parser(
    beacon_code: str,
    start_state: _BoosterCodeState = _BoosterCodeState.BoosterID,
    sep: str = ":",
):
    state = start_state
    token = ""
    curr_val = 0

    last_idx = -1
    last_yield = -1
    for n, c in enumerate(beacon_code):
        if state != _BoosterCodeState.BoosterID and c != sep:
            try:
                curr_val = curr_val * 16 + int(c, 16)
            except ValueError:
                yield curr_val, _BoosterCodeState.ERROR, last_idx
                return
        elif c != sep:
            if ord(c) < ord("A") or ord("Z") < ord(c):
                yield token, _BoosterCodeState.ERROR, last_idx
                return

        last_idx = n

        if c != sep:
            token += c

        if c == sep and state == _BoosterCodeState.BoosterID:
            yield token, state, last_idx
            token = ""
            state = state.next()
            last_yield = last_idx
        elif c == sep and token and not _check_token_length(state, token):
            yield curr_val, _BoosterCodeState.ERROR, last_yield
            return
        elif state != _BoosterCodeState.BoosterID and _check_token_length(state, token):
            yield curr_val, state, last_idx
            last_yield = last_idx
            token = ""
            curr_val = 0
            if state == _BoosterCodeState.star_system:
                return
            state = state.next()
            continue

    if state < _BoosterCodeState.DONE:
        if state != _BoosterCodeState.BoosterID:
            if not _check_token_length(state, token):
                yield curr_val, _BoosterCodeState.INCOMPLETE, last_idx
                return
            yield curr_val, state, last_idx
        else:
            yield token, state, last_idx


def portal_string_parser(portal_code: str):
    state = _PortalCodeState.planet
    curr_val = 0
    token = ""
    token_length = _PORTAL_TOKEN_LENGHT[state]

    last_idx = -1
    for n, c in enumerate(portal_code):
        try:
            v = int(c, 16)
            last_idx = n
            curr_val = curr_val * 16 + v
            token += c
            if len(token) == token_length:
                yield curr_val, state, last_idx

                if state == _PortalCodeState.x:
                    return

                curr_val = 0
                token = ""
                state = state.next()
                token_length = _PORTAL_TOKEN_LENGHT[state]
        except ValueError:
            yield curr_val, _PortalCodeState.ERROR, last_idx
            return
    if token:
        yield curr_val, _PortalCodeState.INCOMPLETE, last_idx
