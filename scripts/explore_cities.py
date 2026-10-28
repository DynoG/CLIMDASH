# scripts/explore_cities.py
"""Profile data/cities.csv (SimpleMaps Algeria gazetteer).

Run from the repo root:  python scripts/explore_cities.py

This script treats the file as a geographic reference, not as a target
list. It profiles name collisions across admin regions, the distribution
of the 'capital' field, and encoding defects. It does NOT flag blank
admin_name values as errors -- SimpleMaps defines the field as optional
for non-capital places.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

CITIES = Path("data/cities.csv")

# Windows-1252 control characters that leak into the source encoding.
# These are genuine defects; the accented names (Sétif, Bejaïa) are valid UTF-8.
MOJIBAKE_PATTERN = re.compile(r"[\x80-\x9f]")

# Plausible bounding box for Algeria -- sanity check only.
ALGERIA_LAT_RANGE = (19.0, 37.5)
ALGERIA_LNG_RANGE = (-8.7, 12.0)


def profile_duplicates(df: pd.DataFrame) -> None:
    """Report name collisions across admin regions (not errors)."""
    print("-" * 70)
    print("Name collisions (same city_ascii, different admin_name):")

    # Composite key: a name is only a true duplicate if it repeats
    # within the SAME admin region.
    df["_composite_key"] = (
        df["city_ascii"].str.lower().str.strip()
        + " | "
        + df["admin_name"].fillna("<blank>").str.lower().str.strip()
    )

    true_dups = df[df["_composite_key"].duplicated(keep=False)]
    if true_dups.empty:
        print("  No true duplicates: every (city_ascii, admin_name) pair is unique.")
    else:
        print(f"  {len(true_dups)} rows share a composite key with another row:")
        print(true_dups[["city", "city_ascii", "admin_name", "population"]]
              .sort_values("city_ascii")
              .to_string(index=False))

    print()
    print("Cross-admin name collisions (legitimate distinct places):")
    name_counts = (
        df.groupby(df["city_ascii"].str.lower().str.strip())["admin_name"]
        .nunique()
        .loc[lambda s: s > 1]
        .sort_values(ascending=False)
    )
    if name_counts.empty:
        print("  None.")
    else:
        for name, n_regions in name_counts.items():
            rows = df[df["city_ascii"].str.lower().str.strip() == name]
            regions = ", ".join(
                rows["admin_name"].fillna("<blank>").unique()
            )
            print(f"  {name!r} appears in {n_regions} admin regions: {regions}")


def profile_capital(df: pd.DataFrame) -> None:
    """Summarise the capital field, which is the reliable selection axis."""
    print("-" * 70)
    print("capital field distribution:")
    counts = df["capital"].fillna("<blank>").value_counts(dropna=False)
    print(counts.to_string())
    print()
    print("Interpretation:")
    print("  primary = country capital (Algiers)")
    print("  admin   = first-level admin capital (wilaya seat)")
    print("  minor   = lower-level admin capital")
    print("  blank   = not a capital; still a valid location for weather reporting")


def profile_admin_name(df: pd.DataFrame) -> None:
    """Report admin_name coverage without treating blanks as defects."""
    print("-" * 70)
    blanks = df["admin_name"].isna().sum()
    print(f"admin_name blank in {blanks} of {len(df)} rows "
          f"({blanks / len(df):.1%}).")
    print("Blank is expected for places that are not an admin capital; "
          "it is not a data-quality error.")
    print()
    print(f"Distinct admin_name values (non-blank): {df['admin_name'].nunique()}")
    print("Top 20 admin regions by city count:")
    print(df["admin_name"].value_counts().head(20).to_string())


def main() -> None:
    df = pd.read_csv(CITIES, encoding="utf-8-sig")

    print("=" * 70)
    print(f"shape: {df.shape}")
    print(f"columns: {df.columns.tolist()}")
    print(f"id uniqueness: {df['id'].is_unique}")
    print()

    # 1. Name collisions and duplicates
    profile_duplicates(df)
    print()

    # 2. capital distribution
    profile_capital(df)
    print()

    # 3. admin_name coverage (informational, not an error)
    profile_admin_name(df)
    print()

    # 4. Coordinate sanity
    print("-" * 70)
    print("Coordinate ranges:")
    print(df[["lat", "lng"]].describe().to_string())
    bad_lat = df[~df["lat"].between(*ALGERIA_LAT_RANGE)]
    bad_lng = df[~df["lng"].between(*ALGERIA_LNG_RANGE)]
    if not bad_lat.empty or not bad_lng.empty:
        print(f"  Outside Algeria bbox: lat={len(bad_lat)}, lng={len(bad_lng)}")
        print(pd.concat([bad_lat, bad_lng])[["city", "lat", "lng"]]
              .drop_duplicates().to_string(index=False))
    else:
        print("  All coordinates fall inside the Algeria bounding box.")
    print()

    # 5. Population distribution
    print("-" * 70)
    pop = df["population"].dropna()
    print(f"Population: n={len(pop)}, min={pop.min():,}, "
          f"median={pop.median():,.0f}, max={pop.max():,}")
    print()
    print("Top 10 by population (for selection sanity):")
    print(df.nlargest(10, "population")[
        ["city", "admin_name", "capital", "population"]]
        .to_string(index=False))
    print()

    # 6. Encoding defects (the only genuine data-quality issue)
    print("-" * 70)
    for col in ("city", "admin_name"):
        hits = df[df[col].astype(str).str.contains(MOJIBAKE_PATTERN)]
        print(f"Rows with Windows-1252 control characters in '{col}': {len(hits)}")
        if not hits.empty:
            print(hits[["city", "admin_name"]].drop_duplicates().to_string(index=False))


if __name__ == "__main__":
    main()