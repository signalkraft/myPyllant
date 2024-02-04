#!/usr/bin/env python3

import argparse
import asyncio
import logging
from datetime import datetime, timedelta

from myPyllant.api import MyPyllantAPI
from myPyllant.const import ALL_COUNTRIES, BRANDS, DEFAULT_BRAND

parser = argparse.ArgumentParser(description="Export data from myVaillant API   .")
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")
parser.add_argument(
    "brand",
    help="Brand your account is registered in, i.e. 'vaillant'",
    default=DEFAULT_BRAND,
    choices=BRANDS.keys(),
)
parser.add_argument(
    "--country",
    help="Country your account is registered in, i.e. 'germany'",
    choices=ALL_COUNTRIES.keys(),
    required=False,
)
parser.add_argument(
    "-v", "--verbose", help="increase output verbosity", action="store_true"
)


async def main(user, password, brand, country):
    async with MyPyllantAPI(user, password, brand, country) as api:
        async for system in api.get_systems():
            print(await api.set_set_back_temperature(system.zones[0], 18))
            print(await api.quick_veto_zone_temperature(system.zones[0], 21, 5))
            print(await api.cancel_quick_veto_zone_temperature(system.zones[0]))
            setpoint = 10.0 if system.control_identifier.is_vrc700 else None
            print(
                await api.set_holiday(
                    system,
                    datetime.now(system.timezone),
                    datetime.now(system.timezone) + timedelta(days=7),
                    setpoint,  # Setpoint is only required for VRC700 systems
                )
            )
            print(await api.cancel_holiday(system))
            if system.domestic_hot_water:
                print(await api.boost_domestic_hot_water(system.domestic_hot_water[0]))
                print(await api.cancel_hot_water_boost(system.domestic_hot_water[0]))
                print(
                    await api.set_domestic_hot_water_temperature(
                        system.domestic_hot_water[0], 46
                    )
                )


if __name__ == "__main__":
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(args.user, args.password, args.brand, args.country))
