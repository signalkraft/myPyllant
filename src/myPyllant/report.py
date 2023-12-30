#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
from datetime import date

from myPyllant.api import MyPyllantAPI
from myPyllant.utils import add_default_parser_args

parser = argparse.ArgumentParser(description="Export data from myVaillant API.")
add_default_parser_args(parser)
parser.add_argument(
    "--year",
    help="Year of the report, defaults to current year",
    type=int,
    default=date.today().year,
    required=False,
)
parser.add_argument(
    "-v", "--verbose", help="increase output verbosity", action="store_true"
)


async def main(user, password, brand, year: int, country=None, write_results=True):
    async with MyPyllantAPI(user, password, brand, country) as api:
        async for system in api.get_systems():
            reports = api.get_yearly_reports(system, year)
            async for report in reports:
                if write_results:
                    with open(report.file_name, "w") as fh:
                        fh.write(report.file_content)
                    sys.stdout.write(f"Wrote {year} report to {report.file_name}\n")
                else:
                    yield report


if __name__ == "__main__":
    args = parser.parse_args()
    kwargs = vars(args)
    verbose = kwargs.pop("verbose")
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    asyncio.run(main(**kwargs))
