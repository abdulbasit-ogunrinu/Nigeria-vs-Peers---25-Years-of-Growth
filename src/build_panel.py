"""Clean the raw WDI pull into a country-year panel and derive analysis tables."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    BASE_YEAR,
    COUNTRIES,
    DATA_PROCESSED,
    DATA_RAW,
    END_YEAR,
    EVENTS,
    FOCUS,
    INDICATORS,
    START_YEAR,
    ensure_dirs,
)


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the balanced country-year panel and the raw long file."""
    raw = pd.read_csv(DATA_RAW / "wdi_raw_long.csv")
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw["year"] = raw["year"].astype(int)

    wide = (
        raw.pivot_table(
            index=["country_code", "year"],
            columns="indicator_code",
            values="value",
            aggfunc="first",
        )
        .rename(columns=INDICATORS)
        .reset_index()
    )

    # Enforce a fully balanced grid so missing years are explicit, not silent.
    full_index = pd.MultiIndex.from_product(
        [list(COUNTRIES), range(START_YEAR, END_YEAR + 1)],
        names=["country_code", "year"],
    )
    panel = (
        wide.set_index(["country_code", "year"])
        .reindex(full_index)
        .reset_index()
        .sort_values(["country_code", "year"])
        .reset_index(drop=True)
    )
    panel["country"] = panel["country_code"].map(COUNTRIES)

    base = panel.loc[
        panel["year"] == BASE_YEAR, ["country_code", "gdp_pc"]
    ].rename(columns={"gdp_pc": "gdp_pc_base"})
    panel = panel.merge(base, on="country_code", how="left")
    panel["gdp_pc_index_2000"] = 100.0 * panel["gdp_pc"] / panel["gdp_pc_base"]
    panel["gdp_pc_yoy"] = (
        panel.groupby("country_code")["gdp_pc"].pct_change() * 100.0
    )

    panel = panel[
        [
            "country_code",
            "country",
            "year",
            "gdp_pc",
            "gdp_growth",
            "gdp_pc_base",
            "gdp_pc_index_2000",
            "gdp_pc_yoy",
        ]
    ]
    return panel, raw


def write_quality_report(raw: pd.DataFrame) -> pd.DataFrame:
    """Log missing years and the latest available observation per series."""
    rows = []
    years = set(range(START_YEAR, END_YEAR + 1))
    for (code, indicator), group in raw.groupby(["country_code", "indicator_code"]):
        observed = set(group.loc[group["value"].notna(), "year"])
        rows.append(
            {
                "country_code": code,
                "country": COUNTRIES.get(code, ""),
                "indicator_code": indicator,
                "n_observed": len(observed),
                "first_year_available": min(observed) if observed else np.nan,
                "latest_year_available": max(observed) if observed else np.nan,
                "missing_years": ", ".join(str(y) for y in sorted(years - observed))
                or "none",
            }
        )
    quality = pd.DataFrame(rows).sort_values(["indicator_code", "country_code"])
    quality.to_csv(DATA_PROCESSED / "data_quality.csv", index=False, lineterminator="\n")
    return quality


def summarise_countries(panel: pd.DataFrame) -> pd.DataFrame:
    """Headline long-run statistics for every country."""
    rows = []
    for code, group in panel.groupby("country_code"):
        growth = group.dropna(subset=["gdp_growth"])
        levels = group.dropna(subset=["gdp_pc"]).sort_values("year")
        if levels.empty:
            continue
        first, last = levels.iloc[0], levels.iloc[-1]
        span = int(last["year"] - first["year"])
        cagr = (
            ((last["gdp_pc"] / first["gdp_pc"]) ** (1.0 / span) - 1.0) * 100.0
            if span > 0 and first["gdp_pc"] > 0
            else np.nan
        )
        cumulative = (
            (last["gdp_pc"] / first["gdp_pc"] - 1.0) * 100.0
            if first["gdp_pc"] > 0
            else np.nan
        )
        max_row = growth.loc[growth["gdp_growth"].idxmax()] if not growth.empty else None
        min_row = growth.loc[growth["gdp_growth"].idxmin()] if not growth.empty else None
        rows.append(
            {
                "country_code": code,
                "country": COUNTRIES[code],
                "first_year": int(first["year"]),
                "gdp_pc_first": first["gdp_pc"],
                "latest_year": int(last["year"]),
                "gdp_pc_latest": last["gdp_pc"],
                "cumulative_gdp_pc_pct": cumulative,
                "cagr_gdp_pc_pct": cagr,
                "mean_gdp_growth_pct": growth["gdp_growth"].mean(),
                "sd_gdp_growth_pct": growth["gdp_growth"].std(),
                "negative_growth_years": int((growth["gdp_growth"] < 0).sum()),
                "best_growth_year": int(max_row["year"]) if max_row is not None else None,
                "best_growth_pct": max_row["gdp_growth"] if max_row is not None else np.nan,
                "worst_growth_year": int(min_row["year"]) if min_row is not None else None,
                "worst_growth_pct": min_row["gdp_growth"] if min_row is not None else np.nan,
            }
        )
    summary = pd.DataFrame(rows)
    summary["cagr_rank"] = summary["cagr_gdp_pc_pct"].rank(ascending=False).astype(int)
    summary = summary.sort_values("cagr_rank").reset_index(drop=True)
    summary.to_csv(DATA_PROCESSED / "summary_by_country.csv", index=False, lineterminator="\n")
    return summary


