import pytest

from nomanssky._formats import (
    format_spec_tokeniser,
    format_expression_parser,
    TokeniserState as TS,
    ExpressionToken as ET,
)
from nomanssky._formula import Ingredient, Formula, FormulaType

TEST_INGREDIENT = Ingredient("Carbon", 42)

TEST_REFINE_FORMULA = Formula(
    result=Ingredient("Faecium", 2),
    ingredients=[Ingredient("Faecium", 1), Ingredient("Oxygen", 1)],
    type=FormulaType.REFINING,
    process="Shit Aeration",
    time=0.05,
)

TEST_CRAFT_FORMULA = Formula(
    result=Ingredient("Living_Glass", 1),
    ingredients=[Ingredient("Glass", 5), Ingredient("Lubricant", 1)],
)

INGREDIENT_TOKENIZER_DATA = [
    (
        "%n%n%n",
        [
            ("%n", TS.PctString),
            ("%n", TS.PctString),
            ("%n", TS.PctString),
        ],
        "CarbonCarbonCarbon",
    ),
    (
        "%n x%q",
        [
            ("%n", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
        ],
        "Carbon x42",
    ),
    (
        " %n ",
        [
            (" ", TS.WhiteSpace),
            ("%n", TS.PctString),
            (" ", TS.WhiteSpace),
        ],
        " Carbon ",
    ),
    (
        "%nn x%q",
        [
            ("%nn", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
        ],
        "carbon x42",
    ),
    (
        "%NN x%q",
        [
            ("%NN", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
        ],
        "CARBON x42",
    ),
    (
        "%Nn x%q",
        [
            ("%Nn", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
        ],
        "Carbon x42",
    ),
    (
        "%%%nn x%q",
        [
            ("%", TS.Literal),
            ("%nn", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
        ],
        "%carbon x42",
    ),
    (
        "%n(%q)",
        [
            ("%n", TS.PctString),
            ("(", TS.Brackets),
            ("%q", TS.PctString),
            (")", TS.Brackets),
        ],
        "Carbon(42)",
    ),
]


@pytest.fixture(scope="module", params=INGREDIENT_TOKENIZER_DATA)
def ingredient_format_data(request):
    yield request.param


def test_tokenizer(ingredient_format_data):
    fmt_spec = ingredient_format_data[0]
    expected_tokens = ingredient_format_data[1]

    tokens = list([x for x in format_spec_tokeniser(fmt_spec)])
    assert tokens == expected_tokens


def test_ingredient_format(ingredient_format_data):
    fmt_spec = ingredient_format_data[0]
    fmt_string = f"{{:{fmt_spec}}}"
    formatted = fmt_string.format(TEST_INGREDIENT)

    assert formatted == ingredient_format_data[2]


FORMULA_TOKENIZER_DATA = [
    (
        "%type %res(%n x%q) <- %ing(' + '%n x%q)%process(' ('%pname %ptime' sec/unit)')",
        [
            ("%type", TS.PctString),
            (" ", TS.WhiteSpace),
            ("%res", TS.PctString),
            ("(", TS.Brackets),
            ("%n", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
            (")", TS.Brackets),
            (" ", TS.WhiteSpace),
            ("<", TS.Brackets),
            ("-", TS.Punctuation),
            (" ", TS.WhiteSpace),
            ("%ing", TS.PctString),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            (" ", TS.WhiteSpace),
            ("+", TS.Punctuation),
            (" ", TS.WhiteSpace),
            ("'", TS.SingleQuote),
            ("%n", TS.PctString),
            (" ", TS.WhiteSpace),
            ("x", TS.Literal),
            ("%q", TS.PctString),
            (")", TS.Brackets),
            ("%process", TS.PctString),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            (" ", TS.WhiteSpace),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            ("%pname", TS.PctString),
            (" ", TS.WhiteSpace),
            ("%ptime", TS.PctString),
            ("'", TS.SingleQuote),
            (" ", TS.WhiteSpace),
            ("sec/unit", TS.Literal),
            (")", TS.Brackets),
            ("'", TS.SingleQuote),
            (")", TS.Brackets),
        ],
        [
            (ET.PctString, "%type"),
            (ET.Literal, " "),
            (ET.PctString, "%res"),
            (
                ET.PctArgs,
                [(ET.PctString, "%n"), (ET.Literal, " x"), (ET.PctString, "%q")],
            ),
            (ET.Literal, " <- "),
            (ET.PctString, "%ing"),
            (
                ET.PctArgs,
                [
                    (ET.QuotedString, " + "),
                    (ET.PctString, "%n"),
                    (ET.Literal, " x"),
                    (ET.PctString, "%q"),
                ],
            ),
            (ET.PctString, "%process"),
            (
                ET.PctArgs,
                [
                    (ET.QuotedString, " ("),
                    (ET.PctString, "%pname"),
                    (ET.Literal, " "),
                    (ET.PctString, "%ptime"),
                    (ET.QuotedString, " sec/unit)"),
                ],
            ),
        ],
        "{R} Faecium x2 <- Faecium x1 + Oxygen x1 (Shit Aeration 0.05 sec/unit)",
        "{C} Living_Glass x1 <- Glass x5 + Lubricant x1",
    ),
    (
        "%res(%n)=%type'('%ing(', '%n)')'",
        [
            ("%res", TS.PctString),
            ("(", TS.Brackets),
            ("%n", TS.PctString),
            (")", TS.Brackets),
            ("=", TS.Punctuation),
            ("%type", TS.PctString),
            ("'", TS.SingleQuote),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            ("%ing", TS.PctString),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            (",", TS.Punctuation),
            (" ", TS.WhiteSpace),
            ("'", TS.SingleQuote),
            ("%n", TS.PctString),
            (")", TS.Brackets),
            ("'", TS.SingleQuote),
            (")", TS.Brackets),
            ("'", TS.SingleQuote),
        ],
        [
            (ET.PctString, "%res"),
            (ET.PctArgs, [(ET.PctString, "%n")]),
            (ET.Literal, "="),
            (ET.PctString, "%type"),
            (ET.QuotedString, "("),
            (ET.PctString, "%ing"),
            (ET.PctArgs, [(ET.QuotedString, ", "), (ET.PctString, "%n")]),
            (ET.QuotedString, ")"),
        ],
        "Faecium={R}(Faecium, Oxygen)",
        "Living_Glass={C}(Glass, Lubricant)",
    ),
    (
        "%res(%nn)='('%ing(', '%nn)')'",
        [
            ("%res", TS.PctString),
            ("(", TS.Brackets),
            ("%nn", TS.PctString),
            (")", TS.Brackets),
            ("=", TS.Punctuation),
            ("'", TS.SingleQuote),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            ("%ing", TS.PctString),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            (",", TS.Punctuation),
            (" ", TS.WhiteSpace),
            ("'", TS.SingleQuote),
            ("%nn", TS.PctString),
            (")", TS.Brackets),
            ("'", TS.SingleQuote),
            (")", TS.Brackets),
            ("'", TS.SingleQuote),
        ],
        [
            (ET.PctString, "%res"),
            (ET.PctArgs, [(ET.PctString, "%nn")]),
            (ET.Literal, "="),
            (ET.QuotedString, "("),
            (ET.PctString, "%ing"),
            (ET.PctArgs, [(ET.QuotedString, ", "), (ET.PctString, "%nn")]),
            (ET.QuotedString, ")"),
        ],
        "faecium=(faecium, oxygen)",
        "living_glass=(glass, lubricant)",
    ),
    (
        "%res",
        [
            ("%res", TS.PctString),
        ],
        [
            (ET.PctString, "%res"),
        ],
        "Faecium x2",
        "Living_Glass x1",
    ),
    (
        "%res='('%ing')'",
        [
            ("%res", TS.PctString),
            ("=", TS.Punctuation),
            ("'", TS.SingleQuote),
            ("(", TS.Brackets),
            ("'", TS.SingleQuote),
            ("%ing", TS.PctString),
            ("'", TS.SingleQuote),
            (")", TS.Brackets),
            ("'", TS.SingleQuote),
        ],
        [
            (ET.PctString, "%res"),
            (ET.Literal, "="),
            (ET.QuotedString, "("),
            (ET.PctString, "%ing"),
            (ET.QuotedString, ")"),
        ],
        "Faecium x2=(Faecium x1 + Oxygen x1)",
        "Living_Glass x1=(Glass x5 + Lubricant x1)",
    ),
]


@pytest.fixture(scope="module", params=FORMULA_TOKENIZER_DATA)
def formula_format_data(request):
    yield request.param


def test_formula_tokenizer(formula_format_data):
    fmt_spec = formula_format_data[0]
    expected_tokens = formula_format_data[1]

    tokens = list([x for x in format_spec_tokeniser(fmt_spec)])
    assert tokens == expected_tokens


def test_formula_expression_parser(formula_format_data):
    fmt_spec = formula_format_data[0]
    expected_tokens = formula_format_data[2]

    tokens = list([x for x in format_expression_parser(fmt_spec)])
    assert tokens == expected_tokens


def test_formula_format(formula_format_data):
    fmt_spec = formula_format_data[0]
    fmt_string = f"{{:{fmt_spec}}}"

    formatted = fmt_string.format(TEST_REFINE_FORMULA)
    assert formatted == formula_format_data[3]

    formatted = fmt_string.format(TEST_CRAFT_FORMULA)
    assert formatted == formula_format_data[4]
