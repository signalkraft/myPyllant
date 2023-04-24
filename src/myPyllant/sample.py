#!/usr/bin/env python3

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from myPyllant.api import MyPyllantAPI
from myPyllant.const import BRANDS, COUNTRIES, DEFAULT_BRAND

parser = argparse.ArgumentParser(description="Export data from myVaillant API   .")
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
    "-v", "--verbose", help="increase output verbosity", action="store_true"
)


async def main(user, password, country, brand):
    async with MyPyllantAPI(user, password, country, brand) as api:
        async for system in api.get_systems():
            print(await api.get_time_zone(system))
            print(await api.set_holiday(system))
            print(
                await api.set_holiday(
                    system, datetime.now(), datetime.now() + timedelta(days=7)
                )
            )
            print(await api.get_time_zone(system))
            print(await api.cancel_holiday(system))
            print(await api.boost_domestic_hot_water(system.domestic_hot_water[0]))
            print(await api.cancel_hot_water_boost(system.domestic_hot_water[0]))
            print(
                await api.set_domestic_hot_water_temperature(
                    system.domestic_hot_water[0], 46
                )
            )
            print(await api.set_set_back_temperature(system.zones[0], 15.5))
            print(await api.quick_veto_zone_temperature(system.zones[0], 21, 5))
            print(await api.cancel_quick_veto_zone_temperature(system.zones[0]))


if __name__ == "__main__":
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(args.user, args.password, args.country, args.brand))
