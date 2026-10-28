"""Template for a token-authenticated REST weather API.

This is NOT a working provider. Copy this file, rename it, fill in the
TODOs, and register it in ``src.ingestion.get_provider()``. The contract
is defined in ``src.providers.base.WeatherProvider``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

from src import config
from src.providers.base import CURRENT_COLUMNS, WeatherProvider


class GenericRestProvider(WeatherProvider):
    """Adapter for any REST API authenticated with a token header."""

    name = "generic_rest"

    def __init__(self) -> None:
        self.base_url = config.GENERIC_API_BASE_URL
        self.token = config.GENERIC_API_TOKEN
        self.auth_header = config.GENERIC_API_AUTH_HEADER

        if not self.base_url or not self.token:
            raise ValueError(
                "GENERIC_API_BASE_URL and GENERIC_API_TOKEN must be set in .env"
            )

    def fetch_current(self, locations: pd.DataFrame) -> pd.DataFrame:
        headers = {self.auth_header: self.token}
        rows = []

        for loc in locations.itertuples():
            # TODO: replace with your API's request shape.
            response = requests.get(
                f"{self.base_url}/current",
                params={"lat": loc.latitude, "lon": loc.longitude},
                headers=headers,
                timeout=config.OPEN_METEO_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            # TODO: map your API's JSON keys onto the normalised schema.
            rows.append(
                {
                    "location_name": loc.location_name,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "temperature_2m": data["main"]["temp"],
                    "precipitation": data.get("rain", {}).get("1h", 0.0),
                    "wind_speed_10m": data["wind"]["speed"],
                    "provider": self.name,
                    "fetched_at_utc": datetime.now(timezone.utc),
                }
            )

        return pd.DataFrame(rows)[CURRENT_COLUMNS]

    def fetch_historical(
        self,
        locations: pd.DataFrame,
        start_date: str,
        end_date: str,
        daily_variables: list[str],
    ) -> pd.DataFrame:
        raise NotImplementedError(
            "Implement fetch_historical using the same pattern as fetch_current. "
            "Return columns: location_name, date, variable, value, provider."
        )