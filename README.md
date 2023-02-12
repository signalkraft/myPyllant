# myPyllant

[![PyPI](https://img.shields.io/pypi/v/myPyllant)](https://pypi.org/project/myPyllant/)

A Python library to interact with the API behind the myVAILLANT app.

Not affiliated with Vaillant, the developers take no responsibility for anything that happens to your Vaillant devices because of this library.

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

## Notes

* Auth is loosely based on https://github.com/TA2k/ioBroker.vaillant
* Most API endpoints are reverse-engineered from the myVaillant app, using https://github.com/mitmproxy/mitmproxy
* Tested on a Vaillant aroTHERM plus heatpump with sensoCOMFORT VRC 720 and sensoNET VR 921
* I'm happy to accept PRs, if you can test them yourself

Logo based on [Hase Icons erstellt von Freepik - Flaticon](https://www.flaticon.com/de/kostenlose-icons/hase) & [Ouroboros Icons erstellt von Freepik - Flaticon](https://www.flaticon.com/de/kostenlose-icons/ouroboros).