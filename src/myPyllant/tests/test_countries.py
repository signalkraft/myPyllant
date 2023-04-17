from unittest import mock

import pytest

from myPyllant.api import MyPyllantAPI
from myPyllant.tests.find_countries import countries_with_realm


async def test_invalid_country() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "invalid", "vaillant")


async def test_invalid_country_for_brand() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "germany", "sdbg")


async def test_invalid_brand() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "germany", "invalid")


async def test_find_countries(mocker) -> None:
    mocker.patch(
        "country_list.countries_for_language", return_value=[("de", "Germany")]
    )
    with mock.patch("requests.head") as patched_head:
        patched_head.return_value.status_code = 200
        assert list(countries_with_realm("vaillant")) == [("germany", "Germany")]
        patched_head.return_value.status_code = 404
        assert list(countries_with_realm("vaillant")) == []
