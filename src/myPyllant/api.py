from __future__ import annotations

import datetime
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import asdict
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp import ClientResponseError

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
    ZONE_OPERATING_TYPES,
)
from myPyllant.enums import (
    ControlIdentifier,
    DeviceDataBucketResolution,
    ZoneOperatingModeVRC700,
    ZoneOperatingMode,
    ZoneCurrentSpecialFunction,
    ZoneTimeProgramType,
    DHWOperationMode,
    VentilationOperationMode,
    VentilationFanStageType,
    DHWOperationModeVRC700,
    DHWCurrentSpecialFunction,
    AmbisenseRoomOperationMode,
    VentilationOperationModeVRC700,
)
from myPyllant.http_client import (
    AuthenticationFailed,
    LoginEndpointInvalid,
    RealmInvalid,
    get_http_client,
)
from myPyllant.models import (
    Device,
    DeviceData,
    DHWTimeProgram,
    DomesticHotWater,
    Home,
    System,
    SystemReport,
    Ventilation,
    Zone,
    ZoneTimeProgram,
    AmbisenseRoom,
    RoomTimeProgram,
)
from myPyllant.utils import (
    datetime_format,
    dict_to_camel_case,
    dict_to_snake_case,
    generate_code,
    get_realm,
    get_default_holiday_dates,
)

logger = logging.getLogger(__name__)


def get_system_id(system: System | str) -> str:
    if isinstance(system, System):
        return system.id
    else:
        return system


def get_api_base(control_identifier: ControlIdentifier | str | None = None) -> str:
    key = str(control_identifier) if control_identifier else DEFAULT_CONTROL_IDENTIFIER
    return API_URL_BASE[key]


def get_system_api_base(
    system: str | System, control_identifier: ControlIdentifier | str
) -> str:
    suffix = ""
    if ControlIdentifier(control_identifier) == ControlIdentifier.TLI:
        suffix = "/tli"
    return f"{get_api_base(control_identifier)}/systems/{get_system_id(system)}{suffix}"


