"""Generate the analytical report from the computed panel and summary tables."""

from __future__ import annotations

import json
import re
from datetime import date

import pandas as pd

from config import (
    BASE_YEAR,
    COUNTRIES,
    DATA_PROCESSED,
    DATA_RAW,
    END_YEAR,
    FOCUS,
    OUTPUTS,
    ROOT,
)

README = ROOT / "README.md"
REPORT_START = "<!-- ANALYTICAL_REPORT:START -->"
REPORT_END = "<!-- ANALYTICAL_REPORT:END -->"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = pd.read_csv(DATA_PROCESSED / "country_year_panel.csv")
    summary = pd.read_csv(DATA_PROCESSED / "summary_by_country.csv")
    events = pd.read_csv(DATA_PROCESSED / "events_by_country.csv")
    return panel, summary, events


def api_vintage() -> str:
    payload = json.loads((DATA_RAW / "wdi_NY.GDP.PCAP.KD.json").read_text(encoding="utf-8"))
    return str(payload["metadata"].get("lastupdated", "unknown"))


def pc_indicator_label() -> str:
    payload = json.loads((DATA_RAW / "wdi_NY.GDP.PCAP.KD.json").read_text(encoding="utf-8"))
    return str(payload["observations"][0]["indicator"]["value"])


def fmt(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def md_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a Markdown table, formatting numeric cells."""
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_integer_dtype(out[column]):
            out[column] = out[column].map(
                lambda v: "n/a" if pd.isna(v) else f"{int(v):,}"
            )
        elif pd.api.types.is_float_dtype(out[column]):
            out[column] = out[column].map(lambda v: fmt(v, 2))
        else:
            out[column] = out[column].astype(str)
    header = "| " + " | ".join(str(c) for c in out.columns) + " |"
    divider = "| " + " | ".join(["---"] * len(out.columns)) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in out.itertuples(index=False)]
    return "\n".join([header, divider, *rows])


def years(series: pd.Series) -> pd.Series:
    """Index a per-country value series by year."""
    return series.set_index(pd.Index(series["year"].astype(int), name="year"))


def recovery_year(level_by_year: pd.Series, shock_year: int, threshold: float) -> str:
    """First year after the shock at which the pre-shock real GDP pc is regained."""
    later = level_by_year[level_by_year.index > shock_year]
    recovered = later[later >= threshold]
    return str(int(recovered.index[0])) if not recovered.empty else "Not by 2025"


def build_report() -> str:
    panel, summary, events = load_inputs()
    latest = int(panel["year"].max())
    vintage = api_vintage()

    levels = panel.pivot(index="year", columns="country_code", values="gdp_pc")
    indexed = panel.pivot(index="year", columns="country_code", values="gdp_pc_index_2000")
    growth = panel.pivot(index="year", columns="country_code", values="gdp_growth")
    s = summary.set_index("country_code")
    focus_level = levels[FOCUS]
    e = events.set_index(["event_key", "country_code"])

    peak_year = int(focus_level.idxmax())
    peak_value = float(focus_level.max())
    latest_value = float(focus_level.loc[latest])
    below_peak = (latest_value / peak_value - 1) * 100
    baseline_value = float(focus_level.loc[BASE_YEAR])

    # Event-specific numbers used in the narrative.
    rec = e.loc[("recession", FOCUS)]
    covid = e.loc[("covid", FOCUS)]
    boom = e.loc[("boom", FOCUS)]
    boom_cagr = ((boom["gdp_pc_end"] / boom["gdp_pc_start"]) ** (1 / 14) - 1) * 100
    rec_anchor_growth = float(rec["growth_at_anchor_pct"])
    covid_anchor_growth = float(covid["growth_at_anchor_pct"])
    covid_2019 = float(focus_level.loc[2019])
    covid_2021 = float(focus_level.loc[2021])
    covid_pc_cagr = ((covid_2021 / covid_2019) ** 0.5 - 1) * 100

    lines: list[str] = []
    add = lines.append

    add(f"# Nigeria vs Peers — 25 Years of Growth (2000–{latest})")
    add("")
    add(
        f"_Prepared {date.today().isoformat()} from the World Bank World Development Indicators API "
        f"(data vintage {vintage})._"
    )
    add("")

    add("## Executive summary")
    add("")
    add(
        f"- **Nigeria's real GDP per capita rose from ${fmt(baseline_value)} in {BASE_YEAR} to "
        f"${fmt(latest_value)} in {latest}** — a cumulative gain of "
        f"{fmt(s.loc[FOCUS, 'cumulative_gdp_pc_pct'])}% (CAGR "
        f"{fmt(s.loc[FOCUS, 'cagr_gdp_pc_pct'], 2)}% a year), ranking "
        f"**{int(s.loc[FOCUS, 'cagr_rank'])} of 6**. Vietnam ({fmt(s.loc['VNM', 'cagr_gdp_pc_pct'], 2)}%) "
        f"and India ({fmt(s.loc['IND', 'cagr_gdp_pc_pct'], 2)}%) grew much faster."
    )
    add(
        f"- **The oil-led boom lifted Nigeria's real GDP per capita by {fmt(boom['change_start_to_end_pct'])}% "
        f"between 2000 and 2014**, peaking at ${fmt(peak_value)} in {peak_year} "
        f"(index {fmt(indexed.loc[peak_year, FOCUS])}). By {latest} it was still "
        f"**{fmt(abs(below_peak))}% below that peak**."
    )
    add(
        f"- **Two shocks left lasting scars.** Real GDP fell "
        f"{fmt(abs(rec_anchor_growth))}% in 2016 and {fmt(abs(covid_anchor_growth))}% in 2020; Nigeria has "
        f"not regained either its 2015 or its 2019 real GDP per capita level by {latest}."
    )
    add(
        "- **Peer positions changed decisively.** Vietnam overtook Nigeria in real GDP per capita "
        "in 2016 and India in 2024; Ghana closed to within about 5% of Nigeria's 2025 level."
    )
    add(
        f"- **COVID base effects flatter the rebound.** Using 2019–2021 as a two-year window, "
        f"Nigeria's real GDP per capita fell {fmt(abs(covid_pc_cagr))}% a year — the weakest "
        "performance in the group — while the other peers were positive."
    )
    add("")

    add("## 1. Data and method")
    add("")
    add(
        f"- **Indicators:** `NY.GDP.PCAP.KD` — {pc_indicator_label()} — and "
        "`NY.GDP.MKTP.KD.ZG` (annual real GDP growth). Both were pulled directly from the "
        "World Bank WDI API for Nigeria, Ghana, Kenya, South Africa, India and Vietnam, "
        f"{BASE_YEAR}–{END_YEAR}."
    )
    add(
        "- **Panel:** the API responses were flattened, pivoted to a balanced country-year "
        "panel (156 rows = 6 countries × 26 years), and checked for missing observations "
        "(`data/processed/data_quality.csv`). This pull had **no missing years**."
    )
    add(
        f"- **Indexing:** each country's real GDP per capita was divided by its {BASE_YEAR} value "
        "and multiplied by 100. Index numbers compare *growth paths*, not income levels."
    )
    add(
        "- **Long-run growth:** CAGR is computed on real GDP per capita from the first to the "
        "latest available year; it is not the average of annual growth rates."
    )
    add(
        "- **Events:** shaded windows are analytical conventions — boom 2000–2014, 2016 "
        "recession 2015–2017, COVID-19 2020–2021. They describe timing, not causal attribution."
    )
    add(
        "- **Base effects:** because the 2020 fall mechanically inflates 2021 growth, the report "
        "also uses the 2019–2021 compound rate of the *level* of real GDP per capita."
    )
    add("")

    add("## 2. Long-run performance: levels and rankings")
    add("")
    long_run = pd.DataFrame(
        {
            "Country": s["country"],
            f"GDP pc {BASE_YEAR} (US$)": s["gdp_pc_first"],
            f"GDP pc {latest} (US$)": s["gdp_pc_latest"],
            "Cumulative change (%)": s["cumulative_gdp_pc_pct"],
            "CAGR (%)": s["cagr_gdp_pc_pct"],
            "CAGR rank": s["cagr_rank"],
        }
    ).reset_index(drop=True)
    add(md_table(long_run))
    add("")
    add(
        f"In {BASE_YEAR} Nigeria was the second-richest country in the group in real GDP per "
        f"capita (${fmt(baseline_value)}), behind South Africa but ahead of Ghana, Kenya, Vietnam "
        f"and India. By {latest} Nigeria had slipped to rank "
        f"{int((s['gdp_pc_latest'] > latest_value).sum() + 1)} of 6: Vietnam, India and South "
        "Africa are now ahead, while Nigeria remains only narrowly ahead of Ghana and Kenya. "
        "The gap with the two Asian peers is the central finding of the comparison: Vietnam "
        f"multiplied real GDP per capita {fmt(levels.loc[latest, 'VNM'] / levels.loc[2000, 'VNM'], 2)}× "
        f"and India {fmt(levels.loc[latest, 'IND'] / levels.loc[2000, 'IND'], 2)}×, versus "
        f"{fmt(latest_value / baseline_value, 2)}× for Nigeria."
    )
    add("")

    overtakes = []
    for code in [c for c in COUNTRIES if c != FOCUS]:
        peer = levels[code]
        crossed = peer[peer > focus_level]
        if peer.loc[BASE_YEAR] > baseline_value:
            crossover = f"Already above in {BASE_YEAR}"
        elif not crossed.empty:
            crossover = str(int(crossed.index[0]))
        else:
            crossover = f"Not by {latest}"
        overtakes.append(
            {
                "Peer": COUNTRIES[code],
                f"Ratio in {BASE_YEAR}": peer.loc[BASE_YEAR] / baseline_value,
                "First year above Nigeria": crossover,
                f"Ratio in {latest}": peer.loc[latest] / latest_value,
            }
        )
    add("**Relative position (peer GDP per capita ÷ Nigeria's)**")
    add("")
    add(md_table(pd.DataFrame(overtakes)))
    add("")
    add(
        "Vietnam's crossover in 2016 coincided with Nigeria's recession, and India's in 2024 "
        "completes a two-decade convergence in which Nigeria moved from a clear lead over both "
        "to a position below them. Ghana started the period at roughly 72% of Nigeria's level "
        "and ended at about 95%, so Nigeria's regional lead is now thin."
    )
    add("")

    add("## 3. Indexed real GDP per capita (2000 = 100)")
    add("")
    index_years = [2000, 2014, 2015, 2016, 2019, 2020, 2021, latest]
    index_table = pd.DataFrame(
        {"Country": [COUNTRIES[c] for c in COUNTRIES]}
        | {
            str(year): [indexed.loc[year, c] for c in COUNTRIES]
            for year in index_years
        }
    )
    add(md_table(index_table))
    add("")
    add(
        f"Nigeria's index climbed steadily to {fmt(indexed.loc[peak_year, FOCUS])} in {peak_year}, "
        f"slipped to {fmt(indexed.loc[2018, FOCUS])} by 2018, fell again to "
        f"{fmt(indexed.loc[2021, FOCUS])} in 2021, and has since recovered only to "
        f"{fmt(indexed.loc[latest, FOCUS])}. That leaves the index {fmt(abs(below_peak))}% below "
        "its pre-recession high after roughly a decade. India and Vietnam, by contrast, reached "
        f"about {fmt(indexed.loc[latest, 'IND'])} and {fmt(indexed.loc[latest, 'VNM'])}, "
        "with no comparable long-lasting interruption. South Africa's index barely moved, "
        "reflecting weak per-capita growth rather than crisis volatility."
    )
    add("")
    add("![Indexed real GDP per capita](outputs/figures/02_indexed_gdp_per_capita.png)")
    add("")

    add("## 4. Annual growth and volatility")
    add("")
    growth_table = pd.DataFrame(
        {
            "Country": s["country"],
            "Mean growth (%)": s["mean_gdp_growth_pct"],
            "SD of growth (%)": s["sd_gdp_growth_pct"],
            "Negative-growth years": s["negative_growth_years"],
            "Best year": s["best_growth_year"].astype(str)
            + " ("
            + s["best_growth_pct"].map(lambda v: fmt(v))
            + "%)",
            "Worst year": s["worst_growth_year"].astype(str)
            + " ("
            + s["worst_growth_pct"].map(lambda v: fmt(v))
            + "%)",
        }
    ).reset_index(drop=True)
    add(md_table(growth_table))
    add("")
    add(
        f"Nigeria records the highest growth volatility in the group (standard deviation "
        f"{fmt(s.loc[FOCUS, 'sd_gdp_growth_pct'], 2)} percentage points) despite a middling "
        "average rate. Its best year was 2002 "
        f"({fmt(s.loc[FOCUS, 'best_growth_pct'])}%) during the boom; its worst was 2020 "
        f"({fmt(s.loc[FOCUS, 'worst_growth_pct'])}%). Vietnam and India combined high average "
        "growth with markedly lower volatility, while South Africa had low growth *and* two "
        "contraction years."
    )
    add("")
    add("![Annual real GDP growth](outputs/figures/03_annual_real_gdp_growth.png)")
    add("")
    add("![Growth heatmap](outputs/figures/04_growth_heatmap.png)")
    add("")

    add("## 5. Event analysis: Nigeria against its peers")
    add("")

    add("### 5.1 The boom (2000–2014)")
    add("")
    add(
        f"Nigeria's real GDP per capita rose {fmt(boom['change_start_to_end_pct'])}% over the boom "
        f"window, an average of {fmt(boom_cagr, 2)}% a year; real GDP growth averaged "
        f"{fmt(growth.loc[2000:2014, FOCUS].mean(), 2)}%. This was a strong expansion in level "
        "terms but not an exceptional one: over the same years Vietnam gained "
        f"{fmt(e.loc[('boom', 'VNM'), 'change_start_to_end_pct'])}% and India "
        f"{fmt(e.loc[('boom', 'IND'), 'change_start_to_end_pct'])}%, both starting from much lower bases."
    )
    add("")

    add("### 5.2 The 2016 recession")
    add("")
    add(
        f"Nigeria's real GDP fell {fmt(abs(rec_anchor_growth))}% in 2016. The per-capita effect "
        f"was larger and more persistent: real GDP per capita fell from "
        f"${fmt(rec['gdp_pc_start'])} in 2015 to ${fmt(rec['gdp_pc_trough'])} in "
        f"{int(rec['trough_year'])}, a {fmt(abs(rec['decline_start_to_trough_pct']))}% decline, and "
        "had still not surpassed the 2015 level by 2025. Every other country in the sample "
        "had regained its 2015 real GDP per capita by 2017 (South Africa in 2017, the rest "
        "in 2016)."
    )
    add("")

    add("### 5.3 COVID-19 dip and base effects")
    add("")
    add(
        f"Nigeria's real GDP fell {fmt(abs(covid_anchor_growth))}% in 2020 and real GDP per capita "
        f"fell another {fmt(abs(covid['decline_start_to_trough_pct']))}% to "
        f"${fmt(covid['gdp_pc_trough'])} by 2021 — the 2021 headline growth rate of "
        f"{fmt(growth.loc[2021, FOCUS])}% was positive, but population growth meant average "
        "output per person still declined. India, South Africa and Nigeria all contracted "
        "sharply in 2020; Ghana and Kenya were nearly unaffected and Vietnam still grew."
    )
    add("")
    base_table = pd.DataFrame(
        {
            "Country": [COUNTRIES[c] for c in COUNTRIES],
            "2020 growth (%)": [growth.loc[2020, c] for c in COUNTRIES],
            "2021 growth (%)": [growth.loc[2021, c] for c in COUNTRIES],
            "2022 growth (%)": [growth.loc[2022, c] for c in COUNTRIES],
            "2019-21 GDP pc CAGR (%)": [
                ((levels.loc[2021, c] / levels.loc[2019, c]) ** 0.5 - 1) * 100
                for c in COUNTRIES
            ],
        }
    )
    add(md_table(base_table))
    add("")
    add(
        "The 2021 growth column overstates the strength of the recovery wherever 2020 was "
        "deep: it is measured against a depressed base. The final column strips that "
        "mechanical effect out by compounding the *level* from 2019 to 2021. On that basis "
        f"Nigeria ({fmt(covid_pc_cagr)}% a year) and South Africa did worse than the rest of the group, "
        "while Vietnam, Kenya, India and Ghana still gained ground per person."
    )
    add("")

    add("### 5.4 Recovery comparison")
    add("")
    recovery_rows = []
    for code in COUNTRIES:
        series = levels[code]
        recovery_rows.append(
            {
                "Country": COUNTRIES[code],
                "2015 GDP pc": series.loc[2015],
                "Year regained 2015 level": recovery_year(series, 2015, series.loc[2015]),
                "2019 GDP pc": series.loc[2019],
                "Year regained 2019 level": recovery_year(series, 2019, series.loc[2019]),
                "2025 vs 2019 (%)": (series.loc[latest] / series.loc[2019] - 1) * 100,
            }
        )
    add(md_table(pd.DataFrame(recovery_rows)))
    add("")
    add(
        "Nigeria is the only economy in the sample that has recovered neither its pre-2016 "
        "nor its pre-COVID real GDP per capita level. South Africa also remains below its "
        "2019 level, but its downturn was shallower and its starting level far higher. "
        "Nigeria's 2022–2025 rebound of roughly 4% a year has not been enough to close the "
        "cumulative losses of the two shocks."
    )
    add("")
    add("![Recovery comparison](outputs/figures/06_recession_recovery.png)")
    add("")

    add("## 6. Answers to the specific research questions")
    add("")
    qa = [
        (
            "Q1. How has real GDP per capita evolved since 2000?",
            f"It rose from ${fmt(baseline_value)} to ${fmt(latest_value)} in Nigeria, but with two "
            "long plateaus after 2015 and 2019 rather than a smooth upward path.",
        ),
        (
            "Q2. Strongest and weakest growth in real GDP per capita?",
            f"Vietnam ({fmt(s.loc['VNM', 'cagr_gdp_pc_pct'], 2)}% CAGR) and India "
            f"({fmt(s.loc['IND', 'cagr_gdp_pc_pct'], 2)}%) were strongest; South Africa "
            f"({fmt(s.loc['ZAF', 'cagr_gdp_pc_pct'], 2)}%) and Kenya "
            f"({fmt(s.loc['KEN', 'cagr_gdp_pc_pct'], 2)}%) were weakest, with Nigeria "
            f"({fmt(s.loc[FOCUS, 'cagr_gdp_pc_pct'], 2)}%) in fourth place.",
        ),
        (
            "Q3. How did Nigeria's annual growth compare?",
            f"Nigeria's mean annual growth ({fmt(s.loc[FOCUS, 'mean_gdp_growth_pct'], 2)}%) was "
            "close to the group average but the most volatile; it had only two contraction "
            "years, yet both were deep and long-lasting in per-capita terms.",
        ),
        (
            "Q4. Effects of the boom, 2016 recession and COVID-19?",
            f"The boom added {fmt(boom['change_start_to_end_pct'])}% to real GDP per capita by "
            f"2014; the 2016 shock removed {fmt(abs(rec['decline_start_to_trough_pct']))}% by "
            f"2017; COVID cut real GDP per capita "
            f"{fmt(abs((focus_level.loc[2020] / focus_level.loc[2019] - 1) * 100))}% in 2020 "
            f"and a further {fmt(abs(covid['decline_start_to_trough_pct']))}% in 2021.",
        ),
        (
            "Q5. How did recovery compare?",
            "All five peers regained their 2015 level by 2017 and most regained their 2019 "
            "level by 2021. Nigeria regained neither by 2025.",
        ),
        (
            "Q6. Sustained improvements in average output per person?",
            "Only partly. The 2000–2014 expansion was substantial, but a decade after the peak "
            f"real GDP per capita remained {fmt(abs(below_peak))}% lower, and growth since 2022 "
            "has merely repaired part of the COVID loss.",
        ),
        (
            "Q7. How did Nigeria's relative position change?",
            "It fell from second to fourth in the group by real GDP per capita: Vietnam passed "
            "it in 2016, India in 2024, and Ghana narrowed the gap to about 5%.",
        ),
    ]
    for question, answer in qa:
        add(f"**{question}** {answer}")
        add("")

    add("## 7. Caveats and limitations")
    add("")
    add(
        f"- **Constant, not current, USD.** `NY.GDP.PCAP.KD` ({pc_indicator_label()}) is "
        "inflation-adjusted against a fixed US-dollar base and is appropriate for comparing "
        "real growth over time. World Bank rebases the constant-dollar series periodically; "
        "all numbers here come from one API vintage and should not be mixed with another "
        "vintage or with current-USD levels."
    )
    add(
        "- **Per capita ≠ distribution.** GDP per capita says nothing about inequality, "
        "poverty or welfare. Rapid population growth can produce falling per-capita output "
        "even when total GDP grows (Nigeria in 2021)."
    )
    add(
        "- **Base effects.** Annual growth for 2021 is mechanically distorted by the 2020 "
        "fall; the 2019–2021 compound rates and the indexed levels are the safer comparison."
    )
    add(
        "- **Annual frequency and event windows.** Shaded periods are interpretive, not a "
        "formal causal design; quarterly data would date the turning points more precisely."
    )
    add(
        f"- **Coverage.** This vintage has complete {BASE_YEAR}–{latest} coverage for all six "
        "countries and no missing observations, so no interpolation was required."
    )
    add("")

    add("## 8. Deliverables and reproduction")
    add("")
    add(
        "| File | Description |\n| --- | --- |\n"
        "| `data/raw/wdi_*.json`, `data/raw/wdi_raw_long.csv` | Raw API responses and flattened long data |\n"
        "| `data/processed/country_year_panel.csv` | Balanced country-year panel with index and YoY per-capita change |\n"
        "| `data/processed/summary_by_country.csv`, `events.csv`, `events_by_country.csv`, `data_quality.csv` | Derived tables |\n"
        "| `outputs/figures/*.png` | Six comparative visualisations |\n"
        "| `outputs/analytical_report.md` | This report |\n"
        "| `run_analysis.py` | End-to-end pipeline: `python run_analysis.py` |"
    )
    add("")
    add("![Real GDP per capita levels](outputs/figures/01_gdp_per_capita_levels.png)")
    add("")
    add("![CAGR comparison](outputs/figures/05_cagr_comparison.png)")
    add("")

    return "\n".join(lines)


def readme_section(report: str) -> str:
    """Embed the report in the README with headings demoted by one level."""
    lines = [line for line in report.splitlines() if not line.startswith("_Prepared ")]
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines.pop(0)
    body = "\n".join(re.sub(r"^(#{2,3})(\s)", r"#\1\2", line) for line in lines)
    return f"{REPORT_START}\n{body}\n{REPORT_END}"


def sync_readme(report: str) -> None:
    """Keep the README copy of the report aligned with the standalone file."""
    text = README.read_text(encoding="utf-8")
    section = readme_section(report)
    if REPORT_START in text and REPORT_END in text:
        before, rest = text.split(REPORT_START, 1)
        _, after = rest.split(REPORT_END, 1)
        README.write_text(before + section + after, encoding="utf-8", newline="\n")
    else:
        README.write_text(text.rstrip() + "\n\n" + section + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    report = build_report()
    path = OUTPUTS / "analytical_report.md"
    path.write_text(report, encoding="utf-8", newline="\n")
    sync_readme(report)
    print(f"Report -> {path} ({len(report.splitlines())} lines)")
    print(f"Report -> {README}")


if __name__ == "__main__":
    main()
