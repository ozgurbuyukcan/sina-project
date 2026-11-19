"""Per-line normal-profile training and causal event detection.

No leak labels are provided to this algorithm. Anomalies are NOT leak diagnoses.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

@dataclass
class DetectorConfig:
    baseline_rows: int = 100
    z_watch: float = 3.5
    persistence: int = 2
    recovery: int = 2
    ml_enabled: bool = True
    random_seed: int = 42


def robust_center_scale(x):
    x = np.asarray(x, dtype=float)
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    return med, max(1.4826 * mad, 0.05 * abs(med), 0.05)


def causal_features(group: pd.DataFrame):
    """Features contain only current or previous readings, never future values."""
    flow = group["flow_lpm"].clip(lower=0).ffill().fillna(0).to_numpy(float)
    ps = group["pressure_bar"]
    pvalid = bool(ps.notna().any())
    if pvalid:
        pressure = ps.where(ps > 0).ffill().fillna(0).to_numpy(float)
    else:
        pressure = np.zeros(len(group), dtype=float)
    lf = np.log1p(flow)
    lp = np.log1p(pressure)
    df = np.diff(lf, prepend=lf[0])
    dp = np.diff(lp, prepend=lp[0])
    # Expanding baseline causes long time-dependence; use lagged rolling window instead.
    trailing_f = pd.Series(lf).shift(1).rolling(5, min_periods=1).median().fillna(lf[0]).to_numpy(float)
    if pvalid:
        return np.column_stack([lf, lp, df, dp, lf - trailing_f]), True
    return np.column_stack([lf, df, lf - trailing_f]), False


def _states(watch: np.ndarray, eligible: np.ndarray, persistence: int, recovery: int):
    statuses = []
    consecutive = 0
    quiet = 0
    alert_active = False
    recovering = False
    for i, w in enumerate(watch):
        if not eligible[i]:
            statuses.append("DATA_QUALITY")
            consecutive = 0; quiet = 0; alert_active = False; recovering = False
            continue
        if w:
            consecutive += 1
            quiet = 0
            if consecutive >= persistence or alert_active:
                alert_active = True
                recovering = False
                statuses.append("ALERT")
            else:
                statuses.append("WATCH")
        elif alert_active or recovering:
            quiet += 1
            consecutive = 0
            if quiet >= recovery:
                statuses.append("NORMAL"); recovering = False; alert_active = False
            else:
                recovering = True; statuses.append("RECOVERING")
        else:
            consecutive = 0
            statuses.append("NORMAL")
    return statuses


def score_lines(quality_df: pd.DataFrame, cfg: DetectorConfig):
    if cfg.baseline_rows < 30:
        raise ValueError("At least 30 baseline measurements are required.")
    if cfg.persistence < 1 or cfg.recovery < 1:
        raise ValueError("Persistence and recovery must be >=1.")
    parts = []
    profile = {}
    for line, g in quality_df.groupby("line_id", sort=False):
        df = g.copy().sort_values("timestamp", kind="mergesort").reset_index(drop=True)
        if len(df) <= cfg.baseline_rows:
            raise ValueError(f"Line {line}: {len(df)} rows; need MORE than {cfg.baseline_rows} for training and scoring.")
        feats, has_pressure = causal_features(df)
        valid = df["quality_ok"].to_numpy(dtype=bool)
        base_idx = np.flatnonzero(valid[:cfg.baseline_rows])
        if len(base_idx) < 30:
            raise ValueError(f"Line {line}: only {len(base_idx)} valid readings within baseline; need at least 30.")
        med = np.median(feats[base_idx], axis=0)
        mad = np.median(np.abs(feats[base_idx] - med), axis=0)
        # Robust normalization with nonzero floor for stable instruments.
        scales = np.maximum(1.4826 * mad, np.maximum(0.04 * np.abs(med), 0.025))
        z = (feats - med) / scales
        # The primary magnitude is absolute log-flow residual, not a leak probability.
        flow_z = np.abs(z[:, 0])
        if has_pressure:
            # Pressure contributes as *evidence*; large benign changes are not automatically leaks.
            pressure_z = np.abs(z[:, 1])
        else:
            pressure_z = np.zeros(len(df))
        ml_signal = np.zeros(len(df), float)
        ml_available = bool(cfg.ml_enabled and len(base_idx) >= 50)
        if ml_available:
            fit_n = max(30, int(len(base_idx) * 0.7))
            fit = base_idx[:fit_n]; cal = base_idx[fit_n:]
            model = IsolationForest(n_estimators=100, contamination="auto", random_state=cfg.random_seed, n_jobs=1)
            model.fit(np.clip(z[fit], -20, 20))
            # Raw anomaly evidence (higher is more anomalous). Threshold based on baseline only.
            raw = -model.score_samples(np.clip(z, -20, 20))
            cutoff = float(np.quantile(raw[cal], 0.99)) if len(cal) else float(np.quantile(raw[fit], 0.99))
            cal_spread = max(float(np.std(raw[cal])) if len(cal) else 0.0, 0.025)
            ml_signal = np.maximum(0.0, (raw - cutoff) / cal_spread)
        # User-configured WATCH threshold uses robust flow score OR ML evidence.
        signal = np.maximum(flow_z / cfg.z_watch, ml_signal)
        watch = (signal >= 1.0) & valid
        watch[:cfg.baseline_rows] = False
        eligible = valid.copy()
        # All baseline rows are calibration, not eligible for detection.
        statuses = _states(watch, eligible, cfg.persistence, cfg.recovery)
        statuses[:cfg.baseline_rows] = ["BASELINE"] * cfg.baseline_rows
        df["status"] = statuses
        df["anomaly_evidence"] = signal
        df["flow_robust_z"] = flow_z
        df["pressure_robust_z"] = pressure_z
        df["ml_evidence"] = ml_signal
        df["baseline_assumed_healthy"] = False
        df.loc[:cfg.baseline_rows - 1, "baseline_assumed_healthy"] = True
        profile[str(line)] = {"training_window": cfg.baseline_rows,"training_rows_valid": len(base_idx),"has_pressure": has_pressure,"trained_isolation_forest": ml_available, "labels_used": False, "data_validation": "assumed healthy, NOT verified", "caveat": "Unsupervised anomaly score; no validated causal diagnosis"}
        parts.append(df)
    return pd.concat(parts, ignore_index=True), profile
