# IMAP Data Access Package

This is a minimal Python package that allows users to download, query, and upload data from the IMAP Science Data Center (SDC).

## Configuration

The folder structure for data files within the IMAP SDC is rigidly
defined, so the data access will mimic that structure to make sure
all data is stored in the same heirarchical structure as the SDC.
This will enable seamless transition between a user's local system
and the SDC.

A user's root data location can be specified as an environment
variable ``IMAP_DATA_DIR`` or through a configuration dictionary
within the package itself ``imap_data_access.config["DATA_DIR"]``.

## Importing as a package

```python
import imap_data_access

# Search for files
results = imap_data_access.query(instrument="mag", data_level="l0")
# TODO: Update with example of return
# list of dictionaries
# []

# Download a file that was returned from the search
imap_data_access.download("imap/mag/l0/2024/01/imap_mag_l0_raw_202040101_20240101_v00-00.pkts")

# Upload a calibration file that exists locally
imap_data_access.upload("imap/mag/calibration/test_calibration.txt")
```
