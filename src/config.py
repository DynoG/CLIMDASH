"""Centralised configuration. Import from here, never call os.getenv elsewhere."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from repo root. `override=False` means real environment variables
# (e.g. set in CI) take precedence over the file — important for deployment.
load_dotenv(override=False)


def _get(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(
            f"Required environment variable {name!r} is missing. "
            "Did you copy .env.example to .env?"
        )
    return value


# ─── Provider ──────────────────────────────────────────────────────────
PROVIDER: str = _get("PROVIDER", "open_meteo")

# ─── Open-Meteo ────────────────────────────────────────────────────────
OPEN_METEO_COMMERCIAL: bool = _get("OPEN_METEO_COMMERCIAL", "false").lower() == "true"
OPEN_METEO_API_KEY: str | None = os.getenv("OPEN_METEO_API_KEY") or None

# ─── Generic REST (future API) ─────────────────────────────────────────
GENERIC_API_BASE_URL: str | None = os.getenv("GENERIC_API_BASE_URL") or None
GENERIC_API_TOKEN: str | None = os.getenv("GENERIC_API_TOKEN") or None
GENERIC_API_AUTH_HEADER: str = _get("GENERIC_API_AUTH_HEADER", "X-API-KEY")

# ─── Paths (resolved to absolute so notebooks work from any cwd) ───────
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
CITIES_CSV: Path = REPO_ROOT / _get("CITIES_CSV", "data/cities.csv")
RAW_CACHE_DIR: Path = REPO_ROOT / _get("RAW_CACHE_DIR", "data/raw")
PROCESSED_DIR: Path = REPO_ROOT / _get("PROCESSED_DIR", "data/processed")

for d in (RAW_CACHE_DIR, PROCESSED_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ─── Defaults ──────────────────────────────────────────────────────────
DEFAULT_METRIC: str = _get("DEFAULT_METRIC", "temperature_2m")
DEFAULT_HISTORY_DAYS: int = int(_get("DEFAULT_HISTORY_DAYS", "7"))