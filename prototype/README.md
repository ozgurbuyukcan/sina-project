# SINA Prototype 1

**Hydraulic monitoring and operator decision-support prototype**, presented for the Xylem Global Student Innovation Challenge 2026, Water Quantity / High School Track.

Public display name: **SINA Prototype 1**. Technical code lineage: **SINA Fresh 0.2.1**. Renaming does not indicate a new trained model or new field-validated results.

## What the software does

- SCAN: loads timestamped flow and optional pressure measurements and flags sensor-quality issues.
- IDENTIFY: computes unsupervised anomaly evidence; a warning is **not** a verified leak.
- NAVIGATE: ranks incidents/sensor groups for operator inspection; it does **not** locate a leak with physical precision.
- ASSESS: provides measurement context, notes, and human review.
- LEARNING DATA: stores candidates for future research only when review/evidence requirements are met; does **not** automatically retrain.

## Run on Windows

Install **Python 3.10 (64-bit)**. Download/clone the repository, open `prototype/`, and run `run_windows.bat`. The launcher creates `.venv` and installs `requirements.txt` on first launch, then opens Streamlit at `http://127.0.0.1:8501`.

Alternatively:

```powershell
cd prototype
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

The built-in sample is **synthetic**. `Upload measured CSV` requires `timestamp` (ISO8601) and `flow_lpm` (litres/minute); optional columns: `pressure_bar` (bar), `line_id`. Units are not guessed. Uploaded data provenance is not independently verified.

## Research limitations and safety

This research prototype is not a field-certified leak detector, does not automatically operate valves or pumps, and does not infer verified water savings. Real leak accuracy requires separate, documented physical validation. The historical reports under `TEST_REPORT*.txt` describe **software tests**, not field leak sensitivity.

The `user_data/` folder and its SQLite databases are **excluded**. Keep personal measurements, private credentials, and operator review databases local. The repository has no license grant until the owner chooses one.

For technical history and Windows gateway notes, see `README_TR.md`, `CHANGELOG_0_2_1_TR.md` and `STABILIZATION_CHECKLIST_TR.md`.
