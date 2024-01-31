"""Data Access for the IMAP Mission

The Interstellar Mapping and Acceleration Probe (IMAP) is a NASA mission to study the
heliosphere. This package contains the data access tools for the IMAP mission. It
provides a convenient way to query the IMAP data archive and download data files.
"""
import os
from pathlib import Path

from imap_data_access.io import download, query, upload

__all__ = ["query", "download", "upload"]
__version__ = "0.2.0"


config = {
    "DATA_ACCESS_URL": os.getenv("IMAP_DATA_ACCESS_URL")
    or "https://api.dev.imap-mission.com",
    "DATA_DIR": Path(os.getenv("IMAP_DATA_DIR") or Path.cwd() / "data"),
}
"""Settings configuration dictionary.

DATA_ACCESS_URL : This is the URL of the data access API.
DATA_DIR : This is where the file data is stored and organized by instrument and level.
    The default location is a 'data/' folder in the current working directory,
    "but this can be set on the command line using the --data-dir option, or through
    the environment variable IMAP_DATA_DIR.
"""
