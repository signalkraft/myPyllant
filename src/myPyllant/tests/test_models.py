import pytest

from ..models import Claim, System
from .test_api import list_test_data


@pytest.mark.parametrize("test_data", list_test_data())
async def test_systems(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.claim, Claim)
        assert isinstance(system.claim.system_id, str)
