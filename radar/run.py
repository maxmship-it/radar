"""The run driver. Code decides what to search next. The model only makes the calls it is handed.

One pipeline for every kind of request. `start` opens a run (or queues it), `next` returns the next batch
of connector calls, or a labeling step, or 'done'. Everything is logged to memory as it happens.
"""
import json, time, datetime, re, concurrent.futures as cf
from . import store, config as C, rule, subjects, yt, ingest

BATCH = 10
PHASES = ["preflight", "free", "pool", "keyword", "label", "snowball", "label2", "rounds", "cross", "crosspick", "vph", "done"]
SUBJECT_KINDS = ("keyword", "like", "subject")


def _date(days):
    return (datetime.date.today() - datetime.timedelta(days=days)).isoformat()


def call(server, name, **inp):
    return {"tool": f"mcp__{server}__{name}", "input": inp}


def _key(c):
    s, n = c["tool"].split("__")[1:]
    return ingest.cache_key(s, n, c["input"])


# ---------- start / queue ----------
def start(spec):
    """spec: {subject, names[], algrow[], tubeai[], vidiq[], youtube[], bucket?, drafts[]?, window_days?}"""
    con = store.db()
    active = store.active_run()
    if active and store.run_state(active).get("phase") not in (None, "done"):
        q = store.kv_get(con, "queue", [])
        q.append(spec)
        store.kv_set(con, "queue", q)
        con.commit()
        return {"queued": True, "behind": active, "position": len(q),
                "say": f"Run '{active}' is still going. '{spec['subject']}' is queued and starts when it finishes. Runs never overlap."}
    slug = re.sub(r"[^a-z0-9]+", "-", spec["subject"].lower()).strip("-")
    run = f"{slug}-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}"
    for t in spec.get("tubeai", []):
        if len(t.split()) > 2:
            raise SystemExit(f"TubeAI term '{t}' is over two words. TubeAI returns nothing for long phrases.")
    st = {"run": run, "subject": spec["subject"].lower(), "spec": spec, "started_at": time.time(), "phase": "preflight",
          "queue": [], "emitted": [], "paged": [], "retried": [], "round": 0, "tools": {}, "notes": [], "extra_ids": [],
          "window_days": spec.get("window_days") or C.WINDOW_DAYS, "stop_reason": None, "round_counts": [], "used_terms": [],
          "label_checked": False}
    store.RUNS.mkdir(exist_ok=True)
    (store.RUNS / "ACTIVE").write_text(run)
    store.save_state(run, st)
    con.execute("INSERT OR REPLACE INTO runs(id,subject,names,window_days,started_at,status) VALUES(?,?,?,?,?,?)",
                (run, st["subject"], json.dumps(spec.get("names", [])), st["window_days"], st["started_at"], "running"))
    con.commit()
    return {"run": run, "say": f"Run {run} started. Call `python -m radar next` and make the calls it returns."}


def elapsed(st):
    return time.time() - st["started_at"]


def out_of_time(st):
    return elapsed(st) > C.TIME_BUDGET_S and not st.get("extra_time")


# ---------- phase builders ----------
def preflight_calls(st):
    return [call("vidIQ", "vidiq_balance"),
            call("TubeAI", "workspace_account"),
            call("Algrow", "get_folder", folder="Radar pool"),
            call("Algrow", "search_viral_videos", search="carnivore diet", content_type="longform", uploaded_within_days=30, min_outlier_score=2, min_video_views=50000, per_page=5),
            call("TubeAI", "explore_videos", search="carnivore", minDate=_date(30), minDuration=181, minOutlier=2, minViews=50000, limit=5,
                 fields=["video_id", "title", "view_count", "outlier_multiplier", "published_at", "channel_id", "channel_name", "channel_subscribers", "duration_seconds", "channel_niche"])]


