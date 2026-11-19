"""SINA 0.1 input contract: independent of the previous SINA codebase."""
from dataclasses import dataclass
import hashlib
import io
import pandas as pd

NEEDED = ("timestamp", "flow_lpm")
ALIASES = {
    "timestamp": ("timestamp", "datetime", "date_time", "time", "tarih", "zaman"),
    "flow_lpm": ("flow_lpm", "flow", "flow_rate", "debi", "flowrate"),
    "pressure_bar": ("pressure_bar", "pressure", "basinc", "basınç", "p_bar"),
    "line_id": ("line_id", "line", "zone", "sensor_group", "hat"),
}

@dataclass
class ParsedInput:
    frame: pd.DataFrame
    dataset_id: str
    notices: list[str]


def parse_csv(file_content: bytes) -> ParsedInput:
    """Parse measured CSV, preserving invalid values for explicit QA warnings.

    Units must be L/min and bar; this function never guesses units or leakage labels.
    """
    if len(file_content) > 32 * 1024 * 1024:
        raise ValueError("CSV size limit is 32 MB for the interactive prototype.")
    try:
        df = pd.read_csv(io.BytesIO(file_content), encoding="utf-8-sig")
    except Exception as exc:
        raise ValueError(f"CSV could not be read: {exc}") from exc
    if len(df) == 0:
        raise ValueError("CSV has no measurements.")
    if len(df) > 120_000:
        raise ValueError("Limit: 120,000 rows. Split a larger file before import.")
    lower = {str(c).strip().lower(): c for c in df.columns}
    selected = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in lower:
                selected[canonical] = lower[alias]
                break
    missing = [col for col in NEEDED if col not in selected]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing) + ". Required units: flow_lpm in L/min, pressure_bar in bar.")
    df = df.rename(columns={source: canonical for canonical, source in selected.items()})
    required = list(NEEDED) + [x for x in ("pressure_bar", "line_id") if x in df]
    df = df[required].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["flow_lpm"] = pd.to_numeric(df["flow_lpm"], errors="coerce")
    if "pressure_bar" not in df:
        df["pressure_bar"] = float("nan")
    else:
        df["pressure_bar"] = pd.to_numeric(df["pressure_bar"], errors="coerce")
    if "line_id" not in df:
        df["line_id"] = "LINE-1"
    df["line_id"] = df["line_id"].fillna("UNASSIGNED").astype(str).str.strip().replace("", "UNASSIGNED")
    if df["timestamp"].isna().any():
        raise ValueError(f"{int(df['timestamp'].isna().sum())} timestamps cannot be parsed. Correct those rows before analysis.")
    notices = []
    if not df["pressure_bar"].notna().any():
        notices.append("Pressure missing: analysis uses flow only; pressure diagnosis is unavailable.")
    if len(set(df["line_id"])) > 30:
        raise ValueError("This prototype accepts at most 30 sensor groups/lines per CSV.")
    if df["timestamp"].duplicated().any() and len(df["line_id"].unique()) > 1:
        notices.append("Repeated timestamps across DIFFERENT lines are valid; within-line duplicates are flagged.")
    df = df.sort_values(["line_id", "timestamp"], kind="mergesort").reset_index(drop=True)
    return ParsedInput(df, hashlib.sha256(file_content).hexdigest()[:20], notices)
