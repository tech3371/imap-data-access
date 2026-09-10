"""Download packet data from webpoda and compare it against production.

This module downloads newly arrived instrument packet data from webpoda, either
for whole days (download_daily_data) or for individual repointings
(download_repointing_data), based on Spacecraft Time (SCT). For any
instrument/date (and repointing, if applicable) that already has an L0 file in
production, the freshly downloaded data is compared against that file via
_compare_and_write_new_data (which uses compare_files), so only new or
changed data is kept and returned.

Location of list of APIDs and associated instruments:
https://lasp.colorado.edu/galaxy/spaces/IMAP/pages/155648242/Packet+Decommutation+Resource+Page+-+IMAP
"""

import datetime
import hashlib
import logging
from pathlib import Path
from typing import Optional

import imap_data_access
from imap_data_access.io import IMAPDataAccessError
from imap_data_access.webpoda import (
    _INSTRUMENT_BUFFER_MINUTES,
    INSTRUMENT_APIDS,
    get_packet_binary_data_sctime,
)

logger = logging.getLogger(__name__)


def download_daily_data(
    instrument: str,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    upload_to_server=False,
):
    """Download data for the apid and start/end time range from webpoda.

    WebPODA stands for packet on demand access. This function requests the
    IMAP specific API endpoint, so all APIDs must be from the IMAP mission.

    Parameters
    ----------
    instrument : str
        The instrument to download data for.
    start_time : datetime.datetime
        The start of the date range to download, in Spacecraft Time (SCT).
    end_time : datetime.datetime
        The end of the date range to download, in Spacecraft Time (SCT).
    upload_to_server : bool, optional
        If True, upload the data to the SDC data bucket, by default False

    Returns
    -------
    list[pathlib.Path]
        One path per day in [start_time, end_time] that has new or changed
        data, skipping days with no packets or where the freshly queried data
        matches what's already in production.
    """
    apids = INSTRUMENT_APIDS[instrument]
    logger.info(f"Downloading data for instrument [{instrument}]")

    # Unique dates between start_time and end_time, inclusive of both endpoints
    unique_dates = [
        start_time.date() + datetime.timedelta(days=i)
        for i in range((end_time.date() - start_time.date()).days + 1)
    ]

    # Iterate over the packet dates to make a query for each individual spacecraft day
    # packet_date 00:00:00 -> packet_date+1 00:00:00
    paths = []
    for date in unique_dates:
        daily_start_time = datetime.datetime.combine(date, datetime.time.min)
        daily_end_time = daily_start_time + datetime.timedelta(days=1)

        # Some instruments request a buffer of packets on either side of the midnight
        # boundary to ensure their packet groupings work together.
        buffer_minutes = _INSTRUMENT_BUFFER_MINUTES.get(instrument, 0)
        buffer_timedelta = datetime.timedelta(minutes=buffer_minutes)
        daily_start_time -= buffer_timedelta
        daily_end_time += buffer_timedelta

        # Iterate over all apids, downloading the content for this time period
        # concatenating all the binary returns into a single binary file
        daily_packet_content = b"".join(
            [
                get_packet_binary_data_sctime(apid, daily_start_time, daily_end_time)
                for apid in apids
            ]
        )
        if not daily_packet_content:
            print(f"No data found for instrument [{instrument}] on {date}. Skipping.")
            print("-" * 80)
            continue

        path = _compare_and_write_new_data(
            instrument=instrument,
            start_time=date,
            content=daily_packet_content,
        )
        # Only keep paths of files that have new data or updated data.
        if path is not None:
            paths.append(path)

    logger.info(f"Finished downloading data for instrument [{instrument}]")
    if upload_to_server:
        for path in paths:
            _upload_if_requested(path, upload_to_server)
            # clean up files after upload to avoid filling up disk space
            path.unlink()

    return paths


