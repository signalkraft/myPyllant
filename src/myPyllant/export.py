#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

from myPyllant.api import MyPyllantAPI
from myPyllant.const import BRANDS, COUNTRIES, DEFAULT_BRAND
from myPyllant.models import DeviceDataBucketResolution

parser = argparse.ArgumentParser(description="Export data from myVaillant API.")
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")
parser.add_argument(
    "country",
    help="Country your account is registered in, i.e. 'germany'",
    choices=COUNTRIES[DEFAULT_BRAND].keys(),
)
parser.add_argument(
    "brand",
    help="Brand your account is registered in, i.e. 'vaillant'",
    default=DEFAULT_BRAND,
    choices=BRANDS.keys(),
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
parser.add_argument(
    "-v", "--verbose", help="increase output verbosity", action="store_true"
)


async def main(
    user, password, country, brand, data=False, resolution=None, start=None, end=None
):
    async with MyPyllantAPI(user, password, country, brand) as api:
        async for system in api.get_systems():
            if data:
                data_list = []
                for device in system.devices:
                    data = [
                        d.dict()
                        async for d in api.get_data_by_device(
                            device, resolution, start, end
                        )
                    ]
                    data_list.append(dict(device=device.dict(), data=data))
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
    kwargs = vars(args)
    verbose = kwargs.pop("verbose")
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    asyncio.run(main(**kwargs))
