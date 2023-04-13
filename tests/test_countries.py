import pytest

from myPyllant.api import MyPyllantAPI


async def test_login() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "invalid", "vaillant")
