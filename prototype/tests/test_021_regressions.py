"""Fresh 0.2.1 regression tests: date alignment, lifecycle, recovery, persistence and E2E.

All sensor data here are SYNTHETIC test fixtures, never physical validation.
"""
import io
import json
import hashlib
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from live_gateway import collect_serial
from sina.detect import DetectorConfig
from sina.feedback import candidate_export_zip, candidate_statistics, capture_event_context
from sina.live import (ingest_packet, live_connect, list_sources, log_gateway_event,
                       source_connection_health, source_quality_counts, live_csv,
                       stable_live_event_ids)
from sina.pipeline import analyze_csv
from sina.plots import event_plot, utc_time
from sina.store import connect, save_review, get_review, export_reviews_csv

ROOT = Path(__file__).resolve().parents[1]
DEMO = (ROOT / 'sample_data' / 'synthetic_demo.csv').read_bytes()


def test_plot_event_marker_uses_utc_iso_not_epoch_number():
    analysis = analyze_csv(DEMO)
    event = analysis.events.iloc[0].to_dict()
    t = utc_time(event['start'])
    fig = event_plot(analysis.scored.loc[analysis.scored.line_id == event['line_id']], t)
    data = fig.to_plotly_json()
    shape = data['layout']['shapes'][0]
    assert isinstance(shape['x0'], str) and shape['x0'] == t.isoformat()
    assert shape['x0'] == shape['x1']
    assert shape['xref'] == 'x' and shape['yref'] == 'paper'
    axis = data['layout']['xaxis']
    assert axis['type'] == 'date'
    assert axis['range'][0] == (t - pd.Timedelta(minutes=5)).isoformat()
    assert axis['range'][1] == (t + pd.Timedelta(minutes=5)).isoformat()
    assert all(abs((utc_time(x) - t).total_seconds()) <= 300
               for x in fig.data[0].x)


def test_plot_timezone_conversion_is_absolute_instant():
    utc = utc_time('2026-11-18T09:00:00Z')
    local = utc_time('2026-11-18T12:00:00+03:00')
    assert local == utc
    df = pd.DataFrame({'timestamp': ['2026-11-18T12:00:00+03:00'],
                       'flow_lpm': [10.0], 'status': ['WATCH']})
    f = event_plot(df, local)
    assert f.layout.shapes[0].x0 == utc.isoformat()
    assert f.layout.xaxis.range[0] == '2026-11-18T08:55:00+00:00'


def test_review_sqlite_survives_reopen_preserves_history(tmp_path):
    results = analyze_csv(DEMO)
    event = results.events.iloc[0].to_dict()
    db = tmp_path/'persist.sqlite3'
    db_id, eid = results.dataset_id, event['event_id']
    conn = connect(db)
    capture_event_context(conn, db_id, event, results.scored, source_origin='synthetic_demo',
                          source_id='demo-synthetic', input_data_sha256=hashlib.sha256(DEMO).hexdigest())
    save_review(conn, db_id, eid, 'investigating', 'unknown', notes='first review')
    conn.close()
    conn = connect(db)
    assert get_review(conn, db_id, eid)['notes'] == 'first review'
    save_review(conn, db_id, eid, 'closed', 'sensor_fault', notes='inspection note',
                physically_verified=True, evidence='synthetic demonstration only')
    conn.close()
    conn = connect(db)
    rev = get_review(conn, db_id, eid)
    assert rev['status'] == 'closed' and rev['physically_verified'] == 1
    assert rev['evidence'] == 'synthetic demonstration only'
    assert conn.execute('SELECT COUNT(*) FROM review_audit').fetchone()[0] == 2
    assert conn.execute('SELECT COUNT(*) FROM event_contexts').fetchone()[0] == 1
    assert len(export_reviews_csv(conn, db_id)) > 40
    assert candidate_statistics(conn)['verified_event_candidates'] == 0
    with pytest.raises(ValueError, match='No eligible'):
        candidate_export_zip(conn)
    conn.close()


