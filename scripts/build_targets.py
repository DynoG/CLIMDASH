# scripts/build_targets.py
"""Generate data/targets.csv from the SimpleMaps Algeria gazetteer.

Selection policy (tune the constants below):
  - Always include country and first-level admin capitals
    (capital in {"primary", "admin"}).
  - Union the top N places by population, regardless of capital status.
  - De-duplicate on (city_ascii, admin_name) -- NOT city_ascii alone,
    because SimpleMaps legitimately contains the same name in different
    wilayas (e.g. Sidi Lakhdar in Mostaganem and Ain Defla).
  - Emit the canonical schema: location_name, latitude, longitude,
    plus admin_name and capital for downstream filtering.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

GAZETTEER = Path("data/cities.csv")
TARGETS = Path("data/targets.csv")

TOP_N_BY_POPULATION = 25
INCLUDE_ALL_CAPITALS = True
MOJIBAKE = re.compile(r"[\x80-\x9f]")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Strip control characters; keep valid UTF-8 accents intact."""
    for col in ("city", "city_ascii", "admin_name"):
        df[col] = (
            df[col].astype("string")
            .str.replace(MOJIBAKE, "", regex=True)
            .str.strip()
        )
    return df


def select(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the selection policy with composite-key de-duplication."""
    parts = [df.nlargest(TOP_N_BY_POPULATION, "population")]

    if INCLUDE_ALL_CAPITALS:
        parts.append(df[df["capital"].isin(["primary", "admin"])])

    combined = pd.concat(parts, ignore_index=True)

    # Composite key: name + admin region. Two Sidi Lakhdars in different
    # wilayas are distinct rows; two Sidi Lakhdars in the same wilaya
    # would be a true duplicate and are collapsed here.
    combined = (
        combined.assign(
            _key=(
                combined["city_ascii"].str.lower().str.strip()
                + "|"
                + combined["admin_name"].fillna("<blank>").str.lower().str.strip()
            )
        )
        .sort_values("population", ascending=False)
        .drop_duplicates("_key", keep="first")
        .drop(columns="_key")
        .sort_values(["admin_name", "population"], ascending=[True, False])
    )
    return combined


def main() -> None:
    raw = pd.read_csv(GAZETTEER, encoding="utf-8-sig")
    cleaned = clean(raw)
    selected = select(cleaned)

    targets = selected.rename(
        columns={
            "city": "location_name",
            "lat": "latitude",
            "lng": "longitude",
        }
    )[
        [
            "location_name",
            "latitude",
            "longitude",
            "admin_name",
            "capital",
            "population",
            "id",
        ]
    ]

    targets.to_csv(TARGETS, index=False)
    print(f"Wrote {len(targets)} targets to {TARGETS}")
    print(targets.head(10).to_string(index=False))


if __name__ == "__main__":
    main()