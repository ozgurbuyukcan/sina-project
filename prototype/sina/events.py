"""Create traceable review episodes. Triage ranking is heuristic, not a diagnosis."""
from hashlib import sha256
import pandas as pd

ACTIVE = {"WATCH", "ALERT", "RECOVERING"}

def events_from_scored(scored: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    records = []
    for line, group in scored.groupby("line_id", sort=False):
        g = group.sort_values("timestamp").reset_index(drop=True)
        active_rows = []
        def finish(rows):
            if not rows: return
            first, last = rows[0], rows[-1]
            start = g.at[first, "timestamp"]
            end = g.at[last, "timestamp"]
            st = g.loc[rows, "status"]
            alarm = bool((st == "ALERT").any())
            tag = "ALERT" if alarm else "WATCH_ONLY"
            key = f"{dataset_id}:{line}:{start.isoformat()}:{tag}"
            interval = g.at[first,"nominal_interval_seconds"]
            secs = (end - start).total_seconds() + (float(interval) if pd.notna(interval) else 0)
            records.append({
                "event_id": sha256(key.encode()).hexdigest()[:14].upper(),
                "line_id": str(line),"event_kind": "HYDRAULIC_ANOMALY",
                "start": start,"end": end,"duration_seconds": round(max(secs,0),1),
                "status": tag,"priority": "INSPECT" if alarm else "REVIEW",
                "peak_evidence": round(float(g.loc[rows,"anomaly_evidence"].max()), 3),
                "flow_at_start_lpm": round(float(g.at[first,"flow_lpm"]),3),
                "pressure_at_start_bar": round(float(g.at[first,"pressure_bar"]),4) if pd.notna(g.at[first,"pressure_bar"]) else None,
                "n_readings": len(rows),
                "explanation": ("Two or more consecutive anomaly readings triggered an alert; the underlying cause is unverified."
                                if alarm else "Anomaly evidence did not persist long enough for an alert; cause unverified."),
            })
        for i, state in enumerate(g["status"]):
            if state in ACTIVE:
                active_rows.append(i)
            else:
                finish(active_rows); active_rows = []
        finish(active_rows)
        # DATA_QUALITY issues remain distinct from hydrological anomaly events.
        for i, flags in enumerate(g["quality_flags"]):
            if not flags or g.at[i,"status"] == "BASELINE": continue
            if len(records) > 5000:
                raise ValueError("Too many events for the interactive prototype.")
            tm = g.at[i,"timestamp"]
            key=f"{dataset_id}:{line}:{tm.isoformat()}:QUALITY:{flags}"
            records.append({
                "event_id":sha256(key.encode()).hexdigest()[:14].upper(),
                "line_id":str(line), "event_kind":"DATA_QUALITY", "start":tm,"end":tm,
                "duration_seconds":0.0,"status":"CHECK_DATA", "priority":"VERIFY_SENSOR",
                "peak_evidence":None,
                "flow_at_start_lpm":float(g.at[i,"flow_lpm"]) if pd.notna(g.at[i,"flow_lpm"]) else None,
                "pressure_at_start_bar":float(g.at[i,"pressure_bar"]) if pd.notna(g.at[i,"pressure_bar"]) else None,
                "n_readings":1,"explanation":f"Data quality flags: {flags}. Not a diagnosed hydraulic fault."})
    schema = ["event_id","line_id","event_kind","start","end","duration_seconds","status","priority","peak_evidence","flow_at_start_lpm","pressure_at_start_bar","n_readings","explanation"]
    return pd.DataFrame.from_records(records, columns=schema).sort_values("start",kind="stable").reset_index(drop=True) if records else pd.DataFrame(columns=schema)
