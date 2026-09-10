"""For given date range and instruments, check if L0 data has changed.

Example:
    python data_checks.py --start-date 20240101 --end-date 20240131 \
        --instruments hi swapi
"""

import argparse
import csv
import datetime

import requests

import imap_data_access
from imap_data_access.io import _make_request
from imap_data_access.webpoda_tenzin import (
    download_daily_data,
    download_repointing_data,
)


def get_repoint_table(start_date, end_date):
    """Query the repoint table for the given date range, downloading the latest file."""
    url = f"{imap_data_access.config['DATA_ACCESS_URL']}/repoint-table"
    params = {
        "start_ingest_date": start_date.strftime("%Y%m%d"),
        "end_ingest_date": end_date.strftime("%Y%m%d"),
    }
    request = requests.Request("GET", url, params=params).prepare()
    with _make_request(request) as response:
        repoint_files = response.json()

    if not repoint_files:
        print("No repoint files found.")
        print("-" * 80)
        return None

    # Entries are cumulative repoint-table snapshots, often sharing the same
    # end_date across multiple versions, so the most recently ingested one is
    # the freshest/most complete table.
    latest_repoint_file = max(
        repoint_files,
        key=lambda item: datetime.datetime.strptime(
            item["ingestion_date"], "%Y-%m-%d, %H:%M:%S"
        ),
    )
    return imap_data_access.download(latest_repoint_file["file_path"])


def parse_args():
    """Parse command line arguments for the start/end date range and instruments."""
    parser = argparse.ArgumentParser(
        description="Check if L0 data has changed for a date range."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        type=lambda s: datetime.datetime.strptime(s, "%Y%m%d"),
        help="Start date in YYYYMMDD format.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        type=lambda s: datetime.datetime.strptime(s, "%Y%m%d"),
        help="End date in YYYYMMDD format.",
    )
    parser.add_argument(
        "--instruments",
        required=True,
        nargs="+",
        help="Instruments to check, e.g. --instruments hi swapi.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # print processing start time
    start_time = datetime.datetime.now()
    print(f"Start time: {start_time}")
    print("=" * 80)
    instrument = args.instruments
    start_date = args.start_date
    # Add one day to the end date to include the entire day in the range
    end_date = args.end_date + datetime.timedelta(days=1)
    for inst in instrument:
        print(f"Checking latest prod file's completeness: {inst}")
        print("=" * 80)
        if inst in ["hi", "lo", "ultra", "glows"]:
            repoint_file_path = get_repoint_table(start_date, end_date)
            if repoint_file_path is None:
                raise ValueError("No repoint files found.")
            # read repoint file content and
            # store a list of rows in the repointing file
            print(f"Reading repoint file: {repoint_file_path.name}")
            with open(repoint_file_path) as f:
                repoint_data = list(csv.DictReader(f))
            download_repointing_data(inst, start_date, end_date, repoint_data)
            # clean up repoint file
            repoint_file_path.unlink()
        else:
            download_daily_data(inst, start_date, end_date)
    # print processing end time
    end_time = datetime.datetime.now()
    print("=" * 80)
    print(f"End time: {end_time}")
    print(f"Total time taken: {end_time - start_time}")
