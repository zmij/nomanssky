import pytest
from collections import namedtuple

from easysqlite._where import *


def test_base_expression():
    exp = Expression()

    assert len(exp) == 0
    assert exp.expression == ""
    assert exp.params == ()


NAME_FIELD = Field("name")
VALUE_FIELD = Field("value")
LIST_OF_INTS = Value([1, 2, 3, 4])

CmpTestData = namedtuple(
    "OpTestData", ["ctor", "cls", "field", "value", "expression", "params"]
)
TEST_CMP_EXPRESSIONS = [
    CmpTestData(Eq(name="foo"), Eq, "name", "foo", "name = ?", ("foo",)),
    CmpTestData(Eq(name=None), Eq, "name", None, "name is null", ()),
    CmpTestData(Ne(name="foo"), Ne, "name", "foo", "name != ?", ("foo",)),
    CmpTestData(Ne(name=None), Ne, "name", None, "name is not null", ()),
    CmpTestData(Lt(value=42), Lt, "value", 42, "value < ?", (42,)),
    CmpTestData(Le(value=42), Le, "value", 42, "value <= ?", (42,)),
    CmpTestData(Gt(value=42), Gt, "value", 42, "value > ?", (42,)),
    CmpTestData(Ge(value=42), Ge, "value", 42, "value >= ?", (42,)),
    CmpTestData(Like(name="foo"), Like, "name", "foo", "name like (?)", ("foo",)),
    # Expression construction with overloaded Field's methods
    CmpTestData(NAME_FIELD == "foo", Eq, "name", "foo", "name = ?", ("foo",)),
    CmpTestData(NAME_FIELD == None, Eq, "name", None, "name is null", ()),
    CmpTestData(NAME_FIELD != "foo", Ne, "name", "foo", "name != ?", ("foo",)),
    CmpTestData(NAME_FIELD != None, Ne, "name", None, "name is not null", ()),
    CmpTestData(VALUE_FIELD < 42, Lt, "value", 42, "value < ?", (42,)),
    CmpTestData(VALUE_FIELD <= 42, Le, "value", 42, "value <= ?", (42,)),
    CmpTestData(VALUE_FIELD > 42, Gt, "value", 42, "value > ?", (42,)),
    CmpTestData(VALUE_FIELD >= 42, Ge, "value", 42, "value >= ?", (42,)),
    CmpTestData(NAME_FIELD.like("foo"), Like, "name", "foo", "name like (?)", ("foo",)),
    # In expression
    CmpTestData(
        In(value=[1, 2, 3, 4]),
        In,
        "value",
        [1, 2, 3, 4],
        "value in (?, ?, ?, ?)",
        (1, 2, 3, 4),
    ),
    CmpTestData(
        VALUE_FIELD & [1, 2, 3, 4],
        In,
        "value",
        [1, 2, 3, 4],
        "value in (?, ?, ?, ?)",
        (1, 2, 3, 4),
    ),
    # Not in expression
    CmpTestData(
        NotIn(value=[1, 2, 3, 4]),
        NotIn,
        "value",
        [1, 2, 3, 4],
        "value not in (?, ?, ?, ?)",
        (1, 2, 3, 4),
    ),
    CmpTestData(
        ~(VALUE_FIELD & [1, 2, 3, 4]),
        NotIn,
        "value",
        [1, 2, 3, 4],
        "value not in (?, ?, ?, ?)",
        (1, 2, 3, 4),
    ),
]


@pytest.fixture(scope="module", params=TEST_CMP_EXPRESSIONS)
def compare(request) -> CmpTestData:
    yield request.param


def test_compare_expressions(compare):
    exp = compare.ctor

    assert isinstance(exp, compare.cls)
    assert isinstance(exp.field, Field)
    assert isinstance(exp.value, Value)

    assert exp.field.name == compare.field
    assert exp.value == compare.value
    if compare.value is None:
        assert exp.value.is_none
    assert exp.expression == compare.expression
    assert exp.params == compare.params
    assert exp.expression.count("?") == len(compare.params)


CompoundTestData = namedtuple(
    "CompoundTestData", ["ctor", "cls", "expression", "params"]
)
TEST_COMPOUND_EXRESSIONS = [
    # Not
    CompoundTestData(Not(Eq(name="foo")), Not, "not (name = ?)", ("foo",)),
    CompoundTestData(~Eq(name="foo"), Ne, "name != ?", ("foo",)),
    # AND and OR
    CompoundTestData(And(Eq(name="foo")), And, "(name = ?)", ("foo",)),
    CompoundTestData(
        And(Eq(name="foo"), Lt(value=42)),
        And,
        "(name = ?) and (value < ?)",
        ("foo", 42),
    ),
    CompoundTestData(
        And(Eq(name=None), Lt(value=42)),
        And,
        "(name is null) and (value < ?)",
        (42,),
    ),
    CompoundTestData(Or(Eq(name="foo")), Or, "(name = ?)", ("foo",)),
    CompoundTestData(
        Or(Eq(name="foo"), Lt(value=42)),
        Or,
        "(name = ?) or (value < ?)",
        ("foo", 42),
    ),
    CompoundTestData(
        Or(Eq(name=None), Lt(value=42)),
        Or,
        "(name is null) or (value < ?)",
        (42,),
    ),
    # Operator interface
    CompoundTestData(
        Eq(name="foo") & Lt(value=42),
        And,
        "(name = ?) and (value < ?)",
        ("foo", 42),
    ),
    CompoundTestData(
        Eq(name="foo") | Lt(value=42),
        Or,
        "(name = ?) or (value < ?)",
        ("foo", 42),
    ),
    # Longer expressions
    CompoundTestData(
        ((NAME_FIELD == "foo") & (VALUE_FIELD < 42)) | (VALUE_FIELD > 100500),
        Or,
        "((name = ?) and (value < ?)) or (value > ?)",
        ("foo", 42, 100500),
    ),
]


@pytest.fixture(scope="module", params=TEST_COMPOUND_EXRESSIONS)
def compound(request) -> CompoundTestData:
    yield request.param


def test_compound_expressions(compound):
    exp = compound.ctor

    assert isinstance(exp, compound.cls)

    assert exp.expression == compound.expression
    assert exp.params == compound.params
    assert exp.expression.count("?") == len(compound.params)


BuildTestData = namedtuple(
    "BuildTestData", ["args", "kwargs", "cls", "expression", "params"]
)
TEST_BUILD_EXPRESSIONS = [
    BuildTestData([NAME_FIELD.like("%bar%")], {}, Like, "name like (?)", ("%bar%",)),
    BuildTestData(
        [], {"name": "foo", "value": 42}, And, "(name = ?) and (value = ?)", ("foo", 42)
    ),
    BuildTestData(
        [NAME_FIELD.like("%baz%")],
        {"id": "foo", "value": 42},
        And,
        "(name like (?)) and (id = ?) and (value = ?)",
        ("%baz%", "foo", 42),
    ),
]


@pytest.fixture(scope="module", params=TEST_BUILD_EXPRESSIONS)
def expression(request) -> BuildTestData:
    yield request.param


def test_build_expression(expression):
    exp = build_expression(*expression.args, **expression.kwargs)

    assert isinstance(exp, expression.cls)
    assert exp.expression == expression.expression
    assert exp.params == expression.params
    assert exp.expression.count("?") == len(expression.params)
