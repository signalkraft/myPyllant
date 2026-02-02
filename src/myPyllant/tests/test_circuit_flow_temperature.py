from .generate_test_data import DATA_DIR
from .utils import load_test_data


async def test_current_circuit_flow_temperature_set(
    mypyllant_aioresponses, mocked_api
) -> None:
    test_data = load_test_data(DATA_DIR / "systemflow_and_energymanagerstate")
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        assert len(system.circuits) > 0
        assert system.circuits[0].current_circuit_flow_temperature == 27.875
    await mocked_api.aiohttp_session.close()


async def test_heating_circuit_flow_setpoint_set(
    mypyllant_aioresponses, mocked_api
) -> None:
    test_data = load_test_data(DATA_DIR / "systemflow_and_energymanagerstate")
    with mypyllant_aioresponses(test_data) as _:
        system = await anext(mocked_api.get_systems())
        assert len(system.circuits) > 0
        assert system.circuits[0].heating_circuit_flow_setpoint == 28.138395
    await mocked_api.aiohttp_session.close()
