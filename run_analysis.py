"""Run the full Nigeria vs Peers pipeline.

Usage:
    python run_analysis.py              # fetch fresh data, rebuild everything
    python run_analysis.py --skip-fetch # reuse data/raw (offline re-run)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from build_panel import main as build  # noqa: E402
from config import DATA_PROCESSED, ensure_dirs  # noqa: E402
from fetch_wdi import main as fetch  # noqa: E402
from report import main as write_report  # noqa: E402
from visualize import main as plot  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Use the raw API files already in data/raw instead of calling the API.",
    )
    args = parser.parse_args()
    ensure_dirs()

    if not args.skip_fetch:
        print("\n[1/4] Pulling World Bank WDI data ...")
        fetch()
    else:
        print("\n[1/4] Skipping API pull; using data/raw ...")

    print("\n[2/4] Building country-year panel and analysis tables ...")
    build()
    panel = pd.read_csv(DATA_PROCESSED / "country_year_panel.csv")
    summary = pd.read_csv(DATA_PROCESSED / "summary_by_country.csv")

    print("\n[3/4] Drawing charts ...")
    plot(panel, summary)

    print("\n[4/4] Writing analytical report ...")
    write_report()
    print("\nDone. Outputs are in data/processed and outputs/.")


if __name__ == "__main__":
    main()
