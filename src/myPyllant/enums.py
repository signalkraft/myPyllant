from __future__ import annotations

from enum import EnumMeta, Enum


class MyPyllantEnumMeta(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        else:
            return True


class MyPyllantEnum(str, Enum, metaclass=MyPyllantEnumMeta):
    def __str__(self):
        """
        Return 'HOUR' instead of 'DeviceDataBucketResolution.HOUR'
        """
        return self.value

    @property
    def display_value(self) -> str:
        return self.value.replace("_", " ").title()


class ControlIdentifier(MyPyllantEnum):
    TLI = "tli"
    VRC700 = "vrc700"

    @property
    def is_vrc700(self) -> bool:
        return self == ControlIdentifier.VRC700


class CircuitState(MyPyllantEnum):
    HEATING = "HEATING"
    COOLING = "COOLING"
    STANDBY = "STANDBY"


class DeviceDataBucketResolution(MyPyllantEnum):
    HOUR = "HOUR"
    DAY = "DAY"
    MONTH = "MONTH"


class ZoneOperatingMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class ZoneOperatingModeVRC700(MyPyllantEnum):
    DAY = "DAY"
    AUTO = "AUTO"
    SET_BACK = "SET_BACK"
    OFF = "OFF"


class ZoneCurrentSpecialFunction(MyPyllantEnum):
    NONE = "NONE"
    QUICK_VETO = "QUICK_VETO"
    HOLIDAY = "HOLIDAY"
    SYSTEM_OFF = "SYSTEM_OFF"
    VENTILATION_BOOST = "VENTILATION_BOOST"
    ONE_DAY_BANK_HOLIDAY = "ONE_DAY_BANK_HOLIDAY"


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


class DHWCurrentSpecialFunctionVRC700(MyPyllantEnum):
    CYLINDER_BOOST = "CYLINDER_BOOST"
    HOLIDAY = "HOLIDAY"
    NONE = "NONE"


class DHWOperationMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class DHWOperationModeVRC700(MyPyllantEnum):
    DAY = "DAY"
    AUTO = "AUTO"
    OFF = "OFF"


class VentilationOperationMode(MyPyllantEnum):
    NORMAL = "NORMAL"
    REDUCED = "REDUCED"
    TIME_CONTROLLED = "TIME_CONTROLLED"
    OFF = "OFF"


class VentilationOperationModeVRC700(MyPyllantEnum):
    """
    TODO: Other than AUTO, these are just guesses
    """

    DAY = "DAY"
    AUTO = "AUTO"
    SET_BACK = "SET_BACK"
    OFF = "OFF"
    NORMAL = "NORMAL"
    REDUCED = "REDUCED"


class VentilationFanStageType(MyPyllantEnum):
    DAY = "DAY"
    NIGHT = "NIGHT"


class AmbisenseRoomOperationMode(MyPyllantEnum):
    MANUAL = "MANUAL"
    OFF = "OFF"
    AUTO = "AUTO"
