"""Comparative charts for real GDP per capita and annual real GDP growth."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import COLOURS, COUNTRIES, EVENTS, FOCUS, FIGURES, SHORT_NAMES, ensure_dirs

plt.rcParams.update(
    {
        "figure.dpi": 120,
        "savefig.dpi": 180,
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
    }
)


def _country_lines(ax: plt.Axes, panel: pd.DataFrame, column: str, **kwargs) -> None:
    """Plot one line per country, drawing the focus country last and boldly."""
    order = [c for c in COUNTRIES if c != FOCUS] + [FOCUS]
    for code in order:
        group = panel[panel["country_code"] == code].dropna(subset=[column])
        if group.empty:
            continue
        focus = code == FOCUS
        ax.plot(
            group["year"],
            group[column],
            color=COLOURS[code],
            linewidth=2.6 if focus else 1.5,
            alpha=1.0 if focus else 0.85,
            linestyle="-" if focus else "-",
            label=f"{COUNTRIES[code]}{' (focus)' if focus else ''}",
            zorder=5 if focus else 3,
            **kwargs,
        )


def _shade_events(ax: plt.Axes, label_top: bool = True) -> None:
    """Add the Nigeria event windows and small labels at the top of the axes."""
    ymin, ymax = ax.get_ylim()
    for event in EVENTS:
        ax.axvspan(
            event["start"] - 0.5,
            event["end"] + 0.5,
            color=event["colour"],
            alpha=event["alpha"],
            lw=0,
            zorder=0,
        )
        if label_top:
            ax.text(
                (event["start"] + event["end"]) / 2,
                ymax - 0.025 * (ymax - ymin),
                SHORT_NAMES[event["key"]],
                ha="center",
                va="top",
                fontsize=8,
                fontweight="bold",
                color=event["colour"],
                zorder=6,
            )
    ax.set_ylim(ymin, ymax)


def _save(fig: plt.Figure, name: str, note: str | None = None) -> None:
    if note:
        fig.text(0.01, 0.005, note, fontsize=8, color="#555555")
        fig.tight_layout(rect=(0.01, 0.035, 0.99, 0.99))
    else:
        fig.tight_layout()
    path = FIGURES / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Figure -> {path.name}")


def plot_levels(panel: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    _country_lines(ax, panel, "gdp_pc")
    ax.set_title("Real GDP per capita, 2000-2025 (constant US$)")
    ax.set_xlabel("Year")
    ax.set_ylabel("GDP per capita (constant US$)")
    ax.set_xlim(1999.7, 2025.3)
    ax.legend(loc="upper left", ncol=2, fontsize=9)
    _save(
        fig,
        "01_gdp_per_capita_levels.png",
        "Source: World Bank WDI, NY.GDP.PCAP.KD. Constant USD; levels are comparable over time within a single vintage.",
    )


def plot_indexed(panel: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    _country_lines(ax, panel, "gdp_pc_index_2000")
    ax.set_title("Real GDP per capita indexed to 2000 = 100")
    ax.set_xlabel("Year")
    ax.set_ylabel("Index (2000 = 100)")
    ax.set_xlim(1999.7, 2025.3)
    ax.set_ylim(85, 385)
    ax.axhline(100, color="#777777", lw=0.9, ls="--", zorder=1)
    ax.legend(loc="upper left", ncol=2, fontsize=9)
    _shade_events(ax, label_top=True)

    focus = panel[panel["country_code"] == FOCUS].set_index("year")
    annotations = [
        (2015, "2015 peak\n182", (2010, 108)),
        (2018, "Post-recession\nlow: 171", (2018.6, 128)),
        (2021, "COVID low\n155", (2022.3, 108)),
    ]
    for year, label, xytext in annotations:
        if year not in focus.index:
            continue
        value = focus.loc[year, "gdp_pc_index_2000"]
        ax.annotate(
            label,
            xy=(year, value),
            xytext=xytext,
            fontsize=8.5,
            color=COLOURS[FOCUS],
            ha="center",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=COLOURS[FOCUS], alpha=0.9),
            arrowprops=dict(arrowstyle="->", color=COLOURS[FOCUS], lw=1.1),
            zorder=7,
        )
    _save(
        fig,
        "02_indexed_gdp_per_capita.png",
        "Source: World Bank WDI, NY.GDP.PCAP.KD. Shaded windows mark Nigeria's boom, 2016 recession and COVID-19 dip.",
    )


def plot_growth(panel: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    _country_lines(ax, panel, "gdp_growth")
    ax.axhline(0, color="#333333", lw=1.0, zorder=2)
    ax.set_title("Annual real GDP growth, 2000-2025")
    ax.set_xlabel("Year")
    ax.set_ylabel("Growth (% per year)")
    ax.set_xlim(1999.7, 2025.3)
    ax.set_ylim(-9, 16)
    ax.legend(loc="upper left", ncol=2, fontsize=9)
    _shade_events(ax, label_top=True)

    focus = panel[panel["country_code"] == FOCUS].dropna(subset=["gdp_growth"])
    for year in (2016, 2020):
        row = focus[focus["year"] == year]
        if row.empty:
            continue
        value = float(row["gdp_growth"].iloc[0])
        ax.scatter([year], [value], s=55, marker="x", c="#B2182B", linewidths=2, zorder=8)
        ax.annotate(
            f"{value:.1f}%",
            xy=(year, value),
            xytext=(year - 1.1, value - 2.2),
            fontsize=8.5,
            color="#B2182B",
            fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#B2182B", lw=1),
            zorder=8,
        )
    _save(
        fig,
        "03_annual_real_gdp_growth.png",
        "Source: World Bank WDI, NY.GDP.MKTP.KD.ZG. Red crosses mark Nigeria's contraction years (2016 and 2020).",
    )


def plot_growth_heatmap(panel: pd.DataFrame) -> None:
    codes = [FOCUS] + [c for c in COUNTRIES if c != FOCUS]
    years = sorted(panel["year"].unique())
    matrix = (
        panel.pivot(index="country_code", columns="year", values="gdp_growth")
        .reindex(index=codes, columns=years)
        .to_numpy(dtype=float)
    )

    fig, ax = plt.subplots(figsize=(17, 5.2))
    image = ax.imshow(matrix, cmap="RdBu_r", vmin=-8, vmax=15, aspect="auto")
    ax.set_xticks(range(len(years)), labels=years, rotation=90, fontsize=8)
    ax.set_yticks(range(len(codes)), labels=[COUNTRIES[c] for c in codes], fontsize=10)
    ax.set_title("Annual real GDP growth heatmap (%)")
    ax.grid(False)
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            if np.isnan(value):
                continue
            ax.text(
                col,
                row,
                f"{value:.1f}",
                ha="center",
                va="center",
                fontsize=6.8,
                color="white" if abs(value) >= 5.5 else "#222222",
            )
    ax.axhline(-0.5, color="#111111", lw=2)
    ax.axhline(0.5, color="#111111", lw=1)
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.01)
    cbar.set_label("Growth (%)")
    _save(
        fig,
        "04_growth_heatmap.png",
        "Source: World Bank WDI, NY.GDP.MKTP.KD.ZG. Note: 2021 rebounds partly reflect the low 2020 base.",
    )


def plot_cagr(summary: pd.DataFrame) -> None:
    data = summary.sort_values("cagr_gdp_pc_pct")
    fig, ax = plt.subplots(figsize=(9, 5))
    colours = [COLOURS[c] for c in data["country_code"]]
    bars = ax.barh(data["country"], data["cagr_gdp_pc_pct"], color=colours, alpha=0.9)
    for bar, value in zip(bars, data["cagr_gdp_pc_pct"]):
        ax.text(
            value + 0.08,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.2f}%",
            va="center",
            fontsize=9,
        )
    ax.set_xlim(0, data["cagr_gdp_pc_pct"].max() * 1.18)
    ax.set_title("Real GDP per capita CAGR, 2000-2025")
    ax.set_xlabel("Average annual growth rate (%)")
    ax.grid(axis="y", alpha=0)
    _save(
        fig,
        "05_cagr_comparison.png",
        "Source: World Bank WDI, NY.GDP.PCAP.KD. CAGR computed from the first to the latest available year.",
    )


def plot_recovery(panel: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), sharey=False)
    windows = [
        (2015, 2010, 2025, "Before the 2016 recession (2015 = 100)"),
        (2019, 2016, 2025, "Before COVID-19 (2019 = 100)"),
    ]
    for ax, (base, start, end, title) in zip(axes, windows):
        subset = panel[(panel["year"] >= start) & (panel["year"] <= end)]
        bases = panel.loc[
            panel["year"] == base, ["country_code", "gdp_pc"]
        ].set_index("country_code")["gdp_pc"]
        for code in COUNTRIES:
            group = subset[subset["country_code"] == code].dropna(subset=["gdp_pc"])
            if group.empty:
                continue
            rebased = 100.0 * group["gdp_pc"] / bases.get(code, np.nan)
            ax.plot(
                group["year"],
                rebased,
                color=COLOURS[code],
                lw=2.6 if code == FOCUS else 1.4,
                alpha=1.0 if code == FOCUS else 0.85,
                label=COUNTRIES[code],
                zorder=5 if code == FOCUS else 3,
            )
        ax.axhline(100, color="#333333", lw=1, ls="--")
        ax.set_title(title)
        ax.set_xlabel("Year")
        ax.set_ylabel("Real GDP per capita (pre-shock = 100)")
        ax.set_xlim(start, end)
    handles = [
        plt.Line2D([], [], color=COLOURS[c], lw=2, label=COUNTRIES[c]) for c in COUNTRIES
    ]
    fig.legend(handles=handles, loc="lower center", ncol=6, fontsize=9)
    fig.suptitle(
        "Downturns and recovery: real GDP per capita around two shocks",
        fontweight="bold",
        fontsize=14,
    )
    fig.tight_layout(rect=(0.01, 0.07, 0.99, 0.93))
    _save(fig, "06_recession_recovery.png")


def main(panel: pd.DataFrame, summary: pd.DataFrame) -> None:
    ensure_dirs()
    plot_levels(panel)
    plot_indexed(panel)
    plot_growth(panel)
    plot_growth_heatmap(panel)
    plot_cagr(summary)
    plot_recovery(panel)


if __name__ == "__main__":
    import pandas as pd

    from config import DATA_PROCESSED

    main(
        pd.read_csv(DATA_PROCESSED / "country_year_panel.csv"),
        pd.read_csv(DATA_PROCESSED / "summary_by_country.csv"),
    )
