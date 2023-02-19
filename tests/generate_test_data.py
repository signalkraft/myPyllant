#!/usr/bin/env python3

import argparse
import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path
from urllib.parse import urlencode

from myPyllant.api import API_URL_BASE, MyPyllantAPI
from myPyllant.models import DeviceDataBucketResolution
from myPyllant.utils import datetime_format

parser = argparse.ArgumentParser(
    description="Generates test data necessary to run integration tests."
)
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")


JSON_DIR = Path(__file__).resolve().parent / "json"


async def main(user, password):
    """
    Generate json data for running testcases.

    :param user:
    :param password:
    :return:
    """
    async with MyPyllantAPI(user, password) as api:
        systems_url = f"{API_URL_BASE}/systems"
        async with api.aiohttp_session.get(
            systems_url, headers=api.get_authorized_headers()
        ) as systems_resp:
            system = await systems_resp.json()
            with open(JSON_DIR / "systems.json", "w") as fh:
                fh.write(json.dumps(await systems_resp.json(), indent=2))

        system_url = f"{API_URL_BASE}/emf/v2/{system[0]['systemId']}/currentSystem"
        async with api.aiohttp_session.get(
            system_url, headers=api.get_authorized_headers()
        ) as current_system_resp:
            with open(JSON_DIR / "current_system.json", "w") as fh:
                current_system = await current_system_resp.json()
                fh.write(json.dumps(current_system, indent=2))

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


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(**vars(args)))
