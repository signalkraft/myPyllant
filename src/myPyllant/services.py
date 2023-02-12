import datetime
from urllib.parse import urlencode

from myPyllant.session import get_session, get_authorized_headers
from myPyllant.models import System, Circuit, Device, DomesticHotWater, Zone
from myPyllant.utils import dict_to_snake_case


base_api_url = (
    "https://api.vaillant-group.com/service-connected-control/end-user-app-api/v1"
)


async def get_systems():
    session = get_session()
    systems_url = f"{base_api_url}/systems"
    async with session.get(
        systems_url, headers=get_authorized_headers()
    ) as systems_resp:
        for system_json in await systems_resp.json():
            system_id = system_json["systemId"]
            system_url = f"{base_api_url}/emf/v2/{system_id}/currentSystem"

            async with session.get(
                system_url, headers=get_authorized_headers()
            ) as current_system_resp:
                current_system = await current_system_resp.json()
            system = System(
                id=system_id,
                current_system=current_system,
                **dict_to_snake_case(system_json),
            )
            yield system


async def get_devices_by_system(system: System, get_buckets: bool = False):
    session = get_session()
    for device_raw in system.current_system.values():
        if not (isinstance(device_raw, dict) and "device_uuid" in device_raw):
            continue
        device = Device(
            system=system,
            **device_raw,
        )

        serial_nos = {d["serial_number"]: d for d in system.devices}

        if device.device_serial_number in serial_nos.keys():
            device_info = serial_nos[device.device_serial_number]
            device.operational_data = dict_to_snake_case(
                device_info.get("operational_data", {})
            )
            device.name = device_info.get("name", "")

        if get_buckets:
            for data in device.data:
                querystring = {
                    "resolution": "DAY",
                    "operationMode": data["operation_mode"],
                    "energyType": data["value_type"],
                    "startDate": data["from"],
                    "endDate": data["to"],
                }
                device_buckets_url = f"{base_api_url}/emf/v2/{system.id}/devices/{device.device_uuid}/buckets?{urlencode(querystring)}"
                async with session.get(
                    device_buckets_url, headers=get_authorized_headers()
                ) as device_buckets_resp:
                    data["buckets"] = dict_to_snake_case(
                        (await device_buckets_resp.json())["data"]
                    )
        yield device


async def quick_veto_zone_temperature(
    zone: Zone, temperature: float, duration_hours: int
):
    session = get_session()
    url = f"{base_api_url}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
    return await session.patch(
        url,
        json={
            "desiredRoomTemperatureSetpoint": temperature,
            "duration": duration_hours,
        },
        headers=get_authorized_headers(),
    )


async def cancel_quick_veto_zone_temperature(zone: Zone):
    session = get_session()
    url = f"{base_api_url}/systems/{zone.system_id}/zones/{zone.index}/quickVeto"
    return await session.delete(url, headers=get_authorized_headers())


async def set_set_back_temperature(zone: Zone, temperature: float):
    session = get_session()
    url = (
        f"{base_api_url}/systems/{zone.system_id}/zones/{zone.index}/setBackTemperature"
    )
    return await session.patch(
        url, json={"setBackTemperature": temperature}, headers=get_authorized_headers()
    )


async def set_holiday(
    system: System, start: datetime.datetime, end: datetime.datetime = None
):
    if not end:
        # Set away for a long time if no end date is set
        end = start + datetime.timedelta(days=365)
    assert start < end
    session = get_session()
    url = f"{base_api_url}/systems/{system.id}/holiday"
    data = {
        "holidayStartDateTime": start.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "holidayEndDateTime": end.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }
    return await session.post(url, json=data, headers=get_authorized_headers())


async def cancel_holiday(system: System):
    session = get_session()
    url = f"{base_api_url}/systems/{system.id}/holiday"
    return await session.delete(url, headers=get_authorized_headers())


async def set_domestic_hot_water_temperature(
    domestic_hot_water: DomesticHotWater, temperature: int
):
    session = get_session()
    url = f"{base_api_url}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/temperature"
    return await session.post(
        url, json={"setPoint": temperature}, headers=get_authorized_headers()
    )


async def boost_domestic_hot_water(domestic_hot_water: DomesticHotWater):
    session = get_session()
    url = f"{base_api_url}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/boost"
    return await session.post(url, json={}, headers=get_authorized_headers())


async def cancel_hot_water_boost(domestic_hot_water: DomesticHotWater):
    session = get_session()
    url = f"{base_api_url}/systems/{domestic_hot_water.system_id}/domesticHotWater/{domestic_hot_water.index}/boost"
    return await session.delete(url, headers=get_authorized_headers())
