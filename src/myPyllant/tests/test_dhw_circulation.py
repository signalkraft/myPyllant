"""
Test that set_domestic_hot_water_circulation_time_program uses the right endpoint.

TLI controllers use PATCH .../tli/domestic-hot-water/{index}/circulation-pump-time-windows,
VRC700 controllers 404 on that path (signalkraft/mypyllant-component#400). The real
myVAILLANT app uses PATCH .../domestic-hot-water/{index}/circulation-pump/time-windows
for them (confirmed with a 202 against the live API) and only sends startTime/endTime
per slot.
"""

import pytest

from ..api import MyPyllantAPI
from ..models import DHWTimeProgram
from .utils import load_test_data, get_system_or_skip
from .generate_test_data import DATA_DIR

TIME_PROGRAM = {
    weekday: [{"start_time": 420, "end_time": 450}]
    for weekday in DHWTimeProgram.weekday_names()
}
EXPECTED_BODY = {
    weekday: [{"startTime": 420, "endTime": 450}]
    for weekday in DHWTimeProgram.weekday_names()
}


@pytest.mark.parametrize(
    "data_dir,expected_suffix",
    [
        (
            "vrc700_dhw.yaml",
            "/domestic-hot-water/{index}/circulation-pump/time-windows",
        ),
        (
            "vrc700_flexotherm",
            "/domestic-hot-water/{index}/circulation-pump/time-windows",
        ),
        (
            "two_systems",
            "/tli/domestic-hot-water/{index}/circulation-pump-time-windows",
        ),
    ],
)
async def test_circulation_time_program_endpoint(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, data_dir, expected_suffix
) -> None:
    with mypyllant_aioresponses(load_test_data(DATA_DIR / data_dir)) as aio:
        system = await get_system_or_skip(mocked_api)
        if not system.domestic_hot_water:
            pytest.skip(f"No domestic hot water in {data_dir} test data")
        dhw = system.domestic_hot_water[0]
        time_program = DHWTimeProgram.from_api(**TIME_PROGRAM)

        updated = await mocked_api.set_domestic_hot_water_circulation_time_program(
            dhw, time_program
        )

        method, url = list(aio.requests.keys())[-1]
        assert method == "PATCH"
        assert str(url).endswith(expected_suffix.format(index=dhw.index)), str(url)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"] == EXPECTED_BODY
        assert updated.time_program_circulation_pump == time_program

        await mocked_api.aiohttp_session.close()
