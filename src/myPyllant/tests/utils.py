import re

from aiohttp import RequestInfo
from aiohttp.client_exceptions import ClientResponseError
from aioresponses import aioresponses

from myPyllant.api import MyPyllantAPI
from myPyllant.const import API_URL_BASE, LOGIN_URL
from myPyllant.utils import get_realm


def _mypyllant_aioresponses():
    class _mypyllant_aioresponses(aioresponses):
        def __init__(self, test_data=None, test_quota=False, **kwargs):
            self.test_data = test_data
            self.test_quota = test_quota
            super().__init__(**kwargs)

        def __enter__(self):
            super().__enter__()

            if self.test_quota:
                e = ClientResponseError(
                    request_info=RequestInfo(
                        url="https://api.vaillant-group.com/service-connected-control/end-user-app-api/v1/claims",
                        method="GET",
                        headers=None,
                    ),
                    history=None,
                    status=403,
                    message="Quota Exceeded",
                )
                self.get(
                    re.compile(r".*"),
                    exception=e,
                )
                self.post(
                    re.compile(r".*"),
                    exception=e,
                )
                self.patch(
                    re.compile(r".*"),
                    exception=e,
                )
                self.delete(
                    re.compile(r".*"),
                    exception=e,
                )

            # auth endpoints
            self.get(
                re.compile(r".*vaillant-germany-b2c/protocol/openid-connect/auth\?"),
                body=f"{LOGIN_URL.format(realm=get_realm('vaillant', 'germany'))}?test=test",
                status=200,
                repeat=True,
            )
            self.get(
                re.compile(r".*bulex-b2c/protocol/openid-connect/auth\?"),
                body=f"{LOGIN_URL.format(realm=get_realm('bulex'))}?test=test",
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
            actions = re.compile(r".*(away-mode|setBackTemperature|temperature)$")
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
                re.compile(r".*domestic-hot-water/.*/temperature$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.patch(
                re.compile(r".*domestic-hot-water/.*/operation-mode$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.post(
                re.compile(r".*domestic-hot-water/.*/boost$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.delete(
                re.compile(r".*domestic-hot-water/.*/boost$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.post(
                re.compile(
                    r".*zones/.*/(quick-veto|manual-mode-setpoint|heating-operation-mode)$"
                ),
                status=200,
                payload={},
                repeat=True,
            )
            self.patch(
                re.compile(
                    r".*zones/.*/(quick-veto|manual-mode-setpoint|heating-operation-mode)$"
                ),
                status=200,
                payload={},
                repeat=True,
            )
            self.delete(
                re.compile(r".*zones/.*/quick-veto$"),
                status=200,
                payload={},
                repeat=True,
            )
            self.patch(
                re.compile(r".*ventilation/.*/(operation-mode|fan-stage)$"),
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
                    re.compile(r".*diagnostic-trouble-codes$"),
                    status=200,
                    payload=self.test_data.get("diagnostic_trouble_codes", []),
                    repeat=True,
                )
            return self

    return _mypyllant_aioresponses


async def _mocked_api(*args, **kwargs) -> MyPyllantAPI:
    api = MyPyllantAPI("test@example.com", "test", "vaillant", "germany")
    api.oauth_session = {
        "access_token": "access_token",
        "refresh_token": "refresh_token",
        "expires_in": 3600,
    }
    api.set_session_expires()
    return api
