"""SINA Prototype 1 — measured-data surveillance, live gateway and evidence-backed review.

Start: python -m streamlit run app.py
The app never controls pumps/valves and never automatically retrains from user labels.
"""
from pathlib import Path
import hashlib
import io
import json
import zipfile

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sina.plots import event_plot
from sina.detect import DetectorConfig
from sina.feedback import (candidate_export_zip, candidate_statistics,
                           capture_event_context, ensure_feedback_schema)
from sina.live import (live_connect, list_sources, live_csv, source_quality_counts, source_connection_health,
                       stable_live_event_ids)
from sina.pipeline import analyze_csv, manifest
from sina.store import connect, save_review, get_review, export_reviews_csv

ROOT=Path(__file__).resolve().parent
FEEDBACK_DB=ROOT/'user_data'/'operator_feedback.sqlite3'
LIVE_DB=ROOT/'user_data'/'live_measurements.sqlite3'
DEMO=ROOT/'sample_data'/'synthetic_demo.csv'

st.set_page_config(page_title='SINA Prototype 1 | Hydraulic Intelligence', page_icon='💧',layout='wide')
st.markdown('''<style>
.block-container{padding-top:1.6rem;max-width:1540px}
[data-testid="stMetric"]{border:1px solid rgba(100,140,160,.22);border-radius:12px;padding:12px}
h1{font-size:2rem}
</style>''', unsafe_allow_html=True)
st.title('SINA Prototype 1 · Hydraulic Intelligence')
st.caption('SINA Prototype 1 · SCAN → IDENTIFY → NAVIGATE → ASSESS → HUMAN-REVIEWED DATA')
st.info('Research decision support only. An anomalous signal does not prove a leak or any other specific hydraulic fault. No automatic pump/valve actions.',icon='ℹ️')

with st.sidebar:
    st.subheader('Measurement source')
    source=st.radio('Select source', ['Synthetic demo (offline)', 'Upload measured CSV', 'Live sensor gateway'],index=0)
    uploaded=st.file_uploader('CSV measurement file',type=['csv'],disabled=source!='Upload measured CSV')
    chosen_live=None
    live_meta=None
    if source=='Live sensor gateway':
        c=live_connect(LIVE_DB)
        try: sources=list_sources(c)
        finally: c.close()
        if sources:
            all_ids=[x['source_id'] for x in sources]
            chosen_live=st.selectbox('Connected source records',all_ids)
            live_meta=next(x for x in sources if x['source_id']==chosen_live)
            st.caption(f"Ingest mode: {live_meta['ingest_mode']} · Records: {live_meta['n_readings']:,}")
            st.caption(f"Latest receive: {live_meta['latest_received_at']}")
            c_health=live_connect(LIVE_DB)
            try: health=source_connection_health(c_health,chosen_live)
            finally: c_health.close()
            st.caption(f"Gateway health: {health['status']} · Last connection event: {health['last_event_type'] or 'none'}")
            if health['status'] in ('STALE','DISCONNECTED','RECONNECTING','NO_RECORDS'):
                st.warning('Gateway health is not currently confirmed. Review connection diagnostics before interpreting old records as live.')
            try:
                age=(pd.Timestamp.now(tz='UTC')-pd.Timestamp(live_meta['latest_received_at'])).total_seconds()
                if age>120:
                    st.warning('No new packets for more than 2 minutes. Stored measurements are shown; gateway/device may be offline.')
            except (ValueError, TypeError):
                st.warning('Latest receive timestamp cannot be verified.')
            if st.button('↻ Refresh live snapshot',use_container_width=True): st.rerun()
            st.caption('The gateway receives continuously; this screen shows the last refreshed snapshot, not an automatic live stream.')
        else:
            st.warning('No sensor records yet. Run start_serial_windows.bat or start_http_windows.bat first.')
    st.divider()
    st.subheader('Detection policy')
    baseline=st.slider('First N rows assumed normal per line',30,200,100,10)
    sensitivity=st.slider('Flow anomaly threshold (robust z)',2.5,7.,3.5,.5)
    ml=st.checkbox('Train baseline Isolation Forest',value=True)
    persistence=st.slider('Consecutive WATCH → ALERT',1,5,2)
    recovery=st.slider('Consecutive quiet readings to recover',1,5,2)
    st.caption('First N samples are ASSUMED healthy. No actual leak labels are available to the model.')
    st.caption('CSV contract: timestamp (ISO8601), flow_lpm (L/min), optional pressure_bar (bar) and line_id.')

if source=='Synthetic demo (offline)':
    raw=DEMO.read_bytes()
    origin='synthetic_demo'
    provenance_source='demo-synthetic-v1'
    st.caption('**Source:** explicitly simulated demonstration only. Not physical observations.')
