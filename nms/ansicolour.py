# -*- coding: utf-8 -*-
"""
TODO Move the library to a separate package
"""

import re

from enum import Enum
from typing import Any, Tuple, List, Set, Dict

_ESC = "\u001b["


def _has_iter(o: Any) -> bool:
    return hasattr(o, "__iter__")


def _to_iterable(o: Any) -> List[Any]:
    if isinstance(o, str) or not _has_iter(o):
        return [o]
    return o


def _flatten(*args) -> List[Any]:
    return [e for a in args if a is not None for e in _to_iterable(a) if e is not None]


def make_escape_code(*codes, _escape: str = _ESC) -> str:
    codes = _flatten(*codes)
    return f"{_escape}{';'.join([str(c) for c in codes])}m"


class ValueOrEnum(Enum):
    @classmethod
    def names(cls) -> List[str]:
        return cls.__members__.keys()

    @classmethod
    def value_or(cls, value: str, default_value: Any = None) -> Any:
        key = value.upper().replace(" ", "_")
        if key in cls.names():
            return cls[key]
        return default_value


def _is_colour(o: object, colour_class: type = None) -> bool:
    if colour_class is not None and colour_class not in _COLOUR_CLASSES:
        return isinstance(o, tuple(_COLOUR_CLASSES | {colour_class}))
    return isinstance(o, tuple(_COLOUR_CLASSES))


class Position(ValueOrEnum):
    FG = 3
    BG = 4

    def __neg__(self) -> "Position":
        if self == Position.FG:
            return Position.BG
        return Position.FG

    def __add__(self, other) -> "Formatter":
        if other is None:
            return self
        if _is_colour(other):
            return Formatter(colour=other, position=self, colour_class=other.__class__)
        elif isinstance(other, Options):
            return Formatter(options=other, position=self)
        else:
            arg = _deduce_arg(other)
            if arg is not None:
                return self.__add__(arg)
        raise NotImplementedError(
            f"Adding a {other.__class__.__name__} to a {self.__class__.__name__} is not implemented, probably on purpose"
        )


class Options(ValueOrEnum):
    CLEAR = 0
    BRIGHT = 1
    DIM = 2
    EM = 3  # In docs it's underline, but different terminals handle it differently
    REV = 7  # In docs it's reverse

    def __lt__(self, other) -> bool:
        if isinstance(other, Options):
            return self.value < other.value
        raise TypeError(
            f"'<' is not supported between instances of '{self.__class__}' and '{other.__class__}'"
        )

    def __str__(self) -> str:
        return str(self.value)

    def __add__(self, other) -> "Formatter":
        if other is None:
            return self
        if _is_colour(other):
            return Formatter(colour=other, options=self, colour_class=other.__class__)
        elif isinstance(other, Position):
            return Formatter(options=self, position=other)
        elif isinstance(other, Options):
            return Formatter(options={self, other})
        elif isinstance(other, Formatter):
            # RHS of + is already a formatter, probably constructed by parenthesis,
            # so suppose we want an 'opposite' formatter with self
            return Formatter(options=self, position=-other.position) + other
        else:
            arg = _deduce_arg(other)
            if arg is not None:
                return self.__add__(arg)
        raise NotImplementedError(
            f"Adding a {other.__class__.__name__} to an {self.__class__.__name__} is not implemented, probably on purpose"
        )


CLEAR = make_escape_code(Options.CLEAR)
RESET_COLOURS = make_escape_code(39, 49)


