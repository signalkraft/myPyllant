from __future__ import annotations

import datetime
import logging
import re
from collections.abc import AsyncIterator
from html import unescape
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
from aiohttp import ClientResponseError
from dateutil.tz import gettz

from myPyllant.const import (
    API_URL_BASE,
    AUTHENTICATE_URL,
    BRANDS,
    CLIENT_ID,
    COUNTRIES,
    DEFAULT_CONTROL_IDENTIFIER,
    DEFAULT_QUICK_VETO_DURATION,
    LOGIN_URL,
    TOKEN_URL,
)
from myPyllant.models import (
    Claim,
    Device,
    DeviceData,
    DeviceDataBucketResolution,
    DHWOperationMode,
    DomesticHotWater,
    System,
    Zone,
    ZoneCurrentSpecialFunction,
    ZoneHeatingOperatingMode,
)
from myPyllant.utils import datetime_format, dict_to_snake_case, generate_code

logger = logging.getLogger(__name__)


class AuthenticationFailed(ConnectionError):
    pass


class LoginEndpointInvalid(ConnectionError):
    pass


async def on_request_start(session, context, params: aiohttp.TraceRequestStartParams):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_start
    """
    logger.debug(f"Starting request {params}")


async def on_request_end(session, context, params: aiohttp.TraceRequestEndParams):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_end
    """
    logger.debug(f"Got response {await params.response.text()}")


