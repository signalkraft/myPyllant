from __future__ import annotations

import calendar
import datetime
import logging
from collections.abc import Iterator
from dataclasses import asdict, fields, field
from typing import TypeVar, Any, Iterable
from pydantic.dataclasses import dataclass

from myPyllant.const import BRANDS
from myPyllant.enums import (
    CircuitState,
    DeviceDataBucketResolution,
    ZoneOperatingMode,
    ZoneCurrentSpecialFunction,
    ZoneHeatingState,
    DHWCurrentSpecialFunction,
    DHWOperationMode,
    VentilationOperationMode,
    ControlIdentifier,
    ZoneOperatingModeVRC700,
    DHWCurrentSpecialFunctionVRC700,
    DHWOperationModeVRC700,
    AmbisenseRoomOperationMode,
    VentilationOperationModeVRC700,
)
from myPyllant.utils import datetime_parse, prepare_field_value_for_dict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="MyPyllantDataClass")


class MyPyllantConfig:
    """
    Necessary for timezone field
    """

    arbitrary_types_allowed = True


@dataclass(kw_only=True, config=MyPyllantConfig)
class MyPyllantDataClass:
    """
    Base class that runs type validation in __init__ and can create an instance from API values
    """

    extra_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls: type[T], **data) -> T:
        """
        Creates enums & dates from strings before calling __init__
        """
        dataclass_fields = fields(cls)
        extra_fields = set(data.keys()) - {f.name for f in dataclass_fields}
        datetime_fields = set(
            f.name for f in dataclass_fields if f.type == "datetime.datetime"
        )
        timezone: datetime.tzinfo | None = data.get("timezone")

        if timezone is None and datetime_fields:
            raise ValueError(
                f"timezone is required in {cls.__name__}.from_api() for datetime field {', '.join(datetime_fields)}"
            )

        for k, v in data.items():
            if k in datetime_fields and timezone is not None:
                data[k] = datetime_parse(v, timezone)

        if extra_fields:
            data["extra_fields"] = {f: data[f] for f in extra_fields}

        return cls(**data)

    def prepare_dict(self) -> dict:
        data = asdict(self)
        return prepare_field_value_for_dict(data)


@dataclass(config=MyPyllantConfig)
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


