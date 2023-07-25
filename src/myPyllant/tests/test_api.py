import json
from datetime import datetime, timedelta, tzinfo

import pytest
from freezegun import freeze_time

from myPyllant.api import MyPyllantAPI
from myPyllant.models import (
    Device,
    DeviceData,
    DeviceDataBucket,
    System,
    Zone,
    ZoneCurrentSpecialFunction,
)

from ..const import DEFAULT_QUICK_VETO_DURATION
from ..utils import datetime_format
from .generate_test_data import JSON_DIR


def get_test_data():
    test_data = []
    for d in [d for d in JSON_DIR.iterdir() if d.is_dir()]:
        user_data = {}
        for f in d.glob("*.json"):
            user_data[f.stem] = json.loads(f.read_text())
        test_data.append(user_data)
    return test_data


async def test_login(mypyllant_aioresponses) -> None:
    with mypyllant_aioresponses() as _:
        async with MyPyllantAPI(
            "test@example.com", "test", "germany", "vaillant"
        ) as mocked_api:
            assert isinstance(mocked_api.oauth_session_expires, datetime)
            assert mocked_api.oauth_session_expires > datetime.now()
            assert mocked_api.access_token == "access_token"
            assert "Authorization" in mocked_api.get_authorized_headers()


async def test_refresh_token(mypyllant_aioresponses, mocked_api) -> None:
    with mypyllant_aioresponses() as _:
        with freeze_time(datetime.now() + timedelta(hours=1)):
            await mocked_api.refresh_token()
            session_expires = mocked_api.oauth_session_expires
        assert session_expires - datetime.now() > timedelta(hours=1)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_systems(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.outdoor_temperature, (float | None))
        assert isinstance(system.water_pressure, float)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_meta_info(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        status = await mocked_api.get_connection_status(system)
        assert isinstance(status, bool)
        time_zone = await mocked_api.get_time_zone(system)
        assert isinstance(time_zone, tzinfo)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_meta_info_system_id(
    mypyllant_aioresponses, mocked_api, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        control_identifier = await mocked_api.get_control_identifier(system.id)
        assert isinstance(control_identifier, str)
        status = await mocked_api.get_connection_status(system.id)
        assert isinstance(status, bool)
        time_zone = await mocked_api.get_time_zone(system.id)
        assert isinstance(time_zone, tzinfo)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_devices(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        if len(system.devices) > 0:
            device = system.devices[0]
            assert isinstance(device, Device)
            assert isinstance(device.name_display, str)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_device_data(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        if len(system.devices) > 0:
            device = system.devices[0]
            device_data = await anext(mocked_api.get_data_by_device(device))
            assert isinstance(device_data, DeviceData)
            assert isinstance(device_data.data[0], DeviceDataBucket)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_quick_veto(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        zone: Zone = system.zones[0]
        # Activating quick veto
        zone.current_special_function = ZoneCurrentSpecialFunction.NONE
        await mocked_api.quick_veto_zone_temperature(zone, 20.0)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["desiredRoomTemperatureSetpoint"] == 20.0
        assert request.kwargs["json"]["duration"] == DEFAULT_QUICK_VETO_DURATION

        # Changing quick veto temperature
        zone.current_special_function = ZoneCurrentSpecialFunction.QUICK_VETO
        await mocked_api.quick_veto_zone_temperature(zone, 20.0)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["desiredRoomTemperatureSetpoint"] == 20.0
        assert "duration" not in request.kwargs["json"]
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_holiday_without_dates(
    mypyllant_aioresponses, mocked_api, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        now = datetime.now()
        with freeze_time(now):
            await mocked_api.set_holiday(system)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["holidayStartDateTime"] == datetime_format(
            now, with_microseconds=True
        )
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_holiday_with_dates(
    mypyllant_aioresponses, mocked_api, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        now = datetime.now()
        with freeze_time(now):
            start = now + timedelta(days=1)
            end = now + timedelta(days=7)
            await mocked_api.set_holiday(system, start, end)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["holidayStartDateTime"] == datetime_format(
            start, with_microseconds=True
        )
        assert request.kwargs["json"]["holidayEndDateTime"] == datetime_format(
            end, with_microseconds=True
        )
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_holiday_wrong_dates(
    mypyllant_aioresponses, mocked_api, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        start = datetime.now() + timedelta(days=1)
        end = start - timedelta(days=7)
        with pytest.raises(ValueError):
            await mocked_api.set_holiday(system, start, end)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_dhw_setpoint(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        await mocked_api.set_domestic_hot_water_temperature(
            system.domestic_hot_water[0], 60
        )
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["setPoint"] == 60
        await mocked_api.aiohttp_session.close()
