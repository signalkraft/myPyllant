#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

from myPyllant.api import MyPyllantAPI
from myPyllant.enums import DeviceDataBucketResolution
from myPyllant.utils import add_default_parser_args

parser = argparse.ArgumentParser(description="Export data from myVaillant API.")
add_default_parser_args(parser)
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
    user,
    password,
    brand,
    country=None,
    data=False,
    resolution=None,
    start=None,
    end=None,
):
    async with MyPyllantAPI(user, password, brand, country) as api:
        export_list = []
        async for system in api.get_systems(
            include_connection_status=True,
            include_diagnostic_trouble_codes=True,
            include_rts=True,
            include_mpc=True,
        ):
            if data:
                for device in system.devices:
                    data = [
                        d.prepare_dict()
                        async for d in api.get_data_by_device(
                            device, resolution, start, end
                        )
                    ]
                    export_list.append(dict(device=device.prepare_dict(), data=data))

            else:
                export_list.append(system.prepare_dict())

        return export_list


if __name__ == "__main__":
    args = parser.parse_args()
    kwargs = vars(args)
    verbose = kwargs.pop("verbose")
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    result = asyncio.run(main(**kwargs))
    sys.stdout.write(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )
    sys.stdout.write("\n")
