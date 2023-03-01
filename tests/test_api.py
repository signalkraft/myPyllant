from datetime import datetime, timedelta
import json

from freezegun import freeze_time

from myPyllant.api import MyPyllantAPI
from myPyllant.export import main as export_main
from myPyllant.models import Device, DeviceData, DeviceDataBucket, System


async def test_login(mypyllant_aioresponses) -> None:
    with mypyllant_aioresponses() as _:
        async with MyPyllantAPI("test@example.com", "test") as mocked_api:
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


async def test_systems(mypyllant_aioresponses, mocked_api) -> None:
    with mypyllant_aioresponses() as _:
        system = await anext(mocked_api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.status_online, bool)
        assert isinstance(system.status_error, bool)
        assert isinstance(system.outdoor_temperature, float)
        assert isinstance(system.mode, str)
        assert isinstance(system.water_pressure, float)
        await mocked_api.aiohttp_session.close()


async def test_devices(mypyllant_aioresponses, mocked_api) -> None:
    with mypyllant_aioresponses() as _:
        system = await anext(mocked_api.get_systems())
        device = await anext(mocked_api.get_devices_by_system(system))

        assert isinstance(device, Device)
        assert isinstance(device.name_display, str)
        await mocked_api.aiohttp_session.close()


async def test_device_data(mypyllant_aioresponses, mocked_api) -> None:
    with mypyllant_aioresponses() as _:
        system = await anext(mocked_api.get_systems())
        device = await anext(mocked_api.get_devices_by_system(system))
        device_data = await anext(mocked_api.get_data_by_device(device))

        assert isinstance(device_data, DeviceData)
        assert isinstance(device_data.data[0], DeviceDataBucket)
        await mocked_api.aiohttp_session.close()


async def test_export(mypyllant_aioresponses, capsys) -> None:
    with mypyllant_aioresponses() as _:
        await export_main("test@example.com", "test")
        captured = capsys.readouterr()
        assert isinstance(json.loads(captured.out), dict)
