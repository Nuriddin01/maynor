import pytest

from app.utils.time_utils import parse_hhmm
from app.utils.validators import parse_minutes, parse_scale_1_5, validate_timezone_name


def test_parse_scale_accepts_valid_value() -> None:
    assert parse_scale_1_5("4") == 4


def test_parse_scale_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        parse_scale_1_5("6")


def test_parse_minutes_rejects_fraction() -> None:
    with pytest.raises(ValueError):
        parse_minutes("10.5")


def test_validate_timezone_name_accepts_valid_timezone() -> None:
    assert validate_timezone_name("Europe/Moscow") == "Europe/Moscow"


def test_parse_hhmm_accepts_correct_format() -> None:
    assert parse_hhmm("07:30").hour == 7
