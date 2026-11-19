"""Radar's memory. One SQLite file that every run reads first and writes last.

Nothing is ever deleted from it. Off-topic videos stay, with their label and reason.
"""
import json, os, sqlite3, time, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = pathlib.Path(os.environ.get("RADAR_DB", ROOT / "store" / "radar.db"))
RUNS = pathlib.Path(os.environ.get("RADAR_RUNS", ROOT / "runs"))
BOARDS = ROOT / "boards"
DATA = ROOT / "data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos(
  id TEXT PRIMARY KEY, title TEXT, channel TEXT, channel_id TEXT, handle TEXT, subs INTEGER,
  views INTEGER, upload_date TEXT, duration_s INTEGER, language TEXT, lang_note TEXT,
  live INTEGER DEFAULT 0, tool_title TEXT, tool_views INTEGER,
  yt_status TEXT, yt_checked_at REAL, first_run TEXT, first_search INTEGER, created_at REAL,
  subject_tag TEXT, title_format TEXT, niche TEXT);
CREATE TABLE IF NOT EXISTS multipliers(
  video_id TEXT, tool TEXT, value REAL, seen_at REAL, run TEXT, PRIMARY KEY(video_id, tool));
CREATE TABLE IF NOT EXISTS snapshots(video_id TEXT, ts REAL, views INTEGER, source TEXT);
CREATE INDEX IF NOT EXISTS snap_v ON snapshots(video_id, ts);
CREATE TABLE IF NOT EXISTS gains(video_id TEXT, ts REAL, gained_24h REAL, source TEXT);
CREATE INDEX IF NOT EXISTS gain_v ON gains(video_id, ts);
CREATE TABLE IF NOT EXISTS searches(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, tool TEXT, kind TEXT, query TEXT, params TEXT,
  window_days INTEGER, page INTEGER, ts REAL, rows INTEGER, new_videos INTEGER, new_outliers INTEGER,
  status TEXT, error TEXT, raw_path TEXT, cache_key TEXT, credits REAL DEFAULT 0, more INTEGER DEFAULT 0, cursor TEXT);
CREATE INDEX IF NOT EXISTS search_key ON searches(cache_key, ts);
CREATE TABLE IF NOT EXISTS hits(search_id INTEGER, video_id TEXT, rank INTEGER);
CREATE INDEX IF NOT EXISTS hit_s ON hits(search_id);
CREATE INDEX IF NOT EXISTS hit_v ON hits(video_id);
CREATE TABLE IF NOT EXISTS labels(
  video_id TEXT, subject TEXT, label TEXT, reason TEXT, labeler TEXT, ts REAL, PRIMARY KEY(video_id, subject));
CREATE TABLE IF NOT EXISTS channels(
  channel_id TEXT PRIMARY KEY, handle TEXT, name TEXT, subs INTEGER, pool INTEGER DEFAULT 0,
  watch INTEGER DEFAULT 0, bucket TEXT, cross_niche TEXT, median_views REAL, uploads_n INTEGER, uploads_at REAL);
CREATE TABLE IF NOT EXISTS uploads(channel_key TEXT, video_id TEXT, title TEXT, views INTEGER, duration_s INTEGER, pos INTEGER, ts REAL,
  PRIMARY KEY(channel_key, video_id));
CREATE TABLE IF NOT EXISTS known_outliers(
  video_id TEXT, subject TEXT, source TEXT, note TEXT, added_at REAL, PRIMARY KEY(video_id, subject));
CREATE TABLE IF NOT EXISTS runs(
  id TEXT PRIMARY KEY, subject TEXT, names TEXT, window_days INTEGER, started_at REAL, ended_at REAL,
  status TEXT, stop_reason TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS tool_calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT, ts REAL, server TEXT, tool TEXT, ok INTEGER, credits REAL DEFAULT 0, note TEXT);
