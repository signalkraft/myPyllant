#!/usr/bin/env python3

import argparse
import asyncio
import copy
import hashlib
import json
import logging
import secrets
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from myPyllant.utils import add_default_parser_args

logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(
    description="Generates test data necessary to run integration tests."
)
add_default_parser_args(parser)
parser.add_argument(
    "--debug", help="Print debug information", action=argparse.BooleanOptionalAction
)
parser.add_argument(
    "--system",
    help="If you have multiple systems, you need to pick one",
    required=False,
)

SALT = secrets.token_bytes(16)
JSON_DIR = Path(__file__).resolve().parent / "json"
ANONYMIZE_ATTRIBUTES = (
    "device_uuid",
    "device_serial_number",
    "deviceId",
    "homeName",
    "serialNumber",
    "systemId",
)


def user_json_dir(user: str) -> Path:
    return (
        JSON_DIR
        / hashlib.sha1(user.encode("UTF-8") + SALT, usedforsecurity=False).hexdigest()
    )


async def main(user, password, brand, country=None, system_index=None):
    """
    Generate json data for running testcases.

    :param user:
    :param password:
    :param brand:
    :param country:
    :return:
    """
    from myPyllant.api import MyPyllantAPI
    from myPyllant.const import API_URL_BASE
    from myPyllant.models import DeviceDataBucketResolution
    from myPyllant.utils import datetime_format

    json_dir = user_json_dir(user)
    json_dir.mkdir(parents=True, exist_ok=True)

    async with MyPyllantAPI(user, password, brand, country) as api:
        homes_url = f"{API_URL_BASE}/homes"
        async with api.aiohttp_session.get(
            homes_url, headers=api.get_authorized_headers()
        ) as homes_resp:
            homes = await homes_resp.json()
            with open(json_dir / "homes.json", "w") as fh:
                anonymized_homes = _recursive_data_anonymize(copy.deepcopy(homes), SALT)
                for system in anonymized_homes:
                    if "address" in system:
                        system.pop("address")
                fh.write(json.dumps(anonymized_homes, indent=2))

        if not homes:
            # No homes means no systems to generate test data for
            print("No homes found.")
            print(f"Wrote homes.json to {json_dir}")
            exit(0)
        elif len(homes) > 1:
            # Multiple systems are claimed by the same user account
            if system_index is not None and 0 <= system_index < len(homes):
                system_id = homes[system_index]["systemId"]
            else:
                print(
                    f"Multiple systems found. "
                    f"Please pick a valid --system, choices are {', '.join([str(i) for i in range(0, len(homes))])}"
                )
                exit(1)
        else:
            # Only one system is claimed
            system_id = homes[0]["systemId"]

        control_identifier_url = (
            f"{API_URL_BASE}/systems/{system_id}/meta-info/control-identifier"
        )
        async with api.aiohttp_session.get(
            control_identifier_url, headers=api.get_authorized_headers()
        ) as ci_response:
            with open(json_dir / "control_identifier.json", "w") as fh:
                control_identifier = await ci_response.json()
                fh.write(json.dumps(control_identifier, indent=2))

        tz_url = f"{API_URL_BASE}/systems/{system_id}/meta-info/time-zone"
        async with api.aiohttp_session.get(
            tz_url, headers=api.get_authorized_headers()
        ) as tz_response:
            with open(json_dir / "time_zone.json", "w") as fh:
                fh.write(json.dumps(await tz_response.json(), indent=2))

        dtc_url = f"{API_URL_BASE}/systems/{system_id}/diagnostic-trouble-codes"
        async with api.aiohttp_session.get(
            dtc_url, headers=api.get_authorized_headers()
        ) as dtc_response:
            dtc = await dtc_response.json()
            anonymized_dtc = _recursive_data_anonymize(copy.deepcopy(dtc), SALT)
            with open(json_dir / "diagnostic_trouble_codes.json", "w") as fh:
                fh.write(json.dumps(anonymized_dtc, indent=2))

        connection_status_url = (
            f"{API_URL_BASE}/systems/{system_id}/meta-info/connection-status"
        )
        async with api.aiohttp_session.get(
            connection_status_url, headers=api.get_authorized_headers()
        ) as status_resp:
            with open(json_dir / "connection_status.json", "w") as fh:
                fh.write(json.dumps(await status_resp.json(), indent=2))

        system_url = f"{API_URL_BASE}/systems/{system_id}/{control_identifier['controlIdentifier']}"
        async with api.aiohttp_session.get(
            system_url, headers=api.get_authorized_headers()
        ) as system_resp:
            with open(json_dir / "system.json", "w") as fh:
                system = await system_resp.json()
                anonymized_homes = _recursive_data_anonymize(
                    copy.deepcopy(system), SALT
                )
                fh.write(json.dumps(anonymized_homes, indent=2))

        current_system_url = f"{API_URL_BASE}/emf/v2/{system_id}/currentSystem"
        async with api.aiohttp_session.get(
            current_system_url, headers=api.get_authorized_headers()
        ) as current_system_resp:
            with open(json_dir / "current_system.json", "w") as fh:
                current_system = await current_system_resp.json()
                anonymized_current_system = _recursive_data_anonymize(
                    copy.deepcopy(current_system), SALT
                )
                fh.write(json.dumps(anonymized_current_system, indent=2))

        mpc_url = f"{API_URL_BASE}/hem/{system_id}/mpc"
        async with api.aiohttp_session.get(
            mpc_url, headers=api.get_authorized_headers()
        ) as mpc_resp:
            with open(json_dir / "mpc.json", "w") as fh:
                mpc = await mpc_resp.json()
                anonymized_mpc = _recursive_data_anonymize(copy.deepcopy(mpc), SALT)
                fh.write(json.dumps(anonymized_mpc, indent=2))

        device = current_system["primary_heat_generator"]
        start = datetime.now().replace(
            microsecond=0, second=0, minute=0, hour=0
        ) - timedelta(days=1)
        end = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)
        querystring = {
            "resolution": DeviceDataBucketResolution.HOUR,
            "operationMode": device["data"][0]["operation_mode"],
            "energyType": device["data"][0]["value_type"],
            "startDate": datetime_format(start),
            "endDate": datetime_format(end),
        }
        device_buckets_url = (
            f"{API_URL_BASE}/emf/v2/{system_id}/"
            f"devices/{device['device_uuid']}/buckets?{urlencode(querystring)}"
        )
        async with api.aiohttp_session.get(
            device_buckets_url, headers=api.get_authorized_headers()
        ) as device_buckets_resp:
            with open(json_dir / "device_buckets.json", "w") as fh:
                device_buckets = await device_buckets_resp.json()
                fh.write(json.dumps(device_buckets, indent=2))
        print(f"Wrote test data to {json_dir}")


def _recursive_data_anonymize(
    data: str | dict | list, salt: bytes = b""
) -> str | dict | list:
    if isinstance(data, list):
        for elem in data:
            _recursive_data_anonymize(elem, salt)

    elif isinstance(data, dict):
        for elem in data.keys():
            if elem in ANONYMIZE_ATTRIBUTES:
                data[elem] = hashlib.sha1(
                    data[elem].encode("UTF-8") + salt, usedforsecurity=False
                ).hexdigest()
                continue
            _recursive_data_anonymize(data[elem], salt)

    return data


if __name__ == "__main__":
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level="DEBUG")

    def signal_handler(sig, frame):
        user_json_dir(args.user).rmdir()
        sys.exit(sig)

    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(main(args.user, args.password, args.brand, args.country, args.system))
