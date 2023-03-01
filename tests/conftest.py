import json
from pathlib import Path
import re

from aioresponses import aioresponses
import pytest

from myPyllant.api import API_URL_BASE, LOGIN_URL, MyPyllantAPI


@pytest.fixture
def mypyllant_aioresponses():
    class _mypyllant_aioresponses(aioresponses):
        def __enter__(self):
            super().__enter__()

            json_dir = Path(__file__).resolve().parent / "json"

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
                json_dir / "systems.json"
            ).exists(), "Missing JSON data, make sure to run `python3 tests/generate_test_data.py username password`"

            # systems endpoint
            with open(json_dir / "systems.json") as fh:
                self.get(f"{API_URL_BASE}/systems", status=200, payload=json.load(fh))

            # currentSystem endpoint
            with open(json_dir / "current_system.json") as fh:
                self.get(
                    re.compile(r".*currentSystem$"),
                    status=200,
                    payload=json.load(fh),
                )

            # device data buckets endpoint
            with open(json_dir / "device_buckets.json") as fh:
                self.get(
                    re.compile(r".*buckets\?.*"),
                    status=200,
                    payload=json.load(fh),
                )

    return _mypyllant_aioresponses


@pytest.fixture
async def mocked_api():
    api = MyPyllantAPI("test@example.com", "test")
    api.oauth_session = {
        "access_token": "access_token",
        "refresh_token": "refresh_token",
    }
    return api
