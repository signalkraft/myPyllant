import pytest

from myPyllant.api import MyPyllantAPI
from myPyllant.tests.utils import _mocked_api, _mypyllant_aioresponses


@pytest.fixture
def mypyllant_aioresponses():
    return _mypyllant_aioresponses()


@pytest.fixture
async def mocked_api() -> MyPyllantAPI:
    return await _mocked_api()