@dataclass(config=MyPyllantConfig)
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
        end_time = self.end_time % 1440
        return datetime.time(end_time // 60, end_time % 60)

    def start_datetime(self, date) -> datetime.datetime:
        return date.replace(
            hour=self.start_time // 60,
            minute=self.start_time % 60,
            second=0,
            microsecond=0,
        )

    def end_datetime(self, date) -> datetime.datetime:
        """
        end_time can be > 1440 for RoomTimeProgramDay, which indicates the time slot ends on a later day

        On all other time programs, end_time is <= 1440. Exactly 1440 is returned as midnight on the next day.
        """
        days = self.end_time // 1440
        end_time = self.end_time % 1440
        return date.replace(
            hour=end_time // 60,
            minute=end_time % 60,
            second=0,
            microsecond=0,
        ) + datetime.timedelta(days=days)


@dataclass(config=MyPyllantConfig)
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
    def from_api(cls, **data):
        for weekday_name in [w for w in cls.weekday_names()]:
            data[weekday_name] = [
                cls.create_day_from_api(index=i, weekday_name=weekday_name, **d)
                for i, d in enumerate(data.get(weekday_name, []))
            ]
        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
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


@dataclass(config=MyPyllantConfig)
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


@dataclass(config=MyPyllantConfig)
class ZoneHeating(MyPyllantDataClass):
    control_identifier: ControlIdentifier
    operation_mode_heating: ZoneOperatingMode | ZoneOperatingModeVRC700
    set_back_temperature: float
    time_program_heating: ZoneTimeProgram | None = None
    manual_mode_setpoint_heating: float | None = None
    day_temperature_heating: float | None = None  # VRC700 only

    @classmethod
    def from_api(cls, **data):
        if "time_program_heating" in data:
            data["time_program_heating"] = ZoneTimeProgram.from_api(
                **data["time_program_heating"]
            )
        control_identifier: ControlIdentifier = data["control_identifier"]
        if control_identifier.is_vrc700:
            data["operation_mode_heating"] = ZoneOperatingModeVRC700(
                data["operation_mode_heating"]
            )
        else:
            data["operation_mode_heating"] = ZoneOperatingMode(
                data["operation_mode_heating"]
            )

        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
class ZoneCooling(MyPyllantDataClass):
    control_identifier: ControlIdentifier
    setpoint_cooling: float
    operation_mode_cooling: ZoneOperatingMode | ZoneOperatingModeVRC700
    time_program_cooling: ZoneTimeProgram
    manual_mode_setpoint_cooling: float | None = None

    @classmethod
    def from_api(cls, **data):
        data["time_program_cooling"] = ZoneTimeProgram.from_api(
            **data["time_program_cooling"]
        )
        control_identifier: ControlIdentifier = data["control_identifier"]
        if control_identifier.is_vrc700:
            data["operation_mode_cooling"] = ZoneOperatingModeVRC700(
                data["operation_mode_cooling"]
            )
        else:
            data["operation_mode_cooling"] = ZoneOperatingMode(
                data["operation_mode_cooling"]
            )

        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
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


@dataclass(config=MyPyllantConfig)
class Zone(MyPyllantDataClass):
    system_id: str
    general: ZoneGeneral
    timezone: datetime.tzinfo
    control_identifier: ControlIdentifier
    index: int
    zone_binding: str
    heating: ZoneHeating
    current_special_function: ZoneCurrentSpecialFunction
    is_active: bool | None = None
    heating_state: ZoneHeatingState | None = None
    is_cooling_allowed: bool | None = None
    is_manual_cooling_active: bool | None = None
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
    def from_api(cls, **data):
        data["heating"] = ZoneHeating.from_api(
            control_identifier=data["control_identifier"], **data["heating"]
        )
        if "cooling" in data:
            data["cooling"] = ZoneCooling.from_api(
                control_identifier=data["control_identifier"], **data["cooling"]
            )
        data["general"] = ZoneGeneral.from_api(
            timezone=data["timezone"], **data["general"]
        )
        return super().from_api(**data)

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
            ZoneOperatingMode.TIME_CONTROLLED,
            ZoneOperatingModeVRC700.AUTO,
        ]


@dataclass(config=MyPyllantConfig)
class Circuit(MyPyllantDataClass):
    system_id: str
    index: int
    circuit_state: CircuitState
    mixer_circuit_type_external: str | None = None
    set_back_mode_enabled: bool | None = None
    zones: list = field(default_factory=list)
    is_cooling_allowed: bool | None = None
    current_circuit_flow_temperature: float | None = None
    heating_curve: float | None = None
    heating_flow_temperature_minimum_setpoint: float | None = None
    heating_flow_temperature_maximum_setpoint: float | None = None
    min_flow_temperature_setpoint: float | None = None
    calculated_energy_manager_state: str | None = None


@dataclass(config=MyPyllantConfig)
class DHWTimeProgramDay(BaseTimeProgramDay):
    def __eq__(self, other):
        """
        When comparing two DHWTimeProgramDay, we only care about start_time and end_time
        """
        if not isinstance(other, DHWTimeProgramDay):
            return False
        return self.start_time == other.start_time and self.end_time == other.end_time


@dataclass(config=MyPyllantConfig)
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


