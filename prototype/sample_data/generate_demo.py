"""Generate entirely SYNTHETIC measurements for UI and regression tests.

Labels are kept in a separate file, never passed to the detector.
"""
from pathlib import Path
import numpy as np
import pandas as pd

DIR=Path(__file__).resolve().parent
rng=np.random.default_rng(20261118)
rows=[]
truth=[]
for name,offset in [('LINE-A',0),('LINE-B',3)]:
    for i in range(300):
        flow=18.0+offset+0.45*np.sin(i/13)+rng.normal(0,.19)
        pressure=.35+0.015*np.sin(i/31)+rng.normal(0,.002)
        label='normal'
        if name=='LINE-A' and 145<=i<152:
            flow+=6.5;pressure-=.045;label='synthetic_flow_disturbance'
        if name=='LINE-A' and i==233:
            flow+=12.0;label='synthetic_single_sample_spike'
        if name=='LINE-B' and 177<=i<188:
            flow-=4.0;pressure-=.025;label='synthetic_pressure_flow_disturbance'
        if name=='LINE-B' and i==262:
            flow=float('nan');label='synthetic_missing_flow'
        ts=pd.Timestamp('2026-08-01T00:00:00Z')+pd.Timedelta(seconds=30*i)
        rows.append({'timestamp':ts.isoformat(),'line_id':name,'flow_lpm':round(flow,4),'pressure_bar':round(pressure,5)})
        if label!='normal':truth.append({'timestamp':ts.isoformat(),'line_id':name,'artificial_scenario':label})
pd.DataFrame(rows).to_csv(DIR/'synthetic_demo.csv',index=False)
pd.DataFrame(truth).to_csv(DIR/'synthetic_truth_NOT_FOR_TRAINING.csv',index=False)
print('Wrote 600 synthetic rows')
