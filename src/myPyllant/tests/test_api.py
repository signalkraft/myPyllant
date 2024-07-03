import logging
from datetime import datetime, timedelta, tzinfo, timezone

import pytest
from freezegun import freeze_time

from ..api import MyPyllantAPI
from ..http_client import RealmInvalid
from ..models import (
    Device,
    DeviceData,
    DeviceDataBucket,
    Home,
    System,
    Zone,
    BaseTimeProgram,
)
from ..enums import (
    ZoneCurrentSpecialFunction,
    ZoneOperatingMode,
    ZoneOperatingModeVRC700,
    ControlIdentifier,
    AmbisenseRoomOperationMode,
)
from .generate_test_data import DATA_DIR
from .utils import list_test_data, load_test_data
from ..const import DEFAULT_QUICK_VETO_DURATION
from ..utils import datetime_format


async def test_login_vaillant(mypyllant_aioresponses) -> None:
    with mypyllant_aioresponses() as _:
        async with MyPyllantAPI(
            "test@example.com", "test", "vaillant", "germany"
        ) as mocked_api:
            assert isinstance(mocked_api.oauth_session_expires, datetime)
            assert mocked_api.oauth_session_expires > datetime.now(timezone.utc)
            assert mocked_api.access_token == "access_token"
            assert "Authorization" in mocked_api.get_authorized_headers()


async def test_login_bulex(mypyllant_aioresponses) -> None:
    with mypyllant_aioresponses() as _:
        async with MyPyllantAPI(
            "test@example.com", "test", "bulex", None
        ) as mocked_api:
            assert isinstance(mocked_api.oauth_session_expires, datetime)
            assert mocked_api.oauth_session_expires > datetime.now(timezone.utc)
            assert mocked_api.access_token == "access_token"
            assert "Authorization" in mocked_api.get_authorized_headers()


async def test_login_invalid_country(mypyllant_aioresponses) -> None:
    with pytest.raises(RealmInvalid):
        MyPyllantAPI("test@example.com", "test", "sdbg", "germany")


async def test_login_country_missing(mypyllant_aioresponses) -> None:
    with pytest.raises(RealmInvalid):
        MyPyllantAPI("test@example.com", "test", "sdbg")


