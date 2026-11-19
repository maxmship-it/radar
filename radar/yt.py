"""YouTube direct, through yt-dlp. Free. No connector.

PRIVACY RULES (MAX DECIDED Nov 19, 2026), enforced here in code:
  - Only runs on a cloud server. On anyone's own computer it refuses, so YouTube never sees Max's IP.
  - Never signs in. Never loads cookies or a browser profile. Nothing ties a request to an account.
"""
import os, re, json, time, statistics, urllib.parse, urllib.request, concurrent.futures as cf
from . import store, rule

SP = {  # YouTube search filters
    "views": "CAM%3D",              # sort by view count, any date
    "views_year": "CAMSBAgFEAE%3D",   # videos from this year, sort by view count
    "views_month": "CAMSBAgEEAE%3D",  # videos from this month, sort by view count
    "relevance": "EgIQAQ%3D%3D",    # videos only
}
BANNED_OPTS = ("cookiefile", "cookiesfrombrowser", "username", "password", "netrc", "usenetrc")


class NotCloud(RuntimeError):
    pass


def guard():
    if not any(k.startswith("CLAUDE_CODE_REMOTE") for k in os.environ):
        raise NotCloud("Radar only searches YouTube from a cloud session, so YouTube never sees Max's own IP. "
                       "This is not a cloud session, so YouTube-direct is switched off here.")


CLIENTS = [None, "tv", "web_safari", "mweb", "web_embedded"]   # tried in order; all signed out


def _ydl(flat=False, playlistend=None, client=None):
    guard()
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "ignore_no_formats_error": True,
            "socket_timeout": 20, "retries": 2, "extractor_retries": 2, "noprogress": True,
            "cachedir": False, "ignoreerrors": False,
            "extractor_args": {"youtube": {"skip": ["hls", "dash", "translated_subs"]}}}
    if flat:
        opts["extract_flat"] = True
    if playlistend:
        opts["playlistend"] = playlistend
    if client:
        opts["extractor_args"] = {"youtube": {"skip": ["hls", "dash", "translated_subs"], "player_client": [client]}}
    assert not any(k in opts for k in BANNED_OPTS)
    return yt_dlp.YoutubeDL(opts)


EN_WORDS = set("the and you your this that with for what why how are is to of in on i my we our it from can will have has not if".split())


def detect_language(info):
    """From YouTube's own data, never from the title a search tool returned (YouTube auto-translates titles).
    Best evidence first: the audio track, then the speech-recognition language, then the creator's own description."""
    lang = (info.get("language") or "").lower()
    if lang:
        return ("en" if lang.startswith("en") else lang.split("-")[0]), f"audio language {info.get('language')}"
    auto = list((info.get("automatic_captions") or {}).keys())
    orig = [k[:-5] for k in auto if k.endswith("-orig")]
    if orig:
        return ("en" if orig[0].lower().startswith("en") else orig[0].split("-")[0]), f"speech recognised as {orig[0]}"
    desc = (info.get("description") or "")[:800]
    text = f"{info.get('title') or ''} {desc}"
    letters = [c for c in text if c.isalpha()]
    if letters:
        non_latin = sum(1 for c in letters if ord(c) > 0x24F) / len(letters)
        if non_latin > 0.2:
            return "xx", f"{non_latin:.0%} non-Latin letters in title and description"
    dw = re.findall(r"[a-zA-Z\u00c0-\u00ff']+", desc.lower())
    if len(dw) >= 20:
        share = sum(1 for w in dw if w in EN_WORDS) / len(dw)
        if share < 0.10:
            return "xx", f"the creator's description is not English ({share:.0%} common English words)"
        return "en", "audio language not given by YouTube; the creator's description is in English"
    return "unknown", "YouTube gave no audio language and the description is too short to tell"