@dataclass(config=MyPyllantConfig)
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
    def from_api(cls, **data):
        data["time_program_dhw"] = DHWTimeProgram.from_api(**data["time_program_dhw"])
        data["time_program_circulation_pump"] = DHWTimeProgram.from_api(
            **data["time_program_circulation_pump"]
        )
        control_identifier: ControlIdentifier = data["control_identifier"]
        if control_identifier.is_vrc700:
            data["current_special_function"] = DHWCurrentSpecialFunctionVRC700(
                data["current_special_function"]
            )
            data["operation_mode_dhw"] = DHWOperationModeVRC700(
                data["operation_mode_dhw"]
            )
        else:
            data["current_special_function"] = DHWCurrentSpecialFunction(
                data["current_special_function"]
            )
            data["operation_mode_dhw"] = DHWOperationMode(data["operation_mode_dhw"])
        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
class Ventilation(MyPyllantDataClass):
    system_id: str
    index: int
    control_identifier: ControlIdentifier
    maximum_day_fan_stage: int
    maximum_night_fan_stage: int
    operation_mode_ventilation: VentilationOperationMode | VentilationOperationModeVRC700
    time_program_ventilation: dict

    @classmethod
    def from_api(cls, **data):
        control_identifier: ControlIdentifier = data["control_identifier"]
        if control_identifier.is_vrc700:
            data["operation_mode_ventilation"] = VentilationOperationModeVRC700(
                data["operation_mode_ventilation"]
            )
        else:
            data["operation_mode_ventilation"] = VentilationOperationMode(
                data["operation_mode_ventilation"]
            )

        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
class DeviceDataBucket(MyPyllantDataClass):
    start_date: datetime.datetime
    end_date: datetime.datetime
    value: float | None = None


@dataclass(config=MyPyllantConfig)
class DeviceData(MyPyllantDataClass):
    operation_mode: str
    device: Any = None
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
    def from_api(cls, **data):
        data["data_from"] = data.pop("from", None)
        data["data_to"] = data.pop("to", None)
        data["data"] = [
            DeviceDataBucket.from_api(timezone=data["timezone"], **dd)
            for dd in data.pop("data", [])
        ]
        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
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
    mpc: dict | None = None
    rts_statistics: dict | None = None
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
        return self.rts_statistics.get("on_off_cycles") if self.rts_statistics else None

    @property
    def operation_time(self) -> int | None:
        return (
            self.rts_statistics.get("operation_time") if self.rts_statistics else None
        )

    @property
    def current_power(self) -> int | None:
        return self.mpc.get("current_power") if self.mpc else None

    @classmethod
    def from_api(cls, **data):
        device_data = []
        if "data" in data:
            for dd in data["data"]:
                if "timezone" not in dd:
                    dd["timezone"] = data["timezone"]
                device_data.append(DeviceData.from_api(**dd))
        data["data"] = device_data
        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
