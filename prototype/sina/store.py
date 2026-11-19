"""SQLite operator feedback; append-only audit history and manual verification.

No model updates from this table until an explicit review and versioned retrain.
"""
import csv
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUS = {"unreviewed", "investigating", "closed"}
DIAGNOSIS = {"unknown", "confirmed_leak", "normal_operation", "sensor_fault", "pump_or_pressure", "possible_obstruction", "other"}


def connect(db_path):
    path=Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn=sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("""CREATE TABLE IF NOT EXISTS reviews(
        dataset_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        status TEXT NOT NULL,
        operator_diagnosis TEXT NOT NULL,
        physically_verified INTEGER NOT NULL DEFAULT 0,
        evidence TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        PRIMARY KEY(dataset_id,event_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS review_audit(
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id TEXT NOT NULL, event_id TEXT NOT NULL,
        status TEXT NOT NULL, operator_diagnosis TEXT NOT NULL,
        physically_verified INTEGER NOT NULL, evidence TEXT NOT NULL,
        notes TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    return conn


def save_review(conn, dataset_id, event_id, status, diagnosis, notes="", physically_verified=False, evidence=""):
    if status not in STATUS or diagnosis not in DIAGNOSIS:
        raise ValueError("Invalid review status or diagnosis")
    if physically_verified and (diagnosis == "unknown" or not evidence.strip()):
        raise ValueError("For physically verified outcomes, enter a diagnosis and a verification method/evidence.")
    if len(notes)>5000 or len(evidence)>2000:
        raise ValueError("Notes/evidence exceed the length limit.")
    t=datetime.now(timezone.utc).isoformat()
    args=(str(dataset_id),str(event_id),status,diagnosis,int(bool(physically_verified)),evidence,notes,t)
    with conn:
        conn.execute("""INSERT INTO reviews(dataset_id,event_id,status,operator_diagnosis,physically_verified,evidence,notes,updated_at)
          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(dataset_id,event_id) DO UPDATE SET status=excluded.status,operator_diagnosis=excluded.operator_diagnosis,
          physically_verified=excluded.physically_verified,evidence=excluded.evidence,notes=excluded.notes,updated_at=excluded.updated_at""",args)
        conn.execute("""INSERT INTO review_audit(dataset_id,event_id,status,operator_diagnosis,physically_verified,evidence,notes,updated_at)
          VALUES(?,?,?,?,?,?,?,?)""",args)


def get_review(conn, dataset_id, event_id):
    conn.row_factory=sqlite3.Row
    row=conn.execute("SELECT * FROM reviews WHERE dataset_id=? AND event_id=?",(dataset_id,event_id)).fetchone()
    return dict(row) if row else None


def export_reviews_csv(conn, dataset_id):
    cur=conn.execute("SELECT dataset_id,event_id,status,operator_diagnosis,physically_verified,evidence,notes,updated_at FROM reviews WHERE dataset_id=? ORDER BY updated_at",(dataset_id,))
    output=io.StringIO()
    w=csv.writer(output)
    w.writerow([x[0] for x in cur.description])
    w.writerows(cur.fetchall())
    return output.getvalue().encode("utf-8-sig")
