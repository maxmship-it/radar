"""Turns a raw connector result into rows. Code reads the tool's own JSON. No model types a row."""
import json, re, hashlib

VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
A = {
    "id": ["video_id", "videoId", "youtube_id", "id"],
    "title": ["title", "video_title", "videoTitle"],
    "channel": ["channel_name", "channelTitle", "channel_title", "channelName", "channel"],
    "channel_id": ["channel_id", "channelId"],
    "handle": ["channel_handle", "channelHandle", "handle"],
    "subs": ["subscriber_count", "channel_subscribers", "subscriberCount", "channelSubscriberCount", "subscribers", "channelSubscribers"],
    "views": ["view_count", "viewCount", "views"],
    "upload_date": ["upload_date", "published_at", "publishedAt", "published", "uploadDate"],
    "duration_s": ["duration_seconds", "durationSeconds", "duration", "lengthSeconds", "durationSec"],
    "gained_24h": ["gained_24h"],
    "vph": ["vph", "viewsPerHour", "views_per_hour"],
    "subject": ["subject"], "title_format": ["title_format"], "niche": ["niche", "channel_niche"],
    "language": ["language", "defaultAudioLanguage", "default_audio_language"],
}
MULT = {
    "algrow": ["outlier_score"], "algrow-pool": ["adjusted_score", "outlier_score"], "algrow-thumb": ["outlier_score"],
    "tubeai": ["outlier_multiplier"], "tubeai-thumb": ["outlier_multiplier"],
    "vidiq": ["breakoutScore", "outlierScore", "outlier_score", "breakout_score", "score"], "vidiq-thumb": ["breakoutScore", "outlierScore"],
}


def _blocks(x):
    return isinstance(x, list) and x and all(isinstance(b, dict) and "type" in b for b in x)


def to_obj(resp, depth=0):
    """Hook gives the tool response as a string, a dict, or a list of content blocks, sometimes
    wrapped ({"result": [{"type": "text", "text": "<json>"}]}). Unwrap until we reach the tool's own JSON."""
    if depth > 4:
        return None, str(resp)[:500]
    if isinstance(resp, dict):
        for k in ("result", "content"):
            if _blocks(resp.get(k)) and len(resp) <= 3:
                return to_obj(resp[k], depth + 1)
        return resp, None
    if _blocks(resp):
        return to_obj("\n".join(b.get("text", "") for b in resp if b.get("type") == "text"), depth + 1)
    if isinstance(resp, list):
        return resp, None
    if isinstance(resp, str):
        s = resp.strip()
        try:
            o = json.loads(s)
        except Exception:
            m = re.search(r"[\[{]", s)
            o = None
            if m:
                try:
                    o = json.JSONDecoder().raw_decode(s[m.start():])[0]
                except Exception:
                    o = None
            if o is None:
                return None, s[:500]
        if isinstance(o, (dict, list)):
            return to_obj(o, depth + 1) if (isinstance(o, dict) and any(_blocks(o.get(k)) for k in ("result", "content"))) or _blocks(o) else (o, None)
        return None, s[:500]
    return None, str(resp)[:500]


def _flat(d):
    """Lift one level of nested dicts (vidIQ nests channel and stats)."""
    out = dict(d)
    for k, v in d.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if k in ("channel", "channelInfo", "snippet") and k2 in ("id",):
                    out.setdefault("channelId", v2)
                elif k in ("channel", "channelInfo") and k2 in ("title", "name"):
                    out["channel_name"] = v2
                elif k in ("channel", "channelInfo") and k2 in ("subscriberCount", "subscribers"):
                    out.setdefault("subscriberCount", v2)
                elif k in ("channel", "channelInfo") and k2 in ("handle", "customUrl"):
                    out.setdefault("channel_handle", v2)
                else:
                    out.setdefault(k2, v2)
    return out


def _pick(d, keys):
    for k in keys:
        if k in d and d[k] is not None and not isinstance(d[k], (dict, list)):
            return d[k]
    return None


