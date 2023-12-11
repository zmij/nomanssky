from enum import IntEnum, auto
from typing import Any, Callable
from collections import deque


class TokeniserState(IntEnum):
    PctString = auto()
    WhiteSpace = auto()
    Literal = auto()
    Punctuation = auto()
    Brackets = auto()  # Brackets or parenthesis
    Number = auto()
    SingleQuote = auto()
    DoubleQuote = auto()


_BRACKETS = "(){}[]<>"
_WHITE_SPACE = " \t\n\r"
_NUMBERS = "012345678"
_PUNCT = "=-+,.;:_"
_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">"}


def _want_state(c: str, __esc="%"):
    if c == __esc:
        return TokeniserState.PctString
    if c in _BRACKETS:
        return TokeniserState.Brackets
    if c in _PUNCT:
        return TokeniserState.Punctuation
    if c in _WHITE_SPACE:
        return TokeniserState.WhiteSpace
    if c in _NUMBERS:
        return TokeniserState.Number
    if c == "'":
        return TokeniserState.SingleQuote
    if c == '"':
        return TokeniserState.DoubleQuote
    return TokeniserState.Literal


class TokenAction(IntEnum):
    # Append current char to current token, retain current_state
    Append = 0
    # Yield current token and start a new token with current char
    YieldAndNewToken = 1
    # Yield current token and start a new empty token with default state
    YieldAndNewEmpty = 2
    # Discart current char and continue
    DiscardAndContinue = 3


"""
WhiteSpace + WhiteSpace = WhiteSpace
Literal + Literal = Literal
Literal + WhiteSpace = Literal, WhiteSpace
WhiteSpace + Literal = Literal, WhiteSpace
Literal + Number = Literal
Number + Literal = Number, Literal


PctString + Literal = PctString
PctString + Number = PctString
PctString + other = PctString, new token
"""


def _state_transition(
    current_state: TokeniserState, current_token: str, new_state: TokeniserState
) -> tuple[TokenAction, TokeniserState]:
    if new_state == TokeniserState.PctString:
        if current_state == TokeniserState.PctString and len(current_token) == 1:
            return TokenAction.DiscardAndContinue, TokeniserState.Literal
    elif current_state == new_state:
        return TokenAction.Append, current_state
    elif current_state == TokeniserState.PctString:
        if new_state in [TokeniserState.Literal, TokeniserState.Number]:
            return TokenAction.Append, current_state
    elif new_state == TokeniserState.Literal and current_state in [
        TokeniserState.PctString,
        TokeniserState.Literal,
    ]:
        return TokenAction.Append, current_state
    elif new_state == TokeniserState.Number and current_state in [
        TokeniserState.Literal,
        TokeniserState.Number,
    ]:
        return TokenAction.Append, current_state
    return TokenAction.YieldAndNewToken, new_state


def format_spec_tokeniser(__format_spec: str):
    """
    Simple format tokeniser, detects pct-prefixed tokens and the rest )
    """
    current_token = ""
    current_state = TokeniserState.Literal
    for c in __format_spec:
        new_state = _want_state(c)
        action, new_state = _state_transition(current_state, current_token, new_state)
        if action == TokenAction.Append:
            current_token += c
        elif action != TokenAction.DiscardAndContinue:
            if current_token:
                yield current_token, current_state

            if action == TokenAction.YieldAndNewToken:
                current_token = c
            elif action == TokenAction.YieldAndNewEmpty:
                current_token = ""
        current_state = new_state
    if current_token:
        yield current_token, current_state


class ExpressionParseState(IntEnum):
    Literal = auto()
    WaitOpenBracket = auto()
    CollectBracketContents = auto()
    SingeQuotedString = auto()
    DoubleQuotedString = auto()


class ExpressionToken(IntEnum):
    Literal = auto()
    QuotedString = auto()
    PctString = auto()
    PctArgs = auto()