def judge_preflight(st, con):
    """Each tool had one cheap search with a known answer. Down or thin tools are named in the first line to Max."""
    run = st["run"]
    for server, label in (("Algrow", "algrow"), ("TubeAI", "tubeai")):
        r = con.execute("SELECT COUNT(*) n, SUM(rows) rows, SUM(status='error') e FROM searches WHERE run=? AND tool=? AND kind='keyword'", (run, label)).fetchone()
        st["tools"][server] = "down" if (not r["n"] or r["e"] or not r["rows"]) else "up"
    b = con.execute("SELECT ok, note FROM tool_calls WHERE run=? AND tool='vidiq_balance' ORDER BY id DESC LIMIT 1", (run,)).fetchone()
    bal = None
    raw = sorted((store.run_dir(run) / "raw").glob("*vidiq_balance.json"))
    if raw:
        obj, _ = ingest.to_obj(json.loads(raw[-1].read_text())["response"])
        bal = (obj or {}).get("totalCredits") if isinstance(obj, dict) else None
    st["vidiq_balance"] = bal
    st["tools"]["vidIQ"] = "up" if (b and b["ok"] and (bal or 0) >= C.VIDIQ_CREDITS_PER_RUN) else "down"
    try:
        yt.guard()
        rows, err = yt.search("carnivore diet", "views_month", 5)
        st["tools"]["YouTube"] = "up" if rows else "down"
    except yt.NotCloud as e:
        st["tools"]["YouTube"] = "off"
        st["notes"].append(str(e))
    down = [k for k, v in st["tools"].items() if v != "up"]
    st["first_line"] = ("All four sources are up: Algrow, TubeAI, vidIQ, YouTube direct." if not down else
                        "DOWN at the start: " + ", ".join(down) + ". " +
                        ("TubeAI is down, so YouTube direct runs extra searches to cover 3 to 8 minute videos. " if "TubeAI" in down else "") +
                        "The run goes on with the rest.")


