import datetime
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Optional

from dataclass_type_validator import dataclass_type_validator

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


@dataclass
class MyPyllantDataClass:
    """
    Base class that runs type validation in __init__
    """

    def __post_init__(self):
        for f in fields(self):
            is_enum = isinstance(f.type, type) and issubclass(f.type, Enum)
            if is_enum:
                value = object.__getattribute__(self, f.name)
                if isinstance(value, str):
                    object.__setattr__(self, f.name, f.type(value))
        dataclass_type_validator(self)


@dataclass
class Claim(MyPyllantDataClass):
    country_code: str
    nomenclature: str
    serial_number: str
    state: str
    system_id: str
    home_name: str | None = None
    address: str | None = None
    product_information: str | None = None
    migration_state: str | None = None
    cag: bool | None = None
    firmware_version: str | None = None
    product_metadata: dict = field(default_factory=dict)


@dataclass
class ZoneHeating(MyPyllantDataClass):
    manual_mode_setpoint_heating: float
    operation_mode_heating: ZoneHeatingOperatingMode
    time_program_heating: dict
    set_back_temperature: float


@dataclass
class Zone(MyPyllantDataClass):
    system_id: str
    general: dict
    index: int
    is_active: bool
    is_cooling_allowed: bool
    zone_binding: str
    heating_state: ZoneHeatingState
    heating: ZoneHeating
    current_special_function: ZoneCurrentSpecialFunction
    current_room_temperature: float | None = None
    desired_room_temperature_setpoint_heating: float | None = None
    desired_room_temperature_setpoint_cooling: float | None = None
    desired_room_temperature_setpoint: float | None = None
    current_room_humidity: float | None = None
    associated_circuit_index: int | None = None
    quick_veto_start_date_time: datetime.datetime | None = None
    quick_veto_end_date_time: datetime.datetime | None = None

    def __post_init__(self):
        if self.quick_veto_start_date_time:
            object.__setattr__(
                self,
                "quick_veto_start_date_time",
                datetime_parse(self.quick_veto_start_date_time),  # noqa
            )
        if self.quick_veto_end_date_time:
            object.__setattr__(
                self,
                "quick_veto_end_date_time",
                datetime_parse(self.quick_veto_end_date_time),  # noqa
            )
        if isinstance(self.heating_state, str):
            object.__setattr__(
                self, "heating_state", ZoneHeatingState(self.heating_state)
            )
        if isinstance(self.current_special_function, str):
            object.__setattr__(
                self,
                "current_special_function",
                ZoneCurrentSpecialFunction(self.current_special_function),
            )
        if isinstance(self.heating, dict):
            object.__setattr__(self, "heating", ZoneHeating(**self.heating))

        super().__post_init__()

    @property
    def name(self):
        return self.general["name"]


@dataclass
class Circuit(MyPyllantDataClass):
    system_id: str
    index: int
    circuit_state: CircuitState
    is_cooling_allowed: bool
    mixer_circuit_type_external: str
    set_back_mode_enabled: bool
    zones: list = field(default_factory=list)
    current_circuit_flow_temperature: float | None = None
    heating_curve: float | None = None
    heating_flow_temperature_minimum_setpoint: float | None = None
    min_flow_temperature_setpoint: float | None = None
    calculated_energy_manager_state: str | None = None

    def __post_init__(self):
        if isinstance(self.circuit_state, str):
            object.__setattr__(self, "circuit_state", CircuitState(self.circuit_state))
        super().__post_init__()


@dataclass
class DomesticHotWater(MyPyllantDataClass):
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

    def __post_init__(self):
        if isinstance(self.current_special_function, str):
            object.__setattr__(
                self,
                "current_special_function",
                DHWCurrentSpecialFunction(self.current_special_function),
            )
        if isinstance(self.operation_mode_dhw, str):
            object.__setattr__(
                self, "operation_mode_dhw", DHWOperationMode(self.operation_mode_dhw)
            )
        super().__post_init__()


