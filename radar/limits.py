"""Algrow's 'similar videos' searches (search by video_url) are capped at 40 a day, then cost $0.20 each.
Every page counts as a call. Radar uses one page per seed, a few seeds per run, and stops well short of the cap."""
import time, re
from . import store, config as C


def note_notice(con, text):
    m = re.search(r"(\d+) of your (\d+) similar videos calls", text or "")
    if m:
        store.kv_set(con, "algrow_like_notice", {"n": int(m.group(1)), "cap": int(m.group(2)), "ts": time.time()})


def like_used_today(con):
    day0 = time.time() - 86400
    counted = con.execute("SELECT COUNT(*) c FROM searches WHERE tool='algrow' AND kind='like' AND status IN ('ok','degraded','error') AND ts>?", (day0,)).fetchone()["c"]
    n = store.kv_get(con, "algrow_like_notice")
    if n and n["ts"] > day0:
        since = con.execute("SELECT COUNT(*) c FROM searches WHERE tool='algrow' AND kind='like' AND status IN ('ok','degraded','error') AND ts>?", (n["ts"],)).fetchone()["c"]
        counted = max(counted, n["n"] + since)
    return counted


def like_left(con, run):
    in_run = con.execute("SELECT COUNT(*) c FROM searches WHERE run IS ? AND tool='algrow' AND kind='like' AND status IN ('ok','degraded','error')", (run,)).fetchone()["c"]
    return max(0, min(C.ALGROW_LIKE_PER_RUN - in_run, C.ALGROW_LIKE_PER_DAY - like_used_today(con)))
