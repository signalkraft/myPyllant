import pytest as pytest

from ..api import MyPyllantAPI
from ..sample import main
from .utils import list_test_data


@pytest.mark.parametrize("test_data", list_test_data())
async def test_sample(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, mocker, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        mocker.patch("myPyllant.api.MyPyllantAPI.__aenter__", return_value=mocked_api)
        await main("test@example.com", "test", "vaillant", "germany")
        await mocked_api.aiohttp_session.close()
