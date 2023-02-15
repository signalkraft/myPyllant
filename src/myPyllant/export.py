#!/usr/bin/env python3

import argparse
import asyncio
import json

from myPyllant.api import MyPyllantAPI


parser = argparse.ArgumentParser(description="Export data from myVaillant API.")
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")
parser.add_argument(
    "-d",
    "--data",
    action="store_true",
    help="Export historical device data (energy useage, etc.)",
)


async def main(user, password, data=False):
    async with MyPyllantAPI(user, password) as api:
        async for system in api.get_systems():
            if data:
                data_list = [
                    d.dict()
                    async for d in api.get_devices_by_system(system, get_buckets=True)
                ]
                print(
                    json.dumps(
                        data_list,
                        indent=2,
                        default=str,
                    )
                )
            else:
                print(json.dumps(system.dict(), indent=2, default=str))


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(args.user, args.password, args.data))