elif source=='Upload measured CSV':
    if uploaded is None:
        st.warning('Upload a CSV first or choose the synthetic demo.')
        st.stop()
    raw=uploaded.getvalue()
    origin='uploaded_unverified'
    provenance_source='uploaded-'+hashlib.sha256(raw).hexdigest()[:14]
    st.caption('**Source:** user-uploaded CSV; physical origin and labels have not been independently verified.')
else:
    if chosen_live is None: st.stop()
    c=live_connect(LIVE_DB)
    try:
        raw=live_csv(c,chosen_live)
        ingest_counts=source_quality_counts(c,chosen_live)
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()
    finally:c.close()
    origin='offline_replay' if live_meta['ingest_mode'] in ('OFFLINE_REPLAY','UNREGISTERED') else 'live_gateway_unverified'
    provenance_source=chosen_live
    if origin=='offline_replay':
        st.warning('**OFFLINE REPLAY:** these records were read from a file, not streamed by a live device. Not eligible as measured training candidates.')
    else:
        st.caption(f'**Source:** local {live_meta["ingest_mode"]} gateway, unverified sensor provenance. The app has not certified hardware calibration.')
    qa=st.columns(2)
    qa[0].metric('Rejected packets',ingest_counts['rejected_packets'])
    qa[1].metric('Gateway-assigned timestamps',ingest_counts['gateway_timestamped'])

cfg=DetectorConfig(baseline_rows=baseline,z_watch=sensitivity,persistence=persistence,recovery=recovery,ml_enabled=ml)
try:
    result=analyze_csv(raw,cfg)
    if source=='Live sensor gateway': stable_live_event_ids(result,chosen_live)
except ValueError as exc:
    st.error(f'Cannot analyze this snapshot: {exc}')
    if source=='Live sensor gateway':
        st.caption('More readings may be needed to establish the assumed-normal baseline. Measurements remain stored in the gateway database.')
    st.stop()
except Exception as exc:
    st.error(f'Unexpected analysis error: {exc}')
    st.stop()

sc=result.scored
events=result.events
issues=sc[sc['quality_flags']!='']
alert_count=int((events['status']=='ALERT').sum())
watch_count=int((events['status']=='WATCH_ONLY').sum())
quality_count=int((events['event_kind']=='DATA_QUALITY').sum())
cols=st.columns(5)
cols[0].metric('Readings',f'{len(sc):,}')
cols[1].metric('Alarm episodes',alert_count)
cols[2].metric('WATCH-only episodes',watch_count)
cols[3].metric('Quality episodes',quality_count)
cols[4].metric('Sensor QA flags',len(issues))
for message in result.notices:st.warning(message)

scan,identify,navigate,assess,learning=st.tabs([
    '01 · SCAN', '02 · IDENTIFY','03 · NAVIGATE','04 · ASSESS','05 · LEARNING DATA'])


with scan:
    st.subheader('Incoming measurements & sensor integrity')
    left,right=st.columns([1.7,1])
    with left:
        selected_line=st.selectbox('Sensor group',sorted(sc.line_id.unique()),key='scan_line')
        segment=sc[sc.line_id==selected_line]
        st.plotly_chart(event_plot(segment),use_container_width=True)
        if segment.pressure_bar.notna().any():
            st.line_chart(segment.set_index('timestamp').pressure_bar,height=170)
            st.caption('Pressure in bar, shown separately. A shape change is not proof of cause.')
    with right:
        st.markdown('**SCAN validity inspection**')
        if len(issues):
            count=(issues.quality_flags.str.split('|').explode().value_counts().rename_axis('Flag').reset_index(name='Readings'))
            st.dataframe(count,hide_index=True,use_container_width=True,height=255)
        else:st.success('No flagged quality conditions in the processed snapshot.')
        st.caption('Negative/missing readings, duplicate timestamps, gaps and flatlines are flagged. Some flatline flags are retrospective. Unknown sensor calibration is not inferred.')
        if origin=='live_gateway_unverified':
            st.caption('Source gateway uses append-only records; duplicates are ignored only if identical; conflicting duplicates are rejected and logged.')
    st.download_button('Download scored readings',sc.to_csv(index=False).encode('utf-8-sig'),
                       f'SINA_scored_{result.dataset_id}.csv',mime='text/csv')

