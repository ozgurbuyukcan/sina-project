import io
import sqlite3
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from sina.schema import parse_csv
from sina.quality import inspect_quality
from sina.detect import score_lines, DetectorConfig, causal_features
from sina.pipeline import analyze_csv, manifest
from sina.store import connect, save_review, get_review, export_reviews_csv

ROOT = Path(__file__).resolve().parents[1]
DEMO=(ROOT/'sample_data'/'synthetic_demo.csv').read_bytes()

@pytest.fixture(scope='module')
def result():
    return analyze_csv(DEMO, DetectorConfig())


def test_demo_contract(result):
    assert result.source_rows==600
    assert set(result.scored.line_id)=={'LINE-A','LINE-B'}
    assert result.model_profiles['LINE-A']['trained_isolation_forest']
    assert result.model_profiles['LINE-B']['trained_isolation_forest']
    assert result.model_profiles['LINE-A']['labels_used'] is False
    assert result.scored.groupby('line_id').status.apply(lambda x:(x=='BASELINE').sum()).to_dict()=={'LINE-A':100,'LINE-B':100}


def test_events_have_stable_ids_and_no_implied_cause(result):
    assert len(result.events)>0
    assert len(result.events.event_id.unique()) == len(result.events)
    assert all('confirmed' not in str(x).lower() for x in result.events.explanation)
    second=analyze_csv(DEMO)
    assert result.events.event_id.tolist()==second.events.event_id.tolist()


def test_anomalies_and_quality_separate(result):
    missing=result.scored[(result.scored.line_id=='LINE-B') & (result.scored.flow_lpm.isna())]
    assert len(missing)==1
    assert missing.iloc[0].status=='DATA_QUALITY'
    assert 'MISSING_FLOW' in missing.iloc[0].quality_flags
    assert len(result.events[result.events.event_kind=='DATA_QUALITY'])>=1
    assert len(result.events[result.events.event_kind=='HYDRAULIC_ANOMALY'])>=1


def test_flow_units_are_not_guessed():
    with pytest.raises(ValueError,match='Missing required columns'):
        parse_csv(b'timestamp,pressure_bar\n2026-01-01,0.3\n')


def test_bad_timestamp_rejected():
    with pytest.raises(ValueError,match='timestamps cannot be parsed'):
        parse_csv(b'timestamp,flow_lpm\nnot-a-time,4\n')


def test_duplicates_and_gaps_flagged():
    t=pd.to_datetime(['2026-01-01T00:00Z','2026-01-01T00:01Z','2026-01-01T00:01Z','2026-01-01T00:02Z','2026-01-01T00:16Z','2026-01-01T00:17Z'],utc=True)
    q=inspect_quality(pd.DataFrame({'timestamp':t,'flow_lpm':[1]*6,'pressure_bar':[0.2]*6,'line_id':['A']*6}))
    assert q.iloc[1].quality_ok == False
    assert 'DUPLICATE_TIMESTAMP' in q.iloc[2].quality_flags
    assert 'TIME_GAP' in q.iloc[4].quality_flags


def test_no_future_leakage_in_features_and_decisions():
    parsed=parse_csv(DEMO)
    quality=inspect_quality(parsed.frame)
    base, _=score_lines(quality,DetectorConfig())
    df=parsed.frame.copy()
    idx=df.index[(df.line_id=='LINE-A') & (df.index==260)][0]
    df.at[idx,'flow_lpm']=5000.0
    changed,_=score_lines(inspect_quality(df),DetectorConfig())
    a=base[base.line_id=='LINE-A'].iloc[:220]
    b=changed[changed.line_id=='LINE-A'].iloc[:220]
    assert np.allclose(a.anomaly_evidence,b.anomaly_evidence)
    assert a.status.tolist()==b.status.tolist()


def test_partial_pressure_missing_is_not_imputed_with_future():
    df=pd.DataFrame({'flow_lpm':[3.]*10, 'pressure_bar':[float('nan'),.2]+[.2]*8})
    x,has_pressure=causal_features(df)
    assert has_pressure
    assert x[0,1]==0.0


def test_adding_label_does_not_affect_model_scores():
    df=pd.read_csv(io.BytesIO(DEMO))
    df['ground_truth_leak']=1
    b=io.BytesIO();df.to_csv(b,index=False)
    s1=analyze_csv(DEMO).scored.anomaly_evidence.to_numpy()
    s2=analyze_csv(b.getvalue()).scored.anomaly_evidence.to_numpy()
    assert np.allclose(s1,s2)


def test_multiline_calibration_independent():
    parsed=parse_csv(DEMO)
    res=analyze_csv(DEMO)
    df=parsed.frame.copy()
    df.loc[df.line_id=='LINE-B','flow_lpm'] += 900
    buf=io.BytesIO();df.to_csv(buf,index=False)
    changed=analyze_csv(buf.getvalue())
    a=res.scored[res.scored.line_id=='LINE-A'].anomaly_evidence.to_numpy()
    b=changed.scored[changed.scored.line_id=='LINE-A'].anomaly_evidence.to_numpy()
    assert np.allclose(a,b)


def test_feedback_verification_and_audit(tmp_path):
    c=connect(tmp_path/'fb.sqlite3')
    save_review(c,'dataset-x','event-x','investigating','unknown','need site visit')
    assert get_review(c,'dataset-x','event-x')['status']=='investigating'
    with pytest.raises(ValueError,match='verification'):
        save_review(c,'dataset-x','event-x','closed','confirmed_leak',physically_verified=True)
    save_review(c,'dataset-x','event-x','closed','confirmed_leak',physically_verified=True,evidence='Visual inspection of connector')
    assert c.execute('SELECT count(*) FROM review_audit').fetchone()[0]==2
    assert b'confirmed_leak' in export_reviews_csv(c,'dataset-x')
    c.close()


def test_manifest_caveats(result):
    m=manifest(result,DetectorConfig()).decode()
    assert 'no validated' not in m or 'no measured' in m
    assert 'labels_used_in_fit' in m


def test_reading_without_pressure():
    df=pd.DataFrame({'timestamp':pd.date_range('2025-01-01',periods=80,freq='30s',tz='UTC').astype(str),'flow_lpm':np.linspace(3,4,80)})
    b=io.BytesIO();df.to_csv(b,index=False)
    res=analyze_csv(b.getvalue(),DetectorConfig(baseline_rows=40))
    assert res.model_profiles['LINE-1']['has_pressure'] is False


def test_no_overlapping_measurements_from_future_baseline():
    df=pd.read_csv(io.BytesIO(DEMO))
    line_a=df[df.line_id=='LINE-A'].copy()
    # Future subset should not alter past scoring after 100 calibration points.
    allb=io.BytesIO();line_a.to_csv(allb,index=False)
    shortb=io.BytesIO();line_a.iloc[:190].to_csv(shortb,index=False)
    allres=analyze_csv(allb.getvalue())
    shortres=analyze_csv(shortb.getvalue())
    assert np.allclose(allres.scored.iloc[:190].anomaly_evidence,shortres.scored.anomaly_evidence)
    assert allres.scored.iloc[:190].status.tolist()==shortres.scored.status.tolist()
