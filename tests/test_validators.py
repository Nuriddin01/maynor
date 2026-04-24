import pytest

from app.utils.time_utils import parse_hhmm
from app.utils.validators import parse_minutes, parse_scale_1_5


def test_parse_minutes_ok() -> None:
    assert parse_minutes("30") == 30


def test_parse_scale_invalid() -> None:
    with pytest.raises(ValueError):
        parse_scale_1_5("7")


def test_parse_hhmm_invalid() -> None:
    with pytest.raises(ValueError):
        parse_hhmm("25:10")