with identify:
    st.subheader('Unsupervised anomaly evidence')
    st.caption('Isolation Forest fits on early assumed-normal measurements. A score is NOT leak probability or fault classification.')
    left,right=st.columns([1.3,1])
    with left:
        selected_line=st.selectbox('View line',sorted(sc.line_id.unique()),key='id_line')
        g=sc[sc.line_id==selected_line]
        chart=go.Figure()
        chart.add_trace(go.Scatter(x=g.timestamp,y=g.anomaly_evidence,mode='lines',name='Relative anomaly evidence'))
        chart.add_hline(y=1,line_dash='dash',line_color='#dc9c3b')
        chart.update_layout(height=325,margin=dict(t=20,b=15,l=16,r=12),yaxis_title='Relative anomaly evidence')
        st.plotly_chart(chart,use_container_width=True)
    with right:
        st.json(result.model_profiles)
        st.info('Alarm levels and priority come from heuristic thresholds. No causal identification or hydraulic topology localization has been validated.')

with navigate:
    st.subheader('Incident triage & investigation queue')
    st.caption('Priorities guide inspection; they are not diagnoses. The queue separates DATA_QUALITY from hydraulic anomalies.')
    if events.empty:
        st.info('No events with these settings. This does not prove the system is fault-free.')
    else:
        f1,f2,f3=st.columns(3)
        line_filter=f1.multiselect('Filter lines',sorted(events.line_id.unique()),default=sorted(events.line_id.unique()))
        kind_filter=f2.multiselect('Event type',sorted(events.event_kind.unique()),default=sorted(events.event_kind.unique()))
        priority_filter=f3.multiselect('Priority',sorted(events.priority.unique()),default=sorted(events.priority.unique()))
        subset=events[events.line_id.isin(line_filter)&events.event_kind.isin(kind_filter)&events.priority.isin(priority_filter)].copy()
        c=connect(FEEDBACK_DB)
        try:
            review_map={eid:get_review(c,result.dataset_id,eid) for eid in events.event_id}
        finally:c.close()
        subset['review_workflow']=subset.event_id.map(lambda eid:(review_map[eid] or {}).get('status','unreviewed'))
        ranks={'INSPECT':0,'VERIFY_SENSOR':1,'REVIEW':2}
        subset['_rank']=subset.priority.map(ranks).fillna(3)
        subset=subset.sort_values(['_rank','start']).drop(columns=['_rank'])
        st.dataframe(subset,hide_index=True,use_container_width=True,height=400)
        st.download_button('Download incident queue',subset.to_csv(index=False).encode('utf-8-sig'),
                           'SINA_incident_queue.csv',mime='text/csv')
        st.caption('Select an event in ASSESS to see its timeline, measurement context, reported cause, evidence and previous operator review.')