def test_end_to_end_5_stages_with_provenance_and_review(tmp_path):
    """SYNTHETIC fixture verifies the software path, not actual leak accuracy."""
    # SCAN + IDENTIFY + NAVIGATE: deterministic analysis of a user-upload-like file.
    result = analyze_csv(DEMO, DetectorConfig(baseline_rows=100))
    assert {'line_id', 'quality_flags', 'anomaly_evidence','status'}.issubset(result.scored.columns)
    assert len(result.events) > 0
    event = result.events.iloc[0].to_dict()
    # ASSESS: persist immutable window, audit and explicit manual report.
    db = tmp_path/'review.db'
    conn = connect(db)
    digest = capture_event_context(conn, result.dataset_id,event,result.scored,
        source_origin='uploaded_unverified', source_id='uploaded-software-fixture',
        input_data_sha256=hashlib.sha256(DEMO).hexdigest())
    save_review(conn,result.dataset_id,event['event_id'],'investigating','unknown')
    assert candidate_statistics(conn)['verified_event_candidates'] == 0
    save_review(conn,result.dataset_id,event['event_id'],'closed','normal_operation',
                physically_verified=True,evidence='SYNTHETIC FIXTURE TEST ONLY')
    conn.close()
    # LEARNING DATA: only an operator-asserted CANDIDATE, not trusted ground truth.
    conn = connect(db)
    assert candidate_statistics(conn)['verified_event_candidates'] == 1
    with zipfile.ZipFile(io.BytesIO(candidate_export_zip(conn))) as z:
        assert z.testzip() is None
        label = pd.read_csv(z.open('operator_verified_events.csv')).iloc[0]
        assert label['context_sha256']==digest
        assert label['label_status']=='operator_physically_verified_claim'
        assert json.loads(z.read('candidate_manifest.json'))['training_performed'] is False
    conn.close()


def test_live_source_fresh_stale_and_disconnect_status(tmp_path):
    conn = live_connect(tmp_path/'live.sqlite3')
    from sina.live import register_source
    register_source(conn,'sensor-01','SERIAL')
    t = datetime.now(timezone.utc)
    assert source_connection_health(conn, 'sensor-01', now=t)['status'] == 'NO_RECORDS'
    ingest_packet(conn, {'timestamp':'2026-11-18T07:00:00Z','line_id':'L1','flow_lpm':12}, 'sensor-01')
    assert source_connection_health(conn, 'sensor-01', now=t)['status']=='RECEIVING'
    assert source_connection_health(conn, 'sensor-01', now=t+timedelta(minutes=5))['status']=='STALE'
    log_gateway_event(conn,'sensor-01','DISCONNECTED','USB unplugged')
    assert source_connection_health(conn,'sensor-01',now=t)['status']=='DISCONNECTED'
    log_gateway_event(conn,'sensor-01','RETRYING','retrying')
    assert source_connection_health(conn,'sensor-01',now=t)['status']=='RECONNECTING'
    log_gateway_event(conn,'sensor-01','CONNECTED','COM3 reappeared')
    assert source_connection_health(conn,'sensor-01',now=t)['status']=='RECEIVING'
    conn.close()


def test_serial_disconnect_reconnect_and_bad_packet(tmp_path):
    """Injected fake transport; does NOT validate physical Arduino or serial drivers."""
    db=tmp_path/'serial.sqlite3'
    class FakeTransport:
        attempts=0
        read_calls=0
        def __init__(self,port,baudrate,timeout):
            type(self).attempts+=1
            if type(self).attempts==1: raise OSError('COM port missing')
            self.reads = [
                b'{"timestamp":"2026-11-18T12:00:00Z","line_id":"A","flow_lpm":5}\n',
                b'garbage-data\n',
                b'{"timestamp":"2026-11-18T12:00:30Z","line_id":"A","flow_lpm":6}\n',
            ]
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def readline(self,*args):
            type(self).read_calls+=1
            if self.reads:return self.reads.pop(0)
            raise OSError('unplugged after test')
    collect_serial(db,'field-01','FAKE-COM',115200,serial_factory=FakeTransport,
                   connection_error=OSError,should_stop=lambda:FakeTransport.read_calls>=3,
                   sleep_fn=lambda secs:None,retry_seconds=0)
    c=live_connect(db)
    assert FakeTransport.attempts==2
    assert list_sources(c)[0]['n_readings']==2
    assert source_quality_counts(c,'field-01')['rejected_packets']==1
    logs=[r[0] for r in c.execute('SELECT event_type FROM gateway_events ORDER BY id')]
    assert 'DISCONNECTED' in logs and 'RETRYING' in logs and 'CONNECTED' in logs
    c.close()