@dataclass
class System(MyPyllantDataClass):
    id: str = field(init=False)
    claim: Claim | None
    state: dict
    properties: dict
    configuration: dict
    timezone: datetime.tzinfo | None
    firmware_update_required: bool | None
    connected: bool | None
    diagnostic_trouble_codes: list[dict] | None
    current_system: dict = field(default_factory=dict)
    zones: list[Zone] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
    domestic_hot_water: list[DomesticHotWater] = field(default_factory=list)
    devices: list["Device"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.claim:
            object.__setattr__(self, "id", self.claim.system_id)
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
        super().__post_init__()

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
            # State and properties get merged into configuration
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

    @property
    def system_name(self) -> str:
        if self.primary_heat_generator:
            return self.primary_heat_generator.product_name_display
        elif self.claim:
            return self.claim.nomenclature
        else:
            return "System"


@dataclass
class Device(MyPyllantDataClass):
    system_id: str
    device_uuid: str
    ebus_id: str
    article_number: str
    device_serial_number: str
    type: str
    device_type: str
    first_data: datetime.datetime
    last_data: datetime.datetime
    name: str | None = None
    product_name: str | None = None
    spn: int | None = None
    bus_coupler_address: int | None = None
    emf_valid: bool | None = None
    operational_data: dict = field(default_factory=dict)
    data: list["DeviceData"] = field(default_factory=list)
    properties: list = field(default_factory=list)

    @property
    def name_display(self) -> str:
        """
        Product name might be empty, fall back to title-cased device type
        """
        return self.name or self.product_name_display

    @property
    def product_name_display(self) -> str:
        """
        Product name might be None, fall back to title-cased device type
        """
        return self.product_name or self.device_type.replace("_", "").title()

    def __post_init__(self):
        if self.first_data:
            object.__setattr__(
                self, "first_data", datetime_parse(self.first_data)  # noqa
            )
        if self.last_data:
            object.__setattr__(
                self, "last_data", datetime_parse(self.last_data)  # noqa
            )
        if self.data and isinstance(self.data[0], dict):
            object.__setattr__(
                self, "data", [DeviceData(**dd) for dd in self.data]
            )  # noqa
        super().__post_init__()


@dataclass
class DeviceDataBucket(MyPyllantDataClass):
    start_date: datetime.datetime
    end_date: datetime.datetime
    value: float | None

    def __post_init__(self):
        if self.start_date:
            object.__setattr__(
                self, "start_date", datetime_parse(self.start_date)  # noqa
            )
        if self.end_date:
            object.__setattr__(self, "end_date", datetime_parse(self.end_date))  # noqa
        super().__post_init__()


@dataclass
class DeviceData(MyPyllantDataClass):
    operation_mode: str
    device: Device | None = None
    data_from: datetime.datetime | None = None
    data_to: datetime.datetime | None = None
    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None
    resolution: DeviceDataBucketResolution | None = None
    energy_type: str | None = None
    value_type: str | None = None
    calculated: bool | None = None
    data: list[DeviceDataBucket] = field(default_factory=list)

    def __init__(self, **kwargs):
        names = {f.name for f in fields(self)}
        kwargs["data_from"] = kwargs.pop("from") if "from" in kwargs else None
        kwargs["data_to"] = kwargs.pop("to") if "to" in kwargs else None
        if "data" in kwargs:
            kwargs["data"] = [DeviceDataBucket(**dd) for dd in kwargs["data"]]
        else:
            kwargs["data"] = None
        if kwargs["data_from"]:
            kwargs["data_from"] = datetime_parse(kwargs["data_from"])
        if kwargs["data_to"]:
            kwargs["data_to"] = datetime_parse(kwargs["data_to"])

        for k, v in kwargs.items():
            if k in names:
                object.__setattr__(self, k, v)
