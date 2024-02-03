import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from aioresponses import CallbackResult, aioresponses

from myPyllant.api import MyPyllantAPI
from myPyllant.const import API_URL_BASE, LOGIN_URL
from myPyllant.tests.generate_test_data import DATA_DIR
from myPyllant.utils import get_realm


def _mypyllant_aioresponses():
    class _mypyllant_aioresponses(aioresponses):
        def __init__(
            self, test_data=None, raise_exception: Exception | None = None, **kwargs
        ):
            self.test_data = test_data
            self.test_exception = raise_exception
            super().__init__(**kwargs)

        def __enter__(self):
            super().__enter__()

            if self.test_exception:
                self.get(
                    re.compile(r".*"),
                    exception=self.test_exception,
                )
                self.post(
                    re.compile(r".*"),
                    exception=self.test_exception,
                )
                self.patch(
                    re.compile(r".*"),
                    exception=self.test_exception,
                )
                self.delete(
                    re.compile(r".*"),
                    exception=self.test_exception,
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
            actions = re.compile(
                r".*(away-mode|setBackTemperature|temperature|holiday)$"
            )
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
                    r".*zones?/.*/(quick-veto|manual-mode-setpoint|heating-operation-mode|heating/operation-mode)$"
                ),
                status=200,
                payload={},
                repeat=True,
            )
            self.patch(
                re.compile(
                    r".*zones?/.*/(quick-veto|manual-mode-setpoint|heating-operation-mode|heating/operation-mode)$"
                ),
                status=200,
                payload={},
                repeat=True,
            )
            self.delete(
                re.compile(r".*zones?/.*/quick-veto$"),
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

            def get_test_data(url: str, key: str, default=None) -> CallbackResult:
                """
                Return test data CallbackResult based on the URL and key
                """
                url_parts = None
                for api_base in API_URL_BASE.values():
                    if url.startswith(api_base):
                        url_parts = url.replace(api_base, "").split("/")
                        break
                if not url_parts:
                    raise ValueError(f"Could not find API base in URL {url}")
                if url_parts[1] == "emf":
                    system_id = url_parts[3]
                else:
                    system_id = url_parts[2]
                return CallbackResult(
                    status=200, payload=self.test_data[system_id].get(key, default)
                )

            def test_data_by_system(url, **kwargs):
                """
                Return test data based on the system ID in the URL
                """
                url = str(url)
                result = None

                match url:
                    case url if re.match(r".*currentSystem$", url):
                        result = get_test_data(url, "current_system")
                    case url if re.match(r".*buckets\?.*", url):
                        result = get_test_data(url, "device_buckets")
                    case url if re.match(r".*systems/.*/tli", url):
                        result = get_test_data(url, "system")
                    case url if re.match(r".*vrc700.*systems.*", url):
                        result = get_test_data(url, "system")
                    case url if re.match(r".*meta-info/control-identifier$", url):
                        result = get_test_data(url, "control_identifier")
                    case url if re.match(r".*meta-info/time-zone", url):
                        result = get_test_data(url, "time_zone")
                    case url if re.match(r".*meta-info/connection-status", url):
                        result = get_test_data(url, "connection_status")
                    case url if re.match(r".*diagnostic-trouble-codes$", url):
                        result = get_test_data(url, "diagnostic_trouble_codes", [])
                    case url if re.match(r".*/mpc$", url):
                        result = get_test_data(url, "mpc", {"devices": []})
                    case url if re.match(r".*/rts/.*", url):
                        result = get_test_data(url, "rts", {"statistics": []})
                return result

            def unmatched_url(url, **kwargs):
                """
                Return test data based on the system ID in the URL
                """
                raise Exception(
                    f"Unmatched URL {url} with test data {self.test_data['_directory']}"
                )

            if self.test_data:
                # Create endpoints with stored JSON test data
                self.get(
                    re.compile(r".*/homes$"),
                    status=200,
                    payload=self.test_data["homes"],
                    repeat=True,
                )
                system_ids = [h["systemId"] for h in self.test_data["homes"]]
                # Handle URLs that contain a system ID
                self.get(
                    re.compile(rf".*({'|'.join(system_ids)}).*"),
                    callback=test_data_by_system,
                    repeat=True,
                )
            self.get(
                re.compile(r".*"),
                callback=unmatched_url,
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


def list_test_data():
    test_data = []
    for d in [d for d in DATA_DIR.iterdir() if d.is_dir()]:
        # check if a json file exists in dir
        if list(d.rglob("*.json")):
            test_data.append(load_test_data(d))
    for f in DATA_DIR.glob("*.yaml"):
        test_data.append({"_directory": str(f), **yaml.safe_load(f.read_text())})
    return test_data


def load_test_data(data_dir: Path):
    user_data: dict[str, Any] = defaultdict(dict)
    user_data["_directory"] = str(data_dir)
    for f in data_dir.rglob("*.json"):
        if f.parent != data_dir:
            user_data[f.parent.stem][f.stem] = json.loads(f.read_text())
        else:
            user_data[f.stem] = json.loads(f.read_text())
    return user_data