def _one(vid):
    """One video, signed out. If YouTube limits one client for this server, the next client is tried."""
    url = f"https://www.youtube.com/watch?v={vid}"
    last, best, lang_seen = None, None, None
    for attempt, client in enumerate(CLIENTS):
        try:
            with _ydl(client=client) as y:
                info = y.extract_info(url, download=False)
            if info.get("view_count") is None and not (info.get("channel") or info.get("uploader")):
                if not exists(vid):
                    return {"id": vid, "status": "gone", "error": "YouTube has no video with this id"}
                last = "empty result"
                continue
            lang, note = detect_language(info)
            if info.get("language") and not lang_seen:
                lang_seen = (lang, note)
            res = {"id": vid, "status": "ok", "title": info.get("title"), "views": info.get("view_count"),
                   "duration_s": info.get("duration"), "upload_date": store.norm_date(info.get("upload_date")),
                   "channel": info.get("channel") or info.get("uploader"), "channel_id": info.get("channel_id"),
                   "handle": info.get("uploader_id"), "subs": info.get("channel_follower_count"),
                   "language": lang, "lang_note": note,
                   "live": 1 if info.get("live_status") in ("was_live", "is_live", "post_live", "is_upcoming") else 0}
            if lang_seen:
                res["language"], res["lang_note"] = lang_seen
            if res["duration_s"] and res["views"] is not None and res["upload_date"]:
                return res
            if best is None or sum(v is not None for v in res.values()) > sum(v is not None for v in best.values()):
                best = res
        except NotCloud:
            raise
        except Exception as e:
            last = str(e)
            low = last.lower()
            if any(p in low for p in ("private video", "video unavailable", "has been removed", "terminated", "not available", "does not exist", "members-only")):
                return {"id": vid, "status": "gone", "error": last[:200]}
            time.sleep(1)
    return {"id": vid, "status": "error", "error": (last or "YouTube returned partial data on every signed-out route")[:200]}


def verify_many(ids, threads=6, max_age_h=0, deadline=None):
    """Check every id on YouTube and write the real title, views, duration, date and channel to memory.
    Returns {id: status}. A made-up id comes back 'gone' and can never become a card."""
    guard()
    con = store.db()
    todo, out = [], {}
    for vid in dict.fromkeys(ids):
        r = con.execute("SELECT yt_status, yt_checked_at FROM videos WHERE id=?", (vid,)).fetchone()
        if r and max_age_h and r["yt_status"] in ("ok", "gone") and r["yt_checked_at"] and time.time() - r["yt_checked_at"] < max_age_h * 3600:
            out[vid] = r["yt_status"]
        else:
            todo.append(vid)
    con.close()
    with cf.ThreadPoolExecutor(threads) as ex:
        futs = {ex.submit(_one, v): v for v in todo}
        for f in cf.as_completed(futs):
            res = f.result()
            _write(res)
            out[res["id"]] = res["status"]
            if deadline and time.time() > deadline:
                for g in futs:
                    g.cancel()
                break
    for v in todo:
        out.setdefault(v, "error")
    # second look, one at a time, at anything YouTube answered only partly under load
    con = store.db()
    again = [r["id"] for r in con.execute(f"SELECT id FROM videos WHERE id IN ({','.join('?' * len(todo))}) AND yt_status='error'", todo)] if todo else []
    con.close()
    for v in again[:40]:
        if deadline and time.time() > deadline:
            break
        res = _one(v)
        if res["status"] != "error":
            _write(res)
            out[v] = res["status"]
    return out


def _write(res):
    con = store.db()
    vid = res["id"]
    if not con.execute("SELECT 1 FROM videos WHERE id=?", (vid,)).fetchone():
        con.execute("INSERT INTO videos(id, created_at) VALUES(?,?)", (vid, time.time()))
    if res["status"] == "ok":
        con.execute("UPDATE videos SET title=?, views=?, duration_s=?, upload_date=?, channel=?, channel_id=?, handle=?, subs=COALESCE(?,subs),"
                    " language=?, lang_note=?, live=?, yt_status='ok', yt_checked_at=? WHERE id=?",
                    (res["title"], res["views"], res["duration_s"], res["upload_date"], res["channel"], res["channel_id"], res["handle"],
                     res["subs"], res["language"], res["lang_note"], res["live"], time.time(), vid))
        if res["views"] is not None:
            con.execute("INSERT INTO snapshots(video_id,ts,views,source) VALUES(?,?,?,'youtube')", (vid, time.time(), res["views"]))
    else:
        con.execute("UPDATE videos SET yt_status=?, yt_checked_at=?, lang_note=? WHERE id=?", (res["status"], time.time(), res.get("error"), vid))
    con.commit()
    con.close()


def exists(vid):
    """Cheap check that a video id is real."""
    guard()
    try:
        u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}", safe="")
        return urllib.request.urlopen(u, timeout=10).status == 200
    except Exception:
        return False