CREATE INDEX IF NOT EXISTS tc_ts ON tool_calls(server, ts);
CREATE TABLE IF NOT EXISTS feedback(run TEXT, card_no INTEGER, video_id TEXT, verdict TEXT, note TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS cards(run TEXT, card_no INTEGER, video_id TEXT, section TEXT, PRIMARY KEY(run, card_no));
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=60000")
    con.executescript(SCHEMA)
    return con


def now():
    return time.time()


def today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def norm_date(d):
    """Any tool's date -> YYYY-MM-DD or None."""
    if not d:
        return None
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    if s.isdigit() and len(s) >= 10:
        return datetime.datetime.fromtimestamp(int(s[:10]), datetime.timezone.utc).date().isoformat()
    return None


def age_days(upload_date, ref=None):
    d = norm_date(upload_date)
    if not d:
        return None
    return ((ref or today()) - datetime.date.fromisoformat(d)).days


def active_run():
    p = RUNS / "ACTIVE"
    if p.exists():
        r = p.read_text().strip()
        return r or None
    return None


def run_dir(run):
    d = RUNS / (run or "_adhoc")
    (d / "raw").mkdir(parents=True, exist_ok=True)
    return d


def run_state(run):
    p = run_dir(run) / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(run, st):
    (run_dir(run) / "state.json").write_text(json.dumps(st, indent=1))


def upsert_tool_row(con, row, run=None, search_id=None):
    """Store a row that came from a search tool. Tool fields are untrusted: they never
    overwrite what YouTube told us. Returns True when the video is new to the store."""
    vid = row["id"]
    cur = con.execute("SELECT id, yt_status FROM videos WHERE id=?", (vid,)).fetchone()
    new = cur is None
    if new:
        con.execute(
            "INSERT INTO videos(id,title,channel,channel_id,subs,views,upload_date,duration_s,tool_title,tool_views,first_run,first_search,created_at,subject_tag,title_format,niche)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, row.get("title"), row.get("channel"), row.get("channel_id"), row.get("subs"), row.get("views"),
             norm_date(row.get("upload_date")), row.get("duration_s"), row.get("title"), row.get("views"),
             run, search_id, now(), row.get("subject"), row.get("title_format"), row.get("niche")))
    else:
        # fill blanks only; YouTube-verified fields win
        verified = cur["yt_status"] == "ok"
        sets, vals = [], []
        for col, key in (("title", "title"), ("channel", "channel"), ("channel_id", "channel_id"), ("subs", "subs"),
                         ("upload_date", "upload_date"), ("duration_s", "duration_s"), ("subject_tag", "subject"),
                         ("title_format", "title_format"), ("niche", "niche")):
            v = row.get(key)
            if col == "upload_date":
                v = norm_date(v)
            if v is None:
                continue
            if col == "subs":
                sets.append("subs=COALESCE(subs,?)") ; vals.append(v)
            else:
                sets.append(f"{col}=COALESCE({col},?)"); vals.append(v)
        if row.get("views") is not None:
            sets.append("tool_views=?"); vals.append(row["views"])
            if not verified:
                sets.append("views=?"); vals.append(row["views"])
        if sets:
            con.execute(f"UPDATE videos SET {', '.join(sets)} WHERE id=?", (*vals, vid))
    if row.get("mult") is not None and row.get("tool"):
        con.execute("INSERT OR REPLACE INTO multipliers(video_id,tool,value,seen_at,run) VALUES(?,?,?,?,?)",
                    (vid, row["tool"], float(row["mult"]), now(), run))
    if row.get("views") is not None:
        con.execute("INSERT INTO snapshots(video_id,ts,views,source) VALUES(?,?,?,?)", (vid, now(), int(row["views"]), row.get("tool") or "tool"))
    if row.get("gained_24h") is not None:
        con.execute("INSERT INTO gains(video_id,ts,gained_24h,source) VALUES(?,?,?,?)", (vid, now(), float(row["gained_24h"]), row.get("gain_src") or row.get("tool") or "tool"))
    return new


def mults(con, vid):
    return {r["tool"]: r["value"] for r in con.execute("SELECT tool,value FROM multipliers WHERE video_id=?", (vid,))}


def kv_get(con, k, default=None):
    r = con.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def kv_set(con, k, v):
    con.execute("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (k, json.dumps(v)))
