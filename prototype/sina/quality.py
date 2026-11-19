"""Data quality flags are separate from hydraulic diagnoses."""
import numpy as np
import pandas as pd


def inspect_quality(df: pd.DataFrame, *, gap_factor: float = 4.0) -> pd.DataFrame:
    """Run causal-ish integrity checks; duplicate and missing values never silently disappear.

    NOTE: spike detection uses the NEXT measurement and is QA retrospectively only.
    Its output is NOT included in the causal detection features.
    """
    pieces = []
    for _, group in df.groupby("line_id", sort=False):
        g = group.copy().sort_values("timestamp", kind="mergesort")
        n = len(g)
        flags = [[] for _ in range(n)]
        flow = g["flow_lpm"].to_numpy(dtype=float)
        pressure = g["pressure_bar"].to_numpy(dtype=float)
        has_pressure = bool(np.isfinite(pressure).any())
        tm = g["timestamp"]
        dup = tm.duplicated(keep=False).to_numpy()
        dts = tm.diff().dt.total_seconds().to_numpy()
        valid = dts[np.isfinite(dts) & (dts > 0)]
        interval = float(np.median(valid)) if len(valid) else float("nan")
        for i in range(n):
            if dup[i]: flags[i].append("DUPLICATE_TIMESTAMP")
            if not np.isfinite(flow[i]): flags[i].append("MISSING_FLOW")
            elif flow[i] < 0: flags[i].append("NEGATIVE_FLOW")
            if has_pressure and not np.isfinite(pressure[i]):
                flags[i].append("MISSING_PRESSURE")
            if np.isfinite(pressure[i]) and pressure[i] <= 0:
                flags[i].append("NONPOSITIVE_PRESSURE")
            if i > 0 and np.isfinite(interval) and np.isfinite(dts[i]) and dts[i] > gap_factor * interval:
                flags[i].append("TIME_GAP")
        # Flatlines are QA hints; stable hydraulics can be legitimate.
        for arr, label in [(flow, "FLAT_FLOW"), (pressure, "FLAT_PRESSURE")]:
            start = 0
            for i in range(1, n + 1):
                same = (i < n and np.isfinite(arr[i]) and np.isfinite(arr[i-1]) and abs(arr[i] - arr[i-1]) <= 1e-9)
                if same: continue
                if i - start >= 6 and np.isfinite(arr[start]):
                    for j in range(start, i): flags[j].append(label)
                start = i
        g["quality_flags"] = ["|".join(x) for x in flags]
        g["quality_ok"] = [not any(x in flags[i] for x in ("DUPLICATE_TIMESTAMP", "MISSING_FLOW", "NEGATIVE_FLOW", "MISSING_PRESSURE", "NONPOSITIVE_PRESSURE", "TIME_GAP")) for i in range(n)]
        g["nominal_interval_seconds"] = interval
        pieces.append(g)
    return pd.concat(pieces).sort_index(kind="stable") if pieces else df.copy()
