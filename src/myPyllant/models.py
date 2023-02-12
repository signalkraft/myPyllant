from typing import Any, Dict, List
import datetime

from pydantic import BaseModel


class Zone(BaseModel):
    system_id: str
    name: str
    index: int
    active: bool
    current_room_temperature: float
    current_special_function: str
    desired_room_temperature_setpoint: float
    manual_mode_setpoint: float
    heating_operation_mode: str
    heating_state: str
    humidity: float
    set_back_temperature: float
    time_windows: dict


class Circuit(BaseModel):
    system_id: str
    index: int
    circuit_state: str
    current_circuit_flow_temperature: float
    heating_curve: float
    is_cooling_allowed: bool
    min_flow_temperature_setpoint: float
    mixer_circuit_type_external: str
    set_back_mode_enabled: bool
    zones: List = []


class DomesticHotWater(BaseModel):
    system_id: str
    index: int
    current_dhw_tank_temperature: float
    current_special_function: str
    max_set_point: float
    min_set_point: float
    operation_mode: str
    set_point: float
    time_windows: dict


class System(BaseModel):
    id: str
    status: Dict[str, bool]
    devices: List[Dict]
    current_system: Dict = {}
    system_configuration: Dict = {}
    system_control_state: Dict = {}
    gateway: Dict = {}
    has_ownership: bool
    zones: List[Zone] = []
    circuits: List[Circuit] = []
    domestic_hot_water: List[DomesticHotWater] = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        zones = self.system_control_state["control_state"]["zones"]
        circuits = self.system_control_state["control_state"]["circuits"]
        domestic_hot_water = self.system_control_state["control_state"][
            "domestic_hot_water"
        ]
        self.zones = [Zone(system_id=self.id, **z) for z in zones]
        self.circuits = [Circuit(system_id=self.id, **c) for c in circuits]
        self.domestic_hot_water = [
            DomesticHotWater(system_id=self.id, **d) for d in domestic_hot_water
        ]

    @property
    def outdoor_temperature(self):
        return self.system_control_state["control_state"]["general"][
            "outdoor_temperature"
        ]

    @property
    def water_pressure(self):
        return self.system_control_state["control_state"]["general"][
            "system_water_pressure"
        ]

    @property
    def mode(self):
        return self.system_control_state["control_state"]["general"]["system_mode"]


class Device(BaseModel):
    system: System
    device_uuid: str
    name: str = ""
    product_name: str
    diagnostic_trouble_codes: List = []
    properties: List = []
    ebus_id: str
    article_number: str
    device_serial_number: str
    device_type: str
    first_data: datetime.datetime
    last_data: datetime.datetime
    operational_data: dict = {}
    data: list = []
