# myPyllant

![PyPI](https://img.shields.io/pypi/v/myPyllant)

A Python library to interact with the API behind the myVAILLANT app.

![myPyllant](https://raw.githubusercontent.com/signalkraft/myPyllant/main/logo.png)

## Install and test

```shell
pip install myPyllant
python3 -m myPyllant.export username password (--data)
```
The `--data` argument exports historical data of the devices in your system.
Without this keyword, information about your system will be exported as JSON.

## Samples

```python
import argparse
import asyncio
from datetime import datetime, timedelta

from myPyllant.session import login, get_session
from myPyllant.services import get_systems, set_holiday, cancel_holiday, boost_domestic_hot_water, cancel_quick_veto_zone_temperature, cancel_hot_water_boost, set_domestic_hot_water_temperature, set_set_back_temperature, quick_veto_zone_temperature


parser = argparse.ArgumentParser(description='Export data from myVaillant API   .')
parser.add_argument('user', help='Username (email address) for the myVaillant app')
parser.add_argument('password', help='Password for the myVaillant app')


async def main(user, password):
    try:
        await login(user, password)
        async for system in get_systems():
            print(await set_holiday(system, datetime.now()))
            print(await set_holiday(system, datetime.now(), datetime.now() + timedelta(days=1)))
            print(await cancel_holiday(system))
            print(await boost_domestic_hot_water(system.domestic_hot_water[0]))
            print(await cancel_hot_water_boost(system.domestic_hot_water[0]))
            print(await set_domestic_hot_water_temperature(system.domestic_hot_water[0], 46))
            print(await set_set_back_temperature(system.zones[0], 15.5))
            print(await quick_veto_zone_temperature(system.zones[0], 21, 5))
            print(await cancel_quick_veto_zone_temperature(system.zones[0]))
    finally:
        await get_session().close()


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(args.user, args.password))

```