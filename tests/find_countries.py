#!/usr/bin/env python3
from pathlib import Path
import re
import sys

from country_list import countries_for_language
import requests

sys.path.append((Path(__file__).resolve().parent / "src").name)

from myPyllant.const import BRANDS, COUNTRIES, DEFAULT_BRAND


def countries_with_realm(brand):
    for code, country in countries_for_language("en"):
        if code == "CZ":
            country_name = "czechrepublic"
        else:
            country_name = re.sub(r"\W+", "", country.lower())
        r = requests.head(
            f"https://identity.vaillant-group.com/auth/realms/"
            f"{brand}-{country_name}-b2c/.well-known/openid-configuration"
        )
        if r.status_code == 200:
            yield country_name, country


def main():
    print("COUNTRIES = {")
    for brand in BRANDS.keys():
        print(f'    "{brand}": {{')
        for country_name, country in countries_with_realm(brand):
            print(f'        "{country_name}": "{country}",')
        print("    },")
    print("}")


if __name__ == "__main__":
    main()