class Colour(ValueOrEnum):
    """
    Colours representing SGR 3 and 4-bit colours
    https://en.wikipedia.org/wiki/ANSI_escape_code#3-bit_and_4-bit
    """

    NONE = None
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    GRAY = 60
    BRIGHT_RED = 61
    BRIGHT_GREEN = 62
    BRIGHT_YELLOW = 63
    BRIGHT_BLUE = 64
    BRIGHT_MAGENTA = 65
    BRIGHT_CYAN = 66
    BRIGHT_WHITE = 67

    def code(
        self,
        *,
        options: Options | Set[Options] = None,
        position: Position = Position.FG,
        _escape: str = _ESC,
    ) -> str:
        if self.value is None:
            return make_escape_code(options, _escape=_escape)
        return make_escape_code(*self.codes(options, position), _escape=_escape)

    def codes(
        self,
        options: Options | Set[Options] = None,
        position: Position = Position.FG,
    ) -> Tuple[int, int]:
        return (options, *self.colour_value(position))

    def colour_value(self, position: Position = Position.FG) -> Tuple[int]:
        if self.value is None:
            return None
        return (position.value * 10 + self.value,)

    def with_background(
        self,
        background: Any,
        options: Options | Set[Options] = None,
        _escape: str = _ESC,
    ) -> str:
        """
        Return a code with self as foreground color and apparently backgroud as background
        """
        return make_escape_code(
            options,
            *self.colour_value(Position.FG),
            *background.colour_value(Position.BG),
            _escape=_escape,
        )

    def __str__(self) -> str:
        return self.code()

    def __add__(self, other) -> "Formatter":
        if other is None:
            return self
        elif isinstance(other, Options):
            return Formatter(colour=self, options=other, colour_class=self.__class__)
        elif isinstance(other, Position):
            return Formatter(colour=self, position=other, colour_class=self.__class__)
        elif isinstance(other, Formatter):
            # RHS of + is already a formatter, probably constructed by parenthesis,
            # so suppose we want an 'opposite' formatter with self
            return Formatter(colour=self, position=-other.position) + other
        else:
            arg = _deduce_arg(other)
            if arg is not None:
                return self.__add__(arg)
        raise NotImplementedError(
            f"Adding a {other.__class__.__name__} to an {self.__class__.__name__} is not implemented, probably on purpose"
        )


class BaseColour:
    def code(
        self,
        *,
        options: Options | Set[Options] = None,
        position: Position = Position.FG,
        _escape: str = _ESC,
    ) -> str:
        if self.value is None:
            return make_escape_code(options, _escape=_escape)
        return make_escape_code(*self.codes(options, position), _escape=_escape)

    def codes(
        self,
        options: Options | Set[Options] = None,
        position: Position = Position.FG,
    ) -> List[Any]:
        return [options, *self.colour_value(position)]

    def with_background(
        self,
        background: Any,
        options: Options | Set[Options] = None,
        _escape: str = _ESC,
    ) -> str:
        """
        Return a code with self as foreground color and apparently backgroud as background
        """
        return make_escape_code(
            options,
            *self.colour_value(Position.FG),
            *background.colour_value(Position.BG),
            _escape=_escape,
        )

    def colour_value(self, position: Position = Position.FG) -> List[int]:
        return []

    def __str__(self) -> str:
        return self.code()

    def __add__(self, other) -> "Formatter":
        if other is None:
            return self
        elif isinstance(other, Options):
            return Formatter(colour=self, options=other, colour_class=self.__class__)
        elif isinstance(other, Position):
            return Formatter(colour=self, position=other, colour_class=self.__class__)
        elif isinstance(other, Formatter):
            # RHS of + is already a formatter, probably constructed by parenthesis,
            # so suppose we want an 'opposite' formatter with self
            return Formatter(colour=self, position=-other.position) + other
        else:
            arg = _deduce_arg(other)
            if arg is not None:
                return self.__add__(arg)
        raise NotImplementedError(
            f"Adding a {other.__class__.__name__} to an {self.__class__.__name__} is not implemented, probably on purpose"
        )


class ValueOrClass:
    @classmethod
    def names(cls) -> List[str]:
        if not hasattr(cls, "__members__"):
            return []
        return cls.__members__.keys()

    @classmethod
    def value_or(cls, value: str, default_value: Any = None) -> Any:
        key = str(value).upper().replace(" ", "_")
        if key in cls.names():
            return cls.__members__[key]
        return default_value


def _add_constant(cls, name: str, *args, **kwargs) -> None:
    value = cls(*args, **kwargs)
    setattr(value, "name", name)
    setattr(cls, name, value)
    if not hasattr(cls, "__members__"):
        setattr(cls, "__members__", {})
    getattr(cls, "__members__")[name] = value


