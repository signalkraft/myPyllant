from __future__ import annotations

from collections.abc import AsyncGenerator
import datetime
import json
import logging
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from myPyllant.models import (
    Device,
    DeviceData,
    DeviceDataBucketResolution,
    DHWOperationMode,
    DomesticHotWater,
    System,
    Zone,
    ZoneHeatingOperatingMode,
)
from myPyllant.utils import (
    datetime_format,
    dict_to_snake_case,
    generate_code,
    random_string,
)

logger = logging.getLogger(__name__)


LOGIN_URL = "https://vaillant-prod.okta.com/api/v1/authn"
LOGIN_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "user-agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
    "x-okta-user-agent-extended": "okta-auth-js/5.4.1 okta-react-native/2.7.0 "
    "react-native/>=0.70.1 ios/14.8 nodejs/undefined",
    "accept-language": "de-de",
}

OAUTH_CLIENT_ID = "0oarllti4egHi7Nwx4x6"
API_URL_BASE = (
    "https://api.vaillant-group.com/service-connected-control/end-user-app-api/v1"
)


class MyPyllantAPI:
    username: str = None
    password: str = None
    aiohttp_session: aiohttp.ClientSession = None
    oauth_session: dict = {}
    oauth_session_expires: datetime.datetime = None

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.aiohttp_session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(),
            raise_for_status=True,
        )

    async def __aenter__(self) -> MyPyllantAPI:
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aiohttp_session.close()

    async def login(self):
        code_verifier, code_challenge = generate_code()

        login_payload = {
            "username": self.username,
            "password": self.password,
        }
        async with self.aiohttp_session.post(
            LOGIN_URL, json=login_payload, headers=LOGIN_HEADERS, raise_for_status=False
        ) as resp:
            login_json = await resp.json()
            if resp.status >= 400:
                logger.error(
                    f"Could not log in, got status {resp.status} this response: {login_json}"
                )
                raise Exception(login_json["errorSummary"])
            session_token = login_json["sessionToken"]

        nonce = random_string(43)
        state = random_string(43)
        authorize_querystring = {
            "nonce": nonce,
            "sessionToken": session_token,
            "response_type": "code",
            "code_challenge_method": "S256",
            "scope": "openid profile offline_access",
            "code_challenge": code_challenge,
            "redirect_uri": "com.okta.vaillant-prod:/callback",
            "client_id": OAUTH_CLIENT_ID,
            "state": state,
        }
        authorize_headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "user-agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
            "accept-language": "de-de",
        }
        authorize_url = (
            "https://vaillant-prod.okta.com/oauth2/default/v1/authorize?"
            + urlencode(authorize_querystring)
        )
        async with self.aiohttp_session.get(
            authorize_url, headers=authorize_headers, allow_redirects=False
        ) as resp:
            await resp.text()
            logger.debug(
                f'Got location from authorize endpoint: {resp.headers["Location"]}'
            )
            parsed_url = urlparse(resp.headers["Location"])
            code = parse_qs(parsed_url.query)["code"]

        token_payload = {
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": "com.okta.vaillant-prod:/callback",
            "client_id": OAUTH_CLIENT_ID,
            "grant_type": "authorization_code",
        }
        token_headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "user-agent": "okta-react-native/2.7.0 okta-oidc-ios/3.11.2 react-native/>=0.70.1 ios/14.8",
            "accept-language": "de-de",
        }
        token_url = "https://vaillant-prod.okta.com/oauth2/default/v1/token"
        async with self.aiohttp_session.post(
            token_url, data=token_payload, headers=token_headers
        ) as resp:
            self.oauth_session = await resp.json()
            logger.debug(f"Got session {self.oauth_session}")
            self.set_session_expires()

    def set_session_expires(self):
        self.oauth_session_expires = datetime.datetime.now() + datetime.timedelta(
            seconds=self.oauth_session["expires_in"]
        )
        logger.debug(f"Session expires in {self.oauth_session_expires}")

    async def refresh_token(self):
        refresh_url = "https://vaillant-prod.okta.com/oauth2/default/v1/token"
        refresh_payload = {
            "refresh_token": self.oauth_session["refresh_token"],
            "client_id": OAUTH_CLIENT_ID,
            "grant_type": "refresh_token",
        }
        refresh_headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "user-agent": "okta-react-native/2.7.0 okta-oidc-ios/3.11.2 react-native/>=0.70.1 ios/14.8",
            "accept-language": "de-de",
        }
        async with self.aiohttp_session.post(
            refresh_url, data=refresh_payload, headers=refresh_headers
        ) as resp:
            self.oauth_session = await resp.json()
            self.set_session_expires()
            return self.oauth_session

    @property
    def access_token(self):
        return self.oauth_session["access_token"]

    def get_authorized_headers(self):
        return {
            "Authorization": "Bearer " + self.access_token,
            "x-app-identifier": "VAILLANT",
            "Accept-Language": "de-de",
            "Accept": "application/json, text/plain, */*",
            "x-client-locale": "de-DE",
            "x-idm-identifier": "OKTA",
            "ocp-apim-subscription-key": "1e0a2f3511fb4c5bbb1c7f9fedd20b1c",
            "User-Agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
            "Connection": "keep-alive",
        }

    async def get_systems(self) -> AsyncGenerator[System, int]:
        systems_url = f"{API_URL_BASE}/systems"
        async with self.aiohttp_session.get(
            systems_url, headers=self.get_authorized_headers()
        ) as systems_resp:
            for system_json in await systems_resp.json():
                logger.debug(f"Got systems response {system_json}")
                system_id = system_json["systemId"]
                system_url = f"{API_URL_BASE}/emf/v2/{system_id}/currentSystem"

                async with self.aiohttp_session.get(
                    system_url, headers=self.get_authorized_headers()
                ) as current_system_resp:
                    current_system_json = await current_system_resp.json()
                    logger.debug(f"Got current system response {current_system_json}")
                system = System(
                    id=system_id,
                    current_system=current_system_json,
                    **dict_to_snake_case(system_json),
                )
                yield system

    @staticmethod
    async def get_devices_by_system(
        system: System,
    ) -> AsyncGenerator[Device, None]:
        for device_raw in system.current_system.values():
            if not (isinstance(device_raw, dict) and "device_uuid" in device_raw):
                continue
            device = Device(
                system=system,
                **device_raw,
            )

            serial_nos = {d["serial_number"]: d for d in system.devices}
            if device.device_serial_number in serial_nos.keys():
                device_info = serial_nos[device.device_serial_number]
                device.operational_data = dict_to_snake_case(
                    device_info.get("operational_data", {})
                )
                device.name = device_info.get("name", "")

            yield device

    async def get_data_by_device(
        self,
        device: Device,
        data_resolution: DeviceDataBucketResolution = DeviceDataBucketResolution.DAY,
        data_from: datetime.datetime | None = None,
        data_to: datetime.datetime | None = None,
    ) -> AsyncGenerator[DeviceData, None]:
        for data in device.data:
            start_date = datetime_format(data_from if data_from else data.data_from)
            end_date = datetime_format(data_to if data_to else data.data_to)
            querystring = {
                "resolution": str(data_resolution),
                "operationMode": data.operation_mode,
                "energyType": data.value_type,
                "startDate": start_date,
                "endDate": end_date,
            }
            device_buckets_url = (
                f"{API_URL_BASE}/emf/v2/{device.system.id}/"
                f"devices/{device.device_uuid}/buckets?{urlencode(querystring)}"
            )
            async with self.aiohttp_session.get(
                device_buckets_url, headers=self.get_authorized_headers()
            ) as device_buckets_resp:
                device_buckets_json = await device_buckets_resp.json()
                logger.debug(f"Got data buckets response {device_buckets_json}")
                yield DeviceData(
                    device=device,
                    **dict_to_snake_case(device_buckets_json),
                )

    async def set_zone_heating_operating_mode(
        self, zone: Zone, mode: ZoneHeatingOperatingMode
    ):
        url = f"{API_URL_BASE}/systems/{zone.system_id}/zones/{zone.index}/heatingOperationMode"
        return await self.aiohttp_session.post(
            url,
            json={
                "heatingOperationMode": str(ZoneHeatingOperatingMode(mode)),
            },
            headers=self.get_authorized_headers(),
        )

    async def quick_veto_zone_temperature(
        self, zone: Zone, temperature: float, duration_hours: int
    ):
        url = f"{API_URL_BASE}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
        return await self.aiohttp_session.post(
            url,
            json={
                "desiredRoomTemperatureSetpoint": temperature,
                "duration": duration_hours,
            },
            headers=self.get_authorized_headers(),
        )

    async def cancel_quick_veto_zone_temperature(self, zone: Zone):
        url = f"{API_URL_BASE}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
        return await self.aiohttp_session.delete(
            url, headers=self.get_authorized_headers()
        )

    async def set_set_back_temperature(self, zone: Zone, temperature: float):
        url = f"{API_URL_BASE}/systems/{zone.system_id}/zones/{zone.index}/setBackTemperature"
        return await self.aiohttp_session.patch(
            url,
            json={"setBackTemperature": temperature},
            headers=self.get_authorized_headers(),
        )

    async def set_holiday(
        self, system: System, start: datetime.datetime, end: datetime.datetime = None
    ):
        if not end:
            # Set away for a long time if no end date is set
            end = start + datetime.timedelta(days=365)
        if not start < end:
            raise Exception("Start of holiday mode must be before end")
        url = f"{API_URL_BASE}/systems/{system.id}/holiday"
        data = {
            "holidayStartDateTime": datetime_format(start, with_microseconds=True),
            "holidayEndDateTime": datetime_format(end, with_microseconds=True),
        }
        return await self.aiohttp_session.post(
            url, json=data, headers=self.get_authorized_headers()
        )

    async def cancel_holiday(self, system: System):
        url = f"{API_URL_BASE}/systems/{system.id}/holiday"
        return await self.aiohttp_session.delete(
            url, headers=self.get_authorized_headers()
        )

    async def set_domestic_hot_water_temperature(
        self, domestic_hot_water: DomesticHotWater, temperature: int | float
    ):
        if isinstance(temperature, float):
            logger.warning(f"Domestic hot water can only be set to whole numbers")
            temperature = int(round(temperature, 0))
        url = (
            f"{API_URL_BASE}/systems/{domestic_hot_water.system_id}/"
            f"domesticHotWater/{domestic_hot_water.index}/temperature"
        )
        return await self.aiohttp_session.post(
            url, json={"setPoint": temperature}, headers=self.get_authorized_headers()
        )

    async def boost_domestic_hot_water(self, domestic_hot_water: DomesticHotWater):
        url = f"{API_URL_BASE}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/boost"
        return await self.aiohttp_session.post(
            url, json={}, headers=self.get_authorized_headers()
        )

    async def cancel_hot_water_boost(self, domestic_hot_water: DomesticHotWater):
        url = f"{API_URL_BASE}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/boost"
        return await self.aiohttp_session.delete(
            url, headers=self.get_authorized_headers()
        )

    async def set_domestic_hot_water_operation_mode(
        self, domestic_hot_water: DomesticHotWater, mode: DHWOperationMode
    ):
        url = (
            f"{API_URL_BASE}/systems/{domestic_hot_water.system_id}/"
            f"domesticHotWater/{domestic_hot_water.index}/operationMode"
        )
        return await self.aiohttp_session.post(
            url,
            json={
                "operationMode": str(DHWOperationMode(mode)),
            },
            headers=self.get_authorized_headers(),
        )
