import pytest
from dacite import WrongTypeError

from myPyllant.api import MyPyllantAPI

from ..models import Home, System, ZoneHeating, ZoneHeatingOperatingMode
from .test_api import list_test_data


@pytest.mark.parametrize("test_data", list_test_data())
async def test_systems(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.home, Home)
        assert isinstance(system.home.system_id, str)
        await mocked_api.aiohttp_session.close()


async def test_type_validation() -> None:
    with pytest.raises(WrongTypeError):
        ZoneHeating.from_api(
            manual_mode_setpoint_heating="15.0",
            operation_mode_heating=ZoneHeatingOperatingMode.MANUAL,
            time_program_heating={},
            set_back_temperature=15.0,
        )
    with pytest.raises(ValueError):
        ZoneHeating.from_api(
            manual_mode_setpoint_heating=15.0,
            operation_mode_heating="INVALID",
            time_program_heating={},
            set_back_temperature=15.0,
        )


@pytest.mark.parametrize("test_data", list_test_data())
async def test_trouble_codes(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        if "diagnostic_trouble_codes" not in test_data:
            pytest.skip("No diagnostic trouble codes in test data, skipping")
        system = await anext(
            mocked_api.get_systems(include_diagnostic_trouble_codes=True)
        )
        assert isinstance(system.diagnostic_trouble_codes, list)
        dtc = system.diagnostic_trouble_codes[0]
        assert isinstance(dtc, dict)
        assert isinstance(dtc["codes"], list)

        system.diagnostic_trouble_codes[0]["codes"] = [1, 2]
        assert system.has_diagnostic_trouble_codes

        system.diagnostic_trouble_codes = [{"codes": []}]
        assert not system.has_diagnostic_trouble_codes
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_ventilation(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        if "ventilation" not in test_data:
            pytest.skip("No ventilation devices in test data, skipping")
        system = await anext(mocked_api.get_systems())
        assert isinstance(system.ventilation, list)
        devices = [d for d in system.devices if d.type == "ventilation"]
        assert devices[0].device_type == "VENTILATION"
        await mocked_api.aiohttp_session.close()
