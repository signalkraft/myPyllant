from datetime import datetime, timedelta
import json

from freezegun import freeze_time
import pytest

from myPyllant.api import MyPyllantAPI
from myPyllant.export import main as export_main
from myPyllant.models import Device, DeviceData, DeviceDataBucket, System

from .generate_test_data import JSON_DIR


async def test_login() -> None:
    with pytest.raises(ValueError) as _:
        MyPyllantAPI("test@example.com", "test", "invalid")