def free_phase(st, con):
    """Memory first, then everything free: YouTube's own search and the upload lists of the pool and watch list."""
    names = st["spec"].get("names") or [st["subject"]]
    win = st["window_days"]
    since = _date(win)
    ids = set()
    # 1. memory: every stored video on this subject inside the window. Found once, never lost.
    mem = [r["id"] for r in con.execute(
        "SELECT v.id FROM videos v JOIN labels l ON l.video_id=v.id WHERE l.subject=? AND l.label='on' AND (v.upload_date IS NULL OR v.upload_date>=?)", (st["subject"], since))]
    mem += [r["video_id"] for r in con.execute("SELECT video_id FROM known_outliers WHERE subject=?", (st["subject"],))]
    for r in con.execute("SELECT id, title FROM videos WHERE (upload_date IS NULL OR upload_date>=?) AND COALESCE(views,0)>=?", (since, C.MIN_SEARCH_VIEWS)):
        if subjects.matches(r["title"], names):
            mem.append(r["id"])
    ids.update(mem)
    st["memory_count"] = len(set(mem))
    if st["tools"].get("YouTube") != "up":
        st["notes"].append("YouTube direct did not run. REQUIRED STEP MISSED: the free sweep and the pool and watch-list upload scan.")
        st["yt_failed"] = True
        st["extra_ids"] = sorted(ids)
        return
    # 2. YouTube's own search, every name, sorted by views, three date ranges so recent videos are not crowded out
    queries = list(dict.fromkeys(st["spec"].get("youtube") or names))
    if st["tools"].get("TubeAI") != "up":
        queries += [f"{n} explained" for n in names[:3]] + [f"{n} truth" for n in names[:3]]
    def one(args):
        q, mode, depth = args
        rows, err = yt.search(q, mode, depth)
        return q, mode, rows, err
    jobs = [(q, m, d) for q in queries for m, d in (("views_month", 30), ("views_year", 50), ("views", 40))]
    with cf.ThreadPoolExecutor(6) as ex:
        results = list(ex.map(one, jobs))
    for q, mode, rows, err in results:
        cur = con.execute("INSERT INTO searches(run,tool,kind,query,params,window_days,page,ts,rows,status,error,cache_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                          (st["run"], "youtube", "keyword", q, json.dumps({"mode": mode}), {"views_month": 30, "views_year": 365, "views": 9999}[mode], 1, time.time(),
                           len(rows), "error" if err else "ok", err, f"yt:{q}:{mode}"))
        sid, new_v = cur.lastrowid, 0
        for i, r in enumerate(rows):
            if (r.get("views") or 0) < C.MIN_SEARCH_VIEWS or (r.get("duration_s") or 999) < rule.MIN_LONGFORM_S:
                continue
            if not subjects.matches(r.get("title"), names) or subjects.junk_reason(r):
                continue
            new_v += store.upsert_tool_row(con, r, st["run"], sid)
            con.execute("INSERT INTO hits(search_id,video_id,rank) VALUES(?,?,?)", (sid, r["id"], i + 1))
            ids.add(r["id"])
        con.execute("UPDATE searches SET new_videos=? WHERE id=?", (new_v, sid))
    con.commit()
    # 3. pool and watch list: read every channel's recent uploads and keep the ones on this subject.
    #    This is what catches the main competitors every time, whatever the search tools do.
    keys = {}
    for r in con.execute("SELECT channel_id FROM channels WHERE pool=1 AND channel_id IS NOT NULL"):
        keys[r["channel_id"]] = 60
    for bucket, handles in subjects.watchlist().items():
        for h in handles:
            keys[h] = 150
    def ups(kn):
        try:
            return kn[0], yt.channel_uploads(kn[0], kn[1])
        except Exception:
            return kn[0], []
    deadline = time.time() + 240
    scanned = found = 0
    with cf.ThreadPoolExecutor(10) as ex:
        for key, ups_ in ex.map(ups, keys.items()):
            scanned += 1 if ups_ else 0
            for u in ups_:
                if (u.get("views") or 0) >= C.MIN_SEARCH_VIEWS and (u.get("duration_s") or 999) >= rule.MIN_LONGFORM_S and subjects.matches(u.get("title"), names):
                    store.upsert_tool_row(con, {"id": u["id"], "title": u["title"], "views": u["views"], "duration_s": u["duration_s"],
                                                "channel_id": key if key.startswith("UC") else None, "tool": None}, st["run"], None)
                    ids.add(u["id"])
                    found += 1
    con.execute("INSERT INTO searches(run,tool,kind,query,params,window_days,page,ts,rows,new_videos,status,cache_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (st["run"], "youtube", "uploads", f"{len(keys)} pool and watch-list channels", "{}", win, 1, time.time(), found, 0, "ok" if scanned else "error", "yt:uploads"))
    st["uploads_scanned"] = scanned
    st["uploads_total"] = len(keys)
    if scanned < 0.8 * len(keys):
        st["notes"].append(f"Upload scan reached {scanned} of {len(keys)} pool and watch-list channels.")
    st["extra_ids"] = sorted(ids)
    con.commit()


def pool_calls(st):
    d = st["window_days"]
    return [call("Algrow", "folder_outliers", folder="Radar pool", days=d, limit=300, min_score=2, sort="views"),
            call("Algrow", "folder_outliers", folder="Radar pool", days=d, limit=300, min_score=3, sort="views"),
            call("Algrow", "folder_outliers", folder="Radar pool", days=C.RECENT_DAYS, limit=300, min_score=2, sort="views"),
            call("Algrow", "folder_outliers", folder="Radar pool", days=d, limit=200, min_score=5, sort="outlier")]


TUBE_FIELDS = ["video_id", "title", "view_count", "outlier_multiplier", "published_at", "channel_id", "channel_name", "channel_handle", "channel_subscribers", "duration_seconds", "channel_niche"]


def keyword_calls(st, algrow=None, tubeai=None, vidiq=None):
    """Each name twice: last 100 days and 18 months, so old big videos do not crowd recent ones out. Each tool in its own dialect."""
    sp, win, out = st["spec"], st["window_days"], []
    up = st["tools"]
    if up.get("Algrow") == "up":
        for q in (algrow if algrow is not None else sp.get("algrow") or sp.get("names") or []):
            for d in (C.RECENT_DAYS, win):
                out.append(call("Algrow", "search_viral_videos", search=q, content_type="longform", uploaded_within_days=d,
                                min_outlier_score=2, min_video_views=C.MIN_SEARCH_VIEWS, per_page=25, sort_by="similarity", page=1))
    if up.get("TubeAI") == "up":
        for q in (tubeai if tubeai is not None else sp.get("tubeai") or []):
            for d in (C.RECENT_DAYS, win):
                out.append(call("TubeAI", "explore_videos", search=q, minDate=_date(d), minDuration=181, minOutlier=2, minViews=C.MIN_SEARCH_VIEWS,
                                sortBy="view_count", limit=25, fields=TUBE_FIELDS))
    if up.get("vidIQ") == "up":
        for q in (vidiq if vidiq is not None else (sp.get("vidiq") or [])[:3]):
            for w in ("threeMonths", "twoYears"):
                out.append(call("vidIQ", "vidiq_outliers", keyword=q, contentType="long", publishedWithin=w, minViews=C.MIN_SEARCH_VIEWS, limit=50, language="en"))
    return out


def follow_ups(st, con):
    """Page until dry, and one retry for a search that errored. No fixed page cap short of MAX_PAGES."""
    out = []
    for r in con.execute("SELECT * FROM searches WHERE run=? AND status IN ('ok','degraded','error') AND tool IN ('algrow','tubeai') AND kind IN ('keyword','like','subject','format')", (st["run"],)):
        if r["id"] in st["paged"]:
            continue
        st["paged"].append(r["id"])
        inp = json.loads(r["params"] or "{}")
        server = "Algrow" if r["tool"] == "algrow" else "TubeAI"
        name = "search_viral_videos" if server == "Algrow" else "explore_videos"
        if r["status"] == "error":
            k = r["cache_key"]
            if k not in st["retried"]:
                st["retried"].append(k)
                out.append({"tool": f"mcp__{server}__{name}", "input": inp, "retry": True})
            else:
                st["notes"].append(f"{server} search '{r['query']}' failed twice: {(r['error'] or '')[:120]}")
            continue
        if r["status"] == "degraded" and r["cache_key"] not in st["retried"]:
            st["retried"].append(r["cache_key"])
            out.append({"tool": f"mcp__{server}__{name}", "input": inp, "retry": True})
            continue
        if r["kind"] == "format":
            continue
        if r["more"] and (r["new_outliers"] or 0) >= C.PAGE_DRY_BELOW:
            if (r["page"] or 1) >= C.MAX_PAGES:
                st["notes"].append(f"{server} '{r['query']}' was still finding new outliers at page {C.MAX_PAGES}, the safety cap.")
                continue
            if server == "Algrow":
                inp["page"] = (r["page"] or 1) + 1
            elif r["cursor"]:
                n_pages = con.execute("SELECT COUNT(*) c FROM searches WHERE run=? AND tool='tubeai' AND query=? AND window_days IS ?", (st["run"], r["query"], r["window_days"])).fetchone()["c"]
                if n_pages >= C.MAX_PAGES:
                    continue
                inp["cursor"] = r["cursor"]
                inp["page"] = (r["page"] or 1) + 1   # stripped again before the call; only for our own page count
            else:
                continue
            out.append({"tool": f"mcp__{server}__{name}", "input": inp})
    # a tool that keeps failing is dropped for the run and its queued calls with it
    for server in ("Algrow", "TubeAI", "vidIQ"):
        e = con.execute("SELECT SUM(ok=0) bad, COUNT(*) n FROM tool_calls WHERE run=? AND server=?", (st["run"], server)).fetchone()
        if st["tools"].get(server) == "up" and (e["bad"] or 0) >= 4 and (e["bad"] or 0) >= 0.5 * e["n"]:
            st["tools"][server] = "failing"
            st["queue"] = [c for c in st["queue"] if f"__{server}__" not in c["tool"]]
            st["notes"].append(f"{server} failed on {e['bad']} of {e['n']} calls and was dropped for the rest of the run.")
            out = [c for c in out if f"__{server}__" not in c["tool"]]
    return out


# hits of this run's searches, including searches answered from the 7 day cache
HITS = ("SELECT DISTINCT h.video_id id FROM hits h JOIN searches s ON s.id=h.search_id WHERE s.status IN ('ok','degraded') "
        "AND s.cache_key IN (SELECT cache_key FROM searches WHERE run=?)")


def candidate_ids(st, con, cross=False):
    """Videos this run should judge: what subject searches returned, plus title matches from the pool, uploads and memory."""
    run, names = st["run"], st["spec"].get("names") or [st["subject"]]
    if cross:
        q = (HITS + " AND (s.kind IN ('format','thumb') OR (s.kind='pool' AND s.query LIKE 'Radar cross-niche%'))")
        return [r["id"] for r in con.execute(q, (run,))]
    ids = set(st.get("extra_ids") or [])
    for r in con.execute(HITS + " AND s.kind IN ('keyword','like','subject') AND s.tool!='youtube'", (run,)):
        ids.add(r["id"])
    for r in con.execute(HITS.replace("h.video_id id", "v.id, v.title").replace("WHERE", "JOIN videos v ON v.id=h.video_id WHERE")
                         + " AND s.kind='pool' AND s.query NOT LIKE 'Radar cross-niche%'", (run,)):
        if subjects.matches(r["title"], names):
            ids.add(r["id"])
    return sorted(ids)


def qualifies(con, v, cross=False):
    m = store.mults(con, v["id"])
    return rule.best(m, v["views"], cross, v["duration_s"])


def verify_and_filter(st, con, cross=False, budget_s=420):
    """Check candidates on YouTube, work out recent-30 where no tool gave a multiplier, auto-label obvious junk.
    Returns how many still wait for YouTube (so a long list is finished over several `next` calls)."""
    ids = candidate_ids(st, con, cross)
    if not ids:
        return 0
    qm = ",".join("?" * len(ids))
    vids = {r["id"]: dict(r) for r in con.execute(f"SELECT * FROM videos WHERE id IN ({qm})", ids)}
    need = []
    for vid, v in vids.items():
        if v["yt_status"] in ("ok", "gone") and (v["yt_checked_at"] or 0) >= st["started_at"]:
            continue
        m = store.mults(con, vid)
        has_tool_pass = any((rule.cross_passes(x, v["views"], v["duration_s"]) if cross else rule.passes(x, v["views"])) for x in m.values())
        no_mult_yet = not m and (v["views"] or 0) >= C.MIN_SEARCH_VIEWS
        known = con.execute("SELECT 1 FROM known_outliers WHERE video_id=?", (vid,)).fetchone()
        if (has_tool_pass or no_mult_yet or known) and not subjects.junk_reason(v):
            need.append(vid)
    con.commit()
    if st["tools"].get("YouTube") != "up":
        return 0
    need.sort(key=lambda i: -(vids[i]["views"] or 0))
    yt.verify_many(need, threads=8, deadline=time.time() + budget_s)
    left = 0
    con2 = store.db()
    fresh = {r["id"]: dict(r) for r in con2.execute(f"SELECT * FROM videos WHERE id IN ({qm})", ids)}
    nomult = [i for i in need if fresh[i]["yt_status"] == "ok" and not any(rule.passes(x, fresh[i]["views"]) for x in store.mults(con2, i).values()) and (fresh[i]["views"] or 0) >= C.MIN_SEARCH_VIEWS]
    con2.close()
    if nomult and not cross:
        yt.add_recent30(nomult)
    for i in need:
        if not (fresh[i]["yt_status"] in ("ok", "gone") and (fresh[i]["yt_checked_at"] or 0) >= st["started_at"]):
            left += 1
    return left


def label_queue(st, con, cross=False):
    """Verified, rule-passing, non-junk candidates that have no label for this subject yet."""
    subj = "cross:" + st["subject"] if cross else st["subject"]
    out = []
    ids = candidate_ids(st, con, cross)
    if not ids:
        return out
    since = _date(C.CROSS_DAYS if cross else st["window_days"])
    for v in con.execute(f"SELECT * FROM videos WHERE id IN ({','.join('?' * len(ids))})", ids):
        v = dict(v)
        if v["yt_status"] != "ok" or (v["yt_checked_at"] or 0) < st["started_at"]:
            continue
        if con.execute("SELECT 1 FROM labels WHERE video_id=? AND subject=?", (v["id"], subj)).fetchone():
            continue
        if not v["upload_date"] or v["upload_date"] < since:
            continue
        b = qualifies(con, v, cross)
        if not b:
            continue
        j = subjects.junk_reason(v)
        if j:
            con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (v["id"], subj, "off", "junk filter: " + j, "code", time.time()))
            continue
        v["best"] = b
        out.append(v)
    con.commit()
    out.sort(key=lambda v: -(v["views"] or 0))
    return out