class MyPyllantAPI:
    username: str
    password: str
    aiohttp_session: aiohttp.ClientSession
    oauth_session: dict = {}
    oauth_session_expires: datetime.datetime | None = None

    def __init__(self, username: str, password: str, country: str, brand: str) -> None:
        if brand not in BRANDS.keys():
            raise ValueError(
                f"Invalid brand, must be one of {', '.join(BRANDS.keys())}"
            )
        if country not in COUNTRIES[brand].keys():
            raise ValueError(
                f"Invalid country, {BRANDS[brand]} only supports {', '.join(COUNTRIES[brand].keys())}"
            )
        self.username = username
        self.password = password
        self.country = country
        self.brand = brand
        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)
        self.aiohttp_session = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(),
            raise_for_status=True,
            trace_configs=[trace_config],
        )

    async def __aenter__(self) -> MyPyllantAPI:
        try:
            await self.login()
        except Exception:
            await self.aiohttp_session.close()
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if not self.aiohttp_session.closed:
            await self.aiohttp_session.close()

    @classmethod
    def get_system_id(cls, system: System | str) -> str:
        if isinstance(system, System):
            return system.id
        else:
            return system

    async def login(self):
        """
        This should really be done in the browser with OIDC, but that's not easy without support from Vaillant

        So instead, we grab the login endpoint from the HTML form of the login website and send username + password
        to obtain a session
        """

        code_verifier, code_challenge = generate_code()
        auth_querystring = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "code": "code_challenge",
            "redirect_uri": "enduservaillant.page.link://login",
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }

        # Grabbing the login URL from the HTML form of the login page
        try:
            async with self.aiohttp_session.get(
                AUTHENTICATE_URL.format(country=self.country, brand=self.brand)
                + "?"
                + urlencode(auth_querystring)
            ) as resp:
                login_html = await resp.text()
        except ClientResponseError as e:
            raise LoginEndpointInvalid from e

        result = re.search(
            LOGIN_URL.format(country=self.country, brand=self.brand) + r"\?([^\"]*)",
            login_html,
        )
        login_url = unescape(result.group())

        logger.debug(f"Got login url {login_url}")

        login_payload = {
            "username": self.username,
            "password": self.password,
            "credentialId": "",
        }
        # Obtaining the code
        async with self.aiohttp_session.post(
            login_url, data=login_payload, allow_redirects=False
        ) as resp:
            logger.debug(f"Got login response headers {resp.headers}")
            if "Location" not in resp.headers:
                raise AuthenticationFailed("Login failed")
            logger.debug(
                f'Got location from authorize endpoint: {resp.headers["Location"]}'
            )
            parsed_url = urlparse(resp.headers["Location"])
            code = parse_qs(parsed_url.query)["code"]

        # Obtaining a access token and refresh token
        token_payload = {
            "grant_type": "authorization_code",
            "client_id": "myvaillant",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": "enduservaillant.page.link://login",
        }

        async with self.aiohttp_session.post(
            TOKEN_URL.format(country=self.country, brand=self.brand),
            data=token_payload,
            raise_for_status=False,
        ) as resp:
            login_json = await resp.json()
            if resp.status >= 400:
                logger.error(
                    f"Could not log in, got status {resp.status} this response: {login_json}"
                )
                raise Exception(login_json)
            self.oauth_session = login_json
            logger.debug(f"Got session {self.oauth_session}")
            self.set_session_expires()

    def set_session_expires(self):
        self.oauth_session_expires = datetime.datetime.now() + datetime.timedelta(
            seconds=self.oauth_session["expires_in"]
        )
        logger.debug(f"Session expires in {self.oauth_session_expires}")

    async def refresh_token(self):
        refresh_payload = {
            "refresh_token": self.oauth_session["refresh_token"],
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
        }
        async with self.aiohttp_session.post(
            TOKEN_URL.format(country=self.country, brand=self.brand),
            data=refresh_payload,
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
            "Accept-Language": "en-GB",
            "Accept": "application/json, text/plain, */*",
            "x-client-locale": "en-GB",
            "x-idm-identifier": "KEYCLOAK",
            "ocp-apim-subscription-key": "1e0a2f3511fb4c5bbb1c7f9fedd20b1c",
            "User-Agent": "okhttp/4.9.2",
            "Connection": "keep-alive",
        }

    async def get_claims(self) -> AsyncIterator[Claim]:
        async with self.aiohttp_session.get(
            f"{API_URL_BASE}/claims", headers=self.get_authorized_headers()
        ) as claims_resp:
            for claim_json in await claims_resp.json():
                yield Claim(**dict_to_snake_case(claim_json))

    async def get_systems(
        self,
        include_timezone=False,
        include_connection_status=False,
        include_firmware_update_required=False,
    ) -> AsyncIterator[System]:
        logger.debug(
            f"Getting systems with include_timezone={include_timezone}"
            f" and include_connection_status={include_connection_status}"
        )
        claims = self.get_claims()
        async for claim in claims:
            control_identifier = await self.get_control_identifier(claim.system_id)
            system_url = (
                f"{API_URL_BASE}/systems/{claim.system_id}/{control_identifier}"
            )
            current_system_url = (
                f"{API_URL_BASE}/emf/v2/{claim.system_id}/currentSystem"
            )

            async with self.aiohttp_session.get(
                system_url, headers=self.get_authorized_headers()
            ) as system_resp:
                system_json = await system_resp.json()

            async with self.aiohttp_session.get(
                current_system_url, headers=self.get_authorized_headers()
            ) as current_system_resp:
                current_system_json = await current_system_resp.json()

            system = System(
                claim=claim,
                timezone=await self.get_time_zone(claim.system_id)
                if include_timezone
                else None,
                connected=await self.get_connection_status(claim.system_id)
                if include_connection_status
                else None,
                firmware_update_required=await self.get_firmware_update_required(
                    claim.system_id
                )
                if include_firmware_update_required
                else None,
                current_system=dict_to_snake_case(current_system_json),
                **dict_to_snake_case(system_json),
            )
            yield system

    async def get_data_by_device(
        self,
        device: Device,
        data_resolution: DeviceDataBucketResolution = DeviceDataBucketResolution.DAY,
        data_from: datetime.datetime | None = None,
        data_to: datetime.datetime | None = None,
    ) -> AsyncIterator[DeviceData]:
        for data in device.data:
            data_from = data_from or data.data_from
            if not data_from:
                raise ValueError(
                    "No data_from set, and no data_from found in device data"
                )
            data_to = data_to or data.data_to
            if not data_to:
                raise ValueError("No data_to set, and no data_to found in device data")
            start_date = datetime_format(data_from)
            end_date = datetime_format(data_to)
            querystring = {
                "resolution": str(data_resolution),
                "operationMode": data.operation_mode,
                "energyType": data.value_type,
                "startDate": start_date,
                "endDate": end_date,
            }
            device_buckets_url = (
                f"{API_URL_BASE}/emf/v2/{device.system_id}/"
                f"devices/{device.device_uuid}/buckets?{urlencode(querystring)}"
            )
            async with self.aiohttp_session.get(
                device_buckets_url, headers=self.get_authorized_headers()
            ) as device_buckets_resp:
                device_buckets_json = await device_buckets_resp.json()
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
                "heatingOperationMode": str(mode),
            },
            headers=self.get_authorized_headers(),
        )

    async def quick_veto_zone_temperature(
        self,
        zone: Zone,
        temperature: float,
        duration_hours: int | None = None,
        default_duration: int | None = None,
    ):
        logger.debug(
            f"Setting quick veto for {zone.name} in {zone.current_special_function} mode"
        )
        if not default_duration:
            default_duration = DEFAULT_QUICK_VETO_DURATION
        url = f"{API_URL_BASE}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
        if zone.current_special_function == ZoneCurrentSpecialFunction.QUICK_VETO:
            logger.debug(
                f"Patching quick veto for {zone.name} because it is already in quick veto mode"
            )
            payload = {
                "desiredRoomTemperatureSetpoint": temperature,
            }
            if duration_hours:
                payload["duration"] = duration_hours
            return await self.aiohttp_session.patch(
                url,
                json=payload,
                headers=self.get_authorized_headers(),
            )
        else:
            return await self.aiohttp_session.post(
                url,
                json={
                    "desiredRoomTemperatureSetpoint": temperature,
                    "duration": duration_hours if duration_hours else default_duration,
                },
                headers=self.get_authorized_headers(),
            )

    async def set_manual_mode_setpoint(
        self,
        zone: Zone,
        temperature: float,
        setpoint_type: str = "HEATING",
    ):
        logger.debug(f"Setting manual mode setpoint for {zone.name}")
        url = f"{API_URL_BASE}/systems/{zone.system_id}/tli/zones/{zone.index}/manual-mode-setpoint"
        payload = {
            "setpoint": temperature,
            "type": setpoint_type,
        }
        return await self.aiohttp_session.patch(
            url,
            json=payload,
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
        self,
        system: System,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ):
        if not start:
            start = datetime.datetime.now()
        if not end:
            # Set away for a long time if no end date is set
            end = start + datetime.timedelta(days=365)
        if not start < end:
            raise ValueError("Start of holiday mode must be before end")
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
            logger.warning("Domestic hot water can only be set to whole numbers")
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
                "operationMode": str(mode),
            },
            headers=self.get_authorized_headers(),
        )

    async def get_connection_status(self, system: System | str) -> bool:
        url = f"{API_URL_BASE}/systems/{self.get_system_id(system)}/meta-info/connection-status"
        response = await self.aiohttp_session.get(
            url,
            headers=self.get_authorized_headers(),
        )
        try:
            return (await response.json())["connected"]
        except KeyError:
            logger.warning("Couldn't get connection status")
            return False

    async def get_control_identifier(self, system: System | str) -> str | None:
        url = f"{API_URL_BASE}/systems/{self.get_system_id(system)}/meta-info/control-identifier"
        response = await self.aiohttp_session.get(
            url,
            headers=self.get_authorized_headers(),
        )
        try:
            return (await response.json())["controlIdentifier"]
        except KeyError:
            logger.warning("Couldn't get control identifier")
            return DEFAULT_CONTROL_IDENTIFIER

    async def get_time_zone(self, system: System | str) -> datetime.tzinfo | None:
        url = f"{API_URL_BASE}/systems/{self.get_system_id(system)}/meta-info/time-zone"
        response = await self.aiohttp_session.get(
            url,
            headers=self.get_authorized_headers(),
        )
        try:
            tz = (await response.json())["timeZone"]
            return gettz(tz)
        except KeyError:
            logger.warning("Couldn't get timezone from API")
            return None

    async def get_firmware_update_required(self, system: System | str) -> bool:
        url = f"{API_URL_BASE}/firmware-update-required/{self.get_system_id(system)}"
        response = await self.aiohttp_session.get(
            url,
            headers=self.get_authorized_headers(),
        )
        return (await response.json())["firmwareUpdateRequired"]
