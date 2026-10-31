"""Orchestration layer: provider selection and location loading.

Notebooks and dashboards import from here. They never import a concrete
provider directly, which is what makes the provider swappable.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.providers.base import WeatherProvider
from src.providers.open_meteo import OpenMeteoProvider


def get_provider(name: str | None = None) -> WeatherProvider:
    """Return the configured provider.

    Add new providers here. This function is the single registry.
    """
    name = (name or config.PROVIDER).lower()

    if name == "open_meteo":
        return OpenMeteoProvider()

    # elif name == "my_new_api":
    #     from src.providers.my_new_api import MyNewApiProvider
    #     return MyNewApiProvider()

    raise ValueError(
        f"Unknown provider {name!r}. "
        f"Available: open_meteo. Register new providers in src/ingestion.py."
    )


def load_locations(
    path: str | Path | None = None,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Load a locations CSV and normalise to the canonical schema.

    Extra columns (admin_name, capital, population, ...) are preserved
    and passed through to callers that want them; the provider contract
    ignores them.

    Parameters
    ----------
    path : str or Path, optional
        CSV path. Defaults to ``config.CITIES_CSV`` (data/targets.csv).
    column_map : dict, optional
        Map of source columns to canonical names. Use this when pointing
        at the gazetteer directly (data/cities.csv), e.g.
        ``{"city": "location_name", "lat": "latitude", "lng": "longitude"}``.
    """
    csv_path = Path(path) if path else config.CITIES_CSV

    # utf-8-sig strips the BOM that prefixes the first column name in the
    # SimpleMaps export; without it pandas names the column "\ufeffcity".
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    if column_map:
        missing_src = set(column_map) - set(df.columns)
        if missing_src:
            raise ValueError(
                f"{csv_path} is missing source columns: {sorted(missing_src)}"
            )
        df = df.rename(columns=column_map)

    required = ["location_name", "latitude", "longitude"]
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(
            f"{csv_path} is missing canonical columns: {sorted(missing)}. "
            "Pass column_map= to translate from a gazetteer schema."
        )

    extras = [c for c in df.columns if c not in required]
    return df[required + extras].copy()


def fetch_current(provider_name: str | None = None) -> pd.DataFrame:
    """Load locations, fetch current conditions, and re-attach location metadata.

    The provider returns exactly CURRENT_COLUMNS. This function merges back
    any extra columns from the locations CSV (admin_name, capital, population,
    id) by row position. Positional merge is safe because the provider
    preserves input order across batches.
    """
    provider = get_provider(provider_name)
    locations = load_locations()
    weather = provider.fetch_current(locations).reset_index(drop=True)
    locations = locations.reset_index(drop=True)

    extras = [
        c for c in locations.columns
        if c not in ("location_name", "latitude", "longitude")
    ]
    if not extras:
        return weather

    return pd.concat([weather, locations[extras]], axis=1)