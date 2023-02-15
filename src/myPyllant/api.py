import datetime
from urllib.parse import urlencode, urlparse, parse_qs
from typing import AsyncGenerator

import aiohttp

from myPyllant.models import Circuit, Device, DomesticHotWater, System, Zone
from myPyllant.utils import dict_to_snake_case, generate_code, random_string


login_url = "https://vaillant-prod.okta.com/api/v1/authn"
oauth_client_id = "0oarllti4egHi7Nwx4x6"
base_api_url = (
    "https://api.vaillant-group.com/service-connected-control/end-user-app-api/v1"
)

login_headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "user-agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
    "x-okta-user-agent-extended": "okta-auth-js/5.4.1 okta-react-native/2.7.0 react-native/>=0.70.1 ios/14.8 nodejs/undefined",
    "accept-language": "de-de",
}


class MyPyllantAPI(object):
    username: str = None
    password: str = None
    aiohttp_session = None
    oauth_session = {}
    oauth_session_expires: datetime.datetime = None

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.aiohttp_session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar())

    async def __aenter__(self):
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aiohttp_session.close()

    async def login(self):
        code_verifier, code_challenge = generate_code()

        login_payload = {
            "username": self.username,
            "password": self.password,
        }
        async with self.aiohttp_session.post(
            login_url, json=login_payload, headers=login_headers
        ) as resp:
            response = await resp.json()
            if "errorSummary" in response:
                raise Exception(response["errorSummary"])
            session_token = response["sessionToken"]

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
            "client_id": oauth_client_id,
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
            parsed_url = urlparse(resp.headers["Location"])
            code = parse_qs(parsed_url.query)["code"]

        token_payload = {
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": "com.okta.vaillant-prod:/callback",
            "client_id": oauth_client_id,
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
            self.set_session_expires()

    def set_session_expires(self):
        self.oauth_session_expires = datetime.datetime.now() + datetime.timedelta(
            seconds=self.oauth_session["expires_in"]
        )

    async def refresh_token(self):
        refresh_url = "https://vaillant-prod.okta.com/oauth2/default/v1/token"
        refresh_payload = {
            "refresh_token": self.oauth_session["refresh_token"],
            "client_id": oauth_client_id,
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

    async def get_systems(self) -> AsyncGenerator[int, System]:
        systems_url = f"{base_api_url}/systems"
        async with self.aiohttp_session.get(
            systems_url, headers=self.get_authorized_headers()
        ) as systems_resp:
            for system_json in await systems_resp.json():
                system_id = system_json["systemId"]
                system_url = f"{base_api_url}/emf/v2/{system_id}/currentSystem"

                async with self.aiohttp_session.get(
                    system_url, headers=self.get_authorized_headers()
                ) as current_system_resp:
                    current_system = await current_system_resp.json()
                system = System(
                    id=system_id,
                    current_system=current_system,
                    **dict_to_snake_case(system_json),
                )
                yield system

    async def get_devices_by_system(
        self, system: System, get_buckets: bool = False
    ) -> AsyncGenerator[int, Device]:
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

            if get_buckets:
                for data in device.data:
                    querystring = {
                        "resolution": "DAY",
                        "operationMode": data["operation_mode"],
                        "energyType": data["value_type"],
                        "startDate": data["from"],
                        "endDate": data["to"],
                    }
                    device_buckets_url = f"{base_api_url}/emf/v2/{system.id}/devices/{device.device_uuid}/buckets?{urlencode(querystring)}"
                    async with self.aiohttp_session.get(
                        device_buckets_url, headers=self.get_authorized_headers()
                    ) as device_buckets_resp:
                        data["buckets"] = dict_to_snake_case(
                            (await device_buckets_resp.json())["data"]
                        )
            yield device

    async def quick_veto_zone_temperature(
        self, zone: Zone, temperature: float, duration_hours: int
    ):
        url = f"{base_api_url}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
        return await self.aiohttp_session.patch(
            url,
            json={
                "desiredRoomTemperatureSetpoint": temperature,
                "duration": duration_hours,
            },
            headers=self.get_authorized_headers(),
        )

    async def cancel_quick_veto_zone_temperature(self, zone: Zone):
        url = f"{base_api_url}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
        return await self.aiohttp_session.delete(url, headers=self.get_authorized_headers())

    async def set_set_back_temperature(self, zone: Zone, temperature: float):
        url = f"{base_api_url}/systems/{zone.system_id}/zones/{zone.index}/setBackTemperature"
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
        assert start < end
        url = f"{base_api_url}/systems/{system.id}/holiday"
        data = {
            "holidayStartDateTime": start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "holidayEndDateTime": end.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }
        return await self.aiohttp_session.post(
            url, json=data, headers=self.get_authorized_headers()
        )

    async def cancel_holiday(self, system: System):
        url = f"{base_api_url}/systems/{system.id}/holiday"
        return await self.aiohttp_session.delete(url, headers=self.get_authorized_headers())

    async def set_domestic_hot_water_temperature(
        self, domestic_hot_water: DomesticHotWater, temperature: int
    ):
        url = f"{base_api_url}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/temperature"
        return await self.aiohttp_session.post(
            url, json={"setPoint": temperature}, headers=self.get_authorized_headers()
        )

    async def boost_domestic_hot_water(self, domestic_hot_water: DomesticHotWater):
        url = f"{base_api_url}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/boost"
        return await self.aiohttp_session.post(
            url, json={}, headers=self.get_authorized_headers()
        )

    async def cancel_hot_water_boost(self, domestic_hot_water: DomesticHotWater):
        url = f"{base_api_url}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/boost"
        return await self.aiohttp_session.delete(url, headers=self.get_authorized_headers())