def on_topic(st, con):
    return [dict(r) for r in con.execute(
        "SELECT v.* FROM videos v JOIN labels l ON l.video_id=v.id WHERE l.subject=? AND l.label='on' AND v.yt_status='ok' ORDER BY v.views DESC", (st["subject"],))]


def snowball_calls(st, con):
    """Ask for videos like the top on-topic outliers. Never from an off-topic video."""
    tops = [v for v in on_topic(st, con) if qualifies(con, v)]
    st["snowballed"] = st.get("snowballed", [])
    out, win = [], st["window_days"]
    fresh = [v for v in tops if v["id"] not in st["snowballed"]]
    if st["tools"].get("Algrow") == "up":
        for v in fresh[:6]:
            out.append(call("Algrow", "search_viral_videos", video_url=f"https://www.youtube.com/watch?v={v['id']}", content_type="longform",
                            uploaded_within_days=win, min_video_views=C.MIN_SEARCH_VIEWS, per_page=25, page=1))
        tags = []
        for v in tops:
            if v.get("subject_tag") and v["subject_tag"] not in tags and v["subject_tag"] not in st["used_terms"]:
                tags.append(v["subject_tag"])
        for t in tags[:4]:
            st["used_terms"].append(t)
            out.append(call("Algrow", "search_viral_videos", subject=t, content_type="longform", uploaded_within_days=win, min_outlier_score=2,
                            min_video_views=C.MIN_SEARCH_VIEWS, sort_by="views", per_page=25, page=1))
    if st["tools"].get("vidIQ") == "up":
        for v in fresh[:2]:
            out.append(call("vidIQ", "vidiq_outliers", seedVideoId=v["id"], contentType="long", publishedWithin="twoYears", minViews=C.MIN_SEARCH_VIEWS, limit=50))
    st["snowballed"] += [v["id"] for v in fresh[:6]]
    return out


