import argparse
import base64
import hashlib
import random
import re
import string
from datetime import datetime

from myPyllant.const import BRANDS, COUNTRIES, DEFAULT_BRAND


def dict_to_snake_case(d):
    """
    Convert {'camelCase': value} to {'camel_case': value} recursively
    """

    snake_pattern = re.compile(r"(?<!^)(?=[A-Z])")

    def to_snake(s):
        return snake_pattern.sub("_", s).lower()

    if isinstance(d, list):
        return [dict_to_snake_case(i) if isinstance(i, (dict, list)) else i for i in d]
    return {
        to_snake(a): dict_to_snake_case(b) if isinstance(b, (dict, list)) else b
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


def datetime_parse(date_string: str) -> datetime:
    return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")


def get_realm(brand: str, country: str) -> str:
    """
    Vaillant and SDBG use `brand-country-b2c` as the realm, Bulex doesn't use a country
    """
    if brand == "bulex":
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