class ExpressionParser:
    def __init__(self, __valid_open_brackets: str = "({{") -> None:
        self._state = self._literal
        self._in_quotes = None
        self._collected_token = ""
        self._valid_brackets = __valid_open_brackets
        self._bracket_level = 0
        self._collected_tokens = []

    def __call__(self, __format_spec: str) -> tuple[ExpressionToken, Any]:
        for token, state in format_spec_tokeniser(__format_spec):
            for expression_token, value in self._state(token, state):
                yield expression_token, value

    def _literal(
        self, token: str, state: TokeniserState
    ) -> tuple[ExpressionToken, Any]:
        if self._in_quotes:
            for et, ev in self._in_quotes(token, state):
                yield et, ev
            return
        if state == TokeniserState.PctString:
            if self._collected_token:
                yield ExpressionToken.Literal, self._collected_token
            yield ExpressionToken.PctString, token

            self._collected_token = ""
            self._state = self._wait_open_bracket
            return
        elif state in [TokeniserState.SingleQuote, TokeniserState.DoubleQuote]:
            if self._collected_token:
                yield ExpressionToken.Literal, self._collected_token

            self._collected_token = ""
            self._in_quotes = lambda t, s: self._quoted_string(token, t, s)
            return
        self._collected_token += token

    def _quoted_string(
        self, quote: str, token: str, state: TokeniserState
    ) -> tuple[ExpressionToken, Any]:
        if token == quote:
            yield ExpressionToken.QuotedString, self._collected_token
            self._collected_token = ""
            self._in_quotes = None
            return
        self._collected_token += token

    def _wait_open_bracket(
        self, token: str, state: TokeniserState
    ) -> tuple[ExpressionToken, Any]:
        if self._in_quotes:
            for et, ev in self._in_quotes(token, state):
                yield et, ev
            return
        if state == TokeniserState.Brackets:
            if token in self._valid_brackets:
                self._collected_token = ""
                self._bracket_level += 1
                matching_bracket = _BRACKET_PAIRS[token]
                self._state = lambda t, s: self._collect_args(matching_bracket, t, s)
                return
        for et, ev in self._literal(token, state):
            yield et, ev

    def _collect_args(
        self, bracket: str, token: str, state: TokeniserState
    ) -> tuple[ExpressionToken, Any]:
        if self._in_quotes:
            for et, ev in self._in_quotes(token, state):
                self._collected_tokens.append((et, ev))
            return
        if token == bracket:
            self._bracket_level -= 1
            if self._bracket_level == 0:
                yield ExpressionToken.PctArgs, self._collected_tokens
                self._collected_tokens = []
                self._state = self._literal
                return
        if state == TokeniserState.PctString:
            if self._collected_token:
                self._collected_tokens.append(
                    (ExpressionToken.Literal, self._collected_token)
                )
                self._collected_token = ""
            self._collected_tokens.append((ExpressionToken.PctString, token))
            return
        for et, ev in self._literal(token, state):
            self._collected_tokens.append((et, ev))


def format_expression_parser(__format_spec: str, __valid_open_brackets: str = "({{"):
    """
    Parses simple format expressions like %n %r(foobar).

    This is NOT a recursive parser, everything inside the brackets is returned in a list of (token, tokeniser_state)
    """
    parser = ExpressionParser(__valid_open_brackets)
    for state, token in parser(__format_spec):
        if state is not None:
            yield state, token


def format_attrib_action(
    attrib_name: str, transform: Callable[[Any], Any] = lambda s: str(s)
) -> Callable[[Any], str]:
    def action(__o: object) -> str:
        if hasattr(__o, attrib_name):
            return transform(getattr(__o, attrib_name))
        return None

    return action


def format_list_attrib_action(
    attrib_name: str, join_str: str, transform: Callable[[Any], Any] = lambda s: str(s)
) -> Callable[[Any], str]:
    def action(__o: object) -> str:
        if hasattr(__o, attrib_name):
            values = getattr(__o, attrib_name)
            if values is not None:
                return join_str.join([transform(x) for x in values])
        return None

    return action


def format_literal_action(literal: str) -> Callable[[Any], str]:
    def action(__o: object) -> str:
        return literal

    return action


if __name__ == "__main__":
    foo = [x for x in format_spec_tokeniser("%r(%n x%x) 1000 n123")]
    print(foo)
    # foo = [
    #     x
    #     for x in format_expression_parser(
    #         " asg '  o_O  ' asdfg %r(%n x%x) 1000 n123 %i(' + '%n x%q)"
    #     )
    # ]
    # print(foo)
    # foo = [x for x in format_expression_parser("%r('quoted'%n x%x)")]
    # print(foo)
    foo = [x for x in format_expression_parser("%r'quoted'('qu0ted arg'%n x%x)")]
    print(foo)
