"""Views per hour that is true: views gained in the last 24 hours, divided by 24.

Never a lifetime average. Never from two counts under 6 hours apart. Looked up by video id, never by title.
Every number carries the source it came from. No real number means the card says "VPH n/a".
"""
import time
from . import store

FRESH_S = 36 * 3600
SOURCE_LABEL = {"algrow-24h": "Algrow 24h", "vidiq-vph": "vidIQ", "algrow-daily": "Algrow daily", "snapshots": "Radar snapshots"}
ORDER = ["algrow-24h", "vidiq-vph", "algrow-daily"]


def _lifetime_vph(v):
    age = store.age_days(v.get("upload_date"))
    if not age or not v.get("views"):
        return None
    return v["views"] / (age * 24.0)


def _sources(con, vid):
    out = {}
    now = time.time()
    for src in ORDER:
        r = con.execute("SELECT gained_24h, ts FROM gains WHERE video_id=? AND source=? AND ts>? ORDER BY ts DESC LIMIT 1", (vid, src, now - FRESH_S)).fetchone()
        if r and r["gained_24h"] is not None and r["gained_24h"] >= 0:
            out[src] = r["gained_24h"] / 24.0
    # Radar's own snapshots: two YouTube counts 6 to 72 hours apart
    snaps = con.execute("SELECT ts, views FROM snapshots WHERE video_id=? AND source='youtube' AND ts>? ORDER BY ts DESC", (vid, now - 80 * 3600)).fetchall()
    if len(snaps) >= 2:
        newest = snaps[0]
        for s in snaps[1:]:
            gap = newest["ts"] - s["ts"]
            if 6 * 3600 <= gap <= 72 * 3600 and newest["views"] >= s["views"]:
                out["snapshots"] = (newest["views"] - s["views"]) / (gap / 3600.0)
                break
    return out


def compute(con, v):
    """-> {'vph': number or None, 'source': label, 'why': reason when n/a}"""
    srcs = _sources(con, v["id"])
    views = v.get("views") or 0
    # a 24 hour gain cannot exceed total views
    srcs = {k: x for k, x in srcs.items() if x * 24 <= max(views, 1)}
    if not srcs:
        return {"vph": None, "source": None, "why": "no source has a 24 hour gain for this video"}
    first = next(k for k in ORDER + ["snapshots"] if k in srcs)
    val = srcs[first]
    age = store.age_days(v.get("upload_date")) or 0
    life = _lifetime_vph(v)
    if age > 30 and life is not None and val > life:
        # an old video moving faster than its lifetime average needs a second source that agrees
        others = [x for k, x in srcs.items() if k != first]
        agree = [x for x in others if x > 0 and 1 / 3 <= (val / x if x else 0) <= 3]
        if not agree:
            return {"vph": None, "source": None, "why": f"{SOURCE_LABEL[first]} says {val:.0f}/hr on a {age} day old video and no second source confirms it"}
    return {"vph": val, "source": SOURCE_LABEL[first], "why": None, "all": {SOURCE_LABEL[k]: round(x, 1) for k, x in srcs.items()}}


def need_lookup(st, con):
    """Card videos that have no fresh source yet, or need a second one. These go to vidIQ by id, 50 per call."""
    from . import board
    ids = []
    for v in board.card_videos(st, con, include_cross=True):
        srcs = _sources(con, v["id"])
        age = store.age_days(v.get("upload_date")) or 0
        life = _lifetime_vph(v)
        if not srcs:
            ids.append(v["id"])
        elif len(srcs) == 1 and age > 30 and life is not None and next(iter(srcs.values())) > life:
            ids.append(v["id"])
    return ids


def agreement(con, ids):
    """How vidIQ's number compares with Algrow's measured 24 hour gain on the same videos. Reported, never assumed."""
    pairs = []
    for vid in ids:
        s = _sources(con, vid)
        if "algrow-24h" in s and "vidiq-vph" in s and s["algrow-24h"] > 0:
            pairs.append(s["vidiq-vph"] / s["algrow-24h"])
    if len(pairs) < 5:
        return None
    pairs.sort()
    within = sum(1 for p in pairs if 0.5 <= p <= 2) / len(pairs)
    return {"n": len(pairs), "median_ratio": round(pairs[len(pairs) // 2], 2), "within_2x": round(within, 2)}
