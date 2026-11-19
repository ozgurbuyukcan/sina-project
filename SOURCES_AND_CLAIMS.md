# Public-facing claim register

This file documents the statements on the site and their status.

| Claim | Basis | Limitation |
|---|---|---|
| SINA Fresh Prototype 1 has five modules and a functional UI | Prototype 1 README plus user's five actual app screenshots | Synthetic demonstration; not field deployment |
| 911 real sensor measurements analyzed | `SINA_operator_scored (3).csv` local verified 911 rows; [Walid et al., Mendeley Data v2](https://doi.org/10.17632/w9594tjkwp.2) | Collected by external researchers, not by the SINA team; leak truth is unknown |
| 51 L/min recorded at minute 238.28 | Verified maximum of the 911-row CSV; next record 15.26667 L/min | No cause known; not Fresh Prototype 1 real-data detection result |
| 33 software tests passed | Local `TEST_REPORT_0_2_1.txt` dated 2026-11-18 | No physical device, browser end-to-end or field accuracy demonstration |
| 126 measurements and 7 controlled events in historical analysis | Earlier Xylem research fact sheet used in project development | Separate water-transmission experimental dataset; not current Fresh Prototype 1 trial |
| 0/7 leak onsets in historical conservative alarm comparison | Earlier research fact sheet | Historical algorithm only; not attributable as Fresh Prototype 1 performance |
| Learning data excludes synthetic demo | SINA Fresh Prototype 1 spec, screenshot, automated test report | Operator verification remains self-reported; not scientific ground truth |

Website is not the application, and this package deliberately contains neither model source code nor raw exported reviews.
