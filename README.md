# IMAP Data Access Package

This lightweight  Python package allows users to download, query, and upload data from the IMAP Science Data Center (SDC).

## Command Line Utility

### Query / Search for data

```bash
# Find all files from the SWE instrument
imap-data-access query --instrument swe
# Find all files during the year 2024
imap-data-access query --start_date 20240101 --end_date 20241231
```

### Download a file

```bash
# Level 0 SWE file on 2024/01/05
imap-data-access download imap/swe/l0/2024/01/imap_swe_l0_sci_20240105_20240105_v00-00.pkts
```

### Upload a file

```bash
# Upload an l1a file after decoding the l0 CCSDS ".pkts" file
imap-data-access upload imap/swe/l1a/2024/01/imap_swe_l1a_sci_20240105_20240105_v00-00.cdf
```

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

## Configuration

### Data directory

The folder structure for data files within the IMAP SDC is rigidly
defined, so the data access will mimic that structure to make sure
all data is stored in the same heirarchical structure as the SDC.
This will enable seamless transition between a user's local system
and the SDC.

A user's root data location can be specified as an environment
variable ``IMAP_DATA_DIR`` or through a configuration dictionary
within the package itself ``imap_data_access.config["DATA_DIR"]``.

The following is the directory structure the IMAP SDC uses.

```text
<IMAP_DATA_DIR>/
  imap/
    <instrument>/
      <data_level>/
        <year>/
          <month>/
            <filename>
```

for example, with ``IMAP_DATA_DIR=/data``:

```text
/data/
  imap/
    swe/
      l0/
        2024/
          01/
            imap_swe_l0_sci_20240105_20240105_v00-00.pkts
```

### Data Access URL

To change the default URL that the package accesses, you can set
the environment variable ``IMAP_DATA_ACCESS_URL`` or within the
package ``imap_data_access.config["DATA_ACCESS_URL"]``. The default
is the development server ``https://api.dev.imap-mission.com``.

## Troubleshooting

### Network issues

#### SSL

If you encounter SSL errors similar to the following:

```text
urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:997)>
```

That generally means the Python environment you're using is not finding your system's root
certificates properly. This means you need to tell Python how to find those certificates
with the following potential solutions.

1. **Upgrade the certifi package**

    ```bash
    pip install --upgrade certifi
    ```

2. **Install system certificates**
    Depending on the Python version you installed the program with the command will look something like this:

    ```bash
    /Applications/Python\ 3.10/Install\ Certificates.command
    ```

#### HTTP Error 502: Bad Gateway

This could mean that the service is temporarily down. If you
continue to encounter this, reach out to the IMAP SDC at
<imap-sdc@lasp.colorado.edu>.

#### FileNotFoundError

This could mean that the local data directory is not set
up with the same paths as the SDC. See the [data directory](#data-directory)
section for an example of how to set this up.
