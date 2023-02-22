from datetime import datetime, timedelta
import json

from freezegun import freeze_time

from myPyllant.api import MyPyllantAPI
from myPyllant.export import main as export_main
from myPyllant.models import Device, DeviceData, DeviceDataBucket, System
from myPyllant.test_utils import get_mocked_api, mypyllant_aioresponses


async def test_login() -> None:
    with mypyllant_aioresponses() as _:
        async with MyPyllantAPI("test@example.com", "test") as api:
            assert isinstance(api.oauth_session_expires, datetime)
            assert api.oauth_session_expires > datetime.now()
            assert api.access_token == "access_token"
            assert "Authorization" in api.get_authorized_headers()


async def test_refresh_token() -> None:
    with mypyllant_aioresponses() as _:
        with freeze_time(datetime.now() + timedelta(hours=1)):
            api = await get_mocked_api()
            await api.refresh_token()
            session_expires = api.oauth_session_expires
        assert session_expires - datetime.now() > timedelta(hours=1)
        await api.aiohttp_session.close()


async def test_systems() -> None:
    with mypyllant_aioresponses() as _:
        api = await get_mocked_api()
        system = await anext(api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.status_online, bool)
        assert isinstance(system.status_error, bool)
        assert isinstance(system.outdoor_temperature, float)
        assert isinstance(system.mode, str)
        assert isinstance(system.water_pressure, float)
        await api.aiohttp_session.close()


async def test_devices() -> None:
    with mypyllant_aioresponses() as _:
        api = await get_mocked_api()
        system = await anext(api.get_systems())
        device = await anext(api.get_devices_by_system(system))

        assert isinstance(device, Device)
        assert isinstance(device.name_display, str)
        await api.aiohttp_session.close()


async def test_device_data() -> None:
    with mypyllant_aioresponses() as _:
        api = await get_mocked_api()

        system = await anext(api.get_systems())
        device = await anext(api.get_devices_by_system(system))
        device_data = await anext(api.get_data_by_device(device))

        assert isinstance(device_data, DeviceData)
        assert isinstance(device_data.data[0], DeviceDataBucket)
        await api.aiohttp_session.close()


async def test_export(capsys) -> None:
    with mypyllant_aioresponses() as _:
        await export_main("test@example.com", "test")
        captured = capsys.readouterr()
        assert isinstance(json.loads(captured.out), dict)
