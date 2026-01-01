from __future__ import annotations
import sqlite3, time, os
from pathlib import Path

DB_PATH = Path(os.environ.get("GENLIB_DB_PATH", ".genlib/backend/jobs.sqlite3"))

SCHEMA_SQL = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  stack TEXT,
  engine TEXT,
  status TEXT,
  pid INTEGER,
  exit_code INTEGER,
  created_at REAL,
  started_at REAL,
  finished_at REAL,
  cancelled_at REAL,
  workdir TEXT,
  stdout_log TEXT,
  stderr_log TEXT,
  meta_json TEXT
);
'''

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()

def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_job(job_id, stack, engine, workdir, stdout_log, stderr_log):
    c = _conn()
    c.execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, stack, engine, "queued", None, None, time.time(), None, None, None, workdir, stdout_log, stderr_log, None)
    )
    c.commit(); c.close()

def update_job(job_id, **fields):
    c = _conn()
    cols = ",".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    c.execute(f"UPDATE jobs SET {cols} WHERE job_id=?", vals)
    c.commit(); c.close()

def get_job(job_id):
    c = _conn()
    r = c.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    cols = [d[0] for d in c.execute("PRAGMA table_info(jobs)")]
    c.close()
    return dict(zip(cols, r)) if r else None

def list_jobs():
    c = _conn()
    rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    cols = [d[0] for d in c.execute("PRAGMA table_info(jobs)")]
    c.close()
    return [dict(zip(cols, r)) for r in rows]