async def test_refresh_token(mypyllant_aioresponses, mocked_api) -> None:
    with mypyllant_aioresponses() as _:
        with freeze_time(datetime.now(timezone.utc) + timedelta(hours=1)):
            await mocked_api.refresh_token()
            session_expires = mocked_api.oauth_session_expires
        assert session_expires - datetime.now(timezone.utc) > timedelta(hours=1)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_systems(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())

        assert isinstance(system, System), "Expected System return type"
        assert isinstance(system.brand, str)
        assert isinstance(system.brand_name, str)
        assert isinstance(system.outdoor_temperature, (float | None))
        assert isinstance(system.outdoor_temperature_average_24h, (float | None))
        assert isinstance(system.water_pressure, float)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_homes(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        home = await anext(mocked_api.get_homes())

        assert isinstance(home, Home), "Expected Home return type"
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_meta_info(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        status = await mocked_api.get_connection_status(system)
        assert isinstance(status, bool)
        time_zone = await mocked_api.get_time_zone(system)
        assert isinstance(time_zone, tzinfo)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_meta_info_system_id(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        control_identifier = await mocked_api.get_control_identifier(system.id)
        assert isinstance(control_identifier, ControlIdentifier)
        status = await mocked_api.get_connection_status(system.id)
        assert isinstance(status, bool)
        time_zone = await mocked_api.get_time_zone(system.id)
        assert isinstance(time_zone, tzinfo)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_devices(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())

        expected = 0
        for test_key, item in test_data.items():
            if "current_system" not in item or test_key != system.id:
                continue
            for device_key, device in item["current_system"].items():
                if (
                    isinstance(device, list)
                    and device_key == "secondary_heat_generators"
                ):
                    expected += len(device)
                if isinstance(device, dict) and "device_uuid" in device:
                    expected += 1

        assert len(system.devices) == expected

        if len(system.devices) > 0:
            device = system.devices[0]
            assert isinstance(device, Device)
            assert isinstance(device.name_display, str)
            assert isinstance(device.brand, str)
            assert isinstance(device.brand_name, str)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_device_data(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        if len(system.devices) > 0:
            device = system.devices[0]
            device_data = await anext(mocked_api.get_data_by_device(device))
            assert isinstance(device_data, DeviceData)
            assert isinstance(device_data.data[0], DeviceDataBucket)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_quick_veto(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        zone: Zone = system.zones[0]
        # Activating quick veto
        zone.current_special_function = ZoneCurrentSpecialFunction.NONE
        await mocked_api.quick_veto_zone_temperature(zone, 20.0)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["desiredRoomTemperatureSetpoint"] == 20.0
        assert request.kwargs["json"]["duration"] == DEFAULT_QUICK_VETO_DURATION

        # Changing quick veto temperature
        zone.current_special_function = ZoneCurrentSpecialFunction.QUICK_VETO
        await mocked_api.quick_veto_zone_temperature(zone, 20.0)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["desiredRoomTemperatureSetpoint"] == 20.0
        assert "duration" not in request.kwargs["json"]
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_holiday_without_dates(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        now = datetime.now(system.timezone)
        with freeze_time(now):
            setpoint = None
            if system.control_identifier.is_vrc700:
                setpoint = 10.0
            await mocked_api.set_holiday(system, setpoint=setpoint)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["startDateTime"] == datetime_format(
            now, with_microseconds=True
        )
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_holiday_with_dates(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        now = datetime.now(system.timezone)
        with freeze_time(now):
            start = now + timedelta(days=1)
            end = now + timedelta(days=7)
            setpoint = None
            if system.control_identifier.is_vrc700:
                setpoint = 10.0
            await mocked_api.set_holiday(system, start, end, setpoint)
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["startDateTime"] == datetime_format(
            start, with_microseconds=True
        )
        assert request.kwargs["json"]["endDateTime"] == datetime_format(
            end, with_microseconds=True
        )
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_holiday_wrong_dates(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        start = datetime.now(system.timezone) + timedelta(days=1)
        end = start - timedelta(days=7)
        with pytest.raises(ValueError):
            await mocked_api.set_holiday(system, start, end)
        await mocked_api.aiohttp_session.close()


@pytest.mark.parametrize("test_data", list_test_data())
async def test_dhw_setpoint(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, test_data
) -> None:
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        if not system.domestic_hot_water:
            return
        await mocked_api.set_domestic_hot_water_temperature(
            system.domestic_hot_water[0], 60
        )
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["setpoint"] == 60
        await mocked_api.aiohttp_session.close()


async def test_no_system(mypyllant_aioresponses, mocked_api: MyPyllantAPI) -> None:
    test_data = load_test_data(DATA_DIR / "no_system")
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        assert system.outdoor_temperature == 15.5625
        assert system.water_pressure == 1.0
        await mocked_api.aiohttp_session.close()


async def test_vrc700_operating_mode(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data = load_test_data(DATA_DIR / "vrc700")
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        assert isinstance(
            system.zones[0].heating.operation_mode_heating,
            ZoneOperatingModeVRC700,
        )

        await mocked_api.set_zone_operating_mode(
            system.zones[0], ZoneOperatingModeVRC700.AUTO
        )
        request = list(aio.requests.values())[-1][0]
        request_url = list(aio.requests.keys())[-1][1]
        assert str(request_url).endswith("heating/operation-mode")
        assert request.kwargs["json"]["operationMode"] == "AUTO"

        with pytest.raises(ValueError):
            await mocked_api.set_zone_operating_mode(
                system.zones[0], ZoneOperatingMode.MANUAL
            )
        await mocked_api.aiohttp_session.close()


async def test_vrc700_holiday(mypyllant_aioresponses, mocked_api: MyPyllantAPI) -> None:
    test_data = load_test_data(DATA_DIR / "vrc700")
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems())
        await mocked_api.set_holiday(
            system,
            datetime.now(system.timezone),
            datetime.now(system.timezone) + timedelta(days=1),
            10.0,
        )
        request = list(aio.requests.values())[-1][0]
        request_url = list(aio.requests.keys())[-1][1]
        assert str(request_url).endswith("/holiday")
        assert request.kwargs["json"]["setpoint"] == 10.0

        await mocked_api.aiohttp_session.close()


async def test_home_without_system(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI, caplog
) -> None:
    test_data = {
        "homes": [
            {
                "homeName": "42f9e5b2390e8d5647494720044a7d20a3f2ee70",
                "serialNumber": "e78edc21e57ac18f264334da843589f8330deb0e",
                "systemId": None,
                "productMetadata": {
                    "productType": "VR921",
                    "productionYear": "22",
                    "productionWeek": "07",
                    "articleNumber": "0020260965",
                },
                "state": "CLAIMED",
                "migrationState": "FINISHED",
                "firmware": {
                    "version": "0357.40.33",
                    "updateEnabled": True,
                    "updateRequired": False,
                },
                "nomenclature": "VR 921",
                "cag": False,
                "countryCode": "BE",
                "productInformation": "VR921",
                "firmwareVersion": "0357.40.33",
            }
        ]
    }
    with mypyllant_aioresponses(test_data) as _:
        with caplog.at_level(logging.WARNING):
            async for _ in mocked_api.get_systems():
                raise AssertionError("Expected no system")
    assert "Skipping home because system_id is missing or empty" in caplog.text
    await mocked_api.aiohttp_session.close()


async def test_get_ambisense_rooms(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data = load_test_data(DATA_DIR / "ambisense")
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))
        assert len(system.ambisense_rooms) == 4

        await mocked_api.get_ambisense_rooms(system.id)

        request_url = list(aio.requests.keys())[-1][1]
        assert str(request_url).endswith("/rooms")

    test_data = load_test_data(DATA_DIR / "ambisense2.yaml")
    with mypyllant_aioresponses(test_data) as aio:
        system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))
        assert len(system.ambisense_rooms) == 6
    await mocked_api.aiohttp_session.close()


async def test_set_ambisense_room_operation_mode(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data_files = ["ambisense", "ambisense2.yaml"]
    for f in test_data_files:
        test_data = load_test_data(DATA_DIR / f)
        with mypyllant_aioresponses(test_data) as aio:
            system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))

            await mocked_api.set_ambisense_room_operation_mode(
                system.ambisense_rooms[0], AmbisenseRoomOperationMode.OFF
            )

            request = list(aio.requests.values())[-1][0]
            request_url = list(aio.requests.keys())[-1][1]
            assert str(request_url).endswith(
                f"/rooms/{system.ambisense_rooms[0].room_index}/configuration/operation-mode"
            )
            assert request.kwargs["json"]["operationMode"] == "off"

    await mocked_api.aiohttp_session.close()


async def test_set_ambisense_room_quick_veto(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data_files = ["ambisense", "ambisense2.yaml"]
    for f in test_data_files:
        test_data = load_test_data(DATA_DIR / f)
        with mypyllant_aioresponses(test_data) as aio:
            system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))

            new_room = await mocked_api.quick_veto_ambisense_room(
                system.ambisense_rooms[0], 22, 220
            )

            request = list(aio.requests.values())[-1][0]
            request_url = list(aio.requests.keys())[-1][1]
            assert str(request_url).endswith(
                f"/rooms/{system.ambisense_rooms[0].room_index}/configuration/quick-veto"
            )
            assert request.kwargs["json"]["temperatureSetpoint"] == 22
            assert request.kwargs["json"]["duration"] == 220

            assert new_room.room_configuration.quick_veto_end_time is not None

            with pytest.raises(ValueError):
                await mocked_api.quick_veto_ambisense_room(
                    system.ambisense_rooms[0], 22, 10
                )

    await mocked_api.aiohttp_session.close()


async def test_cancel_ambisense_room_quick_veto(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data_files = ["ambisense", "ambisense2.yaml"]
    for f in test_data_files:
        test_data = load_test_data(DATA_DIR / f)
        with mypyllant_aioresponses(test_data) as aio:
            system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))

            system.ambisense_rooms[
                0
            ].room_configuration.quick_veto_end_time = datetime.now()
            new_room = await mocked_api.cancel_quick_veto_ambisense_room(
                system.ambisense_rooms[0]
            )

            request_url = list(aio.requests.keys())[-1][1]
            assert str(request_url).endswith(
                f"/rooms/{system.ambisense_rooms[0].room_index}/configuration/quick-veto"
            )
            assert new_room.room_configuration.quick_veto_end_time is None

    await mocked_api.aiohttp_session.close()


async def test_set_ambisense_room_manual_mode_setpoint_temperature(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data_files = ["ambisense", "ambisense2.yaml"]
    for f in test_data_files:
        test_data = load_test_data(DATA_DIR / f)
        with mypyllant_aioresponses(test_data) as aio:
            system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))

            system.ambisense_rooms[
                0
            ].room_configuration.operation_mode = AmbisenseRoomOperationMode.MANUAL
            new_room = (
                await mocked_api.set_ambisense_room_manual_mode_setpoint_temperature(
                    system.ambisense_rooms[0], 10
                )
            )

            request_url = list(aio.requests.keys())[-1][1]
            assert str(request_url).endswith(
                f"/rooms/{system.ambisense_rooms[0].room_index}/configuration/temperature-setpoint"
            )
            assert new_room.room_configuration.temperature_setpoint == 10

    await mocked_api.aiohttp_session.close()


async def test_set_ambisense_room_time_program(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    test_data_files = ["ambisense", "ambisense2.yaml"]
    for f in test_data_files:
        test_data = load_test_data(DATA_DIR / f)
        with mypyllant_aioresponses(test_data) as aio:
            system = await anext(mocked_api.get_systems(include_ambisense_rooms=True))

            await mocked_api.set_ambisense_room_time_program(
                system.ambisense_rooms[0], system.ambisense_rooms[0].time_program
            )

            request_json = aio.requests[list(aio.requests.keys())[-1]][0][1]["json"]
            monday_slot = request_json["monday"][0]
            assert set(monday_slot.keys()) == {"startTime", "temperatureSetpoint"}
            assert set(request_json.keys()) == set(BaseTimeProgram.weekday_names())

            request_url = list(aio.requests.keys())[-1][1]
            assert str(request_url).endswith(
                f"/rooms/{system.ambisense_rooms[0].room_index}/timeprogram"
            )

    await mocked_api.aiohttp_session.close()
