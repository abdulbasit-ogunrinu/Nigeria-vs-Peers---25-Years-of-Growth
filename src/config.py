"""Central configuration: countries, indicators, paths and event windows."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"

COUNTRIES = {
    "NGA": "Nigeria",
    "GHA": "Ghana",
    "KEN": "Kenya",
    "ZAF": "South Africa",
    "IND": "India",
    "VNM": "Vietnam",
}

FOCUS = "NGA"
PEERS = [code for code in COUNTRIES if code != FOCUS]

INDICATORS = {
    "NY.GDP.PCAP.KD": "gdp_pc",      # real GDP per capita, constant USD
    "NY.GDP.MKTP.KD.ZG": "gdp_growth",  # real GDP growth, annual %
}

START_YEAR = 2000
END_YEAR = 2025
BASE_YEAR = 2000
API_BASE = "https://api.worldbank.org/v2"

# Plot colours: Nigeria is emphasised, peers use a colour-blind friendly palette.
COLOURS = {
    "NGA": "#B2182B",   # deep red -- focus country
    "GHA": "#1B7837",
    "KEN": "#2166AC",
    "ZAF": "#762A83",
    "IND": "#E08214",
    "VNM": "#4D4D4D",
}

# Event windows used for shading and interpretation.
EVENTS = [
    {
        "key": "boom",
        "name": "Oil-led boom / pre-recession expansion",
        "start": 2000,
        "end": 2014,
        "anchor": 2005,
        "colour": "#99C98A",
        "alpha": 0.22,
        "note": "High oil prices and robust domestic demand lift real GDP per capita.",
    },
    {
        "key": "recession",
        "name": "2016 recession",
        "start": 2015,
        "end": 2017,
        "anchor": 2016,
        "colour": "#E41A1C",
        "alpha": 0.18,
        "note": "Oil price collapse, FX shortage and output contraction; real GDP falls in 2016.",
    },
    {
        "key": "covid",
        "name": "COVID-19 dip and rebound",
        "start": 2020,
        "end": 2021,
        "anchor": 2020,
        "colour": "#377EB8",
        "alpha": 0.18,
        "note": "2020 contraction; the 2021 rebound is flattered by the low 2020 base.",
    },
]

SHORT_NAMES = {
    "boom": "Nigeria's boom (2000-2014)",
    "recession": "2016 recession",
    "covid": "COVID-19 dip (2020-21)",
}


def ensure_dirs() -> None:
    """Create all output directories."""
    for path in (DATA_RAW, DATA_PROCESSED, OUTPUTS, FIGURES):
        path.mkdir(parents=True, exist_ok=True)
