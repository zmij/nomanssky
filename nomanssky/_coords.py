from enum import IntEnum

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

    def next(self) -> "_BoosterCodeState":
        return _BoosterCodeState(self.value + 1)


class _PortalCodeState(IntEnum):
    planet = 0
    star_system = 1
    y = 2
    z = 3
    x = 4

    def next(self) -> "_PortalCodeState":
        return _PortalCodeState(self.value + 1)


class _CodeState(IntEnum):
    Empty = 0
    Incomplete = 1
    Complete = 2
    Invalid = 3


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
    ) -> None:
        self.planet = planet
        self.star_system = star_system
        self.y = y
        self.x = x
        self.z = z
        if code:
            if sep != ":" or code.find(sep) >= 0:
                # Try parse booster string
                _, booster_state = GalacticCoords.from_booster_code(
                    code, raise_if_invalid=False, coords=self, sep=sep
                )
                if booster_state == _CodeState.Complete:
                    return
                # Retry parsing without booster id
                GalacticCoords.from_booster_code(
                    code,
                    start_state=_BoosterCodeState.x,
                    coords=self,
                    sep=sep,
                    parse_entity="galatic coords",
                    complete_after=_BoosterCodeState.z,
                )
            else:
                GalacticCoords.from_portal_code(code, coords=self)

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
                    (self.y, "02x"),
                    (self.z, "03x"),
                    (self.x, "03x"),
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
                    (_xz_to_booster(self.x), "04X"),
                    (_y_to_booster(self.y), "04X"),
                    (_xz_to_booster(self.z), "04X"),
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
                    _xz_to_booster(self.x),
                    _y_to_booster(self.y),
                    _xz_to_booster(self.z),
                ]
            ]
        )

    @classmethod
    def from_booster_code(
        cls,
        code: str,
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
            coords = GalacticCoords()
        for v, s in parser:
            if s == _BoosterCodeState.BoosterID:
                # Ignore the scanner id
                continue

            if s >= _BoosterCodeState.DONE:
                state = _CodeState.Invalid
                break

            if not _check_token_length(s, v):
                cls.try_log_error(f"Invalid token length for {s}: {v}")
                state = _CodeState.Invalid
                break

            if s >= complete_after:
                state = _CodeState.Complete
            else:
                state = _CodeState.Incomplete

            try:
                int_val = int(v, 16)
                setattr(coords, s.name, _value_from_booster(s, int_val))
            except Exception as e:
                state = _CodeState.Invalid
                cls.try_log_error(f"{e}")
                break
        if raise_if_invalid:
            if state != _CodeState.Complete:
                raise ValueError(
                    f"`{code}` is an {state.name.lower()} value for {parse_entity}"
                )
            return coords
        return coords, state

    @classmethod
    def from_portal_code(
        cls,
        code: str,
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
            coords = GalacticCoords()
        for v, s in parser:
            if s == _PortalCodeState.x:
                state = _CodeState.Complete
            else:
                state = _CodeState.Incomplete

            try:
                int_val = int(v, 16)
                setattr(coords, s.name, int_val)
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
        return coords, state

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
    return len(token) == _BOOSTER_TOKEN_LENGTH[state]


def _y_from_booster(value: int) -> int:
    # TODO check range
    if value < 0x7F:
        return 0x81 + value
    return value - 0x7F


def _y_to_booster(value: int) -> int:
    if value > 0x80:
        return value - 0x81
    return value + 0x7F


def _xz_from_booster(value: int) -> int:
    # TODO check range
    if value < 0x7FF:
        return 0x801 + value
    return value - 0x7FF


def _xz_to_booster(value: int) -> int:
    if value > 0x800:
        return value - 0x801
    return value + 0x7FF


def _value_from_booster(s: _BoosterCodeState, v: int) -> int:
    if s == _BoosterCodeState.y:
        return _y_from_booster(v)
    if s == _BoosterCodeState.x:
        return _xz_from_booster(v)
    if s == _BoosterCodeState.z:
        return _xz_from_booster(v)
    return v


def _value_to_booster(f: str, v: int) -> int:
    if f == "y":
        return _y_to_booster(v)
    if f == "x":
        return _xz_to_booster(v)
    if f == "z":
        return _xz_to_booster(v)
    return v


def booster_string_parser(
    beacon_code: str,
    start_state: _BoosterCodeState = _BoosterCodeState.BoosterID,
    sep: str = ":",
):
    state = start_state
    curr_val = ""

    for c in beacon_code:
        if c == sep:
            yield curr_val, state
            curr_val = ""
            state = state.next()
            continue
        if state == _BoosterCodeState.planet:
            yield c, state
            curr_val = ""
            state = state.next()
            continue
        curr_val += c

    yield curr_val, state


def portal_string_parser(portal_code: str):
    state = _PortalCodeState.planet
    curr_val = ""
    token_length = _PORTAL_TOKEN_LENGHT[state]

    for c in portal_code:
        curr_val += c
        if len(curr_val) == token_length:
            yield curr_val, state

            if state == _PortalCodeState.x:
                return

            curr_val = ""
            state = state.next()
            token_length = _PORTAL_TOKEN_LENGHT[state]
