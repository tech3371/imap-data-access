"""Global pytest configuration for the package."""

import pytest

import imap_data_access


@pytest.fixture(autouse=True)
def _set_global_config(monkeypatch: pytest.fixture, tmp_path: pytest.fixture):
    """Set the global data directory to a temporary directory."""
    monkeypatch.setitem(imap_data_access.config, "DATA_DIR", tmp_path)
    monkeypatch.setitem(
        imap_data_access.config, "DATA_ACCESS_URL", "https://api.test.com"
    )
    monkeypatch.setitem(imap_data_access.config, "API_KEY", "test-api-key")