def download_repointing_data(
    instrument: str,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    repoint_data: list,
    upload_to_server=False,
):
    """Download data for the instrument and start/end time range from webpoda.

    WebPODA stands for packet on demand access. This function requests the
    IMAP specific API endpoint, so all APIDs must be from the IMAP mission.

    repoint_data contains every repointing since launch, so start_time and
    end_time are used to down-select which repoint ID in it to query and
    create new L0 files.

    Parameters
    ----------
    instrument : str
        The instrument to download data for.
    start_time : datetime.datetime
        Only repoint IDs overlapping this start time or later are queried.
    end_time : datetime.datetime
        Only repoint IDs overlapping this end time or earlier are queried.
    repoint_data : list
        A list of dictionaries, each representing a row in the repointing file.
        This file should contain the repointing
        times in the format:
            repoint_start_sec_sclk	UINT
            repoint_start_subsec_sclk	UINT
            repoint_end_sec_sclk	UINT
            repoint_end_subsec_sclk	UINT
            repoint_start_utc	str
            repoint_end_utc	str
            repoint_id	UINT
    upload_to_server : bool, optional
        If True, upload the data to the SDC data bucket, by default False

    Returns
    -------
    list[pathlib.Path]
        One path per repoint ID overlapping [start_time, end_time] that has
        new or changed data, skipping repoint IDs with no packets or where the
        freshly queried data matches what's already in production.
    """
    apids = INSTRUMENT_APIDS[instrument]
    logger.info(f"Downloading data for instrument [{instrument}]")
    file_paths = []

    # Iterate once over every repoint ID overlapping [start_time, end_time],
    # downloading and writing a file for each one that has new/changed data.

    # Find all unique repoint id in the input date range
    repoints = _repoints_overlapping_date_range(repoint_data, start_time, end_time)

    if not repoints:
        print(
            f"No repoint IDs found for instrument [{instrument}] between "
            f"{start_time} and {end_time}. Skipping."
        )
        print("-" * 80)
        return None

    print(
        f"Found repoint IDs for input date range [{start_time}, {end_time}]: "
        f"{[r[0] for r in repoints]}"
    )

    for repoint in repoints:
        repoint_id, pointing_start, pointing_end = repoint

        # Iterate over all apids, downloading the content for this time period
        # concatenating all the binary returns into a single binary file
        pointing_packet_content = b"".join(
            [
                get_packet_binary_data_sctime(apid, pointing_start, pointing_end)
                for apid in apids
            ]
        )
        if not pointing_packet_content:
            print(
                f"No data found for instrument [{instrument}] repoint ID "
                f"[{repoint_id}] for {pointing_start} to {pointing_end}. Skipping."
            )
            print("-" * 80)
            continue

        path = _compare_and_write_new_data(
            instrument=instrument,
            start_time=pointing_start,
            content=pointing_packet_content,
            repointing=repoint_id,
        )
        if path is not None:
            file_paths.append(path)

    logger.info(f"Finished downloading data for instrument [{instrument}]")
    if upload_to_server:
        for path in file_paths:
            _upload_if_requested(path, upload_to_server)
            # clean up files after upload to avoid filling up disk space
            path.unlink()

    return file_paths


