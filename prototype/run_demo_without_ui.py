"""Check the independent Python backend without Streamlit or a browser."""
from pathlib import Path
from sina.pipeline import analyze_csv,manifest
from sina.detect import DetectorConfig

ROOT=Path(__file__).resolve().parent
example=ROOT/'sample_data'/'synthetic_demo.csv'
out=ROOT/'demo_output'
out.mkdir(exist_ok=True)
r=analyze_csv(example.read_bytes(),DetectorConfig())
r.scored.to_csv(out/'scored.csv',index=False)
r.events.to_csv(out/'review_queue.csv',index=False)
(out/'manifest.json').write_bytes(manifest(r,DetectorConfig()))
print('SINA Prototype 1 demo complete:')
print('Measurements:',r.source_rows)
print('Hydraulic anomaly episodes:',int((r.events.event_kind=='HYDRAULIC_ANOMALY').sum()))
print('Confirmed leaks: NOT MEASURED (synthetic demonstration)')
print('Data quality events:',int((r.events.event_kind=='DATA_QUALITY').sum()))
print('Reports:',out)
