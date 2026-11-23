"""Facts for the chat reply, the yield log, and the yes/no proposals. All taken from the logs, never from memory."""
import json, time, datetime
from . import store, config as C, rule, subjects, vph as vphmod, board as boardmod


def two_source(st, con):
    """Every name must have returned rows from at least two independent sources."""
    weak = []
    for name in st["spec"].get("names") or [st["subject"]]:
        nw = set(w for w in subjects.words(name) if w not in subjects.STOP)
        src = set()
        for r in con.execute("SELECT tool, query, rows FROM searches WHERE run=? AND kind='keyword' AND rows>0", (st["run"],)):
            if nw & set(subjects.words(r["query"])):
                src.add({"algrow": "Algrow", "tubeai": "TubeAI", "vidiq": "vidIQ", "youtube": "YouTube"}.get(r["tool"], r["tool"]))
        if len(src) < 2:
            weak.append((name, sorted(src)))
    return weak


def facts(st, con, brd, fails=None, warns=None):
    run = st["run"]
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0]
    cards = [c for s in brd["sections"] if s["key"] not in ("combos", "ideas") for c in s["items"]]
    per = {s["key"]: len(s["items"]) for s in brd["sections"]}
    checked = q("SELECT COUNT(DISTINCT h.video_id) FROM hits h JOIN searches s ON s.id=h.search_id WHERE s.cache_key IN (SELECT cache_key FROM searches WHERE run=?)", run)
    verified = q("SELECT COUNT(*) FROM videos WHERE yt_checked_at>=? AND yt_status='ok'", st["started_at"])
    labeled = {r["label"]: r["c"] for r in con.execute("SELECT label, COUNT(*) c FROM labels WHERE subject=? AND ts>=? GROUP BY label", (st["subject"], st["started_at"]))}
    new_ids = {r["id"] for r in con.execute("SELECT id FROM videos WHERE first_run=?", (run,))}
    main = [c for c in cards if c["no"] and c.get("niche") is None and c.get("pattern") is None]
    finds = sorted([c for c in main if c["vid"] in new_ids] or main, key=lambda c: -(c["views"] or 0))[:3]
    calls = {r["server"]: dict(r) for r in con.execute("SELECT server, COUNT(*) n, SUM(ok=0) bad, SUM(credits) credits FROM tool_calls WHERE run=? GROUP BY server", (run,))}
    errs = [dict(r) for r in con.execute("SELECT tool, kind, query, error FROM searches WHERE run=? AND status='error'", (run,))]
    zero = [dict(r) for r in con.execute("SELECT tool, query, window_days FROM searches WHERE run=? AND kind='keyword' AND status='ok' AND rows=0", (run,))]
    vph_real = sum(1 for c in cards if c["vph"] is not None)
    vph_src = {}
    for c in cards:
        vph_src[c["vph_src"] or "n/a"] = vph_src.get(c["vph_src"] or "n/a", 0) + 1
    known = boardmod.known_outlier_report(st, con, brd)
    hook_err = (store.RUNS / "hook_errors.log")
    out = {
        "what_ran": {"subject": st["subject"], "names": st["spec"].get("names"), "window": f"{st['window_days']} days (18 months)" if st["window_days"] == 548 else f"{st['window_days']} days",
                     "first_line": st.get("first_line"), "minutes": round((time.time() - st["started_at"]) / 60, 1) if not st.get("from_store") else 0,
                     "stop": st.get("stop_reason")},
        "numbers": {"videos_checked": checked + len(st.get("extra_ids") or []), "verified_on_youtube": verified, "labeled_on": labeled.get("on", 0), "labeled_off": labeled.get("off", 0),
                    "borderline_left_off": labeled.get("borderline", 0), "cards_last_100_days": per.get("recent", 0), "cards_100_days_to_18_months": per.get("older", 0),
                    "cards_cross_niche": per.get("cross", 0), "combos": per.get("combos", 0), "ideas": per.get("ideas", 0), "cards_with_real_vph": f"{vph_real} of {len(cards)}", "vph_sources": vph_src,
                    "from_memory": st.get("memory_count", 0), "searches_reused_from_cache": st.get("cached_calls", 0)},
        "biggest_finds": [f"#{c['no']} {c['title']} · {c['channel']} · {c['views']:,} views · {c['mult']}x {c['mult_src']}" for c in finds],
        "budgets": {"TubeAI calls": f"{(calls.get('TubeAI') or {}).get('n', 0)} of {C.TUBEAI_PER_RUN}", "vidIQ credits": f"{int((calls.get('vidIQ') or {}).get('credits') or 0)} of {C.VIDIQ_CREDITS_PER_RUN}",
                    "Algrow calls": (calls.get("Algrow") or {}).get("n", 0), "paid Algrow overage": 0},
        "went_well": [], "didnt_work": [],
    }
    w, d = out["went_well"], out["didnt_work"]
    up = [k for k, v in st.get("tools", {}).items() if v == "up"]
    if up:
        w.append("Up for the whole run: " + ", ".join(up) + ".")
    if st.get("memory_count"):
        w.append(f"{st['memory_count']} videos came straight from memory before any search.")
    if st.get("cached_calls"):
        w.append(f"{st['cached_calls']} searches were answered from the 7 day cache and cost nothing.")
    if st.get("uploads_scanned"):
        w.append(f"Read the upload lists of {st['uploads_scanned']} pool and watch-list channels directly.")
    if (st.get("stop_reason") or "").startswith("dry"):
        w.append("Search stopped on " + st["stop_reason"] + ".")
    ok_known = sum(1 for k in known if k[1] != "MISS")
    if known:
        w.append(f"{ok_known} of {len(known)} known outliers are on the board or have a recorded reason.")
    ag = vphmod.agreement(con, [c["vid"] for c in cards])
    if ag:
        (w if ag["within_2x"] >= 0.7 else d).append(f"vidIQ views per hour vs Algrow's measured 24 hour gain on {ag['n']} videos: median ratio {ag['median_ratio']}, {int(ag['within_2x'] * 100)}% within 2x.")
    for k, v in st.get("tools", {}).items():
        if v != "up":
            d.append(f"{k} was {v}.")
    for server, c in calls.items():
        if c["bad"]:
            d.append(f"{server}: {c['bad']} of {c['n']} calls failed.")
    for e in errs[:12]:
        d.append(f"Failed search: {e['tool']} {e['kind']} '{e['query'][:50]}': {(e['error'] or '')[:100]}")
    if zero:
        d.append(f"{len(zero)} keyword searches returned nothing: " + "; ".join(f"{z['tool']} '{z['query']}' ({z['window_days']}d)" for z in zero[:10]))
    for name, src in two_source(st, con) if not st.get("from_store") else []:
        d.append(f"Two-source rule not met for '{name}': only {', '.join(src) or 'no source'} returned rows.")
    for n in st.get("notes", []):
        d.append(n)
    for r in brd.get("partial_reasons", []):
        d.append("PARTIAL: " + r + ".")
    na = [c for c in cards if c["vph"] is None]
    if na:
        d.append(f"{len(na)} cards show VPH n/a. First reasons: " + "; ".join(f"#{c['no']} {c.get('vph_why')}" for c in na[:3]))
    if labeled.get("borderline"):
        d.append(f"{labeled['borderline']} borderline videos were left off the board. Ask to see them.")
    for vid, status, reason in known:
        if status == "MISS":
            d.append(f"MISS: known outlier {vid} is not on the board and has no recorded reason. Trace it.")
    for f in fails or []:
        d.append("Check failed: " + f)
    for x in warns or []:
        d.append("Check warning: " + x)
    if hook_err.exists() and hook_err.stat().st_mtime >= st["started_at"]:
        d.append("The guard hook logged an internal error during this run. See runs/hook_errors.log.")
    if not d:
        d.append("Nothing failed in the logs for this run.")
    return out