def _repoints_overlapping_date_range(
    repoint_data: list,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
) -> list[tuple[int, datetime.datetime, datetime.datetime]]:
    """Get the repoint IDs in the date range.

    A "pointing" spans from the end of one repointing maneuver to the end of
    the next. Rows with a NaN repoint_end_utc (an incomplete repointing
    maneuver) are skipped.

    Parameters
    ----------
    repoint_data : list
        A list of dictionaries, each representing a row in the repointing file.
    start_time : datetime.datetime
        Only pointings overlapping this start time or later are included.
    end_time : datetime.datetime
        Only pointings overlapping this end time or earlier are included.

    Returns
    -------
    list[tuple[int, datetime.datetime, datetime.datetime]]
        A list of repoint IDs and its pointing start and end times.
    """
    overlapping = []
    for i in range(len(repoint_data) - 1):
        # skip i and i+1 values that are NaN
        if repoint_data[i]["repoint_end_utc"].lower() == "nan":
            # This pointing never "started"
            continue
        if repoint_data[i + 1]["repoint_end_utc"].lower() == "nan":
            # Missing repointing end time, so it isn't a complete "pointing" yet.
            continue
        pointing_start = datetime.datetime.strptime(
            repoint_data[i]["repoint_end_utc"], "%Y-%m-%d %H:%M:%S.%f"
        )
        # NOTE: We need to make sure we are not double grabbing packets into the
        #       pointings. The times included are [repointing_start, repointing_end),
        #       exclusive on the right edge
        pointing_end = datetime.datetime.strptime(
            repoint_data[i + 1]["repoint_end_utc"], "%Y-%m-%d %H:%M:%S.%f"
        )
        if pointing_end < start_time or pointing_start > end_time:
            # This repoint ID doesn't overlap the requested time range, so skip it
            continue
        overlapping.append(
            (int(repoint_data[i]["repoint_id"]), pointing_start, pointing_end)
        )
    return overlapping


def file_hash(path, algo="sha256", chunk_size=8192):
    """Compute the hex digest of the file at path.

    Parameters
    ----------
    path : str
        The path to the file.
    algo : str, optional
        The hashing algorithm to use (default is "sha256").
    chunk_size : int, optional
        The size of the chunks to read at a time (default is 8192).

    Returns
    -------
    str
        The hex digest of the file.
    """
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def format_size(size_bytes):
    """Convert bytes to human-readable format (MB or GB).

    The precision is set to 4 decimal places for both MB and GB.

    Parameters
    ----------
    size_bytes : int
        The size in bytes to format.

    Returns
    -------
    str
        The size in human-readable format, either in MB or GB.
    """
    if size_bytes >= 1e9:
        return f"{size_bytes / 1e9:.4f} GB"
    return f"{size_bytes / 1e6:.4f} MB"


def compare_files(current_file_path, new_file_path):
    """Compare two files by hash/size and print the same log format for every check.

    Parameters
    ----------
    current_file_path : pathlib.Path
        The path to the current production file.
    new_file_path : pathlib.Path
        The path to the newly queried data file.

    Returns
    -------
    bool
        True if the files are different (new data), False if they are the same.
    """
    current_filename = current_file_path.name
    new_filename = new_file_path.name

    current_hash = file_hash(current_file_path)
    new_hash = file_hash(new_file_path)
    current_size = current_file_path.stat().st_size
    new_size = new_file_path.stat().st_size

    if current_size <= new_size and current_hash != new_hash:
        print("Data has changed")
        print(
            f"Prod {current_filename}: (size: {format_size(current_size)}), "
            f"(hash: {current_hash})"
        )
        print(
            f"New     {new_filename}: (size: {format_size(new_size)}), "
            f"(hash: {new_hash})"
        )
        print("-" * 80)
        return True
    else:
        print(f"Data has not changed for {current_filename}.")
        print("-" * 80)
        return False


def _latest_l0_minor_version(
    instrument: str,
    start_time: datetime.datetime,
    repointing: Optional[int] = None,
) -> int:
    """Determine the next available L0 minor version for this instrument/date.

    We need to query the imap_data_access server to see if there have been other
    files created with the same name, and if so, increment the minor version number.

    Parameters
    ----------
    instrument : str
        The instrument name
    start_time : datetime.datetime
        The start time of the data to check for the latest version.
    repointing : int, optional
        The repointing ID to check for the latest version, by default None.

    Returns
    -------
    int
        The next available minor version number: 1 if no L0 file exists yet
        in production for this instrument/date/repointing, otherwise the
        highest existing minor version plus one.
    """
    # See what the latest version is for this file, if any.
    # If there are no files, we will return the first version (minor version 1).
    current_l0_files = imap_data_access.query(
        instrument=instrument,
        data_level="l0",
        descriptor="raw",
        start_date=start_time.strftime("%Y%m%d"),
        # start_date is >= so we need to add an end_date to restrict the query
        end_date=start_time.strftime("%Y%m%d"),
        repointing=repointing,
    )

    if len(current_l0_files):
        # Get the latest minor version incremented by 1 (this is never reset)
        max_minor_version = (
            sorted([file["minor_version"] for file in current_l0_files])[-1] + 1
        )
    else:
        max_minor_version = 1

    return max_minor_version