class MyPyllantAPI:
    username: str
    password: str
    aiohttp_session: aiohttp.ClientSession
    oauth_session: dict = {}
    oauth_session_expires: datetime.datetime | None = None
    control_identifiers: dict[str, str] = {}

    def __init__(
        self, username: str, password: str, brand: str, country: str | None = None
    ) -> None:
        if brand not in BRANDS.keys():
            raise ValueError(
                f"Invalid brand, must be one of {', '.join(BRANDS.keys())}"
            )
        if brand in COUNTRIES:
            # Only need to valid country, if the brand exists as a key in COUNTRIES
            if not country:
                raise RealmInvalid(f"{BRANDS[brand]} requires country to be passed")
            elif country not in COUNTRIES[brand].keys():
                raise RealmInvalid(
                    f"Invalid country, {BRANDS[brand]} only supports {', '.join(COUNTRIES[brand].keys())}"
                )

        self.username = username
        self.password = password
        self.country = country
        self.brand = brand

        self.aiohttp_session = get_http_client()

    async def __aenter__(self) -> MyPyllantAPI:
        try:
            await self.login()
        except Exception:
            await self.aiohttp_session.close()
            raise
        return self

    async def __aexit__(self, *args, **kwargs) -> None:
        if not self.aiohttp_session.closed:
            await self.aiohttp_session.close()

    async def login(self):
        code, code_verifier = await self.get_code()
        self.oauth_session = await self.get_token(code, code_verifier)
        logger.debug("Got session %s", self.oauth_session)
        self.set_session_expires()

    async def get_code(self):
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
        code = None
        try:
            async with self.aiohttp_session.get(
                AUTHENTICATE_URL.format(realm=get_realm(self.brand, self.country))
                + "?"
                + urlencode(auth_querystring),
                allow_redirects=False,
            ) as resp:
                login_html = await resp.text()
                if "Location" in resp.headers:
                    parsed_url = urlparse(resp.headers["Location"])
                    code = parse_qs(parsed_url.query).get("code")
        except ClientResponseError as e:
            raise LoginEndpointInvalid from e

        if not code:
            result = re.search(
                LOGIN_URL.format(realm=get_realm(self.brand, self.country))
                + r"\?([^\"]*)",
                login_html,
            )
            login_url = unescape(result.group()) if result else None
            if not login_url:
                raise AuthenticationFailed("Could not get login URL")

            logger.debug("Got login url %s", login_url)
            login_payload = {
                "username": self.username,
                "password": self.password,
                "credentialId": "",
            }
            # Obtaining the code
            async with self.aiohttp_session.post(
                login_url, data=login_payload, allow_redirects=False
            ) as resp:
                logger.debug("Got login response headers %s", resp.headers)
                if "Location" not in resp.headers:
                    raise AuthenticationFailed("Login failed")
                logger.debug(
                    f'Got location from authorize endpoint: {resp.headers["Location"]}'
                )
                parsed_url = urlparse(resp.headers["Location"])
                code = parse_qs(parsed_url.query)["code"]
        return code, code_verifier

    async def get_token(self, code, code_verifier):
        # Obtaining access token and refresh token
        token_payload = {
            "grant_type": "authorization_code",
            "client_id": "myvaillant",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": "enduservaillant.page.link://login",
        }

        async with self.aiohttp_session.post(
            TOKEN_URL.format(realm=get_realm(self.brand, self.country)),
            data=token_payload,
            raise_for_status=False,
        ) as resp:
            login_json = await resp.json()
            if resp.status >= 400:
                logger.error(
                    f"Could not log in, got status {resp.status} this response: {login_json}"
                )
                raise Exception(login_json)
            return login_json

    def set_session_expires(self):
        self.oauth_session_expires = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(seconds=self.oauth_session["expires_in"])
        logger.debug("Session expires in %s", self.oauth_session_expires)

    async def refresh_token(self):
        refresh_payload = {
            "refresh_token": self.oauth_session["refresh_token"],
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
        }
        async with self.aiohttp_session.post(
            TOKEN_URL.format(realm=get_realm(self.brand, self.country)),
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

    async def get_api_base(
        self,
        system: str | System | None = None,
        control_identifier: ControlIdentifier | str | None = None,
    ) -> str:
        if system and not control_identifier:
            control_identifier = await self.get_control_identifier(system)
        return get_api_base(control_identifier)

    async def get_system_api_base(
        self,
        system: str | System,
        control_identifier: ControlIdentifier | str | None = None,
    ) -> str:
        if not control_identifier:
            control_identifier = await self.get_control_identifier(system)
        return get_system_api_base(system, control_identifier)

    async def get_homes(self) -> AsyncIterator[Home]:
        """
        Returns configured homes and their system IDs

        Returns:
            An Async Iterator with all the configured `Home` objects for the logged-in user
        """
        async with self.aiohttp_session.get(
            f"{await self.get_api_base()}/homes", headers=self.get_authorized_headers()
        ) as homes_resp:
            for home_json in dict_to_snake_case(await homes_resp.json()):
                if "system_id" not in home_json or not home_json["system_id"]:
                    logger.warning(
                        "Skipping home because system_id is missing or empty: %s",
                        home_json,
                    )
                    continue
                timezone = await self.get_time_zone(home_json["system_id"])
                yield Home.from_api(timezone=timezone, **home_json)

    async def get_systems(
        self,
        include_connection_status: bool = False,
        include_diagnostic_trouble_codes: bool = False,
        include_rts: bool = False,
        include_mpc: bool = False,
        include_ambisense_rooms: bool = False,
    ) -> AsyncIterator[System]:
        """
        Returns an async generator of systems under control of the user

        Parameters:
            include_connection_status: Fetches connection status for each system
            include_diagnostic_trouble_codes: Fetches diagnostic trouble codes for each system and device
            include_rts: Fetches RTS data for each system, only supported on TLI controllers
            include_mpc: Fetches MPC data for each system, only supported on TLI controllers
            include_ambisense_rooms: Fetches Ambisense room data

        Returns:
            An Async Iterator with all the `System` objects

        Examples:
            >>> async for system in MyPyllantAPI(**kwargs).get_systems():
            >>>    print(system.water_pressure)
        """
        homes = self.get_homes()
        async for home in homes:
            control_identifier = await self.get_control_identifier(home.system_id)
            system_url = await self.get_system_api_base(home.system_id)
            current_system_url = (
                f"{await self.get_api_base()}/emf/v2/{home.system_id}/currentSystem"
            )

            async with self.aiohttp_session.get(
                system_url, headers=self.get_authorized_headers()
            ) as system_resp:
                system_raw = await system_resp.text()
                if control_identifier.is_vrc700:
                    system_raw = system_raw.replace("domesticHotWater", "dhw")
                    system_raw = system_raw.replace("DomesticHotWater", "Dhw")
                system_json = dict_to_snake_case(json.loads(system_raw))

            async with self.aiohttp_session.get(
                current_system_url, headers=self.get_authorized_headers()
            ) as current_system_resp:
                current_system_json = await current_system_resp.json()

            ambisense_capability = await self.get_ambisense_capability(home.system_id)

            system = System.from_api(
                brand=self.brand,
                home=home,
                timezone=home.timezone,
                control_identifier=control_identifier,
                connected=await self.get_connection_status(home.system_id)
                if include_connection_status
                else None,
                diagnostic_trouble_codes=await self.get_diagnostic_trouble_codes(
                    home.system_id
                )
                if include_diagnostic_trouble_codes
                else None,
                rts=await self.get_rts(home.system_id) if include_rts else {},
                mpc=await self.get_mpc(home.system_id) if include_mpc else {},
                current_system=dict_to_snake_case(current_system_json),
                ambisense_capability=ambisense_capability,
                ambisense_rooms=await self.get_ambisense_rooms(home.system_id)
                if include_ambisense_rooms and ambisense_capability
                else [],
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
        """
        Gets all energy data for a device

        Parameters:
            device: The device
            data_resolution: Which resolution level (i.e. day, month)
            data_from: Starting datetime
            data_to: End datetime

        """
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
                f"{await self.get_api_base()}/emf/v2/{device.system_id}/"
                f"devices/{device.device_uuid}/buckets?{urlencode(querystring)}"
            )
            async with self.aiohttp_session.get(
                device_buckets_url, headers=self.get_authorized_headers()
            ) as device_buckets_resp:
                device_buckets_json = await device_buckets_resp.json()
                yield DeviceData.from_api(
                    timezone=device.timezone,
                    device=device,
                    **dict_to_snake_case(device_buckets_json),
                )

    async def get_yearly_reports(
        self,
        system: System,
        year: int | None = None,
    ) -> AsyncIterator[SystemReport]:
        """
        Returns an async generator of systems under control of the user

        Parameters:
            system: The System object or system ID string
            year: The year of the report
        """
        url = f"{await self.get_api_base()}/emf/v2/{system.id}/report/{year}"
        async with self.aiohttp_session.get(
            url, headers=self.get_authorized_headers()
        ) as report_resp:
            reports_json = await report_resp.json()
            for report in dict_to_snake_case(reports_json):
                yield SystemReport.from_api(**report)

    async def set_zone_operating_mode(
        self,
        zone: Zone,
        mode: ZoneOperatingMode | ZoneOperatingModeVRC700 | str,
        operating_type: str = "heating",
    ):
        """
        Sets the operating mode for a zone

        Parameters:
            zone: The target zone
            mode: The target operating mode
            operating_type: Either heating or cooling
        """
        payload = {}
        operating_type = operating_type.lower()
        if operating_type not in ZONE_OPERATING_TYPES:
            raise ValueError(
                f"Invalid HVAC mode, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
            )
        if zone.control_identifier.is_vrc700:
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{operating_type}/operation-mode"
            mode_enum = ZoneOperatingModeVRC700  # type: ignore
        else:
            if operating_type == "cooling":
                url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/operation-mode"
                payload["type"] = operating_type.upper()
            else:
                url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/{operating_type}-operation-mode"
            mode_enum = ZoneOperatingMode  # type: ignore

        if mode not in mode_enum:
            raise ValueError(
                f"Invalid mode, must be one of {', '.join(mode_enum.__members__)}"
            )

        payload["operationMode"] = str(mode)

        await self.aiohttp_session.patch(
            url,
            json=payload,
            headers=self.get_authorized_headers(),
        )

        # zone.heating.operation_mode_heating or zone.cooling.operation_mode_cooling
        setattr(
            getattr(zone, operating_type),
            f"operation_mode_{operating_type}",
            mode_enum(mode),
        )
        return zone

    async def quick_veto_zone_temperature(
        self,
        zone: Zone,
        temperature: float,
        duration_hours: float | None = None,
        default_duration: float | None = None,
        veto_type: str = "heating",
    ):
        """
        Temporarily overwrites the desired temperature in a zone

        Parameters:
            zone: The target zone
            temperature: The target temperature
            duration_hours: Optional, sets overwrite for this many hours
            default_duration: Optional, falls back to this default duration if duration_hours is not given
            veto_type: Only supported on VRC700 controllers, either heating or cooling
        """
        if not default_duration:
            default_duration = DEFAULT_QUICK_VETO_DURATION
        if zone.control_identifier.is_vrc700:
            if veto_type not in ZONE_OPERATING_TYPES:
                raise ValueError(
                    f"Invalid veto type, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
                )
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{veto_type}/quick-veto"
        else:
            url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/quick-veto"

        if zone.current_special_function == ZoneCurrentSpecialFunction.QUICK_VETO:
            logger.debug(
                f"Patching quick veto for {zone.name} because it is already in quick veto mode"
            )
            payload = {
                "desiredRoomTemperatureSetpoint": temperature,
            }
            if duration_hours:
                payload["duration"] = duration_hours
            await self.aiohttp_session.patch(
                url,
                json=payload,
                headers=self.get_authorized_headers(),
            )
            zone.desired_room_temperature_setpoint = temperature
            return zone
        else:
            await self.aiohttp_session.post(
                url,
                json={
                    "desiredRoomTemperatureSetpoint": temperature,
                    "duration": duration_hours if duration_hours else default_duration,
                },
                headers=self.get_authorized_headers(),
            )
            zone.desired_room_temperature_setpoint = temperature
            zone.quick_veto_start_date_time = datetime.datetime.now(zone.timezone)
            zone.quick_veto_end_date_time = datetime.datetime.now(
                zone.timezone
            ) + datetime.timedelta(hours=(duration_hours or default_duration))
            return zone

    async def quick_veto_zone_duration(
        self,
        zone: Zone,
        duration_hours: float,
        veto_type: str = "heating",
    ):
        """
        Updates the quick veto duration

        Parameters:
            zone: The target zone
            duration_hours: Updates quick veto duration (in hours)
            veto_type: Only supported on VRC700 controllers, either heating or cooling
        """
        if zone.control_identifier.is_vrc700:
            if veto_type not in ZONE_OPERATING_TYPES:
                raise ValueError(
                    f"Invalid veto type, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
                )
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{veto_type}/quick-veto"
        else:
            url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/quick-veto"

        await self.aiohttp_session.patch(
            url,
            json={"duration": duration_hours},
            headers=self.get_authorized_headers(),
        )
        zone.quick_veto_end_date_time = datetime.datetime.now(
            zone.timezone
        ) + datetime.timedelta(hours=duration_hours)
        return zone

    async def set_time_program_temperature(
        self,
        zone: Zone,
        program_type: str,
        temperature: float,
        update_similar_to_dow: str | None = None,
    ):
        logger.debug(f"Setting time program temp {zone.name}")

        if program_type not in ZoneTimeProgramType:
            raise ValueError(
                "Type must be either heating or cooling, not %s", program_type
            )

        if not zone.heating.time_program_heating:
            raise ValueError(
                "There is no time program set, temperature can't be updated",
                program_type,
            )

        time_program = zone.heating.time_program_heating
        time_program.set_setpoint(temperature, update_similar_to_dow)
        return await self.set_zone_time_program(zone, program_type, time_program)

    async def set_manual_mode_setpoint(
        self,
        zone: Zone,
        temperature: float,
        setpoint_type: str = "heating",
    ):
        """
        Sets the desired temperature when in manual mode

        Parameters:
            zone: The target zone
            temperature: The target temperature
            setpoint_type: Either heating or cooling
        """
        logger.debug("Setting manual mode setpoint for %s", zone.name)
        setpoint_type = setpoint_type.lower()
        if setpoint_type not in ZONE_OPERATING_TYPES:
            raise ValueError(
                f"Invalid veto type, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
            )
        payload: dict[str, Any] = {
            "setpoint": temperature,
        }
        if zone.control_identifier.is_vrc700:
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{setpoint_type}/manual-mode-setpoint"

        else:
            url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/manual-mode-setpoint"
            payload["type"] = setpoint_type.upper()
        await self.aiohttp_session.patch(
            url,
            json=payload,
            headers=self.get_authorized_headers(),
        )
        # zone.heating.manual_mode_setpoint_heating or zone.cooling.manual_mode_setpoint_cooling
        setattr(
            getattr(zone, setpoint_type.lower()),
            f"manual_mode_setpoint_{setpoint_type}",
            temperature,
        )

        if (
            setpoint_type == "cooling"
            and zone.cooling
            and zone.cooling.operation_mode_cooling == ZoneOperatingMode.MANUAL
        ):
            zone.desired_room_temperature_setpoint_cooling = temperature

        return zone

    async def set_time_controlled_cooling_setpoint(
        self,
        zone: Zone,
        temperature: float,
    ):
        logger.debug("Setting time controlled setpoint for cooling on %s", zone.name)
        if zone.control_identifier.is_vrc700:
            raise ValueError(
                "Time controlled cooling setpoint is not supported on VRC700 controllers"
            )

        payload: dict[str, Any] = {
            "setpoint": temperature,
        }
        await self.aiohttp_session.patch(
            f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/setpoint-cooling",
            json=payload,
            headers=self.get_authorized_headers(),
        )
        if zone.cooling:
            if zone.cooling.operation_mode_cooling == ZoneOperatingMode.TIME_CONTROLLED:
                zone.desired_room_temperature_setpoint_cooling = temperature
            zone.cooling.setpoint_cooling = temperature
        return zone

    async def cancel_quick_veto_zone_temperature(
        self, zone: Zone, veto_type: str = "heating"
    ):
        """
        Cancels a previously set quick veto in a zone

        Parameters:
            zone: The target zone
            veto_type: Only supported on VRC700 controllers, either heating or cooling
        """
        if zone.control_identifier.is_vrc700:
            if veto_type not in ZONE_OPERATING_TYPES:
                raise ValueError(
                    f"Invalid veto type, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
                )
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{veto_type}/quick-veto"
        else:
            url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/quick-veto"

        await self.aiohttp_session.delete(url, headers=self.get_authorized_headers())
        zone.quick_veto_start_date_time = None
        zone.quick_veto_end_date_time = None
        zone.current_special_function = ZoneCurrentSpecialFunction.NONE
        return zone

    async def set_set_back_temperature(
        self, zone: Zone, temperature: float, setback_type: str = "heating"
    ):
        """
        Sets the temperature that a zone gets lowered to in away mode

        Parameters:
            zone: The target zone
            temperature: The setback temperature
            setback_type: Only supported on VRC700 controllers, either heating or cooling
        """
        if zone.control_identifier.is_vrc700:
            if setback_type not in ZONE_OPERATING_TYPES:
                raise ValueError(
                    f"Invalid setback type, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
                )
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{setback_type}/set-back-temperature"
        else:
            url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/set-back-temperature"
        await self.aiohttp_session.patch(
            url,
            json={"setBackTemperature": temperature},
            headers=self.get_authorized_headers(),
        )
        # TODO: What to do with cooling?
        if setback_type == "heating":
            zone.heating.set_back_temperature = temperature
        return zone

    async def set_zone_time_program(
        self,
        zone: Zone,
        program_type: str,
        time_program: ZoneTimeProgram,
        setback_type: str = "heating",
    ):
        """
        Sets the temperature that a zone gets lowered to in away mode

        Parameters:
            zone: The target zone
            program_type: Which program to set
            time_program: The time schedule
            setback_type: Only supported on VRC700 controllers, either heating or cooling
        """
        if program_type not in ZoneTimeProgramType:
            raise ValueError(
                "Type must be either heating or cooling, not %s", program_type
            )
        if zone.control_identifier.is_vrc700:
            if setback_type not in ZONE_OPERATING_TYPES:
                raise ValueError(
                    f"Invalid veto type, must be one of {', '.join(ZONE_OPERATING_TYPES)}"
                )
            url = f"{await self.get_system_api_base(zone.system_id)}/zone/{zone.index}/{setback_type}/time-windows"
        else:
            url = f"{await self.get_system_api_base(zone.system_id)}/zones/{zone.index}/time-windows"
        data = asdict(time_program)
        data["type"] = program_type
        del data["meta_info"]
        await self.aiohttp_session.patch(
            url,
            json=dict_to_camel_case(data),
            headers=self.get_authorized_headers(),
        )

        # zone.heating.time_program_heating = time_program or zone.cooling.time_program_cooling = time_program
        setattr(
            getattr(zone, setback_type), f"time_program_{setback_type}", time_program
        )
        return zone

    async def set_holiday(
        self,
        system: System,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
        setpoint: float | None = None,
    ):
        """
        Sets away mode / holiday mode on a system

        Parameters:
            system: The target system
            start: Optional, datetime when the system goes into away mode. Defaults to now
            end: Optional, datetime when away mode should end. Defaults to one year from now
            setpoint: Optional, setpoint temperature during holiday, only supported on VRC700 controllers
        """
        start, end = get_default_holiday_dates(start, end, system.timezone)
        logger.debug(
            "Setting holiday mode for system %s to %s - %s", system.id, start, end
        )
        if not start <= end:
            raise ValueError("Start of holiday mode must be before end")

        data = {
            "startDateTime": datetime_format(start, with_microseconds=True),
            "endDateTime": datetime_format(end, with_microseconds=True),
        }

        if system.control_identifier.is_vrc700:
            url = f"{await self.get_system_api_base(system.id)}/holiday"
            if setpoint is None:
                raise ValueError("setpoint is required on this controller")
            data["setpoint"] = setpoint  # type: ignore
        else:
            url = f"{await self.get_system_api_base(system.id)}/away-mode"
            if setpoint is not None:
                raise ValueError("setpoint is not supported on this controller")

        await self.aiohttp_session.post(
            url, json=data, headers=self.get_authorized_headers()
        )
        for zone in system.zones:
            zone.current_special_function = ZoneCurrentSpecialFunction.HOLIDAY
            zone.general.holiday_start_date_time = start
            zone.general.holiday_end_date_time = end
        return system

    async def cancel_holiday(self, system: System):
        """
        Cancels a previously set away mode / holiday mode on a system

        Parameters:
            system: The target system
        """
        if system.control_identifier.is_vrc700:
            url = f"{await self.get_system_api_base(system.id)}/holiday"
        else:
            url = f"{await self.get_system_api_base(system.id)}/away-mode"

        if system.zones and system.zones[0].general.holiday_start_in_future:
            # For some reason cancelling holidays in the future doesn't work, but setting a past value does
            default_holiday = datetime.datetime(2019, 1, 1, 0, 0, 0)
            await self.set_holiday(system, start=default_holiday, end=default_holiday)
        else:
            await self.aiohttp_session.delete(
                url, headers=self.get_authorized_headers()
            )
        for zone in system.zones:
            zone.current_special_function = ZoneCurrentSpecialFunction.NONE
            zone.general.holiday_start_date_time = None
            zone.general.holiday_end_date_time = None
        return system

    async def set_cooling_for_days(
        self,
        system: System,
        start: datetime.datetime | None = None,
        end: datetime.datetime | None = None,
    ):
        if system.control_identifier.is_vrc700:
            raise ValueError("Not supported on VRC700 controllers")

        start, end = get_default_holiday_dates(start, end, system.timezone)

        logger.debug(
            "Setting cooling for days on system %s to %s - %s", system.id, start, end
        )
        if not start <= end:
            raise ValueError("Start of holiday mode must be before end")

        data = {
            "startDateTime": datetime_format(start, with_microseconds=True),
            "endDateTime": datetime_format(end, with_microseconds=True),
        }

        await self.aiohttp_session.post(
            f"{await self.get_system_api_base(system.id)}/cooling-for-days",
            json=data,
            headers=self.get_authorized_headers(),
        )

        system.configuration["system"]["manual_cooling_start_date"] = datetime_format(
            start
        )
        system.configuration["system"]["manual_cooling_end_date"] = datetime_format(end)
        return system

    async def cancel_cooling_for_days(self, system: System):
        if system.control_identifier.is_vrc700:
            raise ValueError("Not supported on VRC700 controllers")

        await self.aiohttp_session.delete(
            f"{await self.get_system_api_base(system.id)}/cooling-for-days",
            headers=self.get_authorized_headers(),
        )
        system.configuration["system"]["manual_cooling_start_date"] = None
        system.configuration["system"]["manual_cooling_end_date"] = None
        return system

    async def set_ventilation_boost(
        self,
        system: System,
    ):
        if system.control_identifier.is_vrc700:
            raise ValueError("Not supported on VRC700 controllers")

        await self.aiohttp_session.post(
            f"{await self.get_system_api_base(system.id)}/ventilation-boost",
            json={},
            headers=self.get_authorized_headers(),
        )

        for zone in system.zones:
            zone.current_special_function = ZoneCurrentSpecialFunction.VENTILATION_BOOST
        return system

    async def cancel_ventilation_boost(self, system: System):
        if system.control_identifier.is_vrc700:
            raise ValueError("Not supported on VRC700 controllers")

        await self.aiohttp_session.delete(
            f"{await self.get_system_api_base(system.id)}/ventilation-boost",
            headers=self.get_authorized_headers(),
        )

        # TODO: Need the switch to the right previous special function
        for zone in system.zones:
            zone.current_special_function = ZoneCurrentSpecialFunction.NONE
        return system

    async def set_domestic_hot_water_temperature(
        self, domestic_hot_water: DomesticHotWater, temperature: int | float
    ):
        """
        Sets the desired hot water temperature

        Parameters:
            domestic_hot_water: The water heater
            temperature: The desired temperature, only whole numbers are supported by the API, floats get rounded
        """
        if isinstance(temperature, float):
            logger.warning("Domestic hot water can only be set to whole numbers")
            temperature = int(round(temperature, 0))
        url = (
            f"{await self.get_system_api_base(domestic_hot_water.system_id)}"
            f"/domestic-hot-water/{domestic_hot_water.index}/temperature"
        )
        await self.aiohttp_session.patch(
            url, json={"setpoint": temperature}, headers=self.get_authorized_headers()
        )
        domestic_hot_water.tapping_setpoint = temperature
        return domestic_hot_water

    async def boost_domestic_hot_water(self, domestic_hot_water: DomesticHotWater):
        """
        Temporarily boosts hot water temperature

        Parameters:
            domestic_hot_water: The water heater
        """
        url = (
            f"{await self.get_system_api_base(domestic_hot_water.system_id)}"
            f"/domestic-hot-water/{domestic_hot_water.index}/boost"
        )
        await self.aiohttp_session.post(
            url, json={}, headers=self.get_authorized_headers()
        )
        domestic_hot_water.current_special_function = (
            DHWCurrentSpecialFunction.CYLINDER_BOOST
        )
        return domestic_hot_water

    async def cancel_hot_water_boost(self, domestic_hot_water: DomesticHotWater):
        """
        Cancels hot water boost

        Parameters:
            domestic_hot_water: The water heater
        """
        url = (
            f"{await self.get_system_api_base(domestic_hot_water.system_id)}"
            f"/domestic-hot-water/{domestic_hot_water.index}/boost"
        )
        await self.aiohttp_session.delete(url, headers=self.get_authorized_headers())
        domestic_hot_water.current_special_function = DHWCurrentSpecialFunction.REGULAR
        return domestic_hot_water

    async def set_domestic_hot_water_operation_mode(
        self,
        domestic_hot_water: DomesticHotWater,
        mode: DHWOperationMode | DHWOperationModeVRC700 | str,
    ):
        """
        Sets the operation mode for water heating

        Parameters:
            domestic_hot_water: The water heater
            mode: The operation mode
        """
        url = (
            f"{await self.get_system_api_base(domestic_hot_water.system_id)}/domestic-hot-water/"
            f"{domestic_hot_water.index}/operation-mode"
        )
        await self.aiohttp_session.patch(
            url,
            json={"operationMode": str(mode)},
            headers=self.get_authorized_headers(),
        )

        if isinstance(mode, str):
            if domestic_hot_water.control_identifier.is_vrc700:
                mode = DHWOperationModeVRC700(mode)
            else:
                mode = DHWOperationMode(mode)
        domestic_hot_water.operation_mode_dhw = mode
        return domestic_hot_water

    async def set_domestic_hot_water_time_program(
        self, domestic_hot_water: DomesticHotWater, time_program: DHWTimeProgram
    ):
        """
        Sets the schedule for heating water

        Parameters:
            domestic_hot_water: The water heater
            time_program: The schedule
        """
        url = (
            f"{await self.get_system_api_base(domestic_hot_water.system_id)}"
            f"/domestic-hot-water/{domestic_hot_water.index}/time-windows"
        )
        data = asdict(time_program)
        del data["meta_info"]
        await self.aiohttp_session.patch(
            url,
            json=dict_to_camel_case(data),
            headers=self.get_authorized_headers(),
        )
        domestic_hot_water.time_program_dhw = time_program
        return domestic_hot_water

    async def set_domestic_hot_water_circulation_time_program(
        self, domestic_hot_water: DomesticHotWater, time_program: DHWTimeProgram
    ):
        """
        Sets the schedule for the water circulation pump

        Parameters:
            domestic_hot_water: The water heater
            time_program: The schedule
        """
        url = (
            f"{await self.get_system_api_base(domestic_hot_water.system_id)}"
            f"/domestic-hot-water/{domestic_hot_water.index}/circulation-pump-time-windows"
        )
        data = asdict(time_program)
        del data["meta_info"]
        await self.aiohttp_session.patch(
            url,
            json=dict_to_camel_case(data),
            headers=self.get_authorized_headers(),
        )
        domestic_hot_water.time_program_circulation_pump = time_program
        return domestic_hot_water

    async def set_ventilation_operation_mode(
        self,
        ventilation: Ventilation,
        mode: VentilationOperationMode | VentilationOperationModeVRC700,
    ):
        """
        Sets the operation mode for a ventilation device

        Parameters:
            ventilation: The ventilation device
            mode: The operation mode
        """
        url = (
            f"{await self.get_system_api_base(ventilation.system_id)}"
            f"/ventilation/{ventilation.index}/operation-mode"
        )
        await self.aiohttp_session.patch(
            url,
            json={
                "operationMode": str(mode),
            },
            headers=self.get_authorized_headers(),
        )
        ventilation.operation_mode_ventilation = mode
        return ventilation

    async def set_ventilation_fan_stage(
        self,
        ventilation: Ventilation,
        maximum_fan_stage: int,
        fan_stage_type: VentilationFanStageType,
    ):
        """
        Sets the maximum fan stage for a stage type

        Parameters:
            ventilation: The ventilation device
            maximum_fan_stage: The maximum fan speed, from 1-6
            fan_stage_type: The fan stage type (day or night)
        """
        url = (
            f"{await self.get_system_api_base(ventilation.system_id)}"
            f"/ventilation/{ventilation.index}/fan-stage"
        )
        await self.aiohttp_session.patch(
            url,
            json={
                "maximumFanStage": maximum_fan_stage,
                "type": str(fan_stage_type),
            },
            headers=self.get_authorized_headers(),
        )
        setattr(
            ventilation,
            f"maximum_{fan_stage_type.lower()}_fan_stage",
            maximum_fan_stage,
        )
        return ventilation

    async def get_connection_status(self, system: System | str) -> bool:
        """
        Returns whether the system is online

        Parameters:
            system: The System object or system ID string
        """
        url = (
            f"{await self.get_api_base()}/systems/"
            f"{get_system_id(system)}/meta-info/connection-status"
        )
        response = await self.aiohttp_session.get(
            url,
            headers=self.get_authorized_headers(),
        )
        try:
            return (await response.json())["connected"]
        except KeyError:
            logger.warning("Couldn't get connection status")
            return False

    async def get_control_identifier(self, system: System | str) -> ControlIdentifier:
        """
        The control identifier is used in the URL to request system information (usually `tli`)

        Parameters:
            system: The System object or system ID string
        """
        system_id = get_system_id(system)

        if system_id in self.control_identifiers:
            # We already have the control identifier cached
            control_identifier = self.control_identifiers[system_id]
        else:
            url = (
                f"{await self.get_api_base()}/systems/"
                f"{system_id}/meta-info/control-identifier"
            )
            response = await self.aiohttp_session.get(
                url,
                headers=self.get_authorized_headers(),
            )
            try:
                control_identifier = (await response.json())["controlIdentifier"]
                self.control_identifiers[system_id] = control_identifier
            except KeyError:
                logger.warning("Couldn't get control identifier")
                control_identifier = DEFAULT_CONTROL_IDENTIFIER

        return ControlIdentifier(control_identifier)

    async def get_time_zone(self, system: System | str) -> datetime.tzinfo | None:
        """
        Gets the configured timezone for a system

        Parameters:
            system: The System object or system ID string
        """
        url = (
            f"{await self.get_api_base()}/systems/"
            f"{get_system_id(system)}/meta-info/time-zone"
        )
        response = await self.aiohttp_session.get(
            url,
            headers=self.get_authorized_headers(),
        )
        try:
            tz = (await response.json())["timeZone"]
            return ZoneInfo(key=tz)
        except KeyError:
            logger.warning("Couldn't get timezone from API")
            return None

    async def get_diagnostic_trouble_codes(
        self, system: System | str
    ) -> list[dict] | None:
        """
        Returns a list of trouble codes by device

        Parameters:
            system: The System object or system ID string
        """
        url = (
            f"{await self.get_api_base()}/systems/"
            f"{get_system_id(system)}/diagnostic-trouble-codes"
        )
        try:
            response = await self.aiohttp_session.get(
                url,
                headers=self.get_authorized_headers(),
            )
        except ClientResponseError as e:
            logger.warning("Could not get diagnostic trouble codes", exc_info=e)
            return None
        result = await response.json()
        return dict_to_snake_case(result)

    async def get_rts(self, system: System | str) -> dict:
        """
        Gets RTS data, which contains on/off cycles and operation time

        Parameters:
            system: The System object or system ID string
        """
        url = f"{await self.get_api_base(system)}/rts/{get_system_id(system)}/devices"
        try:
            response = await self.aiohttp_session.get(
                url,
                headers=self.get_authorized_headers(),
            )
        except ClientResponseError as e:
            logger.warning("Could not get RTS data", exc_info=e)
            return {"statistics": []}
        result = await response.json()
        return dict_to_snake_case(result)

    async def get_mpc(self, system: System | str) -> dict:
        """
        Gets live power usage data per device

        Parameters:
            system: The System object or system ID string
        """
        url = f"{await self.get_api_base(system)}/hem/{get_system_id(system)}/mpc"
        try:
            response = await self.aiohttp_session.get(
                url,
                headers=self.get_authorized_headers(),
            )
        except ClientResponseError as e:
            logger.warning("Could not get MPC data", exc_info=e)
            return {"devices": []}
        result = await response.json()
        return dict_to_snake_case(result)

    async def get_ambisense_capability(self, system: System | str) -> bool:
        """
        Whether a system is ambisense capable

        Parameters:
            system: The System object or system ID string
        """
        url = f"{get_api_base()}/api/v1/ambisense/facilities/{get_system_id(system)}/capability"
        try:
            response = await self.aiohttp_session.get(
                url,
                headers=self.get_authorized_headers(),
            )
        except ClientResponseError as e:
            logger.warning("Could not get ambisense capability data", exc_info=e)
            return False
        result = await response.json()
        return dict_to_snake_case(result).get("rbr_capable", False)

    async def get_ambisense_rooms(self, system: System | str) -> list[dict]:
        """
        Whether a system is ambisense capable

        Parameters:
            system: The System object or system ID string
        """
        url = f"{get_api_base()}/api/v1/ambisense/facilities/{get_system_id(system)}/rooms"
        try:
            response = await self.aiohttp_session.get(
                url,
                headers=self.get_authorized_headers(),
            )
        except ClientResponseError as e:
            logger.warning("Could not get rooms data", exc_info=e)
            return []
        result = dict_to_snake_case(await response.json())
        for room in result:
            room["time_program"] = room.pop("timeprogram")
        return result

    async def set_ambisense_room_operation_mode(
        self,
        room: AmbisenseRoom,
        mode: AmbisenseRoomOperationMode | str,
    ) -> AmbisenseRoom:
        """
        Sets the operation mode for a room

        Parameters:
            room: The room
            mode: The operation mode
        """
        url = f"{await self.get_api_base()}/api/v1/ambisense/facilities/{room.system_id}/rooms/{room.room_index}/configuration/operation-mode"
        await self.aiohttp_session.put(
            url,
            json={"operationMode": str(mode).lower()},
            headers=self.get_authorized_headers(),
        )

        if isinstance(mode, str):
            room.room_configuration.operation_mode = AmbisenseRoomOperationMode(
                mode.upper()
            )
        else:
            room.room_configuration.operation_mode = mode
        return room

    async def quick_veto_ambisense_room(
        self,
        room: AmbisenseRoom,
        temperature: float,
        duration_minutes: int | None = None,
        default_duration: int | None = None,
    ) -> AmbisenseRoom:
        """
        Temporarily overwrites the desired temperature in a room

        Parameters:
            room: The target room
            temperature: The target temperature
            duration_minutes: Optional, sets overwrite for this many minutes
            default_duration: Optional, falls back to this default duration if duration_minutes is not given
        """
        if not default_duration:
            default_duration = (
                int(DEFAULT_QUICK_VETO_DURATION) * 60
            )  # duration for quick veto for room is in minutes

        if duration_minutes and duration_minutes < 30:
            raise ValueError("duration_minutes must be greater than 30")

        url = f"{await self.get_api_base()}/api/v1/ambisense/facilities/{room.system_id}/rooms/{room.room_index}/configuration/quick-veto"

        payload = {
            "temperatureSetpoint": temperature,
            "duration": duration_minutes or default_duration,
        }

        await self.aiohttp_session.put(
            url,
            json=payload,
            headers=self.get_authorized_headers(),
        )

        room.room_configuration.temperature_setpoint = temperature
        room.room_configuration.quick_veto_end_time = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(minutes=(duration_minutes or default_duration))
        return room

    async def cancel_quick_veto_ambisense_room(
        self, room: AmbisenseRoom
    ) -> AmbisenseRoom:
        """
        Cancels a previously set quick veto in a room

        Parameters:
            room: The target room
        """
        url = f"{await self.get_api_base()}/api/v1/ambisense/facilities/{room.system_id}/rooms/{room.room_index}/configuration/quick-veto"

        await self.aiohttp_session.delete(url, headers=self.get_authorized_headers())
        room.room_configuration.quick_veto_end_time = None
        return room

    async def set_ambisense_room_manual_mode_setpoint_temperature(
        self,
        room: AmbisenseRoom,
        temperature: float,
    ):
        """
        Sets the desired temperature when in manual mode. The temperature is only taken into account if the room is in
        MANUAL mode, otherwise it has no effect.

        Parameters:
            room: The target room
            temperature: The target temperature
        """
        logger.debug(
            "Setting manual mode setpoint temperature to %.1f for %s",
            temperature,
            room.name,
        )
        payload: dict[str, Any] = {
            "temperatureSetpoint": temperature,
        }
        url = f"{await self.get_api_base()}/api/v1/ambisense/facilities/{room.system_id}/rooms/{room.room_index}/configuration/temperature-setpoint"

        await self.aiohttp_session.put(
            url,
            json=payload,
            headers=self.get_authorized_headers(),
        )
        room.room_configuration.temperature_setpoint = temperature
        return room

    async def set_ambisense_room_time_program(
        self, room: AmbisenseRoom, time_program: RoomTimeProgram
    ) -> AmbisenseRoom:
        """
        Set time program for an ambisense room

        Parameters:
            room: The target room
            time_program: The new time program
        """
        url = f"{await self.get_api_base()}/api/v1/ambisense/facilities/{room.system_id}/rooms/{room.room_index}/timeprogram"

        data = asdict(time_program, dict_factory=RoomTimeProgram.dict_factory)
        payload = dict_to_camel_case(data)

        await self.aiohttp_session.put(
            url, json=payload, headers=self.get_authorized_headers()
        )
        room.time_program = time_program
        return room
