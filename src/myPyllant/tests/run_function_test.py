#!/usr/bin/env python3

import argparse
import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timedelta

from myPyllant.api import MyPyllantAPI
from myPyllant.models import MyPyllantDataClass
from myPyllant.utils import add_default_parser_args, recursive_compare

parser = argparse.ArgumentParser(
    description="Test service calls with real API, without changing anything."
)
add_default_parser_args(parser)
parser.add_argument(
    "-v", "--verbose", help="increase output verbosity", action="store_true"
)


async def print_changes(func, object: MyPyllantDataClass, *args, **kwargs):
    old = asdict(object)
    new: MyPyllantDataClass = await func(object, *args, **kwargs)
    print(f"{func.__name__} changes:")
    recursive_compare(old, asdict(new))
    print()


async def main(user, password, brand, country):
    async with MyPyllantAPI(user, password, brand, country) as api:
        async for system in api.get_systems(
            include_connection_status=True,
            include_diagnostic_trouble_codes=True,
        ):
            if system.control_identifier.is_vrc700:
                await print_changes(
                    api.set_holiday,
                    system,
                    datetime.now(system.timezone),
                    datetime.now(system.timezone) + timedelta(days=7),
                    10.0,
                )
            else:
                await print_changes(
                    api.set_holiday,
                    system,
                    datetime.now(system.timezone),
                    datetime.now(system.timezone) + timedelta(days=7),
                )
            await print_changes(api.cancel_holiday, system)
            if system.zones:
                zone = system.zones[0]
                await print_changes(
                    api.set_set_back_temperature,
                    zone,
                    zone.heating.set_back_temperature,
                )
                if zone.heating.manual_mode_setpoint_heating:
                    await print_changes(
                        api.set_manual_mode_setpoint,
                        zone,
                        zone.heating.manual_mode_setpoint_heating,
                    )
                await print_changes(
                    api.set_zone_operating_mode,
                    zone,
                    zone.heating.operation_mode_heating,
                )
                await print_changes(api.quick_veto_zone_temperature, zone, 21, 5)
                await print_changes(api.cancel_quick_veto_zone_temperature, zone)
                if zone.heating.time_program_heating:
                    await print_changes(
                        api.set_zone_time_program,
                        zone,
                        "heating",
                        zone.heating.time_program_heating,
                    )

                    if zone.heating.time_program_heating.monday[0].setpoint:
                        await print_changes(
                            api.set_time_program_temperature,
                            zone,
                            "heating",
                            zone.heating.time_program_heating.monday[0].setpoint,
                        )

            if system.domestic_hot_water:
                dhw = system.domestic_hot_water[0]
                await print_changes(
                    api.set_domestic_hot_water_operation_mode,
                    dhw,
                    dhw.operation_mode_dhw,
                )
                await print_changes(api.boost_domestic_hot_water, dhw)
                await print_changes(api.cancel_hot_water_boost, dhw)

                if dhw.tapping_setpoint:
                    await print_changes(
                        api.set_domestic_hot_water_temperature,
                        dhw,
                        int(dhw.tapping_setpoint),
                    )
                await print_changes(
                    api.set_domestic_hot_water_time_program, dhw, dhw.time_program_dhw
                )
                await print_changes(
                    api.set_domestic_hot_water_circulation_time_program,
                    dhw,
                    dhw.time_program_circulation_pump,
                )


if __name__ == "__main__":
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(args.user, args.password, args.brand, args.country))