def _compare_and_write_new_data(
    instrument: str,
    start_time: datetime.datetime,
    content: bytes,
    repointing: Optional[int] = None,
) -> Path:
    """Write freshly queried packet content to disk, comparing against production.

    If no L0 file exists yet in production for this instrument/date/repointing,
    `content` is written directly as minor version 1. If one exists
    already, `content` is written to a new, minor-version-bumped file, then
    compared against the latest production file: if nothing changed,
    None is returned; if the data changed, the new version's
    path is returned.

    Parameters
    ----------
    instrument : str
        The instrument the content belongs to.
    start_time : datetime.datetime
        The start time used to build the file's path (day or pointing start).
    content : bytes
        The freshly queried packet content to write.
    repointing : int, optional
        The repointing ID to build the file's path for, by default None.

    Returns
    -------
    pathlib.Path or None
        The path of the newly written file (minor version 1, or a bumped
        version if the data changed from production), or None if a
        production file already exists and the freshly queried content
        matches it.
    """
    latest_l0_minor_version = _latest_l0_minor_version(
        instrument=instrument, start_time=start_time, repointing=repointing
    )

    if latest_l0_minor_version == 1:
        path = imap_data_access.ScienceFilePath.generate_from_inputs(
            instrument=instrument,
            data_level="l0",
            descriptor="raw",
            start_time=start_time.strftime("%Y%m%d"),
            repointing=repointing,
            major_version=1,
            minor_version=1,
        ).construct_path()

        logger.info(
            f"New L0 file. Saving binary data of size {len(content) // 1000} kB "
            f"to {path}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    # If we get here, this means L0 files already exists and we need to compare
    # the new queried content and see if it has changed.

    # First download the latest L0 file from production to compare against.
    prod_l0_file = imap_data_access.query(
        instrument=instrument,
        data_level="l0",
        descriptor="raw",
        start_date=start_time.strftime("%Y%m%d"),
        # start_date is >= so we need to add an end_date to restrict the query
        end_date=start_time.strftime("%Y%m%d"),
        repointing=repointing,
        version="latest",
    )[0]
    prod_l0_path = imap_data_access.download(prod_l0_file["file_path"])

    new_path = imap_data_access.ScienceFilePath.generate_from_inputs(
        instrument=instrument,
        data_level="l0",
        descriptor="raw",
        start_time=start_time.strftime("%Y%m%d"),
        repointing=repointing,
        major_version=1,
        minor_version=latest_l0_minor_version,
    ).construct_path()

    logger.info(
        f"Saving binary data of size {len(content) // 1000} kB to {new_path} "
        f"to compare against existing {prod_l0_path}"
    )

    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_bytes(content)

    data_changed = compare_files(prod_l0_path, new_path)
    if not data_changed:
        logger.info(
            f"Data for {prod_l0_path} hasn't changed, removing duplicate {new_path}"
        )
        # Clean up the new file since it is a duplicate of the production file
        new_path.unlink()
        prod_l0_path.unlink()
        return None

    logger.info(f"Data for {prod_l0_path} has changed, keeping new version {new_path}")
    return new_path


def _upload_if_requested(path: Path, upload_to_server: bool) -> None:
    """Upload path to the SDC data bucket if requested, logging any failure."""
    if not upload_to_server:
        return
    logger.info("Uploading packet file to the server: %s", path)
    try:
        imap_data_access.upload(path)
    except IMAPDataAccessError as e:
        # We don't want to ruin all subsequent downloads if one fails
        # during upload, so log the error and continue
        logger.error(f"Failed to upload {path} to the server: {e}")
