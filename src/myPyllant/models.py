from collections.abc import Mapping
import datetime
from enum import Enum
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MyPyllantEnum(Enum):
    def __str__(self):
        """
        Return 'HOUR' instead of 'DeviceDataBucketResolution.HOUR'
        """
        return self.value

    @property
    def display_value(self):
        return self.value.replace("_", " ").title()


class DeviceDataBucketResolution(MyPyllantEnum):
    HOUR = "HOUR"
    DAY = "DAY"
    MONTH = "MONTH"


class ZoneHeatingOperatingMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class ZoneCurrentSpecialFunction(MyPyllantEnum):
    NONE = "NONE"
    QUICK_VETO = "QUICK_VETO"
    HOLIDAY = "HOLIDAY"


class ZoneHeatingState(MyPyllantEnum):
    IDLE = "IDLE"
    HEATING_UP = "HEATING_UP"


class DHWCurrentSpecialFunction(MyPyllantEnum):
    CYLINDER_BOOST = "CYLINDER_BOOST"
    REGULAR = "REGULAR"


class DHWOperationMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class Zone(BaseModel):
    system_id: str
    name: str
    index: int
    active: bool
    current_room_temperature: float
    current_special_function: ZoneCurrentSpecialFunction
    desired_room_temperature_setpoint: float
    manual_mode_setpoint: float
    heating_operation_mode: ZoneHeatingOperatingMode
    heating_state: ZoneHeatingState
    humidity: float | None
    set_back_temperature: float
    time_windows: dict


class Circuit(BaseModel):
    system_id: str
    index: int
    circuit_state: str
    current_circuit_flow_temperature: float
    heating_curve: float | None
    is_cooling_allowed: bool
    min_flow_temperature_setpoint: float | None
    mixer_circuit_type_external: str
    set_back_mode_enabled: bool
    zones: list = []


class DomesticHotWater(BaseModel):
    system_id: str
    index: int
    current_dhw_tank_temperature: float | None
    current_special_function: DHWCurrentSpecialFunction
    max_set_point: float
    min_set_point: float
    operation_mode: DHWOperationMode
    set_point: float
    time_windows: dict


class System(BaseModel):
    id: str
    status: dict[str, bool]
    devices: list[dict]
    current_system: dict = {}
    system_configuration: dict = {}
    system_control_state: dict = {}
    gateway: dict = {}
    has_ownership: bool
    zones: list[Zone] = []
    circuits: list[Circuit] = []
    domestic_hot_water: list[DomesticHotWater] = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.zones = [Zone(system_id=self.id, **z) for z in self._raw_zones]
        self.circuits = [Circuit(system_id=self.id, **c) for c in self._raw_circuits]
        self.domestic_hot_water = [
            DomesticHotWater(system_id=self.id, **d)
            for d in self._raw_domestic_hot_water
        ]

    @property
    def _raw_zones(self):
        try:
            return self.system_control_state["control_state"].get("zones", [])
        except KeyError as e:
            logger.info("Could not get zones from system control state", exc_info=e)
            return []

    @property
    def _raw_circuits(self):
        try:
            return self.system_control_state["control_state"].get("circuits", [])
        except KeyError as e:
            logger.info("Could not get circuits from system control state", exc_info=e)
            return []

    @property
    def _raw_domestic_hot_water(self):
        try:
            return self.system_control_state["control_state"].get(
                "domestic_hot_water", []
            )
        except KeyError as e:
            logger.info(
                "Could not get domestic hot water from system control state", exc_info=e
            )
            return []

    @property
    def outdoor_temperature(self):
        try:
            return self.system_control_state["control_state"]["general"][
                "outdoor_temperature"
            ]
        except KeyError as e:
            logger.info(
                "Could not get outdoor temperature from system control state",
                exc_info=e,
            )
            return None

    @property
    def status_online(self) -> bool | None:
        return self.status["online"] if "online" in self.status else None

    @property
    def status_error(self) -> bool | None:
        return self.status["error"] if "error" in self.status else None

    @property
    def water_pressure(self):
        try:
            return self.system_control_state["control_state"]["general"][
                "system_water_pressure"
            ]
        except KeyError as e:
            logger.info(
                "Could not get water pressure from system control state", exc_info=e
            )
            return None

    @property
    def mode(self):
        try:
            return self.system_control_state["control_state"]["general"]["system_mode"]
        except KeyError as e:
            logger.info("Could not get mode from system control state", exc_info=e)
            return None


class Device(BaseModel):
    system: System
    device_uuid: str
    name: str = ""
    product_name: str
    diagnostic_trouble_codes: list = []
    properties: list = []
    ebus_id: str
    article_number: str
    device_serial_number: str
    device_type: str
    first_data: datetime.datetime
    last_data: datetime.datetime
    operational_data: dict = {}
    data: list["DeviceData"] = []

    @property
    def name_display(self):
        return self.name if self.name else self.product_name.title()


class DeviceDataBucket(BaseModel):
    start_date: datetime.datetime
    end_date: datetime.datetime
    value: float


class DeviceData(BaseModel):
    def __init__(self, device: Device = None, **kwargs: Any) -> None:
        kwargs["data_from"] = kwargs.pop("from") if "from" in kwargs else None
        kwargs["data_to"] = kwargs.pop("to") if "to" in kwargs else None
        super().__init__(device=device, **kwargs)

    device: Device | None
    data_from: datetime.datetime | None
    data_to: datetime.datetime | None
    start_date: datetime.datetime | None
    end_date: datetime.datetime | None
    resolution: DeviceDataBucketResolution | None
    operation_mode: str
    energy_type: str | None
    value_type: str | None
    data: list[DeviceDataBucket] = []


Device.update_forward_refs()
