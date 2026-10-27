"""Abstract provider contract.

Every concrete provider MUST return DataFrames with the columns listed
in the docstrings below. Downstream code (mapping, dashboards, reporting)
depends ONLY on these column names — never on a specific provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


# The normalised schema. Keep this in sync with the docstrings.
CURRENT_COLUMNS = [
    "location_name", "latitude", "longitude",
    "temperature_2m", "precipitation", "wind_speed_10m",
    "provider", "fetched_at_utc",
]

HISTORICAL_COLUMNS = [
    "location_name", "date", "variable", "value", "provider",
]


class WeatherProvider(ABC):
    """Contract for all weather data providers."""

    name: str = "abstract"

    @abstractmethod
    def fetch_current(self, locations: pd.DataFrame) -> pd.DataFrame:
        """Fetch current conditions for each row in `locations`.

        Parameters
        ----------
        locations : DataFrame with columns ['location_name','latitude','longitude'].

        Returns
        -------
        DataFrame with exactly the columns in CURRENT_COLUMNS, one row per location.
        """

    @abstractmethod
    def fetch_historical(
        self,
        locations: pd.DataFrame,
        start_date: str,
        end_date: str,
        daily_variables: list[str],
    ) -> pd.DataFrame:
        """Fetch daily historical values in long format.

        Returns
        -------
        DataFrame with exactly the columns in HISTORICAL_COLUMNS.
        """