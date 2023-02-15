import argparse
import asyncio
from datetime import datetime, timedelta

from myPyllant.api import MyPyllantAPI


parser = argparse.ArgumentParser(description="Export data from myVaillant API   .")
parser.add_argument("user", help="Username (email address) for the myVaillant app")
parser.add_argument("password", help="Password for the myVaillant app")


async def main(user, password):
    async with MyPyllantAPI(user, password) as api:
        async for system in api.get_systems():
            print(await api.set_holiday(system, datetime.now()))
            print(
                await api.set_holiday(
                    system, datetime.now(), datetime.now() + timedelta(days=1)
                )
            )
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
    asyncio.run(main(args.user, args.password))