class RoomTimeProgramDay(BaseTimeProgramDay):
    temperature_setpoint: float | None = None

    @property
    def start_datetime_time(self) -> datetime.time:
        return datetime.time(self.start_time // 60, self.start_time % 60)

    def start_datetime(self, date) -> datetime.datetime:
        return date.replace(
            hour=self.start_time // 60,
            minute=self.start_time % 60,
            second=0,
            microsecond=0,
        )

    def __eq__(self, other):
        """
        When comparing two ZoneTimeProgramDay, we only care about start_time, end_time, and setpoint
        """
        if not isinstance(other, RoomTimeProgramDay):
            return False
        return (
            self.start_time == other.start_time
            and self.temperature_setpoint == other.temperature_setpoint
        )


@dataclass(config=MyPyllantConfig)
class RoomTimeProgram(BaseTimeProgram):
    monday: list[RoomTimeProgramDay]
    tuesday: list[RoomTimeProgramDay]
    wednesday: list[RoomTimeProgramDay]
    thursday: list[RoomTimeProgramDay]
    friday: list[RoomTimeProgramDay]
    saturday: list[RoomTimeProgramDay]
    sunday: list[RoomTimeProgramDay]

    @classmethod
    def dict_factory(cls, obj: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        """
        Only includes certain fields when converting to dict with asdict()
        See https://stackoverflow.com/a/76017464

        Example::

            asdict(time_program, dict_factory=RoomTimeProgram.dict_factory)
        """
        include_fields = cls.weekday_names() + ["temperature_setpoint", "start_time"]
        return {k: v for (k, v) in obj if ((v is not None) and (k in include_fields))}

    @classmethod
    def from_api(cls, **data) -> RoomTimeProgram:
        """
        Unlike the other time programs, the Ambisense room time program does not have an end_time.
        Instead, the end_time is the start_time of the next slot.

        It takes this: {"monday": [{"start_time": 360, "temperature_setpoint": 21.0}, {"start_time": 480, "temperature_setpoint": 22.0}]}
        ...and converts it to this: {"monday": [RoomTimeProgramDay(start_time=360, end_time=480, temperature_setpoint=21.0), RoomTimeProgramDay(start_time=480, end_time=10440, temperature_setpoint=22.0)]}

        In RoomTimeProgramDay, end_time can be greater than 1440 (24h), if it ends on a later day.
        """

        # Keep a copy of the original data, because we need to traverse it to find the next time slot,
        # but we want to overwrite the weekdays with RoomTimeProgramDay instances
        orig_data = data.copy()
        for weekday_index, weekday_name in enumerate(cls.weekday_names()):
            weekday_slots = data.pop(weekday_name, [])
            # Make sure slots are sorted ascending by start time, so the next slot is always later
            sorted(weekday_slots, key=lambda x: x["start_time"])
            data[weekday_name] = []
            for slot_index, weekday_slot in enumerate(weekday_slots):
                if "end_time" in weekday_slot:
                    raise ValueError(
                        "Ambisense room time program does not allow setting end_time"
                    )
                if len(weekday_slots) > slot_index + 1:
                    # If there is another slot on the same day, use its start_time as the end_time
                    end_time = weekday_slots[slot_index + 1]["start_time"]
                else:
                    end_time = None
                    i = 0
                    # Iterate over weekdays until we find one with a time program slot
                    while not end_time:
                        i += 1
                        next_weekday_index = (weekday_index + i) % 7
                        next_day = orig_data.get(
                            cls.weekday_names()[next_weekday_index], []
                        )
                        if next_day:
                            # 24h == 1440min
                            end_time = (i * 1440) + next_day[0]["start_time"]
                        elif i == 7:
                            raise ValueError(
                                "Could not find end_time for time program %s"
                                % weekday_slot
                            )

                data[weekday_name].append(
                    cls.create_day_from_api(
                        index=slot_index,
                        end_time=end_time,
                        weekday_name=weekday_name,
                        **weekday_slot,
                    )
                )
        # Skip from_api of BaseTimeProgram, because we already did the conversion to TimeProgramDay
        return super(BaseTimeProgram, cls).from_api(**data)

    @classmethod
    def create_day_from_api(cls, **kwargs):
        if "setpoint" in kwargs:
            # Allow setpoint as well as temperature_setpoint, for consistency with the other classes
            kwargs["temperature_setpoint"] = kwargs.pop("setpoint")
        return RoomTimeProgramDay(**kwargs)


@dataclass(config=MyPyllantConfig)
class AmbisenseDevice(MyPyllantDataClass):
    device_type: str
    name: str
    sgtin: str
    unreach: bool
    low_bat: bool | None = None
    rssi: int | None = None
    rssi_peer: int | None = None


@dataclass(config=MyPyllantConfig)
class AmbisenseRoomConfiguration(MyPyllantDataClass):
    name: str
    operation_mode: AmbisenseRoomOperationMode | None = None
    current_temperature: float | None = None
    temperature_setpoint: float | None = None
    icon_id: str | None = None
    current_humidity: float | None = None
    button_lock: bool | None = None
    window_state: bool | None = None
    quick_veto_end_time: datetime.datetime | None = None
    devices: list[AmbisenseDevice] = field(default_factory=list)

    @classmethod
    def from_api(cls, **data):
        if data["operation_mode"]:
            data["operation_mode"] = AmbisenseRoomOperationMode(
                data["operation_mode"].upper()
            )
        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
class AmbisenseRoom(MyPyllantDataClass):
    system_id: str
    room_index: int
    room_configuration: AmbisenseRoomConfiguration
    time_program: RoomTimeProgram

    @property
    def name(self) -> str:
        return self.room_configuration.name

    @classmethod
    def from_api(cls, **data):
        data["time_program"] = RoomTimeProgram.from_api(**data["time_program"])
        data["room_configuration"] = AmbisenseRoomConfiguration.from_api(
            **data["room_configuration"]
        )
        return super().from_api(**data)


@dataclass(config=MyPyllantConfig)
class System(MyPyllantDataClass):
    id: str
    state: dict
    configuration: dict
    home: Home
    brand: str
    timezone: datetime.tzinfo
    control_identifier: ControlIdentifier
    connected: bool | None = None
    diagnostic_trouble_codes: list | None = None
    properties: dict = field(default_factory=dict)
    current_system: dict = field(default_factory=dict)
    zones: list[Zone] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
    domestic_hot_water: list[DomesticHotWater] = field(default_factory=list)
    ventilation: list[Ventilation] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    mpc: dict | None = None
    rts: dict | None = None
    ambisense_capability: bool = False
    ambisense_rooms: list[AmbisenseRoom] = field(default_factory=list)

    @classmethod
    def from_api(cls, **data):
        if "home" in data and "id" not in data:
            data["id"] = data["home"].system_id
        ambisense_rooms = data.pop("ambisense_rooms")
        system: System = super().from_api(**data)
        logger.debug(f"Creating related models from state: {data}")
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
        # TODO: Is it called ventilations everywhere, or just on VRC700 controllers?
        if "ventilations" in system.configuration:
            ventilation_key = "ventilations"
        else:
            ventilation_key = "ventilation"
        system.ventilation = [
            Ventilation.from_api(
                system_id=system.id,
                control_identifier=system.control_identifier,
                timezone=system.timezone,
                **d,
            )
            for d in system.merge_object(ventilation_key)
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
        system.ambisense_rooms = [
            AmbisenseRoom.from_api(system_id=system.id, **r) for r in ambisense_rooms
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

    def apply_mpc(self, device):
        mpc = self.mpc_by_device_uuid(device["device_uuid"])
        if mpc:
            device["mpc"] = mpc

    @property
    def raw_devices(self) -> Iterator[tuple[str, dict]]:
        for key, device in self.current_system.items():
            if isinstance(device, list) and key == "secondary_heat_generators":
                for secdevice in device:
                    if isinstance(secdevice, dict) and "device_uuid" in secdevice:
                        self.apply_diagnostic(secdevice)
                        self.apply_rts(secdevice)
                        self.apply_mpc(secdevice)
                        yield key, secdevice
            if isinstance(device, dict) and "device_uuid" in device:
                self.apply_diagnostic(device)
                self.apply_rts(device)
                self.apply_mpc(device)
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
                logger.debug("Error when merging state", exc_info=e)
                state = {}
            try:
                properties = next(
                    c for c in self.properties.get(obj_name, []) if c["index"] == idx
                )
            except (StopIteration, KeyError) as e:
                logger.debug("Error when merging properties", exc_info=e)
                properties = {}
            configuration.update(state)
            configuration.update(properties)
            yield configuration

    @property
    def outdoor_temperature(self) -> float | None:
        try:
            return self.state["system"]["outdoor_temperature"]
        except KeyError:
            logger.debug(
                "Could not get outdoor temperature from system control state",
            )
            return None

    @property
    def outdoor_temperature_average_24h(self) -> float | None:
        try:
            return self.state["system"]["outdoor_temperature_average_24h"]
        except KeyError:
            logger.debug(
                "Could not get outdoor temperature average 24h from system control state",
            )
            return None

    @property
    def water_pressure(self) -> float | None:
        try:
            return self.state["system"]["system_water_pressure"]
        except KeyError:
            logger.debug("Could not get water pressure from system control state")
            return None

    @property
    def cylinder_temperature_sensor_top_dhw(self) -> float | None:
        try:
            return self.state["system"]["cylinder_temperature_sensor_top_d_h_w"]
        except KeyError:
            logger.debug(
                "Could not get top DHW cylinder temperature from system control state"
            )
            return None

    @property
    def cylinder_temperature_sensor_bottom_dhw(self) -> float | None:
        try:
            return self.state["system"]["cylinder_temperature_sensor_bottom_d_h_w"]
        except KeyError:
            logger.debug(
                "Could not get bottom DHW cylinder temperature from system control state"
            )
            return None

    @property
    def cylinder_temperature_sensor_top_ch(self) -> float | None:
        try:
            return self.state["system"]["cylinder_temperature_sensor_top_c_h"]
        except KeyError:
            logger.debug(
                "Could not get top CH cylinder temperature from system control state"
            )
            return None

    @property
    def cylinder_temperature_sensor_bottom_ch(self) -> float | None:
        try:
            return self.state["system"]["cylinder_temperature_sensor_bottom_c_h"]
        except KeyError:
            logger.debug(
                "Could not get bottom CH cylinder temperature from system control state"
            )
            return None

    @property
    def is_cooling_allowed(self) -> bool:
        return any([z.is_cooling_allowed for z in self.zones])

    @property
    def manual_cooling_start_date(self) -> datetime.datetime | None:
        manual_cooling_start_date = self.configuration.get("system", {}).get(
            "manual_cooling_start_date"
        )
        if manual_cooling_start_date:
            return datetime_parse(
                manual_cooling_start_date,
                self.timezone,
            )
        return None

    @property
    def manual_cooling_end_date(self) -> datetime.datetime | None:
        manual_cooling_end_date = self.configuration.get("system", {}).get(
            "manual_cooling_end_date"
        )
        if manual_cooling_end_date:
            return datetime_parse(
                manual_cooling_end_date,
                self.timezone,
            )
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
        if not self.rts:
            return None
        statistics = [
            s for s in self.rts.get("statistics", []) if s["device_id"] == device_uuid
        ]
        return statistics[0] if statistics else None

    def mpc_by_device_uuid(self, device_uuid: str) -> dict | None:
        if not self.mpc:
            return None
        mpc = [m for m in self.mpc.get("devices", []) if m["device_id"] == device_uuid]
        return mpc[0] if mpc else None

    @property
    def manual_cooling_planned(self) -> bool:
        return (
            self.manual_cooling_start_date is not None
            and self.manual_cooling_end_date is not None
            and self.manual_cooling_end_date > datetime.datetime.now(self.timezone)
        )

    @property
    def manual_cooling_start_in_future(self) -> bool:
        return (
            self.manual_cooling_start_date is not None
            and self.manual_cooling_start_date > datetime.datetime.now(self.timezone)
        )

    @property
    def manual_cooling_ongoing(self) -> bool:
        return (
            self.manual_cooling_start_date is not None
            and self.manual_cooling_end_date is not None
            and self.manual_cooling_start_date
            < datetime.datetime.now(self.timezone)
            < self.manual_cooling_end_date
        )

    @property
    def manual_cooling_remaining(self) -> datetime.timedelta | None:
        return (
            self.manual_cooling_end_date - datetime.datetime.now(self.timezone)
            if self.manual_cooling_end_date and self.manual_cooling_ongoing
            else None
        )


@dataclass(config=MyPyllantConfig)
class SystemReport(MyPyllantDataClass):
    file_name: str
    file_content: str
