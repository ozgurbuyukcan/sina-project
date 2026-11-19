"""v0.2 integration checks: persistence, auth boundary, provenance and audit eligibility."""
import io
import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import pytest

from sina.live import (live_connect,register_source,parse_sensor_line,ingest_packet,log_ingestion_error,
                       list_sources,source_quality_counts,live_csv,stable_live_event_ids)
from sina.pipeline import analyze_csv
from sina.detect import DetectorConfig
from sina.feedback import (capture_event_context,candidate_export_zip,candidate_statistics)
from sina.store import connect,save_review

ROOT=Path(__file__).resolve().parents[1]
DEMO=(ROOT/'sample_data'/'synthetic_demo.csv').read_bytes()


def test_live_insert_read_and_qa(tmp_path):
    db=live_connect(tmp_path/'live.db')
    register_source(db,'field-A','SERIAL')
    assert ingest_packet(db,{'timestamp':'2026-11-18T09:00:00Z','line_id':'L1','flow_lpm':12.5,'pressure_bar':0.41},'field-A').outcome=='inserted'
    assert ingest_packet(db,{'timestamp':'2026-11-18T12:00:00+03:00','line_id':'L1','flow_lpm':12.5,'pressure_bar':0.41},'field-A').outcome=='duplicate_ignored'
    with pytest.raises(ValueError,match='Conflicting'):
        ingest_packet(db,{'timestamp':'2026-11-18T09:00:00Z','line_id':'L1','flow_lpm':30},'field-A')
    assert len(pd.read_csv(io.BytesIO(live_csv(db,'field-A'))))==1
    assert list_sources(db)[0]['ingest_mode']=='SERIAL'
    assert source_quality_counts(db,'field-A')['rejected_packets']==0
    log_ingestion_error(db,'field-A','bad timestamp','garbage')
    assert source_quality_counts(db,'field-A')['rejected_packets']==1
    db.close()


def test_live_sources_cannot_mix_replay_and_serial(tmp_path):
    db=live_connect(tmp_path/'live.db')
    register_source(db,'field-01','OFFLINE_REPLAY')
    with pytest.raises(ValueError,match='already registered'):
        register_source(db,'field-01','SERIAL')
    db.close()


def test_record_parsing_and_gateway_timestamp():
    p=parse_sensor_line(',LINE-1,9.2,0.33')
    n=__import__('sina.live',fromlist=['normalize_packet']).normalize_packet(p,received_at=datetime(2026,11,18,tzinfo=timezone.utc))
    assert n['timestamp_origin']=='gateway_assigned'
    assert n['timestamp'].startswith('2026-11-18')
    assert parse_sensor_line('{"line_id":"L1","flow_lpm":4}')['flow_lpm']==4
    with pytest.raises(ValueError,match='time-zone'):
        __import__('sina.live',fromlist=['normalize_packet']).normalize_packet({'timestamp':'2026-11-18 10:00','flow_lpm':9})
    with pytest.raises(ValueError,match='finite'):
        __import__('sina.live',fromlist=['normalize_packet']).normalize_packet({'flow_lpm':'NaN'})
    with pytest.raises(ValueError,match='bounds'):
        __import__('sina.live',fromlist=['normalize_packet']).normalize_packet({'flow_lpm':-4})
    with pytest.raises(ValueError,match='8192'):
        parse_sensor_line('x'*9000)


def test_stable_live_event_identity_across_append():
    base=pd.read_csv(io.BytesIO(DEMO))
    a=base[base.line_id=='LINE-A'].copy()
    a1=io.BytesIO();a.to_csv(a1,index=False)
    r1=analyze_csv(a1.getvalue())
    tail=a.copy().iloc[-1:].copy()
    tail['timestamp']='2026-11-19T00:00:00Z'
    full=pd.concat([a,tail],ignore_index=True)
    a2=io.BytesIO();full.to_csv(a2,index=False)
    r2=analyze_csv(a2.getvalue())
    stable_live_event_ids(r1,'test-LINE')
    stable_live_event_ids(r2,'test-LINE')
    assert r1.dataset_id==r2.dataset_id=='live-test-LINE'
    left=r1.events.set_index(['line_id','event_kind','start'])['event_id']
    right=r2.events.set_index(['line_id','event_kind','start'])['event_id']
    common=left.index.intersection(right.index)
    assert len(common)>0
    assert left.loc[common].to_list()==right.loc[common].to_list()


def _choose_event(result):
    return result.events.iloc[0].to_dict()


def test_reviews_are_not_training_data_without_physical_evidence(tmp_path):
    result=analyze_csv(DEMO)
    ev=_choose_event(result)
    c=connect(tmp_path/'feedback.sqlite3')
    capture_event_context(c,result.dataset_id,ev,result.scored,source_origin='synthetic_demo',
        source_id='demo-01',input_data_sha256=hashlib.sha256(DEMO).hexdigest())
    save_review(c,result.dataset_id,ev['event_id'],'closed','confirmed_leak',physically_verified=True,evidence='Demo demonstration only')
    assert candidate_statistics(c)['verified_event_candidates']==0
    with pytest.raises(ValueError,match='No eligible'):
        candidate_export_zip(c)
    c.close()


