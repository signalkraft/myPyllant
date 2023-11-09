from __future__ import annotations

import calendar
import datetime
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum, EnumMeta
from importlib.metadata import version
from typing import TypeVar

from dacite import Config, from_dict

from myPyllant.const import BRANDS
from myPyllant.utils import datetime_parse, version_tuple

logger = logging.getLogger(__name__)


if version_tuple(version("dacite")) < version_tuple("1.7.0"):
    raise Exception(
        "Invalid version of dacite library detected. You are probably using another integration like "
        "Govee which is installing a conflicting, older version."
    )


class MyPyllantEnumMeta(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True


class MyPyllantEnum(Enum, metaclass=MyPyllantEnumMeta):
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
    SYSTEM_OFF = "SYSTEM_OFF"


class ZoneHeatingState(MyPyllantEnum):
    IDLE = "IDLE"
    HEATING_UP = "HEATING_UP"
    COOLING_DOWN = "COOLING_DOWN"


class ZoneTimeProgramType(MyPyllantEnum):
    HEATING = "heating"
    COOLING = "cooling"


class DHWCurrentSpecialFunction(MyPyllantEnum):
    CYLINDER_BOOST = "CYLINDER_BOOST"
    REGULAR = "REGULAR"


class DHWOperationMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class VentilationOperationMode(MyPyllantEnum):
    NORMAL = "NORMAL"
    REDUCED = "REDUCED"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class VentilationFanStageType(MyPyllantEnum):
    DAY = "DAY"
    NIGHT = "NIGHT"


T = TypeVar("T")


@dataclass
class MyPyllantDataClass:
    """
    Base class that runs type validation in __init__ and can create an instance from API values
    """

    @classmethod
    def from_api(cls: type[T], **kwargs) -> T:
        """
        Creates enums & dates from strings before calling __init__
        """
        return from_dict(
            data_class=cls,
            data=kwargs,
            config=Config(cast=[Enum], type_hooks={datetime.datetime: datetime_parse}),
        )


@dataclass
class Claim(MyPyllantDataClass):
    country_code: str
    nomenclature: str
    serial_number: str
    state: str
    system_id: str
    home_name: str | None = None
    address: dict = field(default_factory=dict)
    product_information: str | None = None
    migration_state: str | None = None
    cag: bool | None = None
    firmware_version: str | None = None
    firmware: dict = field(default_factory=dict)
    product_metadata: dict = field(default_factory=dict)

    @property
    def name(self):
        return f"{self.home_name} {self.nomenclature}"


@dataclass
class ZoneTimeProgramDay(MyPyllantDataClass):
    start_time: int
    end_time: int
    setpoint: float | None = None


@dataclass
class ZoneTimeProgram(MyPyllantDataClass):
    monday: list[ZoneTimeProgramDay]
    tuesday: list[ZoneTimeProgramDay]
    wednesday: list[ZoneTimeProgramDay]
    thursday: list[ZoneTimeProgramDay]
    friday: list[ZoneTimeProgramDay]
    saturday: list[ZoneTimeProgramDay]
    sunday: list[ZoneTimeProgramDay]
    meta_info: dict | None = None

    def set_setpoint(self, temperature: float):
        """
        Sets the setpoint on all weekdays of a time program to the new value
        """
        weekday_names = calendar.day_name
        for w in weekday_names:
            day_list: list[ZoneTimeProgramDay] = getattr(self, w.lower())
            for d in day_list:
                d.setpoint = temperature


@dataclass
class ZoneHeating(MyPyllantDataClass):
    manual_mode_setpoint_heating: float
    operation_mode_heating: ZoneHeatingOperatingMode
    time_program_heating: ZoneTimeProgram
    set_back_temperature: float


@dataclass
class ZoneCooling(MyPyllantDataClass):
    setpoint_cooling: float
    manual_mode_setpoint_cooling: float
    operation_mode_cooling: str  # TODO: Need all values
    time_program_cooling: ZoneTimeProgram


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
    cooling: ZoneCooling | None = None
    current_room_temperature: float | None = None
    desired_room_temperature_setpoint_heating: float | None = None
    desired_room_temperature_setpoint_cooling: float | None = None
    desired_room_temperature_setpoint: float | None = None
    current_room_humidity: float | None = None
    associated_circuit_index: int | None = None
    quick_veto_start_date_time: datetime.datetime | None = None
    quick_veto_end_date_time: datetime.datetime | None = None

    @classmethod
    def from_api(cls, **kwargs):
        kwargs["heating"] = ZoneHeating.from_api(**kwargs["heating"])
        return super().from_api(**kwargs)

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
    heating_flow_temperature_maximum_setpoint: float | None = None
    min_flow_temperature_setpoint: float | None = None
    calculated_energy_manager_state: str | None = None


@dataclass
class DHWTimeProgramDay(MyPyllantDataClass):
    start_time: int
    end_time: int


@dataclass
class DHWTimeProgram(MyPyllantDataClass):
    monday: list[DHWTimeProgramDay]
    tuesday: list[DHWTimeProgramDay]
    wednesday: list[DHWTimeProgramDay]
    thursday: list[DHWTimeProgramDay]
    friday: list[DHWTimeProgramDay]
    saturday: list[DHWTimeProgramDay]
    sunday: list[DHWTimeProgramDay]
    meta_info: dict | None = None


@dataclass
class DomesticHotWater(MyPyllantDataClass):
    system_id: str
    index: int
    current_special_function: DHWCurrentSpecialFunction
    max_setpoint: float
    min_setpoint: float
    operation_mode_dhw: DHWOperationMode
    time_program_dhw: DHWTimeProgram
    time_program_circulation_pump: DHWTimeProgram
    current_dhw_temperature: float | None = None
    tapping_setpoint: float | None = None


@dataclass
class Ventilation(MyPyllantDataClass):
    system_id: str
    index: int
    maximum_day_fan_stage: int
    maximum_night_fan_stage: int
    operation_mode_ventilation: VentilationOperationMode
    time_program_ventilation: dict


@dataclass
class System(MyPyllantDataClass):
    id: str
    state: dict
    properties: dict
    configuration: dict
    claim: Claim
    brand: str
    timezone: datetime.tzinfo | None = None
    connected: bool | None = None
    diagnostic_trouble_codes: list | None = None
    current_system: dict = field(default_factory=dict)
    zones: list[Zone] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
    domestic_hot_water: list[DomesticHotWater] = field(default_factory=list)
    ventilation: list[Ventilation] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    mpc: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, **kwargs):
        if "claim" in kwargs and "id" not in kwargs:
            kwargs["id"] = kwargs["claim"].system_id
        system: System = super().from_api(**kwargs)
        logger.debug(f"Creating related models from state: {kwargs}")
        system.zones = [
            Zone.from_api(system_id=system.id, **z)
            for z in system.merge_object("zones")
        ]
        system.circuits = [
            Circuit.from_api(system_id=system.id, **c)
            for c in system.merge_object("circuits")
        ]
        system.domestic_hot_water = [
            DomesticHotWater.from_api(system_id=system.id, **d)
            for d in system.merge_object("dhw")
        ]
        system.ventilation = [
            Ventilation.from_api(system_id=system.id, **d)
            for d in system.merge_object("ventilation")
        ]
        system.devices = [
            Device.from_api(system_id=system.id, type=k, brand=system.brand, **v)
            for k, v in system.raw_devices
        ]
        return system

    @property
    def raw_devices(self) -> Iterator[tuple[str, dict]]:
        for key, device in self.current_system.items():
            if isinstance(device, dict) and "device_uuid" in device:
                dtc = self.diagnostic_trouble_codes_by_serial_number(
                    device["device_serial_number"]
                )
                device["diagnostic_trouble_codes"] = dtc
                yield key, device

    @property
    def primary_heat_generator(self) -> Device | None:
        devices = [d for d in self.devices if d.type == "primary_heat_generator"]
        if len(devices) > 0:
            return devices[0]
        return None

    def merge_object(self, obj_name) -> Iterator[dict]:
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

    @property
    def brand_name(self) -> str:
        return BRANDS[self.brand]

    @property
    def has_diagnostic_trouble_codes(self) -> bool:
        return self.diagnostic_trouble_codes is not None and any(
            [len(d["codes"]) > 0 for d in self.diagnostic_trouble_codes]
        )

    def diagnostic_trouble_codes_by_serial_number(
        self, serial_number: str
    ) -> list | None:
        if self.diagnostic_trouble_codes:
            dtc = [
                d
                for d in self.diagnostic_trouble_codes
                if d["serial_number"] == serial_number
            ]
            return dtc[0]["codes"] if dtc else None
        else:
            return None


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
    brand: str
    name: str | None = None
    product_name: str | None = None
    spn: int | None = None
    bus_coupler_address: int | None = None
    emf_valid: bool | None = None
    operational_data: dict = field(default_factory=dict)
    data: list[DeviceData] = field(default_factory=list)
    properties: list = field(default_factory=list)
    diagnostic_trouble_codes: list | None = None

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

    @property
    def brand_name(self) -> str:
        return BRANDS[self.brand]

    @classmethod
    def from_api(cls, **kwargs):
        kwargs["data"] = (
            [DeviceData.from_api(**dd) for dd in kwargs["data"]]
            if "data" in kwargs
            else []
        )
        return super().from_api(**kwargs)


@dataclass
class DeviceDataBucket(MyPyllantDataClass):
    start_date: datetime.datetime
    end_date: datetime.datetime
    value: float | None = None


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

    @classmethod
    def from_api(cls, **kwargs):
        kwargs["data_from"] = kwargs.pop("from", None)
        kwargs["data_to"] = kwargs.pop("to", None)
        kwargs["data"] = [
            DeviceDataBucket.from_api(**dd) for dd in kwargs.pop("data", [])
        ]
        return super().from_api(**kwargs)


@dataclass
class SystemReport(MyPyllantDataClass):
    file_name: str
    file_content: str
