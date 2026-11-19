#!/usr/bin/env python3
"""Runs before and after every Algrow, TubeAI and vidIQ call made inside the Radar project.

before: refuses tools Radar must never use, dead routes, repeats of cached searches, anything over a
        budget or past the time limit, and paces Algrow under its per-minute limit.
after:  saves the raw result to disk, files the rows into memory, and hands the model a short
        receipt in place of the rows. Rows never pass through a model.
"""
import sys, json, time, os, re, fcntl, pathlib, traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from radar import store, config as C, ingest, rule  # noqa: E402

SEARCH_KINDS = {"keyword", "like", "subject", "format", "channel", "pool", "poolshort", "similar", "browse", "thumb", "ytsearch"}


def out(obj):
    sys.stdout.write(json.dumps(obj))
    sys.exit(0)


def deny(reason):
    out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                "permissionDecisionReason": "RADAR GUARD: " + reason}})


def log_err(where):
    try:
        with open(store.RUNS / "hook_errors.log", "a") as f:
            f.write(f"{time.strftime('%F %T')} {where}\n{traceback.format_exc()}\n")
    except Exception:
        pass


def split(tool_name):
    m = re.match(r"^mcp__(.+?)__(.+)$", tool_name or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def pace_algrow():
    """One shared limiter for everything running at once. Sleeps, never drops."""
    p = store.RUNS / ".limiter.json"
    store.RUNS.mkdir(exist_ok=True)
    with open(store.RUNS / ".limiter.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            ts = json.loads(p.read_text()) if p.exists() else []
        except Exception:
            ts = []
        now = time.time()
        ts = [t for t in ts if now - t < 60]
        if len(ts) >= C.ALGROW_PER_MIN:
            wait = 60 - (now - ts[0]) + 0.5
            time.sleep(max(0, min(wait, 70)))
            now = time.time()
            ts = [t for t in ts if now - t < 60]
        ts.append(now)
        p.write_text(json.dumps(ts))


def pre(d):
    server, name = split(d.get("tool_name"))
    inp = d.get("tool_input") or {}
    if server not in C.ALLOW:
        return
    if name not in C.ALLOW[server]:
        deny(f"{server} {name} is not a tool Radar uses. Radar only searches and reads. It never generates, edits, posts, deletes or changes folders.")
    run = store.active_run()
    con = store.db()
    tool, kind, query = ingest.classify(server, name, inp)
    # folders: only Radar's own two folders, never anything else
    if name in ("save_channels", "create_folder", "get_folder", "folder_outliers"):
        f = str(inp.get("folder") or inp.get("name") or inp.get("folder_name") or "")
        if name in ("save_channels", "create_folder") and f not in C.RADAR_FOLDERS:
            deny(f"Radar may only add to its own folders {sorted(C.RADAR_FOLDERS)}. Got '{f}'.")
    # dead routes
    if name == "search_by_thumbnail" and not (inp.get("video_url") or inp.get("image_url")):
        deny("Algrow thumbnail search by text description has returned nothing in 34 tries. Pass video_url instead.")
    if server == "TubeAI" and name == "explore_videos" and inp.get("search"):
        if len(str(inp["search"]).split()) > 2:
            deny("TubeAI returns nothing for long phrases. Use one or two words.")
        if int(inp.get("limit") or 50) > 25:
            deny("TubeAI keyword pages over 25 fail with a memory or time error. Set limit to 25 or less.")
    if name == "search_longform_channels" and inp.get("demonetized"):
        deny("That search costs $0.20. Radar never makes paid Algrow calls.")
    st = store.run_state(run) if run else {}
    # stopped tools (credit, quota or billing warning seen earlier in this run)
    if server in (st.get("stopped_tools") or {}):
        deny(f"{server} was stopped for this run: {st['stopped_tools'][server]}")
    # time budget
    if run and st.get("started_at") and name not in C.FINISHING_TOOLS and kind in SEARCH_KINDS:
        if time.time() - st["started_at"] > C.TIME_BUDGET_S and not st.get("extra_time"):
            deny("The 30 minute time budget for this run is used up. Stop searching and build the board with what you have.")
    # budgets
    day0 = time.time() - 86400
    if server == "TubeAI":
        n_run = con.execute("SELECT COUNT(*) c FROM tool_calls WHERE server='TubeAI' AND run IS ?", (run,)).fetchone()["c"]
        n_day = con.execute("SELECT COUNT(*) c FROM tool_calls WHERE server='TubeAI' AND ts>?", (day0,)).fetchone()["c"]
        if n_run >= C.TUBEAI_PER_RUN or n_day >= C.TUBEAI_PER_DAY:
            deny(f"TubeAI budget reached ({n_run} this run, {n_day} today).")
    if server == "vidIQ" and name != "vidiq_balance":
        spent = con.execute("SELECT COALESCE(SUM(credits),0) c FROM tool_calls WHERE server='vidIQ' AND run IS ? AND ts>?", (run, day0)).fetchone()["c"]
        if spent + C.VIDIQ_CALL_COST > C.VIDIQ_CREDITS_PER_RUN:
            deny(f"vidIQ budget reached: {int(spent)} of {C.VIDIQ_CREDITS_PER_RUN} credits used this run.")
    if name == "search_by_thumbnail":
        n = con.execute("SELECT COUNT(*) c FROM tool_calls WHERE tool='search_by_thumbnail' AND ts>?", (day0,)).fetchone()["c"]
        if n >= C.ALGROW_THUMB_PER_DAY:
            deny(f"Algrow thumbnail searches today: {n}. The free cap is 40 and Radar stops at {C.ALGROW_THUMB_PER_DAY}.")
    # cache: the same search in the same window inside 7 days is never paid for twice
    if kind in SEARCH_KINDS and not os.environ.get("RADAR_NOCACHE") and not st.get("no_cache"):
        key = ingest.cache_key(server, name, inp)
        r = con.execute("SELECT id, ts, rows, run FROM searches WHERE cache_key=? AND status='ok' AND ts>? ORDER BY ts DESC LIMIT 1",
                        (key, time.time() - C.CACHE_DAYS * 86400)).fetchone()
        if r:
            if run:
                con.execute("INSERT INTO searches(run,tool,kind,query,params,window_days,page,ts,rows,new_videos,new_outliers,status,cache_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (run, tool, kind, query, json.dumps(inp, sort_keys=True), ingest.window_of(server, name, inp), int(inp.get("page") or 1), time.time(), r["rows"], 0, 0, "cached", key))
                con.commit()
            hrs = (time.time() - r["ts"]) / 3600
            deny(f"CACHED. This exact search ran {hrs:.0f}h ago (run {r['run']}) and returned {r['rows']} rows that are already in memory. No call needed. Move on.")
    if server == "Algrow":
        pace_algrow()
    con.close()


def post(d):
    server, name = split(d.get("tool_name"))
    if server not in C.ALLOW:
        return
    inp = d.get("tool_input") or {}
    resp = d.get("tool_response")
    run = store.active_run()
    rd = store.run_dir(run)
    n = len(list((rd / "raw").glob("*.json"))) + 1
    raw_path = rd / "raw" / f"{n:04d}_{server}_{name}.json"
    raw_path.write_text(json.dumps({"ts": time.time(), "tool": d.get("tool_name"), "input": inp, "response": resp, "ms": d.get("duration_ms")}))
    rows, meta = ingest.normalize(server, name, inp, resp)
    con = store.db()
    credits = C.VIDIQ_CALL_COST if (server == "vidIQ" and name != "vidiq_balance") else 0
    con.execute("INSERT INTO tool_calls(run,ts,server,tool,ok,credits,note) VALUES(?,?,?,?,?,?,?)",
                (run, time.time(), server, name, 0 if meta["error"] else 1, credits, (meta["error"] or "; ".join(meta["notices"]))[:300]))
    kind, tool = meta["kind"], meta["tool"]
    is_search = kind in SEARCH_KINDS
    summary = None
    if is_search or kind == "vph":
        cur = con.execute("INSERT INTO searches(run,tool,kind,query,params,window_days,page,ts,rows,status,error,raw_path,cache_key,credits,more,cursor) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (run, tool, kind, meta["query"], json.dumps(inp, sort_keys=True), ingest.window_of(server, name, inp), meta["page"], time.time(), len(rows),
                           "error" if meta["error"] else ("degraded" if "degraded" in meta["notices"] or "incomplete" in meta["notices"] else "ok"),
                           meta["error"], str(raw_path.relative_to(store.ROOT)), ingest.cache_key(server, name, inp), credits, 1 if meta["more"] else 0, meta["cursor"]))
        sid = cur.lastrowid
        new_v = new_o = passing = 0
        cross = bool((store.run_state(run) if run else {}).get("cross_mode"))
        for r in rows:
            seen_run = con.execute("SELECT 1 FROM hits h JOIN searches s ON s.id=h.search_id WHERE h.video_id=? AND s.run IS ? LIMIT 1", (r["id"], run)).fetchone()
            was_new = store.upsert_tool_row(con, r, run, sid)
            con.execute("INSERT INTO hits(search_id,video_id,rank) VALUES(?,?,?)", (sid, r["id"], r.get("rank")))
            new_v += 1 if was_new else 0
            ok = rule.passes(r.get("mult"), r.get("views")) and (r.get("duration_s") is None or r["duration_s"] >= rule.MIN_LONGFORM_S)
            passing += 1 if ok else 0
            if ok and not seen_run:
                new_o += 1
        con.execute("UPDATE searches SET new_videos=?, new_outliers=? WHERE id=?", (new_v, new_o, sid))
        nxt = ""
        if meta["more"]:
            nxt = f" More results exist (next: {'cursor ' + str(meta['cursor']) if meta['cursor'] else 'page ' + str(meta['page'] + 1)})."
        summary = (f"RADAR RECEIPT: {len(rows)} rows filed from {tool} {kind} '{meta['query'][:60]}' page {meta['page']}. "
                   f"{new_v} new to memory, {passing} pass the outlier rule, {new_o} are new outliers for this run.{nxt}"
                   + (f" ERROR: {meta['error']}" if meta["error"] else "")
                   + (f" NOTICES: {'; '.join(meta['notices'])}" if meta["notices"] else "")
                   + " Rows are on disk and in memory. Do not retype them.")
    if name == "get_folder":
        obj, _ = ingest.to_obj(resp)
        chans = []

        def walk(o):
            if isinstance(o, list):
                for x in o:
                    walk(x)
            elif isinstance(o, dict):
                cid = o.get("channel_id") or o.get("id")
                if isinstance(cid, str) and cid.startswith("UC") and len(cid) == 24:
                    chans.append(o)
                else:
                    for v in o.values():
                        walk(v)
        walk(obj)
        folder = str(inp.get("folder"))
        cross = folder == "Radar cross-niche"
        for c in chans:
            cid = c.get("channel_id") or c.get("id")
            con.execute("INSERT OR IGNORE INTO channels(channel_id) VALUES(?)", (cid,))
            con.execute("UPDATE channels SET name=COALESCE(?,name), handle=COALESCE(?,handle), subs=COALESCE(?,subs), pool=CASE WHEN ? THEN pool ELSE 1 END, cross_niche=CASE WHEN ? THEN COALESCE(cross_niche,'yes') ELSE cross_niche END WHERE channel_id=?",
                        (c.get("name") or c.get("channel_name") or c.get("title"), c.get("handle") or c.get("channel_handle"),
                         c.get("subscriber_count") or c.get("subscribers"), cross, cross, cid))
        if chans:
            store.kv_set(con, f"folder_synced:{folder}", time.time())
        summary = f"RADAR RECEIPT: folder '{folder}' has {len(chans)} channels. All filed in memory."
    # a credit, quota or billing warning stops that tool for the run. A routine throttle does not.
    blob = " ".join(meta["notices"]) + " " + (meta["error"] or "")
    if run and re.search(r"credit_notice|billing|charged|\$0\.\d\d|quota exceeded|suspend", blob, re.I):
        st = store.run_state(run)
        st.setdefault("stopped_tools", {})[server] = blob[:200]
        store.save_state(run, st)
    con.commit()
    con.close()
    if summary and (run or name == "get_folder") and not os.environ.get("RADAR_SHOW_ROWS"):
        out({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedMCPToolOutput": summary}})


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)
    try:
        pre(data) if mode == "pre" else post(data)
    except SystemExit:
        raise
    except Exception:
        log_err(mode)
    sys.exit(0)