class Colour8Bit(BaseColour, ValueOrClass):
    """
    Colours representing SGR 8-bit colours
    https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
    """

    # TODO Make an enum-like metaclass that allows arbitrary values
    PREDEFINED = {
        "NONE": None,
        "BLACK": 0,
        "RED": 1,
        "GREEN": 2,
        "YELLOW": 3,
        "BLUE": 4,
        "MAGENTA": 5,
        "TEAL": 6,
        "LIGHT_GRAY": 7,
        "DARK_GRAY": 8,
        "BRIGHT_RED": 9,
        "BRIGHT_GREEN": 10,
        "BRIGHT_YELLOW": 11,
        "BRIGHT_BLUE": 12,
        "BRIGHT_MAGENTA": 13,
        "CYAN": 14,
        "WHITE": 15,
    }
    _MAGIC = 5

    def __init__(self, value: int) -> None:
        super().__init__()
        self.name_ = f"{value}"
        self.value_ = value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name_}: {self.value_}>"

    @property
    def value(self) -> int:
        return self.value_

    @property
    def name(self) -> str:
        return self.name_

    @name.setter
    def name(self, v: str) -> None:
        self.name_ = v

    def colour_value(
        self, position: Position = Position.FG
    ) -> Tuple[int, int, int, int]:
        return position.value * 10 + 8, Colour8Bit._MAGIC, self.value

    @classmethod
    def value_or(cls, value: Any, default_value: Any = None) -> Any:
        v = super().value_or(value, None)
        if v is not None:
            return v
        if isinstance(value, int) and 0 <= value and value <= 255:
            return Colour8Bit(value)
        return default_value


for k, v in Colour8Bit.PREDEFINED.items():
    _add_constant(Colour8Bit, k, v)

HEX_Colour_RE = re.compile("#([0-9a-fA-F]{2,2})([0-9a-fA-F]{2,2})([0-9a-fA-F]{2,2})")


def is_hex_colour(value: str) -> Tuple[bool, int, int, int]:
    m = HEX_Colour_RE.match(value)
    if m:
        return (
            True,
            int(m.group(1), base=16),
            int(m.group(2), base=16),
            int(m.group(3), base=16),
        )
    return False, None, None, None


class Colour24Bit(BaseColour, ValueOrClass):
    """
    Colours representing SGR 24-bit colours
    https://en.wikipedia.org/wiki/ANSI_escape_code#24-bit
    """

    # TODO Make an enum-like metaclass that allows arbitrary values
    PREDEFINED = {
        "NONE": None,
        "BLACK": (0, 0, 0),
        "RED": (0x80, 0, 0),
        "GREEN": (0, 0x80, 0),
        "YELLOW": (0x80, 0x80, 0),
        "BLUE": (0, 0, 0x80),
        "MAGENTA": (0x80, 0, 0x80),
        "TEAL": (0, 0x80, 0x80),
        "LIGHT_GRAY": (0xC0, 0xC0, 0xC0),
        "DARK_GRAY": (0x80, 0x80, 0x80),
        "BRIGHT_RED": (0xFF, 0, 0),
        "BRIGHT_GREEN": (0, 0xFF, 0),
        "BRIGHT_YELLOW": (0xFF, 0xFF, 0),
        "BRIGHT_BLUE": (0, 0, 0xFF),
        "BRIGHT_MAGENTA": (0xFF, 0, 0xFF),
        "CYAN": (0, 0xFF, 0xFF),
        "WHITE": (0xFF, 0xFF, 0xFF),
    }
    _MAGIC = 2

    def __init__(
        self,
        value: Tuple[int, int, int] = None,
        *,
        value_str: str = None,
        r: int = None,
        g: int = None,
        b: int = None,
    ) -> None:
        super().__init__()
        self._r = r
        self._g = g
        self._b = b
        if value:
            if isinstance(value, tuple) and len(value) == 3:
                self.name_ = f"{value}"
                self._r = self._check_component(value[0])
                self._g = self._check_component(value[1])
                self._b = self._check_component(value[2])
            else:
                # TODO raise a value error
                raise ValueError("Value for 24-bit colour must be a three int tuple")
        elif value_str:
            is_hex, r, g, b = is_hex_colour(value_str)
            if not is_hex:
                raise ValueError("Invalid colour string {value}")
            self._r = r
            self._g = g
            self._b = b
        self.name_ = self.value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}.{self.name_}: {self._r:02x} {self._g:02x} {self._b:02x}>"

    def _check_component(self, value: Any) -> int:
        if not isinstance(value, int) or value < 0 or 255 < value:
            raise ValueError("Colour component must be an int in the range [0, 255]")
        return value

    @property
    def value(self) -> str:
        if self._r is None:
            return "None"
        return f"#{self._r:02x}{self._g:02x}{self._b:02x}"

    @property
    def r(self) -> int:
        return self._r

    @property
    def g(self) -> int:
        return self._g

    @property
    def g(self) -> int:
        return self._b

    @property
    def name(self) -> str:
        return self.name_

    @name.setter
    def name(self, v: str) -> None:
        self.name_ = v

    # def codes(
    #     self,
    #     options: Options | Set[Options] = None,
    #     position: Position = Position.FG,
    # ) -> Tuple[Set[Options] | Options, int, int, int, int]:
    #     return (options, position.value * 10 + 8, 2, self._r, self._g, self._b)

    def colour_value(
        self, position: Position = Position.FG
    ) -> Tuple[int, int, int, int]:
        return (position.value * 10 + 8, Colour24Bit._MAGIC, self._r, self._g, self._b)