def summarise_events(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quantify each event window country by country (peak, trough, change)."""
    definitions = pd.DataFrame(
        [
            {
                "event_key": e["key"],
                "event_name": e["name"],
                "start": e["start"],
                "end": e["end"],
                "anchor_year": e["anchor"],
                "colour": e["colour"],
                "note": e["note"],
            }
            for e in EVENTS
        ]
    )
    definitions.to_csv(DATA_PROCESSED / "events.csv", index=False, lineterminator="\n")

    rows = []
    for event in EVENTS:
        for code in COUNTRIES:
            window = panel[
                (panel["country_code"] == code)
                & (panel["year"] >= event["start"])
                & (panel["year"] <= event["end"])
                & panel["gdp_pc"].notna()
            ].sort_values("year")
            if window.empty:
                continue
            first, last = window.iloc[0], window.iloc[-1]
            trough = window.loc[window["gdp_pc"].idxmin()]
            peak = window.loc[window["gdp_pc"].idxmax()]
            anchor_year = event["anchor"]
            anchor_growth = panel.loc[
                (panel["country_code"] == code) & (panel["year"] == anchor_year),
                "gdp_growth",
            ]
            rows.append(
                {
                    "event_key": event["key"],
                    "event_name": event["name"],
                    "country_code": code,
                    "country": COUNTRIES[code],
                    "window_first_year": int(first["year"]),
                    "window_last_year": int(last["year"]),
                    "gdp_pc_start": first["gdp_pc"],
                    "gdp_pc_end": last["gdp_pc"],
                    "change_start_to_end_pct": (last["gdp_pc"] / first["gdp_pc"] - 1)
                    * 100,
                    "trough_year": int(trough["year"]),
                    "gdp_pc_trough": trough["gdp_pc"],
                    "decline_start_to_trough_pct": (
                        trough["gdp_pc"] / first["gdp_pc"] - 1
                    )
                    * 100,
                    "peak_year": int(peak["year"]),
                    "gdp_pc_peak": peak["gdp_pc"],
                    "anchor_year": anchor_year,
                    "growth_at_anchor_pct": (
                        float(anchor_growth.iloc[0]) if not anchor_growth.isna().all() else np.nan
                    ),
                    "is_focus": code == FOCUS,
                }
            )
    by_country = pd.DataFrame(rows)
    by_country.to_csv(DATA_PROCESSED / "events_by_country.csv", index=False, lineterminator="\n")
    return definitions, by_country


def main() -> None:
    ensure_dirs()
    panel, raw = load_panel()
    panel.to_csv(DATA_PROCESSED / "country_year_panel.csv", index=False, lineterminator="\n")

    quality = write_quality_report(raw)
    summary = summarise_countries(panel)
    _, events = summarise_events(panel)

    print(f"Panel: {panel.shape[0]} rows -> country_year_panel.csv")
    print(f"Quality log: {quality.shape[0]} series -> data_quality.csv")
    print(f"Summary: {summary.shape[0]} countries -> summary_by_country.csv")
    print(f"Events: {events.shape[0]} country-event rows -> events_by_country.csv")
    print("\nReal GDP per capita CAGR, 2000 to latest (% per year):")
    print(
        summary[["country", "cagr_gdp_pc_pct", "gdp_pc_first", "gdp_pc_latest"]]
        .to_string(index=False, float_format=lambda x: f"{x:,.2f}")
    )


if __name__ == "__main__":
    main()