def yield_rows(con, run=None):
    """What each search cost and what it found."""
    where, args = ("AND s.run=?", (run,)) if run else ("", ())
    sql = f"""SELECT s.tool, s.kind, s.query, COUNT(DISTINCT s.run) runs, COUNT(*) calls, SUM(s.rows) rows, SUM(s.new_outliers) new_outliers, SUM(s.credits) credits,
              (SELECT COUNT(DISTINCT h.video_id) FROM hits h JOIN searches s2 ON s2.id=h.search_id JOIN runs r ON r.id=s2.run
               JOIN labels l ON l.video_id=h.video_id AND l.subject=r.subject AND l.label='on'
               WHERE s2.tool=s.tool AND s2.kind=s.kind AND s2.query=s.query) on_topic
              FROM searches s WHERE s.status!='cached' AND s.run IS NOT NULL {where}
              GROUP BY s.tool, s.kind, s.query ORDER BY on_topic DESC, rows DESC"""
    return [dict(r) for r in con.execute(sql, args)]


def proposals(st, con, brd):
    """Changes Radar would like to make. Max answers yes or no to each; Radar writes the approved ones itself."""
    props = []
    subj = st["subject"]
    if subj not in subjects.topic_names() and st["spec"].get("names"):
        props.append({"kind": "topic_names", "text": f"Save the names for '{subj}': {', '.join(st['spec']['names'])}", "line": f"{subj}: {', '.join(st['spec']['names'])}"})
    wl = {h.lower() for hs in subjects.watchlist().values() for h in hs}
    wl_ids = {r["channel_id"] for r in con.execute("SELECT DISTINCT channel_id FROM videos WHERE lower(handle) IN (%s)" % ",".join("?" * len(wl)), list(wl))} if wl else set()
    by_ch = {}
    for s in brd["sections"]:
        if s["key"] in ("recent", "older"):
            for c in s["items"]:
                r = con.execute("SELECT channel_id, handle, channel FROM videos WHERE id=?", (c["vid"],)).fetchone()
                by_ch.setdefault(r["channel_id"], {"handle": r["handle"], "name": r["channel"], "n": 0})["n"] += 1
    pool = {r["channel_id"] for r in con.execute("SELECT channel_id FROM channels WHERE pool=1")}
    for cid, c in sorted(by_ch.items(), key=lambda x: -x[1]["n"]):
        if c["n"] >= 2 and c["handle"] and c["handle"].lower() not in wl and cid not in wl_ids:
            props.append({"kind": "watchlist", "text": f"Add {c['name']} ({c['handle']}) to the watch list: {c['n']} on-topic outliers this run", "handle": c["handle"], "channel_id": cid, "bucket": st["spec"].get("bucket") or "ALL"})
    newpool = [(cid, c) for cid, c in by_ch.items() if cid and cid not in pool]
    if newpool:
        props.append({"kind": "pool", "text": f"Add {len(newpool)} channels with on-topic outliers to the Algrow 'Radar pool' folder: " + ", ".join(c["name"] or "?" for _, c in newpool[:12]) + ("..." if len(newpool) > 12 else ""),
                      "channel_ids": [cid for cid, _ in newpool]})
    for y in yield_rows(con):
        if y["runs"] >= 3 and y["on_topic"] == 0 and y["kind"] == "keyword":
            props.append({"kind": "drop", "text": f"Drop the {y['tool']} search '{y['query']}': {y['runs']} runs, {y['rows']} rows, nothing on-topic", "tool": y["tool"], "query": y["query"]})
    for i, p in enumerate(props, 1):
        p["n"] = i
    (store.run_dir(st["run"]) / "proposals.json").write_text(json.dumps(props, indent=1))
    return props


