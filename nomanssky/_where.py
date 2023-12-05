import types
from typing import Tuple, List, Any

"""

What I want to achieve:

T.load(conn, like(name="%foo%") & eq(title="bar") | "field" in (this, that))

"""


def _is_iterable(o: object) -> bool:
    if not isinstance(o, str) and hasattr(o, "__iter__"):
        return True
    return False


class Value:
    def __init__(self, value: Any) -> None:
        self._value = value

    def __eq__(self, __value: object) -> bool:
        if __value is None:
            return self._value is None
        if isinstance(__value, Value):
            return self._value == __value._value
        return self._value == __value

    def __len__(self) -> int:
        if _is_iterable(self._value):
            return len(self._value)
        return 1

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} value = {self._value!r} >"

    @property
    def is_none(self) -> bool:
        return self._value is None

    @property
    def param(self) -> Tuple[Any, ...]:
        if _is_iterable(self._value):
            return tuple(self._value)
        return (self._value,)


class Field:
    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._name}>"

    def __format__(self, __format_spec: str) -> str:
        if __format_spec == "q":
            """Quoted identifier"""
            return f'"{self._name}"'
        return self.__str__()

    def __eq__(self, __value: object) -> "Eq":
        return Eq(_field=self, _value=__value)

    def __ne__(self, __value: object) -> "Ne":
        return Ne(_field=self, _value=__value)

    def __lt__(self, __value: object) -> "Lt":
        return Lt(_field=self, _value=__value)

    def __le__(self, __value: object) -> "Le":
        return Le(_field=self, _value=__value)

    def __gt__(self, __value: object) -> "Gt":
        return Gt(_field=self, _value=__value)

    def __ge__(self, __value: object) -> "Ge":
        return Ge(_field=self, _value=__value)

    def __and__(self, __value: object) -> "In":
        return In(_field=self, _value=__value)

    def like(self, value: Any) -> "Like":
        return Like(_field=self, _value=value)

    @property
    def name(self) -> str:
        return self._name


class Expression:
    ...

    def __len__(self) -> int:
        return 0

    @property
    def expression(self) -> str:
        return ""

    @property
    def params(self) -> Tuple[Any, ...]:
        return ()

    def __invert__(self) -> "Expression":
        return Not(self)

    def __and__(self, __other: "Expression") -> "And":
        if isinstance(__other, Expression):
            return And(self, __other)
        raise NotImplementedError(
            f"{self.__class__.__name__} cannot be `anded` with {__other.__class__name}"
        )

    def __or__(self, __other: Any) -> "Or":
        if isinstance(__other, Expression):
            return Or(self, __other)
        raise NotImplementedError(
            f"{self.__class__.__name__} cannot be `anded` with {__other.__class__name}"
        )

    def __str__(self) -> str:
        return self.expression


class Comparison(Expression):
    _SQL_OP = ""
    _ALLOW_NULLS = False
    """
    Base comparison operator

    TODO Table aliases
    """

    def __init__(self, _field: Field = None, _value: Value = None, **kwargs) -> None:
        super().__init__()
        if _field is not None:
            self._check_null_value(_value)
            if isinstance(_field, Field):
                self._field = _field
            else:
                self._field = Field(_field)
            if isinstance(_value, Value):
                self._value = _value
            else:
                self._value = Value(_value)
        else:
            args = [(k, v) for k, v in kwargs.items()]
            if len(args) != 1:
                raise ValueError(
                    f"{self.__class__.__name__} requires exactly one named parameter"
                )
            field, val = (x for x in args[0])
            self._check_null_value(val)
            self._field = Field(field)
            if isinstance(val, Value):
                self._value = val
            else:
                self._value = Value(val)

    def _check_null_value(self, value) -> None:
        if value is None:
            if not self.__class__._ALLOW_NULLS:
                raise ValueError(
                    f"{self.__class__.__name__} doesn't allow null comparison"
                )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._field:q} `{self._value}`>"

    def __invert__(self) -> Expression:
        if self.__class__ in _OP_INVERSIONS:
            return _OP_INVERSIONS[self.__class__](
                _field=self._field, _value=self._value
            )
        return super().__invert__()

    @property
    def expression(self) -> str:
        return self.__class__._SQL_OP.format(self._field)

    @property
    def field(self) -> Field:
        return self._field

    @property
    def value(self) -> Value:
        return self._value

    @property
    def params(self) -> Tuple[Any, ...]:
        return self._value.param