for k, v in Colour24Bit.PREDEFINED.items():
    _add_constant(Colour24Bit, k, v)

_COLOUR_CLASSES = {Colour, Colour8Bit, Colour24Bit}


class Formatter:
    colour: Colour
    position: Position
    options: Options

    def __init__(
        self,
        *,
        colour: Colour = Colour.NONE,
        position: Position = Position.FG,
        options: Options | Set[Options] = None,
        colour_class: type = Colour,
    ) -> None:
        self.colour = colour or colour_class.NONE
        self.position = position
        if options is not None:
            if not isinstance(options, Options) and not isinstance(options, set):
                raise ValueError(f"`Options` instance or a set of `Options` expected")
        self.options = options
        self._colour_class = colour_class

    def code(self, *, _escape: str = _ESC):
        if not self.options and (
            self.colour is None or self.colour == self._colour_class.NONE
        ):
            return ""
        options = self.options
        if isinstance(options, set):
            options = sorted(list(options))
        return self.colour.code(
            options=self.options, position=self.position, _escape=_escape
        )

    def __call__(self, text: str, clear: bool = True) -> str:
        res = self.code() + text
        if clear:
            res += CLEAR
        return res

    def __str__(self) -> str:
        return self.code()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.colour!r} {self.position!r} {self.options!r}>"

    def __add__(self, other: Any) -> "Formatter":
        if other is None:
            return self
        if _is_colour(other, colour_class=self._colour_class):
            return Formatter(
                colour=other,
                position=self.position,
                options=self.options,
                colour_class=other.__class__,
            )
        elif isinstance(other, Position):
            return Formatter(
                colour=self.colour,
                position=other,
                options=self.options,
                colour_class=self._colour_class,
            )
        elif isinstance(other, Options):
            if isinstance(self.options, Options):
                return Formatter(
                    colour=self.colour,
                    position=self.position,
                    options={self.options, other},
                    colour_class=self._colour_class,
                )
            elif isinstance(self.options, set):
                return Formatter(
                    colour=self.colour,
                    position=self.position,
                    options=self.options | {other},
                    colour_class=self._colour_class,
                )
            else:
                raise RuntimeError(f"Unexpected options type {type(self.options)}")
        elif isinstance(other, Formatter):
            if self.position == other.position:
                raise ValueError(f"Cannot sum options in the same position")
            hl = Highlighter()
            if self.position == Position.FG:
                hl.fg = self
                hl.bg = other
            else:
                hl.fg = other
                hl.bg = self
            return hl
        else:
            arg = _deduce_arg(other)
            if arg is not None:
                return self.__add__(arg)
        raise NotImplementedError(
            f"Adding a {other.__class__.__name__} to a {self.__class__.__name__} is not implemented, probably on purpose"
        )


