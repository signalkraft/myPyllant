#!/usr/bin/env python3

import argparse
import asyncio
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlencode

sys.path.append((Path(__file__).resolve().parent / "src").name)

parser = argparse.ArgumentParser(
    description="Generates test data necessary to run integration tests."
)
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")


JSON_DIR = Path(__file__).resolve().parent / "json"
ANONYMIZE_ATTRIBUTES = (
    "device_uuid",
    "device_serial_number",
    "deviceId",
    "serialNumber",
    "systemId",
)


async def main(user, password):
    """
    Generate json data for running testcases.

    :param user:
    :param password:
    :return:
    """
    from myPyllant.api import API_URL_BASE, MyPyllantAPI
    from myPyllant.models import DeviceDataBucketResolution
    from myPyllant.utils import datetime_format

    async with MyPyllantAPI(user, password) as api:
        systems_url = f"{API_URL_BASE}/systems"
        async with api.aiohttp_session.get(
            systems_url, headers=api.get_authorized_headers()
        ) as systems_resp:
            system = await systems_resp.json()
            with open(JSON_DIR / "systems.json", "w") as fh:
                anonymized_system = _recursive_data_anonymize(copy.deepcopy(system))
                fh.write(json.dumps(anonymized_system, indent=2))

        system_url = f"{API_URL_BASE}/emf/v2/{system[0]['systemId']}/currentSystem"
        async with api.aiohttp_session.get(
            system_url, headers=api.get_authorized_headers()
        ) as current_system_resp:
            with open(JSON_DIR / "current_system.json", "w") as fh:
                current_system = await current_system_resp.json()
                anonymized_current_system = _recursive_data_anonymize(
                    copy.deepcopy(current_system)
                )
                fh.write(json.dumps(anonymized_current_system, indent=2))

        device = current_system["primary_heat_generator"]
        start = datetime.now().replace(
            microsecond=0, second=0, minute=0, hour=0
        ) - timedelta(days=1)
        end = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)
        querystring = {
            "resolution": DeviceDataBucketResolution.DAY,
            "operationMode": device["data"][0]["operation_mode"],
            "energyType": device["data"][0]["value_type"],
            "startDate": datetime_format(start),
            "endDate": datetime_format(end),
        }
        device_buckets_url = (
            f"{API_URL_BASE}/emf/v2/{system[0]['systemId']}/"
            f"devices/{device['device_uuid']}/buckets?{urlencode(querystring)}"
        )
        async with api.aiohttp_session.get(
            device_buckets_url, headers=api.get_authorized_headers()
        ) as device_buckets_resp:
            with open(JSON_DIR / "device_buckets.json", "w") as fh:
                device_buckets = await device_buckets_resp.json()
                fh.write(json.dumps(device_buckets, indent=2))


def _recursive_data_anonymize(data: str | dict | list) -> dict:
    if isinstance(data, list):
        for elem in data:
            _recursive_data_anonymize(elem)

    elif isinstance(data, dict):
        for elem in data.keys():
            if elem in ANONYMIZE_ATTRIBUTES:
                data[elem] = hashlib.sha1(data[elem].encode("UTF-8")).hexdigest()
                continue
            _recursive_data_anonymize(data[elem])

    return data


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(**vars(args)))