with assess:
    st.subheader('Incident investigation & operator verification')
    if events.empty:
        st.info('No incidents to review in this snapshot.')
    else:
        all_events=events.to_dict('records')
        chosen=st.selectbox('Inspect a specific event',range(len(all_events)),
          format_func=lambda i:f"{all_events[i]['event_kind']} · {all_events[i]['priority']} · {all_events[i]['line_id']} · {str(all_events[i]['start'])[:19]} · {all_events[i]['event_id']}")
        ev=all_events[chosen]
        begin=pd.Timestamp(ev['start'])
        k1,k2,k3,k4=st.columns(4)
        k1.metric('Event classification', 'Hydraulic anomaly' if ev['event_kind']=='HYDRAULIC_ANOMALY' else 'Data quality')
        k2.metric('Priority',ev['priority'])
        k3.metric('Model state',ev['status'])
        k4.metric('Peak anomaly evidence', 'N/A' if pd.isna(ev['peak_evidence']) else ev['peak_evidence'])
        st.info(ev['explanation'])
        st.caption(f"Event identifier {ev['event_id']} · Line {ev['line_id']} · Event time {begin.isoformat()} · {ev['n_readings']} flagged readings")
        detail=sc[sc.line_id==ev['line_id']]
        st.plotly_chart(event_plot(detail,begin),use_container_width=True)
        nearby=detail[detail.timestamp.between(begin-pd.Timedelta(minutes=5),begin+pd.Timedelta(minutes=5))]
        cols=['timestamp','flow_lpm','pressure_bar','status','quality_flags','anomaly_evidence']
        with st.expander('See source measurements around this incident'):
            st.dataframe(nearby[cols],hide_index=True,use_container_width=True,height=250)
            st.caption('The five-minute window includes observations after the event and is suitable for RETROSPECTIVE review, not causal real-time input.')
        c=connect(FEEDBACK_DB)
        ensure_feedback_schema(c)
        current=get_review(c,result.dataset_id,ev['event_id']) or {}
        with st.form('operator_review_form'):
            status_options=['unreviewed','investigating','closed']
            status=st.selectbox('Review workflow',status_options,index=status_options.index(current.get('status','unreviewed')))
            labels=['unknown','confirmed_leak','normal_operation','sensor_fault','pump_or_pressure','possible_obstruction','other']
            diagnosis=st.selectbox('Operator-reported finding (not AI output)',labels,index=labels.index(current.get('operator_diagnosis','unknown')))
            physically_verified=st.checkbox('I inspected and physically verified the reported cause',value=bool(current.get('physically_verified',0)))
            evidence=st.text_input('How was it verified? / Evidence reference',value=current.get('evidence',''),
                                   placeholder='e.g. technician photographed a loose connector during site inspection')
            notes=st.text_area('Operator notes',value=current.get('notes',''),max_chars=5000)
            save=st.form_submit_button('Save review + immutable measurement snapshot',type='primary')
        if save:
            try:
                # Check before snapshot to avoid unsupported labels saved as candidate contexts.
                if physically_verified and (diagnosis=='unknown' or not evidence.strip()):
                    raise ValueError('Verified reports require an explicit diagnosis and inspection evidence.')
                capture_event_context(c,result.dataset_id,ev,sc,source_origin=origin,source_id=provenance_source,
                                      input_data_sha256=hashlib.sha256(raw).hexdigest())
                save_review(c,result.dataset_id,ev['event_id'],status,diagnosis,notes,physically_verified,evidence)
                st.success('Review saved with an audit entry and source-window snapshot. NO model training has occurred.')
            except Exception as exc:st.error(str(exc))
        with st.expander('Previously saved review and evidence'):
            st.json(get_review(c,result.dataset_id,ev['event_id']) or {'status':'not reviewed'})
            audit=pd.read_sql_query('''SELECT audit_id,status,operator_diagnosis,physically_verified,evidence,notes,updated_at
                FROM review_audit WHERE dataset_id=? AND event_id=? ORDER BY audit_id DESC''',c,
                params=(result.dataset_id,ev['event_id']))
            st.dataframe(audit,hide_index=True,use_container_width=True)
        st.download_button('Export reviews for this dataset',export_reviews_csv(c,result.dataset_id),
                           'SINA_reviews.csv',mime='text/csv')
        c.close()
    st.divider()
    zbuf=io.BytesIO()
    with zipfile.ZipFile(zbuf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('source_measurements.csv',raw)
        z.writestr('scored_measurements.csv',sc.to_csv(index=False))
        z.writestr('event_queue.csv',events.to_csv(index=False))
        z.writestr('run_manifest.json',manifest(result,cfg))
        z.writestr('source_provenance.json',json.dumps({'source_origin':origin,'source_id':provenance_source,
               'raw_sha256':hashlib.sha256(raw).hexdigest(),'dataset_reference':result.dataset_id},indent=2))
        z.writestr('README.txt','Unverified anomalies are not confirmed leaks. Manually reported labels do not automatically train AI.\n')
    st.download_button('Download current analysis + provenance ZIP',zbuf.getvalue(),
                       f'SINA_export_{result.dataset_id}.zip',mime='application/zip')

with learning:
    st.subheader('Human-verified event library · research candidates')
    st.caption('Reviews are stored locally in SQLite. Only explicitly closed, physically checked, evidenced, non-demo event reviews enter the candidate export. No model is retrained here.')
    c=connect(FEEDBACK_DB)
    try:
        ensure_feedback_schema(c)
        stats=candidate_statistics(c)
        met=st.columns(4)
        met[0].metric('Eligible reviewed events',stats['verified_event_candidates'])
        met[1].metric('Reported leaks',stats['reported_leaks'])
        met[2].metric('Reported other causes',stats['reported_nonleaks'])
        met[3].metric('Context samples',stats['context_samples'])
        st.markdown('''**How a label reaches the candidate library**

1. A sensor or uploaded measurement creates an observation and an event.
2. The operator investigates the event and marks the actual inspection finding, with evidence.
3. The event is closed. Its **frozen review context** and original dataset fingerprint remain linked.
4. It becomes an **operator-verified candidate**, not automatically trusted ground truth.
5. Separate future training must prevent overlapping event windows and evaluate on independent physical campaigns.
''')
        if stats['verified_event_candidates']:
            st.download_button('Export verified event candidates (ZIP)',candidate_export_zip(c),
                               'SINA_operator_verified_candidate_dataset.zip',mime='application/zip')
        else:st.info('No eligible training-candidate events yet. Synthetic demo reviews will not be exported as real measured examples.')
        with st.expander('Review audit log (local)'):
            log=pd.read_sql_query('''SELECT audit_id,dataset_id,event_id,status,operator_diagnosis,physically_verified,evidence,updated_at
             FROM review_audit ORDER BY audit_id DESC LIMIT 200''',c)
            st.dataframe(log,hide_index=True,use_container_width=True)
        st.warning('Human-reported “physically verified” is an operator assertion, not independently certified fact. No ML metrics or accuracy can be inferred from this database alone.')
    finally:c.close()
