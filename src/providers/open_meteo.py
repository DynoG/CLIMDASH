"""Concrete Open-Meteo adapter.

This module is the only place that knows:
  - Open-Meteo endpoint URLs
  - Open-Meteo query parameter names
  - Open-Meteo JSON response shape

Everything downstream depends solely on the normalised schema defined
in ``src.providers.base``.

Authentication note: Open-Meteo's documented commercial method is the
``apikey`` query parameter. Header-based auth (``X-Api-Key``) is supported
here behind ``OPEN_METEO_AUTH_MODE=header`` for forward compatibility, but
query mode is the safe default.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src import config
from src.providers.base import (
    CURRENT_COLUMNS,
    HISTORICAL_COLUMNS,
    WeatherProvider,
)


# ── Endpoints ──────────────────────────────────────────────────────────
FREE_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
COMMERCIAL_FORECAST_URL = "https://customer-api.open-meteo.com/v1/forecast"

FREE_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Commercial archive host follows the same "customer-" prefix pattern.
# Confirm against your subscription documentation before relying on it.
COMMERCIAL_ARCHIVE_URL = "https://customer-archive-api.open-meteo.com/v1/archive"


class OpenMeteoAPIError(RuntimeError):
    """Raised when Open-Meteo returns an error payload.

    The API returns HTTP 4xx with a JSON body like
    ``{"error": true, "reason": "..."}`` on bad requests.
    """


class OpenMeteoProvider(WeatherProvider):
    """Open-Meteo implementation of :class:`WeatherProvider`."""

    name = "open_meteo"

    def __init__(
        self,
        api_key: str | None = None,
        commercial: bool | None = None,
        auth_mode: str | None = None,
        timeout: int | None = None,
        batch_size: int | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.OPEN_METEO_API_KEY
        self.commercial = (
            commercial if commercial is not None else config.OPEN_METEO_COMMERCIAL
        )
        self.auth_mode = (auth_mode or config.OPEN_METEO_AUTH_MODE).lower()
        self.timeout = timeout or config.OPEN_METEO_REQUEST_TIMEOUT
        self.batch_size = batch_size or config.OPEN_METEO_BATCH_SIZE
        self.cache_dir = cache_dir or config.RAW_CACHE_DIR

        if self.auth_mode not in {"query", "header"}:
            raise ValueError(
                f"OPEN_METEO_AUTH_MODE must be 'query' or 'header', got "
                f"{self.auth_mode!r}"
            )
        if self.commercial and not self.api_key:
            raise ValueError(
                "Commercial mode requires OPEN_METEO_API_KEY to be set in .env"
            )

        self._forecast_url = (
            COMMERCIAL_FORECAST_URL if self.commercial else FREE_FORECAST_URL
        )
        self._archive_url = (
            COMMERCIAL_ARCHIVE_URL if self.commercial else FREE_ARCHIVE_URL
        )

    # ── Public contract ────────────────────────────────────────────────

    def fetch_current(self, locations: pd.DataFrame) -> pd.DataFrame:
        """Return one row per location with current conditions."""
        self._validate_locations(locations)

        frames = []
        for chunk in self._chunks(locations, self.batch_size):
            payload = self._get_json(
                self._forecast_url,
                params=self._current_params(chunk),
                cache_key_parts=("current", chunk.to_json()),
            )
            frames.append(self._normalise_current(chunk, payload))

        result = pd.concat(frames, ignore_index=True)
        return result[CURRENT_COLUMNS]

    def fetch_historical(
        self,
        locations: pd.DataFrame,
        start_date: str,
        end_date: str,
        daily_variables: list[str],
    ) -> pd.DataFrame:
        """Return long-format daily history: location, date, variable, value."""
        self._validate_locations(locations)
        if not daily_variables:
            raise ValueError("daily_variables must contain at least one variable")

        frames = []
        for chunk in self._chunks(locations, self.batch_size):
            payload = self._get_json(
                self._archive_url,
                params=self._historical_params(
                    chunk, start_date, end_date, daily_variables
                ),
                cache_key_parts=(
                    "historical",
                    chunk.to_json(),
                    start_date,
                    end_date,
                    ",".join(daily_variables),
                ),
            )
            frames.append(
                self._normalise_historical(chunk, payload, daily_variables)
            )

        result = pd.concat(frames, ignore_index=True)
        return result[HISTORICAL_COLUMNS]

    # ── Request builders ───────────────────────────────────────────────

    def _current_params(self, locations: pd.DataFrame) -> dict[str, str]:
        return {
            "latitude": ",".join(locations["latitude"].astype(str)),
            "longitude": ",".join(locations["longitude"].astype(str)),
            "current": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": "auto",
        }

    def _historical_params(
        self,
        locations: pd.DataFrame,
        start_date: str,
        end_date: str,
        daily_variables: list[str],
    ) -> dict[str, str]:
        return {
            "latitude": ",".join(locations["latitude"].astype(str)),
            "longitude": ",".join(locations["longitude"].astype(str)),
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join(daily_variables),
            "timezone": "auto",
        }

    # ── Transport (auth, error handling, optional caching) ─────────────

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str],
        cache_key_parts: tuple[str, ...],
    ) -> Any:
        params = dict(params)
        headers: dict[str, str] = {}

        if self.commercial:
            if self.auth_mode == "header":
                headers["X-Api-Key"] = self.api_key or ""
            else:
                params["apikey"] = self.api_key or ""

        cache_path = self._cache_path(url, params, cache_key_parts)
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        response = requests.get(
            url, params=params, headers=headers, timeout=self.timeout
        )
        try:
            payload = response.json()
        except ValueError:
            response.raise_for_status()
            raise OpenMeteoAPIError(
                f"Open-Meteo returned non-JSON content (HTTP {response.status_code})"
            )
        # Open-Meteo returns a dict for single-coordinate requests and a
        # list of dicts for multi-coordinate ones. The error envelope
        # ({"error": true, "reason": ...}) only ever arrives as a dict,
        # so we look for it there and never call .get() on a list.
        error_payload = payload if isinstance(payload, dict) else {}

        if response.status_code >= 400 or error_payload.get("error") is True:
            reason = error_payload.get("reason", response.text)
            raise OpenMeteoAPIError(
                f"Open-Meteo API error (HTTP {response.status_code}): {reason}"
            )

        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _cache_path(
        self, url: str, params: dict[str, str], key_parts: tuple[str, ...]
    ) -> Path:
        digest = hashlib.sha256(
            json.dumps([url, params, key_parts], sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return self.cache_dir / f"open_meteo_{digest}.json"

    # ── Response normalisation ─────────────────────────────────────────

    def _normalise_current(
        self, locations: pd.DataFrame, payload: Any
    ) -> pd.DataFrame:
        records = self._as_list(payload)
        if len(records) != len(locations):
            raise OpenMeteoAPIError(
                f"Expected {len(locations)} records, received {len(records)}"
            )

        rows = []
        for loc, data in zip(locations.itertuples(), records):
            current = data.get("current") or {}
            rows.append(
                {
                    "location_name": loc.location_name,
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "temperature_2m": current.get("temperature_2m"),
                    "precipitation": current.get("precipitation"),
                    "wind_speed_10m": current.get("wind_speed_10m"),
                    "provider": self.name,
                    "fetched_at_utc": datetime.now(timezone.utc),
                }
            )
        return pd.DataFrame(rows)

    def _normalise_historical(
        self,
        locations: pd.DataFrame,
        payload: Any,
        daily_variables: list[str],
    ) -> pd.DataFrame:
        records = self._as_list(payload)
        if len(records) != len(locations):
            raise OpenMeteoAPIError(
                f"Expected {len(locations)} records, received {len(records)}"
            )

        rows = []
        for loc, data in zip(locations.itertuples(), records):
            daily = data.get("daily") or {}
            dates = daily.get("time") or []
            for variable in daily_variables:
                values = daily.get(variable) or []
                for date, value in zip(dates, values):
                    rows.append(
                        {
                            "location_name": loc.location_name,
                            "date": date,
                            "variable": variable,
                            "value": value,
                            "provider": self.name,
                        }
                    )
        return pd.DataFrame(rows)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _as_list(payload: Any) -> list[dict]:
        """Single-coordinate responses are dicts; multi are lists."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
        raise OpenMeteoAPIError(f"Unexpected payload type: {type(payload)!r}")

    @staticmethod
    def _chunks(df: pd.DataFrame, size: int):
        for start in range(0, len(df), size):
            yield df.iloc[start : start + size]

    @staticmethod
    def _validate_locations(locations: pd.DataFrame) -> None:
        required = {"location_name", "latitude", "longitude"}
        missing = required - set(locations.columns)
        if missing:
            raise ValueError(f"locations is missing columns: {sorted(missing)}")
        if locations.empty:
            raise ValueError("locations DataFrame is empty")