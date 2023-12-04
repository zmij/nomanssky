import pytest

from typing import List, Tuple
from collections import namedtuple

from nomanssky import GalacticCoords, CoordinateSpace
from nomanssky._coords import _CodeState as CodeState

SCANNER_ID = "HUKYA"
VALID_PORTAL_CODE = "00380256EC6B"
VALID_COORDS = "046A:0081:0D6D:0038"
VALID_BOOSTER_CODE = SCANNER_ID + ":" + VALID_COORDS


ParserTestData = namedtuple(
    "ParserTestData",
    ["code", "expected_state", "expected_last_idx", "expected_valid_part"],
)


def generate_invalid_codes(valid_str: str) -> List[Tuple[str, CodeState, int, str]]:
    for i in range(0, len(valid_str)):
        invalid_str = valid_str[:i] + "*" + valid_str[i + 1 :]
        yield ParserTestData(invalid_str, CodeState.Invalid, i - 1, valid_str[:i])


def generate_incomplete_codes(
    valid_str: str, range_start: int = 1
) -> List[Tuple[str, CodeState, int, str]]:
    for i in range(range_start, len(valid_str)):
        invalid_str = valid_str[:i]
        yield ParserTestData(invalid_str, CodeState.Incomplete, i - 1, valid_str[:i])


def generate_extra_data(
    valid_str: str, number: int = 5
) -> List[Tuple[str, CodeState, int, str]]:
    last_idx = len(valid_str) - 1
    for i in range(1, number):
        long_str = valid_str + "A" * i
        yield ParserTestData(long_str, CodeState.Complete, last_idx, valid_str)


PORTAL_CODES = (
    [
        ParserTestData("", CodeState.Empty, -1, ""),
        ParserTestData("w", CodeState.Invalid, -1, ""),
        ParserTestData(VALID_PORTAL_CODE, CodeState.Complete, 11, VALID_PORTAL_CODE),
    ]
    + [x for x in generate_invalid_codes(VALID_PORTAL_CODE)]
    + [x for x in generate_incomplete_codes(VALID_PORTAL_CODE)]
    + [x for x in generate_extra_data(VALID_PORTAL_CODE)]
)

BOOSTER_CODES = (
    [
        ParserTestData("", CodeState.Empty, -1, ""),
        ParserTestData(
            VALID_BOOSTER_CODE,
            CodeState.Complete,
            len(VALID_BOOSTER_CODE) - 1,
            VALID_BOOSTER_CODE,
        ),
    ]
    + [x for x in generate_invalid_codes(VALID_BOOSTER_CODE)]
    + [
        x
        for x in generate_incomplete_codes(
            VALID_BOOSTER_CODE, range_start=len(SCANNER_ID) + 1
        )
    ]
    + [x for x in generate_extra_data(VALID_BOOSTER_CODE)]
)


@pytest.fixture(scope="module", params=PORTAL_CODES)
def portal_code(request):
    param = request.param
    yield param


@pytest.fixture(scope="module", params=BOOSTER_CODES)
def booster_code(request):
    param = request.param
    yield param


@pytest.fixture(
    scope="module", params=[CoordinateSpace.Portal, CoordinateSpace.Galactic]
)
def coord_space(request):
    yield request.param


def test_parse_portal_code(portal_code, coord_space):
    coords, state, last_idx = GalacticCoords.from_portal_code(
        portal_code.code, raise_if_invalid=False, coordinate_space=coord_space
    )

    assert state == portal_code.expected_state
    assert last_idx == portal_code.expected_last_idx
    assert portal_code.code[: last_idx + 1] == portal_code.expected_valid_part

    if state == CodeState.Complete:
        assert coords.portal_code == portal_code.expected_valid_part


def test_parse_booster_code(booster_code, coord_space):
    coords, state, last_idx = GalacticCoords.from_booster_code(
        booster_code.code, raise_if_invalid=False, coordinate_space=coord_space
    )
    assert state == booster_code.expected_state
    assert last_idx == booster_code.expected_last_idx
    assert booster_code.code[: last_idx + 1] == booster_code.expected_valid_part

    if state == CodeState.Complete:
        assert coords.booster_code(alpha=SCANNER_ID) == booster_code.expected_valid_part