def _deduce_arg(arg: Any, colour_cls: type = Colour) -> Any:
    if isinstance(arg, str):
        is_hex, r, g, b = is_hex_colour(arg)
        if is_hex:
            return Colour24Bit(r=r, g=g, b=b)
        else:
            for t in [colour_cls, Options, Position]:
                v = t.value_or(arg)
                if v is not None:
                    return v
            return None
    else:
        v = colour_cls.value_or(arg)
        return v


def _args_parser(*args, colour_class=Colour):
    for a in args:
        if isinstance(a, (Options, Position)) or _is_colour(
            a, colour_class=colour_class
        ):
            yield a
            continue
        v = _deduce_arg(a, colour_cls=colour_class)
        if v is not None:
            yield v
            continue
    return


def _parse_args(
    args: Tuple[Any], position: Position = None, colour_class=Colour
) -> Formatter:
    options = None
    colour = None

    parser = _args_parser(*_to_iterable(args), colour_class=colour_class)
    for arg in parser:
        if _is_colour(arg, colour_class=colour_class):
            colour = arg
        elif isinstance(arg, Options):
            if options is None:
                options = arg
            elif isinstance(options, set):
                options.add(arg)
            else:
                options = {options, arg}
        elif isinstance(arg, Position):
            if position is None:
                position = arg

    return Formatter(colour=colour, position=position, options=options)


class Highlighter:
    def __init__(
        self,
        fg: Tuple[Any] = None,
        bg: Tuple[str] = None,
        colour_class=Colour,
    ):
        self.fg = (
            fg
            and _parse_args(fg, position=Position.FG, colour_class=colour_class)
            or None
        )
        self.bg = (
            bg
            and _parse_args(bg, position=Position.BG, colour_class=colour_class)
            or None
        )

    def __call__(self, text: str, _escape=_ESC) -> str:
        if self.fg and self.bg:
            # TODO merge options
            return (
                self.fg.colour.with_background(
                    self.bg.colour, self.fg.options, _escape=_escape
                )
                + text
                + CLEAR
            )
        elif self.fg:
            return self.fg(text)
        elif self.bg:
            return self.bg(text)
        return text

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} FG={self.fg!r} BG={self.bg!r}>"


def highlight(
    text: str,
    fg: Tuple[Any] = None,
    bg: Tuple[str] = None,
    *,
    cls=Colour,
    _escape: str = _ESC,
) -> str:
    hl = Highlighter(fg=fg, bg=bg, colour_class=cls)
    return hl(text, _escape=_escape)


def highlight_8bit(
    text: str,
    fg: Tuple[Any] = None,
    bg: Tuple[str] = None,
    *,
    _escape: str = _ESC,
) -> str:
    return highlight(text, fg=fg, bg=bg, cls=Colour8Bit, _escape=_escape)


if __name__ == "__main__":
    hl = highlight
    # for c in range(1, 255):
    #     print(
    #         highlight_8bit("normal", fg=c),
    #         highlight_8bit("bright", fg=(c, "bright")),
    #         highlight_8bit("dim", fg=(c, "dim")),
    #     )
    # print(higlight("text", fg="#ff00ab", bg="#003b83"))
    print(hl(" 4-bit: Expect red on blue :P", fg="red", bg="blue"))
    print(hl(" 8-bit: Expect red on blue :P", fg=Colour8Bit.RED, bg=Colour8Bit.BLUE))
    print(hl("24-bit: Expect red on blue :P", fg=Colour8Bit.RED, bg=Colour24Bit.BLUE))
    print(highlight("this is a test", fg="dim"))
    for v in [
        Colour.BLUE + Options.EM,
        Position.FG + "bright",
        Options.BRIGHT + Options.EM,
        (Colour.BLUE) + (Colour.RED + "bg"),
    ]:
        print(f"{v!r}")
    print(f"{Colour.BLUE + 'em' + 'bright'}this is an f-string{CLEAR}")
    print(highlight("this is highlight call", fg=("blue", "em", "bright")))