def _num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return x
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def _dur(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return int(x)
    s = str(x)
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", s)
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
    if s.isdigit():
        return int(s)
    if re.match(r"^\d+(:\d\d){1,2}$", s):
        t = 0
        for p in s.split(":"):
            t = t * 60 + int(p)
        return t
    return None


def find_rows(obj):
    """The biggest list of dicts in the result whose items carry a YouTube video id."""
    best = []

    def walk(o):
        nonlocal best
        if isinstance(o, list):
            items = [_flat(x) for x in o if isinstance(x, dict)]
            good = [x for x in items if VID_RE.match(str(_pick(x, A["id"]) or ""))]
            if len(good) > len(best):
                best = good
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(obj)
    return best


def classify(server, name, inp):
    """-> (tool label, kind, query)"""
    inp = inp or {}
    if server == "Algrow":
        if name == "search_viral_videos":
            if inp.get("same_format_as"):
                return "algrow", "format", str(inp["same_format_as"])
            if inp.get("video_url"):
                return "algrow", "like", str(inp["video_url"])
            if inp.get("subject"):
                return "algrow", "subject", str(inp["subject"])
            q = str(inp.get("search") or inp.get("keyword") or "")
            if q.startswith("@") or q.startswith("UC") or "youtube.com" in q or "youtu.be" in q:
                return "algrow", "channel", q
            return "algrow", "keyword" if q else "browse", q
        if name == "folder_outliers":
            return "algrow-pool", "pool", f"{inp.get('folder')} min{inp.get('min_score')} {inp.get('sort', 'outlier')}"
        if name == "search_by_thumbnail":
            return "algrow-thumb", "thumb", str(inp.get("video_url") or inp.get("image_url") or inp.get("q") or "")
        if name == "get_video_daily_views":
            return "algrow-daily", "vph", str(inp.get("video_id"))
        if name == "youtube_search":
            return "algrow-yt", "ytsearch", str(inp.get("query"))
        if name == "get_channel_videos":
            return "algrow-chan", "channel", str(inp.get("channel_id"))
        return "algrow-other", name, json.dumps(inp, sort_keys=True)[:200]
    if server == "TubeAI":
        if name == "explore_videos":
            if inp.get("search"):
                return "tubeai", "keyword", str(inp["search"])
            if inp.get("similarToHandle"):
                return "tubeai", "similar", str(inp["similarToHandle"])
            if inp.get("channelIds") or inp.get("channelHandles"):
                ids = inp.get("channelIds") or inp.get("channelHandles")
                return "tubeai", "poolshort", hashlib.sha1(",".join(sorted(ids)).encode()).hexdigest()[:10] + f" x{len(ids)}"
            return "tubeai", "browse", ",".join(inp.get("niches") or [])
        if name == "explore_similar_thumbnails":
            return "tubeai-thumb", "thumb", str(inp.get("video"))
        return "tubeai-other", name, json.dumps(inp, sort_keys=True)[:200]
    if server == "vidIQ":
        if name == "vidiq_outliers":
            if inp.get("seedVideoId"):
                return "vidiq", "like", str(inp["seedVideoId"])
            if inp.get("channelIds") and not inp.get("keyword"):
                return "vidiq", "channel", ",".join(inp["channelIds"])[:200]
            return "vidiq", "keyword", str(inp.get("keyword") or "")
        if name == "vidiq_get_videos_by_ids":
            return "vidiq-ids", "vph", f"{len(inp.get('videoIds') or [])} ids"
        if name == "vidiq_similar_thumbnails":
            return "vidiq-thumb", "thumb", json.dumps(inp, sort_keys=True)[:200]
        return "vidiq-other", name, ""
    return server.lower(), name, ""


def window_of(server, name, inp):
    inp = inp or {}
    if server == "Algrow":
        if name == "folder_outliers":
            return inp.get("days", 7)
        return inp.get("uploaded_within_days", 364)
    if server == "TubeAI" and inp.get("minDate"):
        import datetime
        try:
            return (datetime.date.today() - datetime.date.fromisoformat(inp["minDate"])).days
        except Exception:
            return None
    if server == "vidIQ":
        return {"thisWeek": 7, "thisMonth": 30, "threeMonths": 90, "sixMonths": 182, "oneYear": 365, "twoYears": 730, "allTime": 9999}.get(inp.get("publishedWithin"))
    return None


def cache_key(server, name, inp):
    """Same search, same window bucket, same filters -> same key. Page and cursor are kept so each page caches on its own."""
    d = {k: v for k, v in (inp or {}).items() if k not in ("userGoal", "minDate", "fields", "showThumbnails")}
    w = window_of(server, name, inp)
    d["_w"] = w
    return hashlib.sha1((server + "." + name + json.dumps(d, sort_keys=True, default=str)).encode()).hexdigest()[:16]


def normalize(server, name, inp, resp):
    tool, kind, query = classify(server, name, inp)
    obj, bad = to_obj(resp)
    meta = {"tool": tool, "kind": kind, "query": query, "error": None, "more": False, "cursor": None, "notices": [], "page": int((inp or {}).get("page") or 1)}
    text = (json.dumps(obj)[:4000] if obj is not None else (bad or "")).lower()
    if obj is None:
        meta["error"] = bad or "empty result"
    elif isinstance(obj, dict):
        for k in ("limit_notice", "credit_notice"):
            if obj.get(k):
                meta["notices"].append(f"{k}: {obj[k]}")
        err = obj.get("error") or (obj.get("message") if obj.get("success") is False else None)
        if err or obj.get("isError"):
            meta["error"] = str(err or obj)[:400]
        if obj.get("degraded"):
            meta["notices"].append("degraded")
        st = obj.get("search_status")
        if isinstance(st, dict) and st.get("complete") is False:
            meta["notices"].append("incomplete")
        meta["cursor"] = obj.get("nextCursor") or obj.get("next_cursor")
    if meta["error"] is None and any(p in text[:600] for p in ("rate limit", "too many requests", "exceeded its memory or time budget", "quota")) and not find_rows(obj):
        meta["error"] = text[:300]
    rows = []
    if kind == "vph" and tool == "algrow-daily" and isinstance(obj, dict):
        days = obj.get("days") or []
        gained = [d for d in days if isinstance(d, dict) and d.get("views_gained") is not None]
        if gained:
            last = gained[-1]
            rows.append({"id": str(inp.get("video_id"))[-11:], "views": last.get("view_count"), "gained_24h": last.get("views_gained"), "gain_src": "algrow-daily", "tool": None})
        return rows, meta
    raw = find_rows(obj) if obj is not None else []
    for i, r in enumerate(raw):
        row = {"id": str(_pick(r, A["id"])), "rank": i + 1, "tool": tool if tool in MULT else None}
        for f in ("title", "channel", "channel_id", "handle", "upload_date", "subject", "title_format", "niche", "language"):
            v = _pick(r, A[f])
            row[f] = str(v) if v is not None else None
        row["subs"] = _num(_pick(r, A["subs"]))
        row["views"] = _num(_pick(r, A["views"]))
        row["duration_s"] = _dur(_pick(r, A["duration_s"]))
        row["mult"] = _num(_pick(r, MULT.get(tool, []))) if tool in MULT else None
        g = _num(_pick(r, A["gained_24h"]))
        if g is not None:
            row["gained_24h"], row["gain_src"] = g, "algrow-24h"
        vph = _num(_pick(r, A["vph"]))
        if vph is not None and g is None and server == "vidIQ":
            row["gained_24h"], row["gain_src"] = vph * 24, "vidiq-vph"
        for f in ("subs", "views"):
            if row[f] is not None:
                row[f] = int(row[f])
        rows.append(row)
    if server == "Algrow" and name == "search_viral_videos":
        per = int((inp or {}).get("per_page") or 50)
        meta["more"] = bool(obj.get("has_more")) if isinstance(obj, dict) and "has_more" in obj else len(rows) >= per
    elif meta["cursor"]:
        meta["more"] = True
    return rows, meta
