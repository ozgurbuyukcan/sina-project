"""Verifiable operator review contexts, candidate training exports and audit trails.

Human-reported labels are NOT independent leak ground truth. No online self-training.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import sqlite3
import zipfile

import pandas as pd

VALID_ORIGINS = {'synthetic_demo','uploaded_unverified','live_gateway_unverified','offline_replay'}
CANDIDATE_DIAGNOSES = {'confirmed_leak','normal_operation','sensor_fault','pump_or_pressure'}


def ensure_feedback_schema(conn: sqlite3.Connection) -> None:
    conn.execute('''CREATE TABLE IF NOT EXISTS event_contexts(
        dataset_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        event_start TEXT NOT NULL,
        line_id TEXT NOT NULL,
        event_kind TEXT NOT NULL,
        source_origin TEXT NOT NULL,
        source_id TEXT NOT NULL,
        input_data_sha256 TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        window_json TEXT NOT NULL,
        window_sha256 TEXT NOT NULL,
        PRIMARY KEY(dataset_id,event_id)
    )''')
    conn.commit()


def context_window(scored: pd.DataFrame, event_row: dict, *, minutes: int = 5) -> list[dict]:
    """Snapshot both directions for RESEARCH REVIEW only; never used in causal model fit."""
    stamp = pd.Timestamp(event_row['start'])
    mask = (scored['line_id'] == str(event_row['line_id'])) & (scored['timestamp'].between(
        stamp - pd.Timedelta(minutes=minutes), stamp + pd.Timedelta(minutes=minutes)))
    nearby = scored.loc[mask].head(2000)
    fields = ('timestamp','line_id','flow_lpm','pressure_bar','quality_flags','status','anomaly_evidence')
    samples=[]
    for row in nearby.to_dict('records'):
        sample={}
        for name in fields:
            value = row.get(name)
            if name == 'timestamp': value = pd.Timestamp(value).isoformat()
            elif isinstance(value,float) and not math.isfinite(value): value=None
            elif hasattr(value,'item'): value=value.item()
            sample[name]=value
        samples.append(sample)
    return samples


def capture_event_context(conn: sqlite3.Connection, dataset_id: str, event: dict, scored: pd.DataFrame,
                          *, source_origin: str, source_id: str, input_data_sha256: str) -> str:
    if source_origin not in VALID_ORIGINS: raise ValueError('Invalid declared source origin')
    ensure_feedback_schema(conn)
    window=context_window(scored,event)
    if not window: raise ValueError('Cannot label an event without its source measurements')
    data=json.dumps(window,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False)
    digest=hashlib.sha256(data.encode()).hexdigest()
    with conn:
        # Immutable first-review snapshot, even if later live samples change.
        conn.execute('''INSERT OR IGNORE INTO event_contexts
            (dataset_id,event_id,event_start,line_id,event_kind,source_origin,source_id,input_data_sha256,recorded_at,window_json,window_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
                str(dataset_id),str(event['event_id']),pd.Timestamp(event['start']).isoformat(),
                str(event['line_id']),str(event['event_kind']),source_origin,str(source_id),str(input_data_sha256),
                datetime.now(timezone.utc).isoformat(),data,digest))
    return digest


def _candidate_rows(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    ensure_feedback_schema(conn)
    conn.row_factory=sqlite3.Row
    rows=conn.execute('''SELECT c.*, r.operator_diagnosis, r.physically_verified, r.evidence,
       r.notes, r.updated_at, r.status AS review_status
       FROM event_contexts c JOIN reviews r ON c.dataset_id=r.dataset_id AND c.event_id=r.event_id
       WHERE r.status='closed' AND r.physically_verified=1
       AND r.operator_diagnosis!='unknown' AND TRIM(r.evidence)!=''
       ORDER BY c.source_id,c.event_start,c.event_id''').fetchall()
    events=[]; samples=[]
    for r in rows:
        item=dict(r)
        # Synthetic and replayed sources must not become 'field measured' training candidates.
        if item['source_origin'] in {'synthetic_demo','offline_replay'} or item['source_id'].lower().startswith(('demo-','test-','synthetic-','replay-')):
            continue
        if item['operator_diagnosis'] not in CANDIDATE_DIAGNOSES: continue
        raw=item['window_json']
        if hashlib.sha256(raw.encode()).hexdigest()!=item['window_sha256']:
            raise ValueError('Review context checksum mismatch: refusing training export')
        payload=json.loads(raw)
        if not payload: continue
        eid=item['event_id']
        events.append({
            'dataset_id':item['dataset_id'],'event_id':eid,'source_id':item['source_id'],
            'line_id':item['line_id'],'event_start':item['event_start'],
            'event_kind':item['event_kind'],
            'candidate_task':('hydraulic_event_review' if item['event_kind']=='HYDRAULIC_ANOMALY' else 'sensor_data_quality_review'),
            'source_origin':item['source_origin'],'reported_cause':item['operator_diagnosis'],
            'label_status':'operator_physically_verified_claim','evidence':item['evidence'],
            'notes':item['notes'],'reviewed_at':item['updated_at'],
            'context_sha256':item['window_sha256'],'input_data_sha256':item['input_data_sha256'],
            'cross_validation_group':f"{item['source_id']}:{item['event_start'][:10]}",
            'sample_count':len(payload),
        })
        start=pd.Timestamp(item['event_start'])
        for sample in payload:
            samples.append({'event_id':eid,'source_id':item['source_id'],
                'relative_seconds_from_event':(pd.Timestamp(sample['timestamp'])-start).total_seconds(),
                'timestamp':sample['timestamp'], 'line_id':sample['line_id'],
                'flow_lpm':sample.get('flow_lpm'),'pressure_bar':sample.get('pressure_bar'),
                'quality_flags':sample.get('quality_flags'),'detector_state':sample.get('status'),
                'anomaly_evidence':sample.get('anomaly_evidence')})
    return events,samples


def candidate_statistics(conn: sqlite3.Connection) -> dict[str, int]:
    events,samples=_candidate_rows(conn)
    return {'verified_event_candidates':len(events),'context_samples':len(samples),
            'reported_leaks':sum(r['reported_cause']=='confirmed_leak' for r in events),
            'reported_nonleaks':sum(r['reported_cause']!='confirmed_leak' for r in events)}


def candidate_export_zip(conn: sqlite3.Connection) -> bytes:
    events,samples=_candidate_rows(conn)
    if not events:
        raise ValueError('No eligible verified operator review contexts. Close and verify measured-source events first.')
    def table_bytes(rows: list[dict]) -> bytes:
        out=io.StringIO()
        w=csv.DictWriter(out,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)
        return out.getvalue().encode('utf-8-sig')
    event_data=table_bytes(events)
    sample_data=table_bytes(samples)
    disclaimer=('NOT GROUND TRUTH: Operator-reported physically checked event labels. '
      'Sensor measurements are user-supplied; source and verification are not independently audited. '
      'Windows contain both past and future context for retrospective event review only. '
      'NO automatic retraining or accuracy claim. Do not split neighboring windows randomly: '
      'hold out entire independent sites/campaigns and disclose small sample sizes.\n')
    manifest={
        'schema':'sina.review_candidates.v1', 'event_count':len(events), 'context_samples':len(samples),
        'event_csv_sha256':hashlib.sha256(event_data).hexdigest(),
        'sample_csv_sha256':hashlib.sha256(sample_data).hexdigest(),
        'verified_means':'operator attests physical check; not independently certified',
        'labels_are_event_level':True,'training_performed':False,
        'source_org':sorted({r['source_origin'] for r in events}),
    }
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('operator_verified_events.csv',event_data)
        z.writestr('event_context_samples.csv',sample_data)
        z.writestr('candidate_manifest.json',json.dumps(manifest,indent=2,ensure_ascii=False))
        z.writestr('READ_ME_FIRST.txt',disclaimer)
    return out.getvalue()
