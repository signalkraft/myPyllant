import argparse
import base64
import hashlib
import random
import re
import string
from datetime import datetime, tzinfo, timedelta
from enum import Enum

from myPyllant.const import BRANDS, COUNTRIES, DEFAULT_BRAND, DEFAULT_HOLIDAY_DURATION


def dict_to_snake_case(d):
    """
    Convert {'camelCase': value} to {'camel_case': value} recursively
    """
    if d is None:
        return None

    snake_pattern = re.compile(r"(?<!^)(?=[A-Z])")

    def to_snake(s):
        return snake_pattern.sub("_", s).lower()

    if isinstance(d, list):
        return [dict_to_snake_case(i) if isinstance(i, (dict, list)) else i for i in d]
    return {
        to_snake(a): dict_to_snake_case(b) if isinstance(b, (dict, list)) else b
        for a, b in d.items()
    }


def dict_to_camel_case(d):
    """
    Convert {'camel_case': value} to {'camelCase': value} recursively
    """
    if d is None:
        return None

    def to_camel(s):
        p = s.split("_")
        return p[0] + "".join(x.capitalize() or "_" for x in p[1:])

    if isinstance(d, list):
        return [dict_to_camel_case(i) if isinstance(i, (dict, list)) else i for i in d]
    return {
        to_camel(a): dict_to_camel_case(b) if isinstance(b, (dict, list)) else b
        for a, b in d.items()
    }


def random_string(length):
    return "".join(
        random.choices(
            string.ascii_lowercase + string.ascii_uppercase + string.digits, k=length
        )
    )


def generate_code() -> tuple[str, str]:
    rand = random.SystemRandom()
    code_verifier = "".join(rand.choices(string.ascii_letters + string.digits, k=128))

    code_sha_256 = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    b64 = base64.urlsafe_b64encode(code_sha_256)
    code_challenge = b64.decode("utf-8").replace("=", "")

    return code_verifier, code_challenge


def datetime_format(date: datetime, with_microseconds=False) -> str:
    """
    Some endpoints need three digits of microseconds, some don't :shrug:
    """
    if with_microseconds:
        return date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    else:
        return date.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def datetime_parse(date_string: str, timezone: tzinfo) -> datetime:
    if "." in date_string:
        return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone
        )
    else:
        return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone
        )


def get_realm(brand: str, country: str | None = None) -> str:
    """
    Vaillant and SDBG use `brand-country-b2c` as the realm, Bulex doesn't use a country
    """
    if brand == "bulex":
        return f"{brand}-b2c"
    elif not country:
        return f"{brand}-b2c"
    else:
        return f"{brand}-{country}-b2c"


def add_default_parser_args(parser: argparse.ArgumentParser):
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
        choices=COUNTRIES[DEFAULT_BRAND].keys(),
        required=False,
    )


def version_tuple(v):
    # See https://stackoverflow.com/a/11887825
    return tuple(map(int, (v.split("."))))


def prepare_field_value_for_dict(value):
    from myPyllant.models import MyPyllantDataClass

    match value:
        case tzinfo() | Enum():
            value = str(value)
        case MyPyllantDataClass():
            value = value.prepare_dict()
        case dict():
            value = {k: prepare_field_value_for_dict(v) for k, v in value.items()}
        case list():
            value = [prepare_field_value_for_dict(v) for v in value]
    return value


def get_default_holiday_dates(
    start, end, timezone, default_holiday_duration=DEFAULT_HOLIDAY_DURATION
) -> tuple[datetime, datetime]:
    """
    If no start or end date is given, use the current date and add the default holiday duration
    """
    if not start:
        start = datetime.now(timezone)
    if not end:
        end = start + timedelta(days=default_holiday_duration)
    return start, end