def test_replayed_source_cannot_qualify_as_measured(tmp_path):
    result=analyze_csv(DEMO)
    ev=result.events.iloc[0].to_dict()
    db=connect(tmp_path/'review.sqlite3')
    capture_event_context(db,'replay-demo',ev,result.scored,source_origin='offline_replay',
                          source_id='replay-sample',input_data_sha256='fixture-only')
    save_review(db,'replay-demo',ev['event_id'],'closed','confirmed_leak',
                physically_verified=True,evidence='assertion does not create physical truth')
    assert candidate_statistics(db)['verified_event_candidates']==0
    db.close()


def test_live_gateway_to_analysis_to_feedback_retains_identity(tmp_path):
    """Synthetic serial-shaped stream; verifies the LIVE source pipeline, not real hardware."""
    db=tmp_path/'sensor.db'
    conn=live_connect(db)
    from sina.live import register_source
    register_source(conn,'demo-software-hardware-path','SERIAL')
    base=pd.Timestamp('2026-11-18T12:00:00Z')
    for n in range(170):
        # Synthetic step ensures two or more anomalous readings after the baseline.
        flow=35.0 if 135 <= n < 142 else 10.0 + 0.10*((n%5)-2)
        packet={'timestamp':(base+pd.Timedelta(seconds=30*n)).isoformat(),
                'line_id':'line-a', 'flow_lpm':flow, 'pressure_bar':0.36}
        assert ingest_packet(conn,packet,'demo-software-hardware-path').outcome == 'inserted'
    csv_bytes=live_csv(conn,'demo-software-hardware-path')
    conn.close()
    result=analyze_csv(csv_bytes,DetectorConfig(baseline_rows=100,ml_enabled=False))
    stable_live_event_ids(result,'demo-software-hardware-path')
    assert result.dataset_id=='live-demo-software-hardware-path'
    assert (result.events.event_kind=='HYDRAULIC_ANOMALY').any()
    event=result.events.query('event_kind=="HYDRAULIC_ANOMALY"').iloc[0].to_dict()
    fid=event['event_id']
    store_path=tmp_path/'feedback.db'
    c=connect(store_path)
    capture_event_context(c,result.dataset_id,event,result.scored,source_origin='live_gateway_unverified',
                          source_id='demo-software-hardware-path',input_data_sha256=hashlib.sha256(csv_bytes).hexdigest())
    save_review(c,result.dataset_id,fid,'closed','unknown',notes='SYNTHETIC integration fixture; not inspected')
    c.close()
    c=connect(store_path)
    assert get_review(c,result.dataset_id,fid)['status']=='closed'
    assert candidate_statistics(c)['verified_event_candidates']==0
    c.close()


def test_non_destructive_migration_preserves_reviews_and_live_records(tmp_path):
    from migrate_from_02 import migrate
    old=tmp_path/'SINA_FRESH_0_2'; new=tmp_path/'SINA_FRESH_0_2_1'
    old_db=old/'user_data'/'operator_feedback.sqlite3'
    c=connect(old_db)
    save_review(c,'d1','e1','closed','normal_operation',notes='original operator note',
                physically_verified=True,evidence='review document on file')
    c.close()
    old_sensor=old/'user_data'/'live_measurements.sqlite3'
    c=live_connect(old_sensor)
    from sina.live import register_source
    register_source(c,'field-02','SERIAL')
    ingest_packet(c,{'timestamp':'2026-11-18T12:00:00Z','flow_lpm':8.5},'field-02')
    c.close()
    migrated=migrate(old,new)
    assert set(migrated.values())=={'copied_and_integrity_checked'}
    c=connect(new/'user_data'/'operator_feedback.sqlite3')
    assert get_review(c,'d1','e1')['notes']=='original operator note'
    c.close()
    c=live_connect(new/'user_data'/'live_measurements.sqlite3')
    assert list_sources(c)[0]['n_readings']==1
    c.close()
    # Both originals remain intact and reopen normally.
    c=connect(old_db)
    assert get_review(c,'d1','e1')['status']=='closed'
    c.close()
    with pytest.raises(FileExistsError,match='refuses overwrite'):
        migrate(old,new)


def test_migration_never_operates_on_same_folder(tmp_path):
    from migrate_from_02 import migrate
    with pytest.raises(ValueError,match='different'):
        migrate(tmp_path,tmp_path)