def test_verified_measured_event_export_and_checksum(tmp_path):
    result=analyze_csv(DEMO)
    ev=_choose_event(result)
    c=connect(tmp_path/'feedback.sqlite3')
    capture_event_context(c,result.dataset_id,ev,result.scored,source_origin='uploaded_unverified',
        source_id='uploaded-reference',input_data_sha256=hashlib.sha256(DEMO).hexdigest())
    # Research test artificially treats a demo CSV as if uploaded data. This proves filtering logic,
    # NOT that the demo has become a real physical measurement.
    save_review(c,result.dataset_id,ev['event_id'],'investigating','confirmed_leak',
                physically_verified=True,evidence='inspection form entered')
    assert candidate_statistics(c)['verified_event_candidates']==0
    save_review(c,result.dataset_id,ev['event_id'],'closed','confirmed_leak',
                physically_verified=True,evidence='inspection form entered')
    assert candidate_statistics(c)['verified_event_candidates']==1
    archive=candidate_export_zip(c)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert z.testzip() is None
        m=json.loads(z.read('candidate_manifest.json'))
        assert m['event_count']==1 and m['training_performed'] is False
        events=pd.read_csv(z.open('operator_verified_events.csv'))
        context=pd.read_csv(z.open('event_context_samples.csv'))
        assert events.reported_cause.iloc[0]=='confirmed_leak'
        assert not context.empty
        assert events['label_status'].iloc[0]=='operator_physically_verified_claim'
    assert c.execute('SELECT count(*) FROM review_audit').fetchone()[0]==2
    c.close()


def test_context_immutable_after_initial_review(tmp_path):
    result=analyze_csv(DEMO)
    ev=_choose_event(result)
    c=connect(tmp_path/'feedback.sqlite3')
    d1=capture_event_context(c,result.dataset_id,ev,result.scored,source_origin='uploaded_unverified',
        source_id='uploaded-reference',input_data_sha256='abc')
    changed=result.scored.copy();changed['flow_lpm']=changed['flow_lpm']+999
    d2=capture_event_context(c,result.dataset_id,ev,changed,source_origin='uploaded_unverified',
        source_id='uploaded-reference',input_data_sha256='abc')
    assert d1!=d2
    persisted=c.execute('SELECT window_sha256 FROM event_contexts').fetchone()[0]
    assert persisted==d1
    c.close()


def test_unverified_labels_do_not_export_even_if_closed(tmp_path):
    result=analyze_csv(DEMO)
    ev=_choose_event(result)
    c=connect(tmp_path/'feedback.sqlite3')
    capture_event_context(c,result.dataset_id,ev,result.scored,source_origin='uploaded_unverified',
        source_id='uploaded-reference',input_data_sha256='abc')
    save_review(c,result.dataset_id,ev['event_id'],'closed','normal_operation',physically_verified=False)
    assert candidate_statistics(c)['verified_event_candidates']==0
    c.close()


def test_local_http_gateway_requires_token_and_records_real_request(tmp_path):
    """Exercise an actual loopback listener; no fake HTTP mocks or external network."""
    import os
    import socket
    import subprocess
    import sys
    import time
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError

    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        port=s.getsockname()[1]
    db=tmp_path/'http.sqlite3'
    token='test-only-local-token-1234567'
    env={**os.environ,'SINA_INGEST_TOKEN':token}
    cmd=[sys.executable,str(ROOT/'live_gateway.py'),'--mode','http','--source','field-http',
         '--db',str(db),'--http-port',str(port)]
    p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        ready=False
        for _ in range(50):
            if p.poll() is not None:break
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):pass
                ready=True;break
            except OSError:time.sleep(.05)
        assert ready, 'Local HTTP process did not listen'
        url=f'http://127.0.0.1:{port}/v1/measurements'
        body=json.dumps({'timestamp':'2026-11-18T12:00:00Z','line_id':'L1','flow_lpm':9.0,'pressure_bar':.3}).encode()
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(url,data=body,headers={'Content-Type':'application/json'}),timeout=2)
        assert exc.value.code==401
        req=Request(url,data=body,headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'})
        with urlopen(req,timeout=2) as response:
            assert response.status==201
            assert json.loads(response.read())['outcome']=='inserted'
        with urlopen(req,timeout=2) as response:
            assert response.status==200
            assert json.loads(response.read())['outcome']=='duplicate_ignored'
        c=live_connect(db)
        assert list_sources(c)[0]['n_readings']==1
        c.close()
    finally:
        p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill()