def channel_followup(st, con):
    """Creators repeat what works: read the uploads of every channel with an on-topic outlier."""
    if st["tools"].get("YouTube") != "up":
        return 0
    names = st["spec"].get("names") or [st["subject"]]
    done = set(st.get("followed", []))
    chans = [c for c in dict.fromkeys(v["channel_id"] for v in on_topic(st, con) if v["channel_id"] and qualifies(con, v)) if c not in done][:60]
    found = 0
    with cf.ThreadPoolExecutor(8) as ex:
        for key, ups in zip(chans, ex.map(lambda k: yt.channel_uploads(k, 120), chans)):
            for u in ups:
                if (u.get("views") or 0) >= C.MIN_SEARCH_VIEWS and (u.get("duration_s") or 999) >= rule.MIN_LONGFORM_S and subjects.matches(u.get("title"), names):
                    if u["id"] not in st["extra_ids"]:
                        store.upsert_tool_row(con, {"id": u["id"], "title": u["title"], "views": u["views"], "duration_s": u["duration_s"], "channel_id": key, "tool": None}, st["run"], None)
                        st["extra_ids"].append(u["id"])
                        found += 1
    st["followed"] = sorted(done | set(chans))
    con.commit()
    return found


def cross_calls(st, con):
    """Cross-niche, hard-capped at 15 calls, no paid calls. Format first, then the standing pool, then thumbnail lookalikes."""
    tops = [v for v in on_topic(st, con) if qualifies(con, v)][:3]
    out = []
    if st["tools"].get("Algrow") == "up":
        for v in tops:
            out.append(call("Algrow", "search_viral_videos", same_format_as=v["id"], content_type="longform", per_page=15))
        out.append(call("Algrow", "folder_outliers", folder="Radar cross-niche", days=C.CROSS_DAYS, limit=120, min_score=10, sort="views"))
        for v in tops:
            out.append(call("Algrow", "search_by_thumbnail", video_url=f"https://www.youtube.com/watch?v={v['id']}", min_views=200000, uploaded_within_days=C.CROSS_DAYS, limit=20))
    if st["tools"].get("TubeAI") == "up":
        for w in (st["spec"].get("format_words") or [])[:2]:
            out.append(call("TubeAI", "mini_titles", search=w, show=["formats"], sort="best_performing", limit=15))
    return out[:C.CROSS_MAX_CALLS]


