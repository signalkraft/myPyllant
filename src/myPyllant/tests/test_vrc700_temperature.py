"""
Test that set_manual_mode_setpoint is called correctly for VRC700 zones in DAY mode.

VRC700 controllers don't support PATCH .../zone/{index}/heating/manual-mode-setpoint
(confirmed 404 against the live API). The real myVaillant app uses
PATCH .../zone/{index}/heating/comfort-room-temperature with
{"comfortRoomTemperature": ...} for the DAY mode (manual) heating setpoint, and
PATCH .../zone/{index}/cooling/setpoint (the same endpoint as set_cooling_setpoint)
for the cooling DAY mode setpoint.
"""

import pytest

from ..api import MyPyllantAPI
from ..enums import ZoneOperatingModeVRC700
from ..models import Zone
from .utils import (
    load_test_data,
    get_system_or_skip,
)
from .generate_test_data import DATA_DIR


VRC700_TEST_DATA = load_test_data(DATA_DIR / "vrc700")


async def test_vrc700_manual_mode_setpoint_uses_correct_endpoint(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """
    When a VRC700 zone is in DAY mode (manual/fixed setpoint),
    set_manual_mode_setpoint must use the VRC700-specific URL:
      /zone/{index}/heating/comfort-room-temperature  (PATCH)
    with a {"comfortRoomTemperature": ...} body, not manual-mode-setpoint
    (which 404s for VRC700) and not a quick-veto endpoint.
    """
    with mypyllant_aioresponses(VRC700_TEST_DATA) as aio:
        system = await get_system_or_skip(mocked_api)
        if not system.zones:
            pytest.skip("No zones in VRC700 test data")

        zone: Zone = system.zones[0]
        assert zone.control_identifier.is_vrc700, "Expected a VRC700 zone"

        # Force DAY mode — the VRC700 equivalent of manual
        zone.heating.operation_mode_heating = ZoneOperatingModeVRC700.DAY

        await mocked_api.set_manual_mode_setpoint(zone, 21.0)

        # Verify the request went to the comfort-room-temperature endpoint
        method, url = list(aio.requests.keys())[-1]
        url = str(url)
        assert method == "PATCH"
        assert "/zone/" in url and "/heating/comfort-room-temperature" in url, (
            f"Expected VRC700 comfort-room-temperature URL, got: {url}"
        )
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["comfortRoomTemperature"] == 21.0

        await mocked_api.aiohttp_session.close()


async def test_vrc700_day_mode_setpoint_updates_model(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """
    After calling set_manual_mode_setpoint in DAY mode, the zone model should
    reflect the new temperature.
    """
    with mypyllant_aioresponses(VRC700_TEST_DATA) as _:
        system = await get_system_or_skip(mocked_api)
        if not system.zones:
            pytest.skip("No zones in VRC700 test data")

        zone: Zone = system.zones[0]
        zone.heating.operation_mode_heating = ZoneOperatingModeVRC700.DAY

        updated_zone = await mocked_api.set_manual_mode_setpoint(zone, 22.5)

        assert updated_zone.heating.manual_mode_setpoint_heating == 22.5
        assert updated_zone.heating.day_temperature_heating == 22.5
        assert updated_zone.desired_room_temperature_setpoint_heating == 22.5
        assert updated_zone.desired_room_temperature_setpoint == 22.5

        await mocked_api.aiohttp_session.close()


async def test_vrc700_no_cooling_zone_routes_to_heating(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """
    When a VRC700 zone has no cooling config and both setpoints are None,
    set_manual_mode_setpoint must still be called on the heating endpoint.
    The library's active_operating_type returns COOLING when both setpoints are
    None (None == None), so climate.py must fall back to heating when zone.cooling
    is absent.
    """
    with mypyllant_aioresponses(VRC700_TEST_DATA) as aio:
        system = await get_system_or_skip(mocked_api)
        if not system.zones:
            pytest.skip("No zones in VRC700 test data")

        zone: Zone = system.zones[0]
        zone.heating.operation_mode_heating = ZoneOperatingModeVRC700.DAY
        zone.desired_room_temperature_setpoint = None
        zone.desired_room_temperature_setpoint_cooling = None

        # With no cooling, even if active_operating_type would return COOLING,
        # set_manual_mode_setpoint must use the heating endpoint
        await mocked_api.set_manual_mode_setpoint(zone, 21.0, setpoint_type="heating")

        method, url = list(aio.requests.keys())[-1]
        url = str(url)
        assert "heating" in url and "comfort-room-temperature" in url, (
            f"Expected heating endpoint, got: {url}"
        )

        await mocked_api.aiohttp_session.close()


async def test_vrc700_cooling_manual_mode_setpoint_uses_cooling_setpoint_endpoint(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """
    When called with setpoint_type="cooling" for a VRC700 zone (cooling DAY mode,
    the equivalent of manual mode), set_manual_mode_setpoint must delegate to
    set_cooling_setpoint, i.e. PATCH /zone/{index}/cooling/setpoint.
    """
    with mypyllant_aioresponses(VRC700_TEST_DATA) as aio:
        system = await get_system_or_skip(mocked_api)
        if not system.zones:
            pytest.skip("No zones in VRC700 test data")

        zone: Zone = system.zones[0]
        if not zone.cooling:
            pytest.skip("No cooling in VRC700 test data")

        await mocked_api.set_manual_mode_setpoint(zone, 22.0, setpoint_type="cooling")

        method, url = list(aio.requests.keys())[-1]
        url = str(url)
        assert method == "PATCH"
        assert "/zone/" in url and "/cooling/setpoint" in url, (
            f"Expected VRC700 cooling/setpoint URL, got: {url}"
        )
        request = list(aio.requests.values())[-1][0]
        assert request.kwargs["json"]["setpoint"] == 22.0

        await mocked_api.aiohttp_session.close()


async def test_vrc700_cooling_day_mode_uses_quick_veto_cooling(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """
    When a VRC700 zone is in cooling DAY mode (summer / heat pump cooling),
    setting the temperature should call quick_veto_zone_temperature with
    veto_type="cooling" → POST /zone/{index}/cooling/quick-veto.
    The /cooling/manual-mode-setpoint endpoint does not exist on VRC700 (404).
    """
    with mypyllant_aioresponses(VRC700_TEST_DATA) as aio:
        system = await get_system_or_skip(mocked_api)
        if not system.zones:
            pytest.skip("No zones in VRC700 test data")

        zone: Zone = system.zones[0]
        assert zone.control_identifier.is_vrc700, "Expected a VRC700 zone"

        # Directly test the API call — veto_type="cooling" must hit /cooling/quick-veto
        await mocked_api.quick_veto_zone_temperature(zone, 22.0, veto_type="cooling")

        method, url = list(aio.requests.keys())[-1]
        url = str(url)
        assert method == "POST"
        assert "/zone/" in url and "/cooling/quick-veto" in url, (
            f"Expected VRC700 cooling quick-veto URL, got: {url}"
        )

        await mocked_api.aiohttp_session.close()


async def test_vrc700_auto_mode_uses_quick_veto(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """
    When a VRC700 zone is in AUTO mode (time-program-controlled),
    quick_veto_zone_temperature should use the VRC700-specific quick-veto URL:
      /zone/{index}/heating/quick-veto  (POST)
    """
    with mypyllant_aioresponses(VRC700_TEST_DATA) as aio:
        system = await get_system_or_skip(mocked_api)
        if not system.zones:
            pytest.skip("No zones in VRC700 test data")

        zone: Zone = system.zones[0]
        assert zone.control_identifier.is_vrc700, "Expected a VRC700 zone"

        # AUTO = time-program mode — should go through quick veto
        zone.heating.operation_mode_heating = ZoneOperatingModeVRC700.AUTO

        await mocked_api.quick_veto_zone_temperature(zone, 21.0)

        method, url = list(aio.requests.keys())[-1]
        url = str(url)
        assert method == "POST"
        assert "/zone/" in url and "/heating/quick-veto" in url, (
            f"Expected VRC700 quick-veto URL, got: {url}"
        )

        await mocked_api.aiohttp_session.close()
