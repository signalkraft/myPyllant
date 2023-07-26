import re

from aioresponses import aioresponses

from myPyllant.api import MyPyllantAPI
from myPyllant.const import API_URL_BASE, LOGIN_URL


def _mypyllant_aioresponses():
    class _mypyllant_aioresponses(aioresponses):
        def __init__(self, test_data=None, **kwargs):
            self.test_data = test_data
            super().__init__(**kwargs)

        def __enter__(self):
            super().__enter__()

            # auth endpoints
            self.get(
                re.compile(r".*openid-connect/auth\?"),
                body=f"{LOGIN_URL.format(brand='vaillant', country='germany')}?test=test",
                status=200,
                repeat=True,
            )
            self.post(
                re.compile(r".*login-actions/authenticate\?"),
                status=200,
                headers={"Location": "test?code=code"},
                repeat=True,
            )
            self.post(
                re.compile(r".*openid-connect/token$"),
                status=200,
                payload={
                    "expires_in": 3600,
                    "access_token": "access_token",
                    "refresh_token": "refresh_token",
                },
                repeat=True,
            )
            # API endpoints
            actions = re.compile(r".*(holiday|setBackTemperature|temperature)$")
            self.post(
                actions,
                status=200,
                payload={},
                repeat=True,
            )
            self.patch(
                actions,
                status=200,
                payload={},
                repeat=True,
            )
            self.delete(
                actions,
                status=200,
                payload={},
                repeat=True,
            )
            self.post(
                re.compile(r".*domesticHotWater/.*/temperature$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.post(
                re.compile(r".*domesticHotWater/.*/boost$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.delete(
                re.compile(r".*domesticHotWater/.*/boost$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.post(
                re.compile(r".*zones/.*/quickVeto$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.patch(
                re.compile(r".*zones/.*/quickVeto$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.delete(
                re.compile(r".*zones/.*/quickVeto$"),
                status=200,
                payload={},
                repeat=True,
            )

            if self.test_data:
                # Create endpoints with stored JSON test data
                self.get(
                    f"{API_URL_BASE}/claims",
                    status=200,
                    payload=self.test_data["claims"],
                    repeat=True,
                )
                self.get(
                    re.compile(r".*currentSystem$"),
                    status=200,
                    payload=self.test_data["current_system"],
                    repeat=True,
                )
                self.get(
                    re.compile(r".*buckets\?.*"),
                    status=200,
                    payload=self.test_data["device_buckets"],
                    repeat=True,
                )
                self.get(
                    re.compile(
                        rf".*systems/.*/{self.test_data['control_identifier']['controlIdentifier']}"
                    ),
                    status=200,
                    payload=self.test_data["system"],
                    repeat=True,
                )
                self.get(
                    re.compile(r".*meta-info/control-identifier$"),
                    status=200,
                    payload=self.test_data["control_identifier"],
                    repeat=True,
                )
                self.get(
                    re.compile(r".*meta-info/time-zone"),
                    status=200,
                    payload=self.test_data["time_zone"],
                    repeat=True,
                )
                self.get(
                    re.compile(r".*meta-info/connection-status"),
                    status=200,
                    payload=self.test_data["connection_status"],
                    repeat=True,
                )
                self.get(
                    re.compile(r".*firmware-update-required.*"),
                    status=200,
                    payload=self.test_data["firmware_update_required"],
                    repeat=True,
                )
            return self

    return _mypyllant_aioresponses


async def _mocked_api(*args, **kwargs) -> MyPyllantAPI:
    api = MyPyllantAPI("test@example.com", "test", "germany", "vaillant")
    api.oauth_session = {
        "access_token": "access_token",
        "refresh_token": "refresh_token",
        "expires_in": 3600,
    }
    api.set_session_expires()
    return api
