import pytest

from myPyllant.api import MyPyllantAPI


async def test_invalid_country() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "invalid", "vaillant")


async def test_invalid_country_for_brand() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "germany", "sdbg")


async def test_invalid_brand() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "germany", "invalid")
