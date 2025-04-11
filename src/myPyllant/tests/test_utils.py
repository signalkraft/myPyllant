from datetime import datetime, timezone
from myPyllant.utils import datetime_parse
from zoneinfo import ZoneInfo

"""
Tests for the `datetime_parse` function from the `myPyllant.utils` module.

Functions:
    test_datetime_parse:
        Verifies that `datetime_parse` correctly parses ISO 8601 datetime strings
        with UTC timezone into `datetime` objects.

    test_datetime_parse_local_datetime:
        Ensures that `datetime_parse` correctly parses ISO 8601 datetime strings
        with a specified local timezone and returns a `datetime` object with the
        appropriate timezone information.

    test_datetime_parse_zulu_datetime:
        Tests that `datetime_parse` correctly handles ISO 8601 datetime strings
        with a "Z" (Zulu) timezone and converts them to the specified local timezone.
"""


async def test_datetime_parse() -> None:
    assert isinstance(
        datetime_parse("2022-03-28T19:37:12.27334Z", timezone.utc), datetime
    )
    assert isinstance(datetime_parse("2022-03-28T19:37:12Z", timezone.utc), datetime)


async def test_datetime_parse_local_datetime():
    london_timezone = ZoneInfo("Europe/London")
    date_string = "2025-04-10T18:00:03+01:00"
    parsed_date = datetime_parse(date_string, None)
    assert isinstance(parsed_date, datetime)
    assert parsed_date == datetime(2025, 4, 10, 18, 0, 3, tzinfo=london_timezone)


async def test_datetime_parse_zulu_datetime():
    london_timezone = ZoneInfo("Europe/London")
    date_string = "2025-04-10T17:00:03Z"
    parsed_date = datetime_parse(date_string, london_timezone)
    assert isinstance(parsed_date, datetime)
    assert parsed_date == datetime(2025, 4, 10, 18, 0, 3, tzinfo=london_timezone)