def search(query, mode="views", depth=40):
    """YouTube's own search. Returns flat entries: id, title, views, duration_s, channel, channel_id."""
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query) + "&sp=" + SP[mode]
    try:
        with _ydl(flat=True, playlistend=depth) as y:
            d = y.extract_info(url, download=False)
    except NotCloud:
        raise
    except Exception as e:
        return [], str(e)[:200]
    rows = []
    for e in (d.get("entries") or []):
        if not e or not e.get("id") or len(e["id"]) != 11:
            continue
        rows.append({"id": e["id"], "title": e.get("title"), "views": e.get("view_count"), "duration_s": int(e["duration"]) if e.get("duration") else None,
                     "channel": e.get("channel") or e.get("uploader"), "channel_id": e.get("channel_id"), "tool": None})
    return rows, None


def fetch_uploads(key, n=31):
    """Network only, no database: safe to run in threads. key is a UC id or @handle."""
    url = f"https://www.youtube.com/channel/{key}/videos" if key.startswith("UC") else f"https://www.youtube.com/{key if key.startswith('@') else '@' + key}/videos"
    try:
        with _ydl(flat=True, playlistend=n) as y:
            d = y.extract_info(url, download=False)
    except NotCloud:
        raise
    except Exception:
        return None
    return [{"id": e["id"], "title": e.get("title"), "views": e.get("view_count"), "duration_s": int(e["duration"]) if e.get("duration") else None}
            for e in (d.get("entries") or []) if e and e.get("id")]


def uploads_many(want, threads=10, max_age_h=24, deadline=None):
    """want: {channel key: how many uploads}. Reads the day-old cache, fetches the rest in threads, writes in one place.
    Returns {key: [uploads]}; a key that could not be read is missing."""
    guard()
    con = store.db()
    out, todo = {}, []
    for key, n in want.items():
        rows = con.execute("SELECT video_id id, title, views, duration_s, ts FROM uploads WHERE channel_key=? ORDER BY pos", (key,)).fetchall()
        if rows and time.time() - rows[0]["ts"] < max_age_h * 3600 and len(rows) >= min(n, 25):
            out[key] = [dict(r) for r in rows]
        else:
            todo.append((key, n))
    con.close()
    got = {}
    ex = cf.ThreadPoolExecutor(threads)
    futs = {ex.submit(fetch_uploads, k, n): k for k, n in todo}
    try:
        for f in cf.as_completed(futs, timeout=max(5, deadline - time.time()) if deadline else None):
            got[futs[f]] = f.result()
    except cf.TimeoutError:
        pass
    ex.shutdown(wait=False, cancel_futures=True)
    con = store.db()
    for key, rows in got.items():
        if rows is None:
            continue
        con.execute("DELETE FROM uploads WHERE channel_key=?", (key,))
        for i, r in enumerate(rows):
            con.execute("INSERT OR REPLACE INTO uploads(channel_key,video_id,title,views,duration_s,pos,ts) VALUES(?,?,?,?,?,?,?)",
                        (key, r["id"], r["title"], r["views"], r["duration_s"], i, time.time()))
        out[key] = rows
    con.commit()
    con.close()
    return out


def recent30(vid, views, ups):
    """views / median views of the channel's last 30 other uploads. None when the channel has under 10 others."""
    others = [u["views"] for u in (ups or []) if u["id"] != vid and u.get("views")]
    if len(others) < 10 or not views:
        return None
    med = statistics.median(others[:30])
    return round(views / med, 2) if med else None


def add_recent30(ids, threads=8, deadline=None):
    """Work out recent-30 for these videos and save it as a multiplier. Channel lists are fetched once each."""
    guard()
    if not ids:
        return 0
    con = store.db()
    vids = [dict(r) for r in con.execute(f"SELECT id, views, channel_id FROM videos WHERE id IN ({','.join('?' * len(ids))})", list(ids))]
    con.close()
    ups = uploads_many({v["channel_id"]: 31 for v in vids if v["channel_id"]}, threads, deadline=deadline)
    con = store.db()
    n = 0
    for v in vids:
        m = recent30(v["id"], v["views"], ups.get(v["channel_id"]))
        if m is not None:
            con.execute("INSERT OR REPLACE INTO multipliers(video_id,tool,value,seen_at,run) VALUES(?,?,?,?,?)", (v["id"], "recent30", m, time.time(), store.active_run()))
            n += 1
    con.commit()
    con.close()
    return n
