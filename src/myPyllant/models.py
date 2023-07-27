import datetime
import logging
from collections.abc import Iterator
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from myPyllant.utils import datetime_parse

logger = logging.getLogger(__name__)


class MyPyllantEnum(Enum):
    def __str__(self):
        """
        Return 'HOUR' instead of 'DeviceDataBucketResolution.HOUR'
        """
        return self.value

    @property
    def display_value(self) -> str:
        return self.value.replace("_", " ").title()


class CircuitState(MyPyllantEnum):
    HEATING = "HEATING"
    COOLING = "COOLING"
    STANDBY = "STANDBY"


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
    COOLING_DOWN = "COOLING_DOWN"


class DHWCurrentSpecialFunction(MyPyllantEnum):
    CYLINDER_BOOST = "CYLINDER_BOOST"
    REGULAR = "REGULAR"


class DHWOperationMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class Claim(BaseModel):
    country_code: str
    nomenclature: str
    serial_number: str
    state: str
    system_id: str


class ZoneHeating(BaseModel):
    manual_mode_setpoint_heating: float
    operation_mode_heating: ZoneHeatingOperatingMode
    time_program_heating: dict
    set_back_temperature: float


class Zone(BaseModel):
    system_id: str
    general: dict
    index: int
    is_active: bool
    is_cooling_allowed: bool
    zone_binding: str
    current_room_temperature: float | None
    current_special_function: ZoneCurrentSpecialFunction
    desired_room_temperature_setpoint_heating: float | None
    desired_room_temperature_setpoint_cooling: float | None
    desired_room_temperature_setpoint: float | None
    heating_state: ZoneHeatingState
    current_room_humidity: float | None
    heating: ZoneHeating
    associated_circuit_index: int | None
    quick_veto_start_date_time: datetime.datetime | None
    quick_veto_end_date_time: datetime.datetime | None

    def __init__(self, **data: Any):
        if "quick_veto_start_date_time" in data:
            data["quick_veto_start_date_time"] = datetime_parse(
                data["quick_veto_start_date_time"]
            )
        if "quick_veto_end_date_time" in data:
            data["quick_veto_end_date_time"] = datetime_parse(
                data["quick_veto_end_date_time"]
            )
        super().__init__(**data)

    @property
    def name(self):
        return self.general["name"]


class Circuit(BaseModel):
    system_id: str
    index: int
    circuit_state: CircuitState
    current_circuit_flow_temperature: float | None
    heating_curve: float | None
    is_cooling_allowed: bool
    min_flow_temperature_setpoint: float | None
    mixer_circuit_type_external: str
    set_back_mode_enabled: bool
    zones: list = []


class DomesticHotWater(BaseModel):
    system_id: str
    index: int
    current_dhw_temperature: float | None
    current_special_function: DHWCurrentSpecialFunction
    max_setpoint: float
    min_setpoint: float
    operation_mode_dhw: DHWOperationMode
    tapping_setpoint: float | None
    time_program_dhw: dict
    time_program_circulation_pump: dict


class System(BaseModel):
    id: str
    claim: Claim | None
    current_system: dict = {}
    state: dict
    properties: dict
    configuration: dict
    zones: list[Zone] = []
    circuits: list[Circuit] = []
    domestic_hot_water: list[DomesticHotWater] = []
    devices: list["Device"] = []
    timezone: datetime.tzinfo | None
    firmware_update_required: bool | None
    connected: bool | None

    def __init__(self, **data: Any) -> None:
        if "claim" in data and "id" not in data:
            data["id"] = data["claim"].system_id
        super().__init__(**data)
        logger.debug(f"Creating related models from state: {data}")
        self.zones = [Zone(system_id=self.id, **z) for z in self._merge_object("zones")]
        self.circuits = [
            Circuit(system_id=self.id, **c) for c in self._merge_object("circuits")
        ]
        self.domestic_hot_water = [
            DomesticHotWater(system_id=self.id, **d) for d in self._merge_object("dhw")
        ]
        self.devices = [
            Device(system_id=self.id, type=k, **v) for k, v in self._raw_devices
        ]

    class Config:
        arbitrary_types_allowed = True  # Necessary for timezone

    @property
    def _raw_devices(self) -> Iterator[tuple[str, dict]]:
        for key, device in self.current_system.items():
            if isinstance(device, dict) and "device_uuid" in device:
                yield key, device

    @property
    def primary_heat_generator(self) -> Optional["Device"]:
        devices = [d for d in self.devices if d.type == "primary_heat_generator"]
        if len(devices) > 0:
            return devices[0]
        return None

    def _merge_object(self, obj_name) -> Iterator[dict]:
        """
        The Vaillant API returns information about zones, circuits, and dhw separately as
        configuration, state, and properties.

        This function merges everything together into one big dict for a given object (i.e. zones)
        """
        indexes = [o["index"] for o in self.configuration.get(obj_name, [])]
        for idx in indexes:
            # deepcopy() avoids unintentional changes to the referenced objects
            configuration = next(
                c for c in self.configuration.get(obj_name, []) if c["index"] == idx
            )
            try:
                state = next(
                    c for c in self.state.get(obj_name, []) if c["index"] == idx
                )
            except (StopIteration, KeyError) as e:
                logger.warning("Error when merging state", exc_info=e)
                state = {}
            try:
                properties = next(
                    c for c in self.properties.get(obj_name, []) if c["index"] == idx
                )
            except (StopIteration, KeyError) as e:
                logger.warning("Error when merging properties", exc_info=e)
                properties = {}
            # index is part of all three fields, delete from two to avoid multiple keyword argument error in dict init
            configuration.update(state)
            configuration.update(properties)
            yield configuration

    @property
    def outdoor_temperature(self) -> float | None:
        try:
            return self.state["system"]["outdoor_temperature"]
        except KeyError:
            logger.info(
                "Could not get outdoor temperature from system control state",
            )
            return None

    @property
    def water_pressure(self) -> float | None:
        try:
            return self.state["system"]["system_water_pressure"]
        except KeyError:
            logger.info("Could not get water pressure from system control state")
            return None


class Device(BaseModel):
    system_id: str
    device_uuid: str
    name: str = ""
    product_name: str
    diagnostic_trouble_codes: list = []
    properties: list = []
    ebus_id: str
    article_number: str
    device_serial_number: str
    type: str
    device_type: str
    first_data: datetime.datetime
    last_data: datetime.datetime
    operational_data: dict = {}
    data: list["DeviceData"] = []

    @property
    def name_display(self) -> str:
        return self.name if self.name else self.product_name.title()


class DeviceDataBucket(BaseModel):
    start_date: datetime.datetime
    end_date: datetime.datetime
    value: float | None


class DeviceData(BaseModel):
    def __init__(self, device: Device | None = None, **kwargs: Any) -> None:
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


# Updating string type hints for pydantic
System.update_forward_refs()
Device.update_forward_refs()
