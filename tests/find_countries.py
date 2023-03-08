#!/usr/bin/env python3
import re

from country_list import countries_for_language
import requests


def countries_with_realm():
    for code, country in countries_for_language("en"):
        country_name = re.sub(r"\W+", "", country.lower())
        r = requests.head(
            f"https://identity.vaillant-group.com/auth/realms/"
            f"vaillant-{country_name}-b2c/.well-known/openid-configuration"
        )
        if r.status_code == 200:
            yield country_name, country


def main():
    print("COUNTRIES = {")
    for country_name, country in countries_with_realm():
        print(f'  "{country_name}": "{country}",')
    print("}")


if __name__ == "__main__":
    main()