def vph_calls(st, con):
    from . import vph
    ids = vph.need_lookup(st, con)
    out = []
    if st["tools"].get("vidIQ") in ("up", "failing") and ids:
        for i in range(0, len(ids), 50):
            out.append(call("vidIQ", "vidiq_get_videos_by_ids", videoIds=ids[i:i + 50]))
    return out


# ---------- the loop ----------
def _emit(st, calls, con=None):
    """Queue calls. A search that ran in the last 7 days for the same window is answered from memory, not called again."""
    seen = set(st["emitted"]) | {_key(c) + str(c["input"].get("cursor", "")) for c in st["queue"]}
    own = store.db() if con is None else con
    for c in calls:
        k = _key(c) + str(c["input"].get("cursor", ""))
        retry = c.pop("retry", False)
        if k in seen and not retry:
            continue
        seen.add(k)
        server, name = c["tool"].split("__")[1:]
        tool, kind, query = ingest.classify(server, name, c["input"])
        if not retry and not st.get("no_cache") and kind not in ("vph",) and name not in ("vidiq_balance", "workspace_account", "mini_titles"):
            r = own.execute("SELECT id, run, tool, kind, query, window_days FROM searches WHERE cache_key=? AND status='ok' AND ts>? AND run IS NOT ? ORDER BY ts DESC LIMIT 1",
                            (_key(c), time.time() - C.CACHE_DAYS * 86400, st["run"])).fetchone()
            if r:
                # reuse page 1 and every later page that search fetched
                for o in own.execute("SELECT cache_key, rows, page FROM searches WHERE run IS ? AND tool=? AND kind=? AND query=? AND window_days IS ? AND status='ok'",
                                     (r["run"], r["tool"], r["kind"], r["query"], r["window_days"])):
                    own.execute("INSERT INTO searches(run,tool,kind,query,params,window_days,page,ts,rows,new_videos,new_outliers,status,cache_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (st["run"], tool, kind, query, json.dumps(c["input"], sort_keys=True), r["window_days"], o["page"], time.time(), o["rows"], 0, 0, "cached", o["cache_key"]))
                st["cached_calls"] = st.get("cached_calls", 0) + 1
                st["emitted"].append(k)
                continue
        st["queue"].append(c)
    own.commit()
    if con is None:
        own.close()


def _pop(st):
    batch, st["queue"] = st["queue"][:BATCH], st["queue"][BATCH:]
    for c in batch:
        st["emitted"].append(_key(c) + str(c["input"].get("cursor", "")))
        c.pop("retry", None)
        if "TubeAI" in c["tool"]:
            c["input"].pop("page", None)
    return batch


def next_step():
    run = store.active_run()
    if not run:
        return {"action": "idle", "say": "No run is active. Start one with `python -m radar start`."}
    st = store.run_state(run)
    con = store.db()
    try:
        res = _advance(st, con)
    finally:
        store.save_state(run, st)
        con.commit()
        con.close()
    res.setdefault("phase", st["phase"])
    res["minutes_used"] = round(elapsed(st) / 60, 1)
    res["minutes_budget"] = C.TIME_BUDGET_S // 60
    return res


def _goto(st, phase):
    st["phase"] = phase


def _advance(st, con):
    while True:
        ph = st["phase"]
        if ph == "done":
            return {"action": "done", "say": "Searching is finished. Next: `python -m radar combos-help`, write the combos, then `python -m radar board`."}
        # out of time: drop what is queued, say so, and finish with what we have
        if out_of_time(st) and ph in ("free", "pool", "keyword", "snowball", "rounds") and not st.get("stop_reason"):
            dropped = len(st["queue"])
            st["queue"] = []
            st["stop_reason"] = f"time budget ({C.TIME_BUDGET_S // 60} minutes) ran out during the {ph} step with {dropped} searches not run"
            st["notes"].append("Stopped on the time budget, not on dry results. " + st["stop_reason"])
            _goto(st, "label2")
            continue
        if ph not in ("preflight",):
            _emit(st, follow_ups(st, con), con)
        if st["queue"]:
            return {"action": "call", "calls": _pop(st), "say": "Make every call below exactly as written. Results are captured by code. Then run `python -m radar next` again."}
        if ph == "preflight":
            if not st.get("preflight_sent"):
                st["preflight_sent"] = True
                st["phase_flag"] = "preflight"
                st["no_cache"] = True
                st["queue"] = preflight_calls(st)
                store.save_state(st["run"], st)
                continue
            st["no_cache"] = False
            judge_preflight(st, con)
            _goto(st, "free")
            return {"action": "say", "say": st["first_line"] + " Tell Max this line now, then run `python -m radar next`."}
        if ph == "free":
            free_phase(st, con)
            _goto(st, "pool")
            continue
        if ph == "pool":
            _goto(st, "keyword")
            if st["tools"].get("Algrow") == "up":
                _emit(st, pool_calls(st), con)
            else:
                st["notes"].append("REQUIRED STEP MISSED: Algrow pool scan and Algrow keyword search (Algrow was down).")
            _emit(st, keyword_calls(st), con)
            st["used_terms"] += (st["spec"].get("algrow") or []) + (st["spec"].get("tubeai") or []) + (st["spec"].get("names") or [])
            continue
        if ph in ("keyword", "snowball_wait", "rounds_wait"):
            left = verify_and_filter(st, con)
            if left and not out_of_time(st):
                return {"action": "say", "say": f"{left} candidates still being checked on YouTube. Run `python -m radar next` again."}
            q = label_queue(st, con)
            nxt = {"keyword": "snowball", "snowball_wait": "rounds", "rounds_wait": "rounds"}[ph]
            st["after_label"] = nxt
            if q:
                _goto(st, "labeling")
                return {"action": "label", "count": len(q), "say": f"{len(q)} candidates need an on-topic label. Run `python -m radar label-queue`, write the labels file, run `python -m radar label-import <file>`, then `python -m radar next`."}
            _goto(st, nxt)
            continue
        if ph == "labeling":
            q = label_queue(st, con)
            if q:
                return {"action": "label", "count": len(q), "say": f"{len(q)} candidates still have no label. Label them all, then run next."}
            _goto(st, st.get("after_label") or "snowball")
            continue
        if ph == "snowball":
            n_on = len([v for v in on_topic(st, con) if qualifies(con, v)])
            st["round_counts"].append(n_on)
            _emit(st, snowball_calls(st, con), con)
            found = channel_followup(st, con)
            st["notes_followup"] = found
            _goto(st, "snowball_wait")
            continue
        if ph == "rounds":
            n_on = len([v for v in on_topic(st, con) if qualifies(con, v)])
            prev = st["round_counts"][-1] if st["round_counts"] else 0
            added = n_on - prev
            st["round_counts"].append(n_on)
            st["round"] += 1
            if st["round"] > 1 and added < C.ROUND_DRY_BELOW:
                st["stop_reason"] = f"dry results: round {st['round'] - 1} added {added} new on-topic outliers"
                _goto(st, "label2")
                continue
            if st["round"] > 5:
                st["stop_reason"] = "round limit (5) reached while rounds were still finding new outliers"
                st["notes"].append("Stopped at the 5 round limit, not on dry results.")
                _goto(st, "label2")
                continue
            terms = subjects.new_terms([v["title"] for v in on_topic(st, con)], st["used_terms"], 6)
            st["used_terms"] += terms
            if not terms:
                st["stop_reason"] = "dry results: the outlier titles hold no search words that have not been searched"
                _goto(st, "label2")
                continue
            st["round_terms"] = st.get("round_terms", []) + [terms]
            _emit(st, keyword_calls(st, algrow=terms, tubeai=[t for t in terms if len(t.split()) <= 2][:4], vidiq=[]), con)
            _emit(st, snowball_calls(st, con), con)
            channel_followup(st, con)
            _goto(st, "rounds_wait")
            continue
        if ph == "label2":
            left = verify_and_filter(st, con)
            q = label_queue(st, con)
            if q:
                st["after_label"] = "label2"
                _goto(st, "labeling")
                return {"action": "label", "count": len(q), "say": f"{len(q)} last candidates need a label. `python -m radar label-queue`, then label-import, then next."}
            if not st["label_checked"]:
                return {"action": "label-check", "say": "Second pass: run `python -m radar label-check`, re-judge those 20 highest-view videos with fresh eyes, import any changes with `python -m radar label-import <file> --check`, then `python -m radar next`. If none change, run `python -m radar label-import --check-ok`."}
            _goto(st, "cross")
            continue
        if ph == "cross":
            _goto(st, "crosspick")
            if st["spec"].get("cross", True):
                _emit(st, cross_calls(st, con), con)
            continue
        if ph == "crosspick":
            verify_and_filter(st, con, cross=True, budget_s=180)
            q = label_queue(st, con, cross=True)
            _goto(st, "vph")
            if q:
                return {"action": "cross-pick", "count": len(q), "say": f"{len(q)} cross-niche videos pass the bar. Run `python -m radar cross-queue`, pick at most {C.CROSS_MAX_CARDS} whose title pattern or thumbnail idea transfers to this subject, import with `python -m radar cross-import <file>`, then next. If none transfer, just run next."}
            continue
        if ph == "vph":
            if not st.get("vph_sent"):
                st["vph_sent"] = True
                _emit(st, vph_calls(st, con), con)
                if st["queue"]:
                    continue
            _goto(st, "done")
            con.execute("UPDATE runs SET ended_at=?, status='searched', stop_reason=? WHERE id=?", (time.time(), st.get("stop_reason"), st["run"]))
            continue
        raise SystemExit(f"unknown phase {ph}")


def finish(run):
    """Close the run and start the next queued one, if any."""
    con = store.db()
    st = store.run_state(run)
    st["phase"] = "done"
    st["finished"] = True
    store.save_state(run, st)
    con.execute("UPDATE runs SET status='done', ended_at=COALESCE(ended_at,?) WHERE id=?", (time.time(), run))
    q = store.kv_get(con, "queue", [])
    nxt = None
    if q:
        spec = q.pop(0)
        store.kv_set(con, "queue", q)
        con.commit()
        (store.RUNS / "ACTIVE").write_text("")
        nxt = start(spec)
    else:
        (store.RUNS / "ACTIVE").write_text("")
        con.commit()
    return nxt
