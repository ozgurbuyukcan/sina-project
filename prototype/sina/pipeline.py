"""Single entrypoint for four-stage pipeline."""
from dataclasses import dataclass
import json
import pandas as pd
from .schema import parse_csv
from .quality import inspect_quality
from .detect import score_lines, DetectorConfig
from .events import events_from_scored

@dataclass
class Analysis:
    dataset_id: str
    scored: pd.DataFrame
    events: pd.DataFrame
    model_profiles: dict
    notices: list[str]
    source_rows: int


def analyze_csv(raw: bytes, cfg: DetectorConfig | None = None) -> Analysis:
    parsed=parse_csv(raw)
    quality=inspect_quality(parsed.frame)
    config=cfg or DetectorConfig()
    scored, profiles=score_lines(quality, config)
    events=events_from_scored(scored, parsed.dataset_id)
    return Analysis(parsed.dataset_id,scored,events,profiles,parsed.notices,len(parsed.frame))


def manifest(result: Analysis, cfg: DetectorConfig) -> bytes:
    return json.dumps({
        "project":"SINA Prototype 1 — Hydraulic Intelligence Platform",
        "dataset_sha256_prefix":result.dataset_id,
        "measurements":result.source_rows,
        "input_units":{"flow_lpm":"L/min","pressure_bar":"bar"},
        "settings":vars(cfg),
        "profiles":result.model_profiles,
        "event_count":len(result.events),
        "claim":"Unsupervised anomaly surveillance only: events are not verified leaks, no measured water savings.",
        "labels_used_in_fit":False,
        "feedback_training":"manual verification stored locally, never used for automatic retraining"
    },indent=2,ensure_ascii=False).encode("utf-8")
