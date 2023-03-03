from datetime import datetime, timedelta
import json

from freezegun import freeze_time
import pytest

from myPyllant.api import MyPyllantAPI
from myPyllant.export import main as export_main
from myPyllant.models import Device, DeviceData, DeviceDataBucket, System

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


@pytest.mark.parametrize("test_data", get_test_data())
async def test_systems(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.status_online, bool)
        assert isinstance(system.status_error, bool)
        assert isinstance(system.outdoor_temperature, (float | None))
        assert isinstance(system.mode, str)
        assert isinstance(system.water_pressure, float)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_devices(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        device = await anext(mocked_api.get_devices_by_system(system))

        assert isinstance(device, Device)
        assert isinstance(device.name_display, str)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_device_data(mypyllant_aioresponses, mocked_api, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        device = await anext(mocked_api.get_devices_by_system(system))
        device_data = await anext(mocked_api.get_data_by_device(device))

        assert isinstance(device_data, DeviceData)
        assert isinstance(device_data.data[0], DeviceDataBucket)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", get_test_data())
async def test_export(mypyllant_aioresponses, capsys, test_data) -> None:
    with mypyllant_aioresponses(test_data) as _:
        await export_main("test@example.com", "test")
        captured = capsys.readouterr()
        assert isinstance(json.loads(captured.out), dict)
