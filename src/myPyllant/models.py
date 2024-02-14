from __future__ import annotations

import calendar
import datetime
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import TypeVar, Any

from dacite import Config, from_dict
from dacite.dataclasses import get_fields

from myPyllant.const import BRANDS
from myPyllant.enums import (
    CircuitState,
    DeviceDataBucketResolution,
    ZoneHeatingOperatingMode,
    ZoneCurrentSpecialFunction,
    ZoneHeatingState,
    DHWCurrentSpecialFunction,
    DHWOperationMode,
    VentilationOperationMode,
    ControlIdentifier,
    ZoneHeatingOperatingModeVRC700,
    DHWCurrentSpecialFunctionVRC700,
    DHWOperationModeVRC700,
)
from myPyllant.utils import datetime_parse, prepare_field_value_for_dict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="MyPyllantDataClass")


@dataclass(kw_only=True)
class MyPyllantDataClass:
    """
    Base class that runs type validation in __init__ and can create an instance from API values
    """

    extra_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def type_hooks(cls: type[T], timezone: datetime.tzinfo | None) -> dict:
        if timezone:
            return {datetime.datetime: lambda x: datetime_parse(x, timezone)}
        else:
            return {}

    @classmethod
    def from_api(cls: type[T], **kwargs) -> T:
        """
        Creates enums & dates from strings before calling __init__
        """
        dataclass_fields = get_fields(cls)
        extra_fields = set(kwargs.keys()) - {f.name for f in dataclass_fields}
        datetime_fields = set(f.name for f in dataclass_fields if "datetime" in f.type)
        timezone: datetime.tzinfo | None = kwargs.get("timezone")

        if timezone is None and datetime_fields:
            raise ValueError(
                f"timezone is required in {cls.__name__}.from_api() for datetime field {', '.join(datetime_fields)}"
            )

        if extra_fields:
            kwargs["extra_fields"] = {f: kwargs[f] for f in extra_fields}

        return from_dict(
            data_class=cls,
            data=kwargs,
            config=Config(cast=[Enum], type_hooks=cls.type_hooks(timezone)),
        )

    def prepare_dict(self) -> dict:
        data = asdict(self)
        return prepare_field_value_for_dict(data)


