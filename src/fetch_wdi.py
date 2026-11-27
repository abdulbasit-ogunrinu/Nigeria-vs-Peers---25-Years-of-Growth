"""Pull raw indicator data from the World Bank WDI API and save it unchanged.

API docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from config import (
    API_BASE,
    COUNTRIES,
    DATA_RAW,
    END_YEAR,
    INDICATORS,
    START_YEAR,
    ensure_dirs,
)


def fetch_indicator(indicator: str, country_codes: list[str]) -> tuple[dict, list[dict]]:
    """Fetch every page of one indicator for the selected countries."""
    url = f"{API_BASE}/country/{';'.join(country_codes)}/indicator/{indicator}"
    metadata: dict = {}
    observations: list[dict] = []
    page = 1

    while True:
        params = {
            "format": "json",
            "date": f"{START_YEAR}:{END_YEAR}",
            "per_page": 1000,
            "page": page,
        }
        response = requests.get(
            url,
            params=params,
            timeout=60,
            headers={"User-Agent": "nigeria-vs-peers-wdi-analysis/1.0"},
        )
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, list) or len(payload) != 2:
            raise RuntimeError(f"Unexpected WDI response for {indicator}: {payload!r}")
        page_meta, rows = payload
        if not isinstance(rows, list):
            raise RuntimeError(f"WDI returned an error for {indicator}: {page_meta}")

        if not metadata:
            metadata = dict(page_meta)
        observations.extend(rows)

        if page >= int(page_meta.get("pages", 1)):
            break
        page += 1
        time.sleep(0.2)  # be gentle with the public API

    return metadata, observations


def tidy_rows(rows: list[dict], indicator: str) -> list[dict[str, Any]]:
    """Flatten WDI JSON records into a tidy list of dictionaries."""
    tidy = []
    for row in rows:
        tidy.append(
            {
                "country_code": row.get("countryiso3code") or "",
                "country": (row.get("country") or {}).get("value", ""),
                "year": int(row["date"]),
                "indicator_code": indicator,
                "indicator": (row.get("indicator") or {}).get("value", ""),
                "value": row.get("value"),
                "unit": row.get("unit", ""),
                "obs_status": row.get("obs_status", ""),
                "decimal": row.get("decimal"),
            }
        )
    return tidy


def main() -> None:
    ensure_dirs()
    all_rows: list[dict[str, Any]] = []
    for indicator in INDICATORS:
        metadata, rows = fetch_indicator(indicator, list(COUNTRIES))
        raw_path = DATA_RAW / f"wdi_{indicator}.json"
        raw_path.write_text(
            json.dumps({"metadata": metadata, "observations": rows}, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        all_rows.extend(tidy_rows(rows, indicator))
        print(
            f"{indicator}: {len(rows)} observations, "
            f"vintage {metadata.get('lastupdated', 'unknown')} -> {raw_path.name}"
        )

    import pandas as pd

    raw = pd.DataFrame(all_rows).sort_values(
        ["indicator_code", "country_code", "year"]
    )
    raw.to_csv(DATA_RAW / "wdi_raw_long.csv", index=False, lineterminator="\n")
    missing = int(raw["value"].isna().sum())
    print(
        f"Raw long file: {len(raw)} rows, {missing} missing values -> "
        f"{(DATA_RAW / 'wdi_raw_long.csv').name}"
    )


if __name__ == "__main__":
    main()
