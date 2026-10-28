"""Tests for provider normalisation and location loading. Network is mocked."""

from __future__ import annotations

import pandas as pd
import pytest

from src.providers.base import CURRENT_COLUMNS, HISTORICAL_COLUMNS
from src.providers.open_meteo import OpenMeteoAPIError, OpenMeteoProvider


@pytest.fixture
def locations():
    return pd.DataFrame(
        {
            "location_name": ["Algiers", "Cairo"],
            "latitude": [36.7538, 30.0444],
            "longitude": [3.0588, 31.2357],
        }
    )


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_current_normalises_multiple_locations(
    monkeypatch, locations, tmp_path
):
    payload = [
        {
            "latitude": 36.75,
            "longitude": 3.06,
            "current": {
                "temperature_2m": 22.4,
                "precipitation": 0.0,
                "wind_speed_10m": 14.2,
            },
        },
        {
            "latitude": 30.04,
            "longitude": 31.24,
            "current": {
                "temperature_2m": 31.1,
                "precipitation": 0.0,
                "wind_speed_10m": 9.8,
            },
        },
    ]
    monkeypatch.setattr(
        "src.providers.open_meteo.requests.get",
        lambda *a, **k: FakeResponse(payload),
    )

    df = OpenMeteoProvider(cache_dir=tmp_path).fetch_current(locations)

    assert list(df.columns) == CURRENT_COLUMNS
    assert len(df) == 2
    assert df.loc[0, "location_name"] == "Algiers"
    assert df.loc[0, "temperature_2m"] == 22.4


def test_fetch_current_wraps_single_location_object(monkeypatch, tmp_path):
    locations = pd.DataFrame(
        {"location_name": ["Algiers"], "latitude": [36.75], "longitude": [3.06]}
    )
    payload = {
        "latitude": 36.75,
        "longitude": 3.06,
        "current": {
            "temperature_2m": 22.4,
            "precipitation": 0.0,
            "wind_speed_10m": 14.2,
        },
    }
    monkeypatch.setattr(
        "src.providers.open_meteo.requests.get",
        lambda *a, **k: FakeResponse(payload),
    )

    df = OpenMeteoProvider(cache_dir=tmp_path).fetch_current(locations)
    assert list(df.columns) == CURRENT_COLUMNS
    assert len(df) == 1


def test_fetch_current_raises_on_api_error(monkeypatch, locations, tmp_path):
    payload = {"error": True, "reason": "Parameter count must be between 1 and 100."}
    monkeypatch.setattr(
        "src.providers.open_meteo.requests.get",
        lambda *a, **k: FakeResponse(payload, status_code=400),
    )

    with pytest.raises(OpenMeteoAPIError, match="Parameter count"):
        OpenMeteoProvider(cache_dir=tmp_path).fetch_current(locations)


def test_fetch_historical_long_format(monkeypatch, locations, tmp_path):
    payload = [
        {
            "latitude": 36.75,
            "longitude": 3.06,
            "daily": {
                "time": ["2024-01-01", "2024-01-02"],
                "temperature_2m_max": [18.0, 19.5],
                "precipitation_sum": [0.0, 4.2],
            },
        },
        {
            "latitude": 30.04,
            "longitude": 31.24,
            "daily": {
                "time": ["2024-01-01", "2024-01-02"],
                "temperature_2m_max": [24.0, 25.1],
                "precipitation_sum": [0.0, 0.0],
            },
        },
    ]
    monkeypatch.setattr(
        "src.providers.open_meteo.requests.get",
        lambda *a, **k: FakeResponse(payload),
    )

    df = OpenMeteoProvider(cache_dir=tmp_path).fetch_historical(
        locations,
        start_date="2024-01-01",
        end_date="2024-01-02",
        daily_variables=["temperature_2m_max", "precipitation_sum"],
    )

    assert list(df.columns) == HISTORICAL_COLUMNS
    assert len(df) == 8  # 2 locations x 2 variables x 2 days
    assert set(df["variable"]) == {"temperature_2m_max", "precipitation_sum"}


def test_load_locations_handles_bom_and_schema(tmp_path):
    from src.ingestion import load_locations

    path = tmp_path / "cities.csv"
    path.write_text(
        "\ufeffcity,lat,lng\nAlgiers,36.77,3.06\nOran,35.70,-0.63\n",
        encoding="utf-8",
    )
    df = load_locations(
        path,
        column_map={
            "city": "location_name",
            "lat": "latitude",
            "lng": "longitude",
        },
    )
    assert list(df.columns) == ["location_name", "latitude", "longitude"]
    assert df.iloc[0]["location_name"] == "Algiers"


def test_load_locations_preserves_extra_columns(tmp_path):
    from src.ingestion import load_locations

    path = tmp_path / "targets.csv"
    path.write_text(
        "location_name,latitude,longitude,admin_name,capital\n"
        "Algiers,36.77,3.06,Alger,primary\n",
        encoding="utf-8",
    )
    df = load_locations(path)
    assert "admin_name" in df.columns
    assert "capital" in df.columns
    assert df.iloc[0]["capital"] == "primary"