@dataclass
class Home(MyPyllantDataClass):
    country_code: str
    timezone: datetime.tzinfo
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
class BaseTimeProgramDay(MyPyllantDataClass):
    index: int
    weekday_name: str
    start_time: int
    end_time: int

    def __eq__(self, other):
        raise NotImplementedError

    @property
    def start_datetime_time(self) -> datetime.time:
        return datetime.time(self.start_time // 60, self.start_time % 60)

    @property
    def end_datetime_time(self) -> datetime.time:
        return datetime.time(self.end_time // 60, self.end_time % 60)

    def start_datetime(self, date) -> datetime.datetime:
        return date.replace(
            hour=self.start_time // 60,
            minute=self.start_time % 60,
            second=0,
            microsecond=0,
        )

    def end_datetime(self, date) -> datetime.datetime:
        if self.end_time == 1440:
            return date.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + datetime.timedelta(days=1)
        else:
            return date.replace(
                hour=self.end_time // 60,
                minute=self.end_time % 60,
                second=0,
                microsecond=0,
            )


@dataclass
class BaseTimeProgram(MyPyllantDataClass):
    monday: list
    tuesday: list
    wednesday: list
    thursday: list
    friday: list
    saturday: list
    sunday: list
    meta_info: dict | None = None

    @property
    def has_time_program(self):
        return any(
            [len(getattr(self, weekday)) > 0 for weekday in self.weekday_names()]
        )

    @classmethod
    def weekday_names(cls):
        return [w.lower() for w in calendar.day_name]

    def matching_weekdays(self, time_program_day: BaseTimeProgramDay):
        """
        Returns a list of weekday names that have a matching BaseTimeProgramDay
        """
        return [
            w
            for w in self.weekday_names()
            if any([d == time_program_day for d in getattr(self, w)])
        ]

    def check_overlap(self):
        for weekday in self.weekday_names():
            day_list: list[BaseTimeProgramDay] = getattr(self, weekday)
            if len(day_list) == 0:
                continue
            day_list.sort(key=lambda x: x.start_time)
            # Create non-overlapping BaseTimeProgramDays
            for i, day in enumerate(day_list):
                other_slots = day_list[i + 1 :]
                for other_slot in other_slots:
                    if (
                        day.end_time > other_slot.start_time
                        and day.start_time < other_slot.end_time
                    ):
                        raise ValueError(
                            f"Time program {day.start_datetime_time} - {day.end_datetime_time} "
                            f"overlaps with {other_slot.start_datetime_time} - {other_slot.end_datetime_time}"
                        )

    def as_datetime(
        self, start, end
    ) -> Iterator[tuple[ZoneTimeProgramDay, datetime.datetime, datetime.datetime]]:
        current = start
        while current < end:
            weekday = current.strftime("%A").lower()
            for time_program in getattr(self, weekday):
                if time_program.start_datetime(current) < end:
                    yield (
                        time_program,
                        time_program.start_datetime(current),
                        time_program.end_datetime(current),
                    )
                else:
                    break
            current += datetime.timedelta(days=1)

    @classmethod
    def create_day_from_api(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def from_api(cls, **kwargs):
        for weekday_name in [w for w in cls.weekday_names()]:
            kwargs[weekday_name] = [
                cls.create_day_from_api(index=i, weekday_name=weekday_name, **d)
                for i, d in enumerate(kwargs.get(weekday_name, []))
            ]
        return super().from_api(**kwargs)


@dataclass
class ZoneTimeProgramDay(BaseTimeProgramDay):
    setpoint: float | None = None

    def __eq__(self, other):
        """
        When comparing two ZoneTimeProgramDay, we only care about start_time, end_time, and setpoint
        """
        if not isinstance(other, ZoneTimeProgramDay):
            return False
        return (
            self.start_time == other.start_time
            and self.end_time == other.end_time
            and self.setpoint == other.setpoint
        )


@dataclass
class ZoneTimeProgram(BaseTimeProgram):
    monday: list[ZoneTimeProgramDay]
    tuesday: list[ZoneTimeProgramDay]
    wednesday: list[ZoneTimeProgramDay]
    thursday: list[ZoneTimeProgramDay]
    friday: list[ZoneTimeProgramDay]
    saturday: list[ZoneTimeProgramDay]
    sunday: list[ZoneTimeProgramDay]

    @classmethod
    def create_day_from_api(cls, **kwargs):
        return ZoneTimeProgramDay(**kwargs)

    def set_setpoint(
        self, temperature: float, update_similar_to_dow: str | None = None
    ):
        """
        Sets the setpoint on all weekdays of a time program to the new value
        """
        weekday_names = [w.lower() for w in calendar.day_name]
        if update_similar_to_dow and update_similar_to_dow not in weekday_names:
            raise ValueError(
                "%s is not a valid weekday, use one of %s or None",
                update_similar_to_dow,
                ", ".join(weekday_names),
            )
        # TODO: Implement update_similar_to_dow check
        for w in weekday_names:
            day_list: list[ZoneTimeProgramDay] = getattr(self, w)
            for d in day_list:
                d.setpoint = temperature


@dataclass
class ZoneHeating(MyPyllantDataClass):
    control_identifier: ControlIdentifier
    operation_mode_heating: ZoneHeatingOperatingMode | ZoneHeatingOperatingModeVRC700
    time_program_heating: ZoneTimeProgram
    set_back_temperature: float
    manual_mode_setpoint_heating: float | None = None
    day_temperature_heating: float | None = None  # VRC700 only

    @classmethod
    def from_api(cls, **kwargs):
        kwargs["time_program_heating"] = ZoneTimeProgram.from_api(
            **kwargs["time_program_heating"]
        )
        control_identifier: ControlIdentifier = kwargs["control_identifier"]
        if control_identifier.is_vrc700:
            kwargs["operation_mode_heating"] = ZoneHeatingOperatingModeVRC700(
                kwargs["operation_mode_heating"]
            )
        else:
            kwargs["operation_mode_heating"] = ZoneHeatingOperatingMode(
                kwargs["operation_mode_heating"]
            )

        return super().from_api(**kwargs)


@dataclass
class ZoneCooling(MyPyllantDataClass):
    setpoint_cooling: float
    manual_mode_setpoint_cooling: float | None
    operation_mode_cooling: str  # TODO: Need all values
    time_program_cooling: ZoneTimeProgram

    @classmethod
    def from_api(cls, **kwargs):
        kwargs["time_program_cooling"] = ZoneTimeProgram.from_api(
            **kwargs["time_program_cooling"]
        )
        return super().from_api(**kwargs)


@dataclass
class ZoneGeneral(MyPyllantDataClass):
    name: str
    timezone: datetime.tzinfo
    holiday_start_date_time: datetime.datetime | None = None
    holiday_end_date_time: datetime.datetime | None = None

    @property
    def holiday_planned(self) -> bool:
        return (
            self.holiday_start_date_time is not None
            and self.holiday_end_date_time is not None
            and self.holiday_end_date_time > datetime.datetime.now(self.timezone)
        )

    @property
    def holiday_start_in_future(self) -> bool:
        return (
            self.holiday_start_date_time is not None
            and self.holiday_start_date_time > datetime.datetime.now(self.timezone)
        )

    @property
    def holiday_ongoing(self) -> bool:
        return (
            self.holiday_start_date_time is not None
            and self.holiday_end_date_time is not None
            and self.holiday_start_date_time
            < datetime.datetime.now(self.timezone)
            < self.holiday_end_date_time
        )

    @property
    def holiday_remaining(self) -> datetime.timedelta | None:
        return (
            self.holiday_end_date_time - datetime.datetime.now(self.timezone)
            if self.holiday_end_date_time and self.holiday_ongoing
            else None
        )


@dataclass
class Zone(MyPyllantDataClass):
    system_id: str
    general: ZoneGeneral
    timezone: datetime.tzinfo
    control_identifier: ControlIdentifier
    index: int
    zone_binding: str
    heating: ZoneHeating
    current_special_function: ZoneCurrentSpecialFunction
    is_active: bool | None
    heating_state: ZoneHeatingState | None = None
    is_cooling_allowed: bool | None = None
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
        kwargs["heating"] = ZoneHeating.from_api(
            control_identifier=kwargs["control_identifier"], **kwargs["heating"]
        )
        kwargs["cooling"] = (
            ZoneCooling.from_api(**kwargs["cooling"]) if "cooling" in kwargs else None
        )
        kwargs["general"] = ZoneGeneral.from_api(
            timezone=kwargs["timezone"], **kwargs["general"]
        )
        return super().from_api(**kwargs)

    def get_associated_circuit(self, system: System):
        if self.associated_circuit_index in [c.index for c in system.circuits]:
            return next(
                c for c in system.circuits if c.index == self.associated_circuit_index
            )
        return None

    @property
    def name(self):
        return self.general.name

    @property
    def quick_veto_ongoing(self) -> bool:
        return (
            self.quick_veto_start_date_time is not None
            and self.quick_veto_end_date_time is not None
            and self.quick_veto_start_date_time
            < datetime.datetime.now(self.timezone)
            < self.quick_veto_end_date_time
        )

    @property
    def quick_veto_remaining(self) -> datetime.timedelta | None:
        return (
            self.quick_veto_end_date_time - datetime.datetime.now(self.timezone)
            if self.quick_veto_end_date_time and self.quick_veto_ongoing
            else None
        )

    @property
    def is_eco_mode(self) -> bool:
        return (
            self.is_auto_heating_mode
            and self.current_special_function == ZoneCurrentSpecialFunction.NONE
            and self.desired_room_temperature_setpoint == 0.0
        )

    @property
    def is_auto_heating_mode(self) -> bool:
        return self.heating.operation_mode_heating in [
            ZoneHeatingOperatingMode.TIME_CONTROLLED,
            ZoneHeatingOperatingModeVRC700.AUTO,
        ]


@dataclass
class Circuit(MyPyllantDataClass):
    system_id: str
    index: int
    circuit_state: CircuitState
    mixer_circuit_type_external: str
    set_back_mode_enabled: bool | None = None
    zones: list = field(default_factory=list)
    is_cooling_allowed: bool | None = None
    current_circuit_flow_temperature: float | None = None
    heating_curve: float | None = None
    heating_flow_temperature_minimum_setpoint: float | None = None
    heating_flow_temperature_maximum_setpoint: float | None = None
    min_flow_temperature_setpoint: float | None = None
    calculated_energy_manager_state: str | None = None


@dataclass
class DHWTimeProgramDay(BaseTimeProgramDay):
    def __eq__(self, other):
        """
        When comparing two DHWTimeProgramDay, we only care about start_time and end_time
        """
        if not isinstance(other, DHWTimeProgramDay):
            return False
        return self.start_time == other.start_time and self.end_time == other.end_time


@dataclass
class DHWTimeProgram(BaseTimeProgram):
    monday: list[DHWTimeProgramDay]
    tuesday: list[DHWTimeProgramDay]
    wednesday: list[DHWTimeProgramDay]
    thursday: list[DHWTimeProgramDay]
    friday: list[DHWTimeProgramDay]
    saturday: list[DHWTimeProgramDay]
    sunday: list[DHWTimeProgramDay]

    @classmethod
    def create_day_from_api(cls, **kwargs):
        return DHWTimeProgramDay(**kwargs)


@dataclass
class DomesticHotWater(MyPyllantDataClass):
    system_id: str
    index: int
    control_identifier: ControlIdentifier
    current_special_function: DHWCurrentSpecialFunction | DHWCurrentSpecialFunctionVRC700
    max_setpoint: float
    min_setpoint: float
    operation_mode_dhw: DHWOperationMode | DHWOperationModeVRC700
    time_program_dhw: DHWTimeProgram
    time_program_circulation_pump: DHWTimeProgram
    current_dhw_temperature: float | None = None
    tapping_setpoint: float | None = None

    @property
    def is_cylinder_boosting(self) -> bool:
        return self.current_special_function in [
            DHWCurrentSpecialFunction.CYLINDER_BOOST,
            DHWCurrentSpecialFunctionVRC700.CYLINDER_BOOST,
        ]

    @classmethod
    def from_api(cls, **kwargs):
        kwargs["time_program_dhw"] = DHWTimeProgram.from_api(
            **kwargs["time_program_dhw"]
        )
        kwargs["time_program_circulation_pump"] = DHWTimeProgram.from_api(
            **kwargs["time_program_circulation_pump"]
        )
        control_identifier: ControlIdentifier = kwargs["control_identifier"]
        if control_identifier.is_vrc700:
            kwargs["current_special_function"] = DHWCurrentSpecialFunctionVRC700(
                kwargs["current_special_function"]
            )
            kwargs["operation_mode_dhw"] = DHWOperationModeVRC700(
                kwargs["operation_mode_dhw"]
            )
        else:
            kwargs["current_special_function"] = DHWCurrentSpecialFunction(
                kwargs["current_special_function"]
            )
            kwargs["operation_mode_dhw"] = DHWOperationMode(
                kwargs["operation_mode_dhw"]
            )
        return super().from_api(**kwargs)


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
    home: Home
    brand: str
    timezone: datetime.tzinfo
    control_identifier: ControlIdentifier
    connected: bool | None = None
    diagnostic_trouble_codes: list | None = None
    current_system: dict = field(default_factory=dict)
    zones: list[Zone] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
    domestic_hot_water: list[DomesticHotWater] = field(default_factory=list)
    ventilation: list[Ventilation] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    mpc: dict = field(default_factory=dict)
    rts: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, **kwargs):
        if "home" in kwargs and "id" not in kwargs:
            kwargs["id"] = kwargs["home"].system_id
        system: System = super().from_api(**kwargs)
        logger.debug(f"Creating related models from state: {kwargs}")
        system.extra_fields = system.merge_extra_fields()
        system.zones = [
            Zone.from_api(
                system_id=system.id,
                timezone=system.timezone,
                control_identifier=system.control_identifier,
                **z,
            )
            for z in system.merge_object("zones")
        ]
        system.circuits = [
            Circuit.from_api(system_id=system.id, timezone=system.timezone, **c)
            for c in system.merge_object("circuits")
        ]
        system.domestic_hot_water = [
            DomesticHotWater.from_api(
                system_id=system.id,
                timezone=system.timezone,
                control_identifier=system.control_identifier,
                **d,
            )
            for d in system.merge_object("dhw")
        ]
        system.ventilation = [
            Ventilation.from_api(system_id=system.id, timezone=system.timezone, **d)
            for d in system.merge_object("ventilation")
        ]
        system.devices = [
            Device.from_api(
                system_id=system.id,
                timezone=system.timezone,
                type=k,
                brand=system.brand,
                **v,
            )
            for k, v in system.raw_devices
        ]
        return system

    def apply_diagnostic(self, device):
        dtc = self.diagnostic_trouble_codes_by_serial_number(
            device["device_serial_number"]
        )
        device["diagnostic_trouble_codes"] = dtc

    def apply_rts(self, device):
        rts_statistics = self.rts_statistics_by_device_uuid(device["device_uuid"])
        if rts_statistics:
            device["rts_statistics"] = rts_statistics

    @property
    def raw_devices(self) -> Iterator[tuple[str, dict]]:
        for key, device in self.current_system.items():
            if isinstance(device, list) and key == "secondary_heat_generators":
                for secdevice in device:
                    if isinstance(secdevice, dict) and "device_uuid" in secdevice:
                        self.apply_diagnostic(secdevice)
                        self.apply_rts(secdevice)
                        yield key, secdevice
            if isinstance(device, dict) and "device_uuid" in device:
                self.apply_diagnostic(device)
                self.apply_rts(device)
                yield key, device

    @property
    def primary_heat_generator(self) -> Device | None:
        devices = [d for d in self.devices if d.type == "primary_heat_generator"]
        if len(devices) > 0:
            return devices[0]
        return None

    def merge_extra_fields(self) -> dict:
        return (
            self.extra_fields
            | self.configuration.get("system", {})
            | self.state.get("system", {})
            | self.properties.get("system", {})
        )

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
        elif self.home:
            return self.home.nomenclature
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

    def rts_statistics_by_device_uuid(self, device_uuid: str) -> dict | None:
        statistics = [
            s for s in self.rts.get("statistics", []) if s["device_id"] == device_uuid
        ]
        return statistics[0] if statistics else None


@dataclass
class Device(MyPyllantDataClass):
    system_id: str
    timezone: datetime.tzinfo
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
    rts_statistics: dict = field(default_factory=dict)
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
        if self.product_name:
            return (
                self.product_name.title()
                if self.product_name.islower()
                else self.product_name
            )
        else:
            return self.device_type.replace("_", "").title()

    @property
    def brand_name(self) -> str:
        return BRANDS[self.brand]

    @property
    def on_off_cycles(self) -> int | None:
        return self.rts_statistics.get("on_off_cycles")

    @property
    def operation_time(self) -> int | None:
        return self.rts_statistics.get("operation_time")

    @classmethod
    def from_api(cls, **kwargs):
        data = []
        if "data" in kwargs:
            for dd in kwargs["data"]:
                if "timezone" not in dd:
                    dd["timezone"] = kwargs["timezone"]
                data.append(DeviceData.from_api(**dd))
        kwargs["data"] = data
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
            DeviceDataBucket.from_api(timezone=kwargs["timezone"], **dd)
            for dd in kwargs.pop("data", [])
        ]
        return super().from_api(**kwargs)


@dataclass
class SystemReport(MyPyllantDataClass):
    file_name: str
    file_content: str
