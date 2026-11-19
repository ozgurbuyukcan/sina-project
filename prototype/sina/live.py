"""Local sensor ingestion with explicit provenance, bounded input, no implied diagnosis.

Live sensor gateway is an independent process. It writes SQLite; the UI reads snapshots.
Sources are separated and records are append-only. No remote network exposure by default.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

import pandas as pd

MAX_PACKET_BYTES = 8192
MAX_SOURCE_LENGTH = 64
SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


@dataclass(frozen=True)
class IngestResult:
    outcome: str
    source_id: str
    line_id: str
    timestamp: str
    timestamp_origin: str


def validate_source_id(source_id: str) -> str:
    sid = str(source_id).strip()
    if not SOURCE_PATTERN.fullmatch(sid):
        raise ValueError('source_id must contain 1–64 letters, digits, _, -, or .')
    return sid


def live_connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            line_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            flow_lpm REAL NOT NULL,
            pressure_bar REAL,
            timestamp_origin TEXT NOT NULL,
            received_at TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            UNIQUE(source_id, line_id, timestamp)
        );
        CREATE INDEX IF NOT EXISTS ix_measurements_source_ts ON measurements(source_id,timestamp);
        CREATE TABLE IF NOT EXISTS source_registry (
            source_id TEXT PRIMARY KEY,
            ingest_mode TEXT NOT NULL CHECK (ingest_mode IN ('SERIAL','HTTP','OFFLINE_REPLAY')),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ingestion_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            received_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            payload_sample TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gateway_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            happened_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_gateway_events_source ON gateway_events(source_id,id);
    ''')
    conn.commit()
    return conn


def register_source(conn: sqlite3.Connection, source_id: str, mode: str) -> None:
    sid = validate_source_id(source_id)
    if mode not in {'SERIAL','HTTP','OFFLINE_REPLAY'}:
        raise ValueError('Invalid source mode')
    with conn:
        existing = conn.execute('SELECT ingest_mode FROM source_registry WHERE source_id=?', (sid,)).fetchone()
        if existing and existing['ingest_mode'] != mode:
            raise ValueError(f'Source {sid} already registered as {existing["ingest_mode"]}; use a separate ID for {mode}')
        conn.execute('INSERT OR IGNORE INTO source_registry(source_id,ingest_mode,created_at) VALUES(?,?,?)',
                     (sid,mode,datetime.now(timezone.utc).isoformat()))


def _real_number(value: Any, name: str, *, nullable: bool = False) -> float | None:
    if nullable and (value is None or value == ''):
        return None
    if isinstance(value, bool):
        raise ValueError(f'{name} cannot be a boolean')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be numeric') from exc
    if not math.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def normalize_packet(payload: dict[str, Any], *, received_at: datetime | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError('Expected an object with sensor measurements')
    received_at = received_at or datetime.now(timezone.utc)
    line_id = str(payload.get('line_id', 'LINE-1')).strip()
    if not SOURCE_PATTERN.fullmatch(line_id):
        raise ValueError('line_id must contain 1–64 letters, digits, _, -, or .')
    flow = _real_number(payload.get('flow_lpm'), 'flow_lpm')
    pressure = _real_number(payload.get('pressure_bar'), 'pressure_bar', nullable=True)
    # Conservative broad hardware plausibility checks, not an installation-specific diagnosis.
    if flow < 0 or flow > 1_000_000:
        raise ValueError('flow_lpm outside accepted ingest bounds [0, 1000000]')
    if pressure is not None and (pressure < 0 or pressure > 1000):
        raise ValueError('pressure_bar outside accepted ingest bounds [0, 1000]')
    stamp = payload.get('timestamp')
    origin = 'device_supplied'
    if stamp is None or stamp == '':
        tm = received_at.astimezone(timezone.utc)
        origin = 'gateway_assigned'
    else:
        try:
            tm = pd.Timestamp(stamp)
        except Exception as exc:
            raise ValueError('Invalid timestamp') from exc
        if pd.isna(tm) or tm.tzinfo is None:
            raise ValueError('Device timestamp must include UTC Z or an explicit time-zone offset')
        tm = tm.tz_convert('UTC').to_pydatetime()
    return {
        'line_id': line_id,
        'flow_lpm': flow,
        'pressure_bar': pressure,
        'timestamp': tm.isoformat(timespec='microseconds'),
        'timestamp_origin': origin,
        'received_at': received_at.astimezone(timezone.utc).isoformat(timespec='microseconds'),
    }


def parse_sensor_line(text: str) -> dict[str, Any]:
    """Accept JSONL or a CSV record: timestamp,line_id,flow_lpm,pressure_bar.

    For Arduino Uno without a clock: `,LINE-1,7.25,0.32` uses gateway time.
    """
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_PACKET_BYTES:
        raise ValueError('Sensor packet exceeds 8192 bytes')
    text = text.strip()
    if not text:
        raise ValueError('Empty sensor record')
    if text.startswith('{'):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError('Invalid JSON record') from exc
        if not isinstance(obj, dict):
            raise ValueError('JSON record must be an object')
        return obj
    parts = next(csv.reader([text]))
    if len(parts) not in (3, 4):
        raise ValueError('CSV sensor record requires timestamp,line_id,flow_lpm[,pressure_bar]')
    return {'timestamp': parts[0].strip(), 'line_id': parts[1].strip(), 'flow_lpm': parts[2].strip(),
            'pressure_bar': parts[3].strip() if len(parts) == 4 else None}


def ingest_packet(conn: sqlite3.Connection, payload: dict[str, Any], source_id: str) -> IngestResult:
    sid = validate_source_id(source_id)
    normalized = normalize_packet(payload)
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    normalized['payload_sha256'] = payload_hash
    with conn:
        previous = conn.execute('''SELECT flow_lpm,pressure_bar FROM measurements
            WHERE source_id=? AND line_id=? AND timestamp=?''',
            (sid, normalized['line_id'], normalized['timestamp'])).fetchone()
        if previous is not None:
            old_p = previous['pressure_bar']
            new_p = normalized['pressure_bar']
            if previous['flow_lpm'] == normalized['flow_lpm'] and (old_p == new_p or (old_p is None and new_p is None)):
                return IngestResult('duplicate_ignored', sid, normalized['line_id'], normalized['timestamp'], normalized['timestamp_origin'])
            raise ValueError('Conflicting measurement at the same source, line and timestamp; original was preserved')
        conn.execute('''INSERT INTO measurements(source_id,line_id,timestamp,flow_lpm,pressure_bar,timestamp_origin,received_at,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?)''', (sid, normalized['line_id'], normalized['timestamp'], normalized['flow_lpm'],
            normalized['pressure_bar'], normalized['timestamp_origin'], normalized['received_at'], payload_hash))
    return IngestResult('inserted', sid, normalized['line_id'], normalized['timestamp'], normalized['timestamp_origin'])


def log_ingestion_error(conn: sqlite3.Connection, source_id: str, reason: str, raw: str) -> None:
    sid = validate_source_id(source_id)
    with conn:
        conn.execute('INSERT INTO ingestion_errors(source_id,received_at,reason,payload_sample) VALUES(?,?,?,?)',
                     (sid, datetime.now(timezone.utc).isoformat(), str(reason)[:500], str(raw)[:1000]))


def list_sources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(x) for x in conn.execute('''SELECT m.source_id, COUNT(*) AS n_readings,
        COUNT(DISTINCT m.line_id) AS n_lines, MAX(m.timestamp) AS latest_timestamp,
        MAX(m.received_at) AS latest_received_at, COALESCE(r.ingest_mode,'UNREGISTERED') AS ingest_mode
        FROM measurements m LEFT JOIN source_registry r ON m.source_id=r.source_id
        GROUP BY m.source_id ORDER BY m.source_id''')]


def source_quality_counts(conn: sqlite3.Connection, source_id: str) -> dict[str, int]:
    validate_source_id(source_id)
    row = conn.execute('SELECT COUNT(*) FROM ingestion_errors WHERE source_id=?', (source_id,)).fetchone()
    assigned = conn.execute('SELECT COUNT(*) FROM measurements WHERE source_id=? AND timestamp_origin=?',
        (source_id, 'gateway_assigned')).fetchone()
    return {'rejected_packets': int(row[0]), 'gateway_timestamped': int(assigned[0])}


def live_frame(conn: sqlite3.Connection, source_id: str, *, row_limit: int = 120_000) -> pd.DataFrame:
    validate_source_id(source_id)
    count = conn.execute('SELECT COUNT(*) FROM measurements WHERE source_id=?',(source_id,)).fetchone()[0]
    if count > row_limit:
        raise ValueError(f'Live source contains {count:,} rows; export/archive a segment first (limit {row_limit:,}).')
    return pd.read_sql_query('''SELECT timestamp,flow_lpm,pressure_bar,line_id FROM measurements
        WHERE source_id=? ORDER BY line_id,timestamp''',conn,params=(source_id,))


def live_csv(conn: sqlite3.Connection, source_id: str) -> bytes:
    df = live_frame(conn, source_id)
    if df.empty:
        raise ValueError('No measurements yet for this source')
    return df.to_csv(index=False).encode('utf-8')


def stable_live_event_ids(analysis, source_id: str) -> None:
    """Event identity must not change as new rows arrive or WATCH becomes ALERT."""
    sid = validate_source_id(source_id)
    for i, row in analysis.events.iterrows():
        basis = f"live:{sid}:{row['line_id']}:{row['event_kind']}:{pd.Timestamp(row['start']).isoformat()}"
        analysis.events.at[i, 'event_id'] = hashlib.sha256(basis.encode()).hexdigest()[:14].upper()
    analysis.dataset_id = f'live-{sid}'


def log_gateway_event(conn: sqlite3.Connection, source_id: str, event_type: str, detail: str = '') -> None:
    """Record connection lifecycle separately from malformed sensor packets."""
    sid = validate_source_id(source_id)
    if event_type not in {'CONNECTED','DISCONNECTED','RETRYING','STARTED','STOPPED'}:
        raise ValueError('Unrecognized gateway event')
    with conn:
        conn.execute('INSERT INTO gateway_events(source_id,happened_at,event_type,detail) VALUES(?,?,?,?)',
                     (sid, datetime.now(timezone.utc).isoformat(), event_type, str(detail)[:500]))


def source_connection_health(conn: sqlite3.Connection, source_id: str, *,
                             now: datetime | None = None, stale_seconds: float = 120) -> dict:
    """Observational indicator; a fresh packet does not certify sensor calibration.

    Primarily uses received_at rather than device timestamps (which can be skewed).
    """
    sid = validate_source_id(source_id)
    if stale_seconds <= 0:
        raise ValueError('stale_seconds must be positive')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must carry a time zone')
    last = conn.execute('SELECT MAX(received_at) FROM measurements WHERE source_id=?', (sid,)).fetchone()[0]
    mode = conn.execute('SELECT ingest_mode FROM source_registry WHERE source_id=?',(sid,)).fetchone()
    event = conn.execute('SELECT event_type,detail,happened_at FROM gateway_events WHERE source_id=? ORDER BY id DESC LIMIT 1',(sid,)).fetchone()
    age = None
    if last is not None:
        age = max(0, (now.astimezone(timezone.utc)-datetime.fromisoformat(last)).total_seconds())
    status = ('OFFLINE_REPLAY' if mode is not None and mode['ingest_mode']=='OFFLINE_REPLAY'
              else 'DISCONNECTED' if event is not None and event['event_type'] in ('DISCONNECTED','STOPPED')
              else 'RECONNECTING' if event is not None and event['event_type']=='RETRYING'
              else 'NO_RECORDS' if last is None
              else 'STALE' if age > stale_seconds
              else 'RECEIVING')
    return {'status':status, 'last_received_at':last,'age_seconds':age,
            'last_event_type':event['event_type'] if event is not None else None,
            'last_event_detail':event['detail'] if event is not None else None}