class NullComparison(Comparison):
    _NULL_OP = ""
    _ALLOW_NULLS = True

    @property
    def expression(self) -> str:
        if self._value.is_none:
            return self.__class__._NULL_OP.format(self.field)
        return super().expression

    @property
    def params(self) -> Tuple[Any, ...]:
        if self._value.is_none:
            return ()
        return super().params


class Eq(NullComparison):
    """
    Construct a `fields = something` expression.

    e.g. Eq(name="foo")
    Constructor expects a single named parameter, that name is used as a field name
    """

    _SQL_OP = "{} = ?"
    _NULL_OP = "{} is null"


class Ne(NullComparison):
    _SQL_OP = "{} != ?"
    _NULL_OP = "{} is not null"


class Lt(Comparison):
    _SQL_OP = "{} < ?"


class Le(Comparison):
    _SQL_OP = "{} <= ?"


class Gt(Comparison):
    _SQL_OP = "{} > ?"


class Ge(Comparison):
    _SQL_OP = "{} >= ?"


class Like(Comparison):
    _SQL_OP = "{} like (?)"


class NotLike(Comparison):
    _SQL_OP = "{} not like (?)"


class In(Comparison):
    @property
    def expression(self) -> str:
        return f"{self.field} in ({', '.join(['?'] * len(self._value))})"


class NotIn(Comparison):
    @property
    def expression(self) -> str:
        return f"{self.field} not in ({', '.join(['?'] * len(self._value))})"


class CompoundExpression(Expression):
    _SQL_OP = "--not an op--"

    def __init__(self, *expressions: tuple[Expression, ...]) -> None:
        # TODO check arg types and raise
        super().__init__()
        self._sub_expressions = [x for x in expressions if isinstance(x, Expression)]

    @property
    def expression(self) -> str:
        return self.__class__._SQL_OP.join(
            [f"({e.expression})" for e in self._sub_expressions]
        )

    @property
    def params(self) -> Tuple[Any, ...]:
        return tuple(x for e in self._sub_expressions for x in e.params)


class Not(Expression):
    def __init__(self, expression: Expression) -> None:
        super().__init__()
        self._expression = expression

    def __invert__(self) -> Expression:
        return self._expression

    @property
    def expression(self) -> str:
        return f"not ({self._expression.expression})"

    @property
    def params(self) -> Tuple[Any, ...]:
        return self._expression.params


class And(CompoundExpression):
    _SQL_OP = " and "

    def __and__(self, __other: Expression) -> "And":
        return And(*self._sub_expressions, __other)


class Or(CompoundExpression):
    _SQL_OP = " or "

    def __or__(self, __other: Expression) -> "Or":
        return Or(*self._sub_expressions, __other)


_OP_INVERSIONS = {
    Eq: Ne,
    Ne: Eq,
    Lt: Ge,
    Le: Gt,
    Gt: Le,
    Ge: Lt,
    Like: NotLike,
    NotLike: Like,
    In: NotIn,
    NotIn: In,
}


def build_expression(
    *args: tuple[Expression, ...], __op=And, __kwarg_op=Eq, **kwargs
) -> Expression:
    kwarg_expressions = tuple(__kwarg_op(_field=k, _value=v) for k, v in kwargs.items())
    if not kwarg_expressions and len(args) == 1:
        return args[0]
    return __op(*args, *kwarg_expressions)


if __name__ == "__main__":
    # exp = build_expression(Like("name", "%bar%"), name="foo", value=42)
    # print(exp, exp.params)
    exp = build_expression(Like("name", "%bar%"))
    print(exp, exp.params)
