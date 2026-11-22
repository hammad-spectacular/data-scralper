"""
lead_store.py
-------------
Keeps every lead you have ever found in a local SQLite file (leads.db) so results
survive restarts, repeat searches can show only NEW leads, and you can reopen all
saved leads later. Your edits (Manual Email / Contacted) stay in cache.json and are
layered on top by place_id, so they work for saved leads too.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DB_FILE = Path(__file__).parent / "leads.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    place_id     TEXT PRIMARY KEY,
    data         TEXT NOT NULL,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    search_label TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS lead_edits (
    place_id  TEXT PRIMARY KEY,
    edited_at TEXT NOT NULL
)
"""

# Columns that are user edits or rebuilt on every run — never stored with the lead
_NOT_STORED = ("Manual Email", "Seen Before", "First Seen", "Last Seen")

# The user's own edits. They live inside the lead's JSON, but a later save
# (a fresh search re-saving the same lead) must never overwrite them.
EDITABLE_FIELDS = ("Notes", "Contacted", "Contacted On", "Manual Email")


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open a connection with the schema in place — and always close it again.

    `executescript`, not `execute`: the schema is more than one CREATE TABLE
    statement and sqlite3's execute() only ever runs a single statement
    ("You can only execute one statement at a time"), which broke every call
    into this module once the `lead_edits` table was added.

    Using `with sqlite3.connect(...)` on its own would commit/rollback but
    never close the file handle, so the connection is closed here explicitly.
    """
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _stamp() -> str:
    """Second-resolution stamp — two edits in the same minute must still count as two."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def known_ids() -> set[str]:
    with _connect() as conn:
        return {row[0] for row in conn.execute("SELECT place_id FROM leads")}


def version() -> tuple[int, str, str]:
    """(row count, newest last_seen, newest edit) — changes whenever the saved leads change."""
    with _connect() as conn:
        n, newest = conn.execute("SELECT COUNT(*), COALESCE(MAX(last_seen), '') FROM leads").fetchone()
        edited = conn.execute("SELECT COALESCE(MAX(edited_at), '') FROM lead_edits").fetchone()[0]
    return n, newest, edited


def count() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]


def save_leads(df: pd.DataFrame, search_label: str = "") -> None:
    """Insert new leads; refresh data and last_seen of known ones (first_seen is kept).

    The user's own edits (Notes / Status / Email) are kept: whatever is already
    stored for a lead wins, so re-running a search never wipes a note.
    """
    if df.empty:
        return
    records = json.loads(df.drop(columns=list(_NOT_STORED), errors="ignore").to_json(orient="records"))
    now = _now()
    with _connect() as conn:
        existing: dict[str, dict] = {}
        for pid, data in conn.execute("SELECT place_id, data FROM leads"):
            try:
                existing[pid] = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                existing[pid] = {}
        rows = []
        for r in records:
            old = existing.get(r.get("place_id", ""))
            if old:
                for field in EDITABLE_FIELDS:
                    if field in old:
                        r[field] = old[field]
            rows.append((r["place_id"], json.dumps(r, ensure_ascii=False), now, now, search_label))
        conn.executemany(
            """INSERT INTO leads (place_id, data, first_seen, last_seen, search_label)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(place_id) DO UPDATE SET
                   data = excluded.data, last_seen = excluded.last_seen""",
            rows,
        )


# Columns filled by the social / 🎬 video scan (app._scan_leads) that a batch job
# writes back into the saved table.
SCAN_COLUMNS = ("Socials", "Social Link", "Video Content", "Video Sources", "Video Links")


def merge_scan_results(saved: pd.DataFrame, updated: pd.DataFrame) -> pd.DataFrame:
    """
    Copy a batch scan's results (social links + video verdicts) from the `updated`
    rows back into the full `saved` table by place_id, then re-score so priorities
    reflect the new verdicts. Everything else — including your own edits — is kept.
    """
    if saved.empty or updated.empty or "place_id" not in saved.columns or "place_id" not in updated.columns:
        return saved
    from lead_scorer import score_dataframe          # local import: scorer is standalone

    out = saved.set_index("place_id", drop=False)
    upd = updated.set_index("place_id")
    cols = [c for c in SCAN_COLUMNS if c in upd.columns]
    common = out.index.intersection(upd.index)
    for col in cols:
        out.loc[common, col] = upd.loc[common, col]
    return score_dataframe(out.reset_index(drop=True))


def load_leads() -> pd.DataFrame:
    """All saved leads, most recently seen first (empty DataFrame if none)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT data, first_seen, last_seen FROM leads ORDER BY last_seen DESC, first_seen DESC"
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    records = [{**json.loads(d), "First Seen": first, "Last Seen": last} for d, first, last in rows]
    df = pd.DataFrame(records)
    df["Seen Before"] = True
    return df


def lead_field(place_id: str, field: str, default: str = "") -> str:
    """One field of one lead, straight from leads.db (the default when not saved yet)."""
    with _connect() as conn:
        row = conn.execute("SELECT data FROM leads WHERE place_id = ?", (place_id,)).fetchone()
    if row is None:
        return default
    try:
        return str(json.loads(row[0]).get(field, default))
    except (json.JSONDecodeError, TypeError):
        return default


def lead_fields(place_ids: list[str], field: str) -> dict[str, str]:
    """{place_id: value} for one field of many leads, in a single query."""
    if not place_ids:
        return {}
    marks = ",".join("?" * len(place_ids))
    out: dict[str, str] = {}
    with _connect() as conn:
        for pid, data in conn.execute(
            f"SELECT place_id, data FROM leads WHERE place_id IN ({marks})", list(place_ids)
        ):
            try:
                out[pid] = str(json.loads(data).get(field, ""))
            except (json.JSONDecodeError, TypeError):
                out[pid] = ""
    return out


def clear() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM leads")
        conn.execute("DELETE FROM lead_edits")


def update_lead_field(place_id: str, field: str, value: str) -> None:
    """Update a single field in a lead's data JSON in leads.db.

    Runs a direct UPDATE against the `leads` table using `place_id` as the
    primary key, so edits persist across page reloads and app restarts.
    `last_seen` is deliberately left alone — editing a note must not reshuffle
    the saved-leads list — but the edit is stamped so the app knows the saved
    list changed and refreshes it.
    """
    with _connect() as conn:
        row = conn.execute("SELECT data FROM leads WHERE place_id = ?", (place_id,)).fetchone()
        if row is None:
            return
        data = json.loads(row[0])
        data[field] = value
        conn.execute(
            "UPDATE leads SET data = ? WHERE place_id = ?",
            (json.dumps(data, ensure_ascii=False), place_id),
        )
        conn.execute(
            """INSERT INTO lead_edits (place_id, edited_at) VALUES (?, ?)
               ON CONFLICT(place_id) DO UPDATE SET edited_at = excluded.edited_at""",
            (place_id, _stamp()),
        )