def approve(run, numbers):
    """Write the approved changes. Only ever called after Max said yes to those numbers."""
    props = json.loads((store.run_dir(run) / "proposals.json").read_text())
    done, todo = [], []
    stamp = datetime.date.today().isoformat()
    for p in props:
        if p["n"] not in numbers:
            continue
        if p["kind"] == "topic_names":
            f = store.DATA / "topic_names.md"
            if not f.exists():
                f.write_text("# TOPIC NAMES\n\nOne line per subject: the subject, then every name people use for it in titles.\n\n")
            with open(f, "a") as fh:
                fh.write(p["line"] + "\n")
            done.append(p["text"])
        elif p["kind"] == "watchlist":
            f = store.DATA / "watchlist.md"
            txt = f.read_text()
            head = f"## {p['bucket']}"
            if head not in txt:
                head = "## ALL"
            txt = txt.replace(head + "\n", head + "\n" + p["handle"] + "\n", 1)
            f.write_text(txt)
            done.append(p["text"])
        elif p["kind"] == "pool":
            todo.append({"tool": "mcp__Algrow__save_channels", "input": {"folder": "Radar pool", "channel_ids": p["channel_ids"]}, "note": "Make this call to finish the pool addition."})
            done.append(p["text"] + " (call queued)")
        elif p["kind"] == "drop":
            con = store.db()
            d = store.kv_get(con, "dropped_searches", [])
            d.append({"tool": p["tool"], "query": p["query"], "date": stamp})
            store.kv_set(con, "dropped_searches", d)
            con.commit()
            done.append(p["text"])
    if done:
        with open(store.ROOT / "DECISIONS.md", "a") as fh:
            fh.write(f"\n## {stamp} (approved after run {run})\n" + "".join(f"- {d}\n" for d in done))
    return done, todo
