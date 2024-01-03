from datetime import datetime, timezone

from myPyllant.utils import datetime_parse


async def test_datetime_parse() -> None:
    assert isinstance(
        datetime_parse("2022-03-28T19:37:12.27334Z", timezone.utc), datetime
    )
    assert isinstance(datetime_parse("2022-03-28T19:37:12Z", timezone.utc), datetime)
