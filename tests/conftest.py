import re

from aioresponses import aioresponses
import pytest

from myPyllant.api import MyPyllantAPI
from myPyllant.const import API_URL_BASE, LOGIN_URL


@pytest.fixture
def mypyllant_aioresponses():
    class _mypyllant_aioresponses(aioresponses):
        def __init__(self, test_data=None, **kwargs):
            self.test_data = test_data
            super().__init__(**kwargs)

        def __enter__(self):
            super().__enter__()

            # auth endpoints
            self.get(
                re.compile(r".*openid-connect/auth\?"),
                body=f"{LOGIN_URL.format(country='germany')}?test=test",
                status=200,
            )
            self.post(
                re.compile(r".*login-actions/authenticate\?"),
                status=200,
                headers={"Location": "test?code=code"},
            )
            self.post(
                re.compile(r".*openid-connect/token$"),
                status=200,
                payload={
                    "expires_in": 3600,
                    "access_token": "access_token",
                    "refresh_token": "refresh_token",
                },
            )

            if self.test_data:
                # Create endpoints with stored JSON test data
                self.get(
                    f"{API_URL_BASE}/systems",
                    status=200,
                    payload=self.test_data["systems"],
                )
                self.get(
                    re.compile(r".*currentSystem$"),
                    status=200,
                    payload=self.test_data["current_system"],
                )
                self.get(
                    re.compile(r".*buckets\?.*"),
                    status=200,
                    payload=self.test_data["device_buckets"],
                )

    return _mypyllant_aioresponses


@pytest.fixture
async def mocked_api():
    api = MyPyllantAPI("test@example.com", "test", "germany")
    api.oauth_session = {
        "access_token": "access_token",
        "refresh_token": "refresh_token",
    }
    return api
