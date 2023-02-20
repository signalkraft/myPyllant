from datetime import datetime, timedelta
import json
from pathlib import Path
import re

from aioresponses import aioresponses
from freezegun import freeze_time

from myPyllant.api import API_URL_BASE, LOGIN_URL, MyPyllantAPI
from myPyllant.export import main as export_main
from myPyllant.models import Device, DeviceData, DeviceDataBucket, System


class mypyllant_aioresponses(aioresponses):
    def __enter__(self):
        super().__enter__()

        # auth endpoints
        self.post(LOGIN_URL, status=200, payload={"sessionToken": "test"})
        self.get(
            re.compile(r".*v1/authorize\?"),
            status=200,
            headers={"Location": "test?code=code"},
        )
        self.post(
            re.compile(r".*v1/token$"),
            status=200,
            payload={
                "expires_in": 3600,
                "access_token": "access_token",
                "refresh_token": "refresh_token",
            },
        )

        assert (
            Path(__file__).resolve().parent / "json/systems.json"
        ).exists(), "Missing JSON data, make sure to run `python3 tests/generate_test_data.py username password`"

        # systems endpoint
        with open(Path(__file__).resolve().parent / "json/systems.json") as fh:
            self.get(f"{API_URL_BASE}/systems", status=200, payload=json.load(fh))

        # currentSystem endpoint
        with open(Path(__file__).resolve().parent / "json/current_system.json") as fh:
            self.get(
                re.compile(r".*currentSystem$"),
                status=200,
                payload=json.load(fh),
            )

        # device data buckets endpoint
        with open(Path(__file__).resolve().parent / "json/device_buckets.json") as fh:
            self.get(
                re.compile(r".*buckets\?.*"),
                status=200,
                payload=json.load(fh),
            )


async def get_mocked_api():
    api = MyPyllantAPI("test@example.com", "test")
    api.oauth_session = {
        "access_token": "access_token",
        "refresh_token": "refresh_token",
    }
    return api


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


async def test_systems() -> None:
    with mypyllant_aioresponses() as _:
        system = await anext((await get_mocked_api()).get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.status_online, bool)
        assert isinstance(system.status_error, bool)
        assert isinstance(system.outdoor_temperature, float)
        assert isinstance(system.mode, str)
        assert isinstance(system.water_pressure, float)


async def test_devices() -> None:
    with mypyllant_aioresponses() as _:
        system = await anext((await get_mocked_api()).get_systems())
        device = await anext((await get_mocked_api()).get_devices_by_system(system))

        assert isinstance(device, Device)
        assert isinstance(device.name_display, str)


async def test_device_data() -> None:
    with mypyllant_aioresponses() as _:
        system = await anext((await get_mocked_api()).get_systems())
        device = await anext((await get_mocked_api()).get_devices_by_system(system))
        device_data = await anext((await get_mocked_api()).get_data_by_device(device))

        assert isinstance(device_data, DeviceData)
        assert isinstance(device_data.data[0], DeviceDataBucket)


async def test_export(capsys) -> None:
    with mypyllant_aioresponses() as _:
        await export_main("test@example.com", "test")
        captured = capsys.readouterr()
        assert isinstance(json.loads(captured.out), dict)
