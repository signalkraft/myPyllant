#!/usr/bin/env python3

import argparse
import asyncio
from datetime import datetime
import json
import sys

from myPyllant.api import MyPyllantAPI
from myPyllant.const import COUNTRIES
from myPyllant.models import DeviceDataBucketResolution

parser = argparse.ArgumentParser(description="Export data from myVaillant API.")
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")
parser.add_argument(
    "country",
    help="Country your account is registered in, i.e. 'germany'",
    choices=COUNTRIES.keys(),
)
parser.add_argument(
    "-d",
    "--data",
    action=argparse.BooleanOptionalAction,
    help="Export historical device data",
)
parser.add_argument(
    "-r",
    "--resolution",
    type=DeviceDataBucketResolution,
    choices=DeviceDataBucketResolution,
    default=DeviceDataBucketResolution.DAY,
    help="Export historical device data (energy usage, etc.) in this resolution",
)
parser.add_argument(
    "-s",
    "--start",
    type=datetime.fromisoformat,
    help="Date where the data should start (ISO format)",
)
parser.add_argument(
    "-e",
    "--end",
    type=datetime.fromisoformat,
    help="Date where the data should end (ISO format)",
)


async def main(
    user, password, country, data=False, resolution=None, start=None, end=None
):
    async with MyPyllantAPI(user, password, country) as api:
        async for system in api.get_systems():
            if data:
                data_list = [
                    {
                        "device": d.dict()
                        | {
                            "data": [
                                d
                                async for d in api.get_data_by_device(
                                    d, resolution, start, end
                                )
                            ]
                        }
                    }
                    async for d in api.get_devices_by_system(system)
                ]
                sys.stdout.write(
                    json.dumps(
                        data_list,
                        indent=2,
                        default=str,
                    )
                )
            else:
                sys.stdout.write(json.dumps(system.dict(), indent=2, default=str))
                sys.stdout.write("\n")


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(**vars(args)))
