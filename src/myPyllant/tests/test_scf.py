"""
Tests for the ``scf`` control identifier (Vaillant iQconnect generation, e.g. VR_NEEXT).

iQconnect systems report ``controlIdentifier == "scf"`` from
``/systems/{id}/meta-info/control-identifier``. Before ``scf`` was a member of the
``ControlIdentifier`` enum, ``ControlIdentifier("scf")`` raised ``ValueError`` in
``get_control_identifier()`` and aborted the whole data fetch. These tests lock in that
``scf`` resolves and that the URL helpers treat it like the generic (non-tli) base.

The ``data/scf`` fixture is a real capture from an iQconnect account (geoCOMPACT VWS 52/8.1
iQ, ``VR_NEEXT``), produced by ``tests/generate_test_data.py`` and anonymized by it - it
includes the ``scf_state.json`` state tree, so the tests below exercise the real shape rather
than a hand-written stub. They still skip themselves if no capture is present, so the suite
stays green for anyone who drops the fixture.
"""

import pytest

from ..api import MyPyllantAPI, get_api_base, get_system_api_base
from ..const import API_URL_BASE, SYSTEM_CONTROL_API_URL_BASE
from ..enums import ControlIdentifier
from .generate_test_data import DATA_DIR
from .utils import list_test_data, load_test_data

SCF_DATA_DIR = DATA_DIR / "scf"
requires_scf_state_data = pytest.mark.skipif(
    # The system id is a per-run salted hash, so match on the shape, not a fixed id
    not any(SCF_DATA_DIR.glob("*/scf_state.json")),
    reason=(
        "No captured scf state tree yet - run generate_test_data.py against an iQconnect "
        "account and commit the anonymized scf_state.json into tests/data/scf/"
    ),
)


def test_scf_is_a_valid_control_identifier() -> None:
    assert ControlIdentifier("scf") is ControlIdentifier.SCF
    assert ControlIdentifier.SCF.value == "scf"


def test_is_scf_property() -> None:
    assert ControlIdentifier.SCF.is_scf
    assert not ControlIdentifier.TLI.is_scf
    assert not ControlIdentifier.VRC700.is_scf
    # scf is its own identifier, not a flavour of the others
    assert not ControlIdentifier.SCF.is_vrc700
    assert not ControlIdentifier.SCF.is_unsupported


def test_scf_has_a_base_url() -> None:
    assert "scf" in API_URL_BASE
    assert get_api_base(ControlIdentifier.SCF) == API_URL_BASE["scf"]
    assert get_api_base("scf") == API_URL_BASE["scf"]


def test_scf_system_api_base_uses_generic_shape() -> None:
    # scf falls into the generic ``case _`` branch (like vrc700): plain /systems/{id},
    # no /tli suffix.
    system_id = "00000000-0000-0000-0000-000000000000"
    assert get_system_api_base(system_id, ControlIdentifier.SCF) == (
        f"{API_URL_BASE['scf']}/systems/{system_id}"
    )


async def test_scf_home_is_skipped_by_get_systems(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """An scf/iQconnect home has no aggregate System, so get_systems skips it (like an
    unsupported controller). Its state is served by system-control/v1 and handled by the
    consumer (the Home Assistant component), not by the System model here."""
    test_data = load_test_data(DATA_DIR / "scf")
    with mypyllant_aioresponses(test_data) as _:
        systems = [s async for s in mocked_api.get_systems()]
        await mocked_api.aiohttp_session.close()
    assert systems == []


@requires_scf_state_data
def test_scf_fixture_state_has_the_expected_sections() -> None:
    test_data = load_test_data(SCF_DATA_DIR)
    system_ids = [k for k in test_data if k not in ("_directory", "homes")]
    for system_id in system_ids:
        state = test_data[system_id]["scf_state"]
        data = state["data"]
        # At least one of the sections a consumer would walk must be present with real
        # leaves (value/metadata dicts), otherwise the fixture doesn't exercise anything.
        sections = (
            "systemParameters",
            "zoneSettings",
            "circuitSettings",
            "domesticHotWaterSettings",
        )
        assert any(s in data for s in sections)


@requires_scf_state_data
async def test_scf_state_is_served_from_fixture(
    mypyllant_aioresponses, mocked_api: MyPyllantAPI
) -> None:
    """Proves the test harness can replay a system-control/v1 URL at all - before this,
    _mypyllant_aioresponses.get_test_data() raised ValueError for any such URL."""
    test_data = load_test_data(SCF_DATA_DIR)
    system_ids = [k for k in test_data if k not in ("_directory", "homes")]
    with mypyllant_aioresponses(test_data):
        for system_id in system_ids:
            url = f"{SYSTEM_CONTROL_API_URL_BASE}/systems/{system_id}/state"
            async with mocked_api.aiohttp_session.get(
                url, headers=mocked_api.get_authorized_headers()
            ) as resp:
                assert (await resp.json()) == test_data[system_id]["scf_state"]
    await mocked_api.aiohttp_session.close()


def test_scf_data_dir_is_picked_up_by_list_test_data() -> None:
    """tests/data/scf/ is already picked up by every
    @pytest.mark.parametrize("test_data", list_test_data()) test in the suite
    (test_api.py, ...) - this documents that expectation; list_test_data() itself needs
    no scf-specific code."""
    dirs = {d["_directory"] for d in list_test_data()}
    assert str(SCF_DATA_DIR) in dirs
