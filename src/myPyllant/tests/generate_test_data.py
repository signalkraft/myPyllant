#!/usr/bin/env python3

import argparse
import asyncio
import copy
import hashlib
import json
import logging
import secrets
import signal
from typing import Any, TypeVar

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


async def main(user, password, brand, country=None, write_results=True):
    """
    Generate json data for running testcases.

    :param user:
    :param password:
    :param brand:
    :param country:
    :param write_results:
    :return:
    """
    from myPyllant.api import MyPyllantAPI
    from myPyllant.const import API_URL_BASE
    from myPyllant.models import DeviceDataBucketResolution
    from myPyllant.utils import datetime_format

    results: dict[str, Any] = {}
    json_dir = user_json_dir(user)
    if write_results:
        json_dir.mkdir(parents=True, exist_ok=True)

    def create_result(result, name, directory=None):
        if write_results:
            if directory:
                write_dir = json_dir / directory
            else:
                write_dir = json_dir
            with open(write_dir / f"{name}.json", "w") as fh_json:
                fh_json.write(json.dumps(result, indent=2))
        if directory:
            if directory not in results:
                results[directory] = {}
            results[directory][name] = result
        else:
            results[name] = result

    async with MyPyllantAPI(user, password, brand, country) as api:
        homes_url = f"{API_URL_BASE}/homes"
        async with api.aiohttp_session.get(
            homes_url, headers=api.get_authorized_headers()
        ) as homes_resp:
            homes = await homes_resp.json()
            anonymized_homes = _recursive_data_anonymize(copy.deepcopy(homes), SALT)
            for home in anonymized_homes:
                if "address" in home:
                    home.pop("address")
            create_result(
                anonymized_homes,
                name="homes",
            )

        if not homes:
            # No homes means no systems to generate test data for
            print("No homes found.")
            if write_results:
                print(f"Wrote homes.json to {json_dir}")
                exit(0)
            else:
                return results

        for home in homes:
            anonymized_home = _recursive_data_anonymize(copy.deepcopy(home), SALT)
            anonymized_system_id = anonymized_home["systemId"]
            real_system_id = home["systemId"]
            print(f"Generating test data for {anonymized_system_id}")

            if write_results:
                (json_dir / anonymized_system_id).mkdir(parents=True, exist_ok=True)

            control_identifier_url = (
                f"{API_URL_BASE}/systems/{real_system_id}/meta-info/control-identifier"
            )
            async with api.aiohttp_session.get(
                control_identifier_url, headers=api.get_authorized_headers()
            ) as ci_response:
                control_identifier = await ci_response.json()
                create_result(
                    control_identifier,
                    "control_identifier",
                    anonymized_system_id,
                )

            tz_url = f"{API_URL_BASE}/systems/{real_system_id}/meta-info/time-zone"
            async with api.aiohttp_session.get(
                tz_url, headers=api.get_authorized_headers()
            ) as tz_response:
                create_result(
                    await tz_response.json(),
                    "time_zone",
                    anonymized_system_id,
                )

            dtc_url = (
                f"{API_URL_BASE}/systems/{real_system_id}/diagnostic-trouble-codes"
            )
            async with api.aiohttp_session.get(
                dtc_url, headers=api.get_authorized_headers()
            ) as dtc_response:
                dtc = await dtc_response.json()
                anonymized_dtc = _recursive_data_anonymize(copy.deepcopy(dtc), SALT)
                create_result(
                    anonymized_dtc,
                    "diagnostic_trouble_codes",
                    anonymized_system_id,
                )

            connection_status_url = (
                f"{API_URL_BASE}/systems/{real_system_id}/meta-info/connection-status"
            )
            async with api.aiohttp_session.get(
                connection_status_url, headers=api.get_authorized_headers()
            ) as status_resp:
                create_result(
                    await status_resp.json(),
                    "connection_status",
                    anonymized_system_id,
                )

            system_url = f"{API_URL_BASE}/systems/{real_system_id}/{control_identifier['controlIdentifier']}"
            async with api.aiohttp_session.get(
                system_url, headers=api.get_authorized_headers()
            ) as system_resp:
                home = await system_resp.json()
                anonymized_homes = _recursive_data_anonymize(copy.deepcopy(home), SALT)
                create_result(
                    anonymized_homes,
                    "system",
                    anonymized_system_id,
                )

            current_system_url = f"{API_URL_BASE}/emf/v2/{real_system_id}/currentSystem"
            async with api.aiohttp_session.get(
                current_system_url, headers=api.get_authorized_headers()
            ) as current_system_resp:
                current_system = await current_system_resp.json()
                anonymized_current_system = _recursive_data_anonymize(
                    copy.deepcopy(current_system), SALT
                )
                create_result(
                    anonymized_current_system,
                    "current_system",
                    anonymized_system_id,
                )

            mpc_url = f"{API_URL_BASE}/hem/{real_system_id}/mpc"
            async with api.aiohttp_session.get(
                mpc_url, headers=api.get_authorized_headers()
            ) as mpc_resp:
                mpc = await mpc_resp.json()
                anonymized_mpc = _recursive_data_anonymize(copy.deepcopy(mpc), SALT)
                create_result(
                    anonymized_mpc,
                    "mpc",
                    anonymized_system_id,
                )

            device = current_system["primary_heat_generator"]
            start = datetime.now().replace(
                microsecond=0, second=0, minute=0, hour=0
            ) - timedelta(days=1)
            end = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)
            if device and "data" in device:
                querystring = {
                    "resolution": DeviceDataBucketResolution.HOUR,
                    "operationMode": device["data"][0]["operation_mode"],
                    "energyType": device["data"][0]["value_type"],
                    "startDate": datetime_format(start),
                    "endDate": datetime_format(end),
                }
                device_buckets_url = (
                    f"{API_URL_BASE}/emf/v2/{real_system_id}/"
                    f"devices/{device['device_uuid']}/buckets?{urlencode(querystring)}"
                )
                async with api.aiohttp_session.get(
                    device_buckets_url, headers=api.get_authorized_headers()
                ) as device_buckets_resp:
                    device_buckets = await device_buckets_resp.json()
                create_result(
                    device_buckets,
                    "device_buckets",
                    anonymized_system_id,
                )

    if write_results:
        print(f"Wrote test data to {json_dir}")
    else:
        return results


T = TypeVar("T")


def _recursive_data_anonymize(data: T, salt: bytes = b"") -> T:
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

    asyncio.run(main(args.user, args.password, args.brand, args.country))
