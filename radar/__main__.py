"""python -m radar <command>. Every command prints JSON or plain lines for the model running Radar to act on."""
import sys, json, time, argparse, datetime, re, pathlib
from . import store, config as C, rule, subjects, run as runmod, board as boardmod, report, vph as vphmod


def jprint(o):
    print(json.dumps(o, indent=1, ensure_ascii=False))


def _st(run=None):
    run = run or store.active_run()
    if not run:
        raise SystemExit("No active run.")
    return store.run_state(run)


def _line(v, b=None):
    b = b or v.get("best")
    m = f"{b[1]:.1f}x {rule.TOOL_LABEL.get(b[0], b[0])}" if b else "-"
    return f"{v['id']}\t{(v['views'] or 0):>9,}\t{m:<16}\t{(v['channel'] or '')[:22]:<22}\t{v['title']}"


def cmd_start(a):
    spec = json.loads(pathlib.Path(a.spec).read_text()) if a.spec else {}
    if a.subject:
        spec["subject"] = a.subject
    tn = subjects.topic_names().get(spec["subject"].lower())
    if tn and not spec.get("names"):
        spec["names"] = tn
    spec.setdefault("names", [spec["subject"]])
    jprint(runmod.start(spec))


def cmd_next(a):
    jprint(runmod.next_step())


def cmd_label_queue(a):
    st = _st()
    con = store.db()
    q = runmod.label_queue(st, con, cross=a.cross)
    subj = st["subject"]
    if a.cross:
        print(f"# CROSS-NICHE picks for '{subj}'. Bar already applied in code: 10x+, 200,000+ views, 40 minutes or less, last 12 months.")
        print(f"# Pick at most {C.CROSS_MAX_CARDS}. A video only gets in if its title pattern or thumbnail idea transfers to Max's subject. Never pad.")
        print("# File format, one line per pick:  <id> TAB <niche> TAB <the pattern rewritten for Max's subject, one line>")
    else:
        print(f"# LABEL for subject '{subj}'. Names: {', '.join(st['spec'].get('names') or [])}")
        print("# The test: is this video ABOUT what Max asked for, under any of those names? Same broad area is not enough. When unsure, it is off.")
        print("# File format, one line per video:  <id> TAB <on|off|borderline> TAB <one-line reason>")
        print("# For a gaming, music, kids or other never-relevant CHANNEL, start the reason with 'junk channel' and code will drop that channel from now on.")
        mx = con.execute("SELECT v.title, l.label FROM labels l JOIN videos v ON v.id=l.video_id WHERE l.subject=? AND l.labeler='max' ORDER BY l.ts DESC LIMIT 12", (subj,)).fetchall()
        if mx:
            print("# Max's own calls on this subject (learn from them):")
            for r in mx:
                print(f"#   {r['label'].upper():<4} {r['title']}")
    print(f"# {len(q)} videos. Columns: id, views, multiplier, channel, title")
    for v in q[: a.limit]:
        print(_line(v))


def cmd_label_import(a):
    st = _st()
    con = store.db()
    subj = st["subject"]
    if a.check_ok:
        st["label_checked"] = True
        store.save_state(st["run"], st)
        print("Second pass recorded: no labels changed.")
        return
    n = bad = kept = 0
    for line in pathlib.Path(a.file).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            bad += 1
            continue
        vid, lab = parts[0].strip(), parts[1].strip().lower()
        reason = parts[2].strip() if len(parts) > 2 else ""
        if lab not in ("on", "off", "borderline") or not con.execute("SELECT 1 FROM videos WHERE id=?", (vid,)).fetchone():
            bad += 1   # an id that is not in memory is ignored: labels can never add a video
            continue
        cur = con.execute("SELECT labeler FROM labels WHERE video_id=? AND subject=?", (vid, subj)).fetchone()
        if cur and cur["labeler"] == "max":
            kept += 1  # Max's own call always stands
            continue
        con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (vid, subj, lab, reason, "check" if a.check else "model", time.time()))
        if lab == "off" and reason.lower().startswith("junk channel"):
            ch = con.execute("SELECT channel_id FROM videos WHERE id=?", (vid,)).fetchone()
            subjects.add_junk_channel(con, ch and ch["channel_id"])     # learned: this channel never needs a label again
        n += 1
    if a.check:
        st["label_checked"] = True
        store.save_state(st["run"], st)
    con.commit()
    print(f"{n} labels saved, {bad} lines ignored (bad format or unknown id), {kept} left as Max set them.")


def cmd_label_check(a):
    st = _st()
    con = store.db()
    rows = con.execute("SELECT v.*, l.label, l.reason FROM videos v JOIN labels l ON l.video_id=v.id WHERE l.subject=? AND l.labeler IN ('model','check') AND l.ts>=? ORDER BY v.views DESC LIMIT 20",
                       (st["subject"], st["started_at"])).fetchall()
    print(f"# SECOND PASS for '{st['subject']}'. These are the 20 highest-view videos labeled this run. A wrong call on a big video costs the most.")
    print("# Re-judge each one from scratch. To change one, put it in a file as <id> TAB <on|off|borderline> TAB <reason> and import with --check.")
    for r in rows:
        print(f"{r['id']}\t{r['label'].upper():<10}\t{(r['views'] or 0):>10,}\t{(r['channel'] or '')[:22]:<22}\t{r['title']}\t| {r['reason']}")


def cmd_cross_import(a):
    st = _st()
    con = store.db()
    subj = "cross:" + st["subject"]
    ok = {v["id"] for v in runmod.label_queue(st, con, cross=True)}
    n = 0
    for line in pathlib.Path(a.file).read_text().splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or parts[0].strip() not in ok or n >= C.CROSS_MAX_CARDS:
            continue
        con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (parts[0].strip(), subj, "on", f"{parts[1].strip()} | {parts[2].strip()}", "model", time.time()))
        n += 1
    con.commit()
    print(f"{n} cross-niche picks saved (cap {C.CROSS_MAX_CARDS}).")


def cmd_combos_help(a):
    st = _st()
    con = store.db()
    brd = boardmod.build(st, con)
    print("# Write runs/%s/combos.json: a list of up to 10 objects, best first:" % st["run"])
    print('#   {"title": "...", "thumb_words": "3 WORDS OR FEWER", "image_line": "his version of the image, under 100 characters", "model_vid": "<id of a card below>", "depends": "only if it needs the video to cover a specific point"}')
    print("# Rules: each combo is modeled on a real card below. Spread them across different outliers and formats. At least 3 from CROSS-NICHE when it has good ones.")
    print("# Sharpen Max's draft titles first if he gave any: %s" % json.dumps(st["spec"].get("drafts") or []))
    print("# Never hooks. No invented numbers (write [number]). No em dashes. Exposé titles never say carnivore. Fewer than 10 is fine; never pad.")
    print("# LOOK at the real thumbnails of the top cards before writing: boards/thumbs via `python -m radar thumbs`.")
    for s in brd["sections"]:
        if s["key"] == "combos":
            continue
        print(f"## {s['name']}")
        for c in s["items"][: (40 if s["key"] != "cross" else 8)]:
            print(f"{c['no']:>3}  {c['vid']}  {c['views']:>10,}  {c['mult']}x {c['mult_src']:<9}  {c['channel'][:20]:<20}  {c['title']}" + (f"   [{c['niche']}: {c['pattern']}]" if c.get("pattern") else ""))


def cmd_thumbs(a):
    """Save the real thumbnails of the top cards so the model can look at them before writing combos."""
    import urllib.request
    st = _st()
    con = store.db()
    brd = boardmod.build(st, con)
    d = store.run_dir(st["run"]) / "thumbs"
    d.mkdir(exist_ok=True)
    out = []
    cards = [c for s in brd["sections"] if s["key"] != "combos" for c in (s["items"][:a.n] if s["key"] != "cross" else s["items"])]
    for c in cards:
        p = d / f"{c['no']:03d}_{c['vid']}.jpg"
        if not p.exists():
            try:
                p.write_bytes(urllib.request.urlopen(f"https://i.ytimg.com/vi/{c['vid']}/mqdefault.jpg", timeout=10).read())
            except Exception:
                continue
        out.append(str(p))
    print("\n".join(out))


def cmd_board(a):
    from . import render
    con = store.db()
    if a.from_store:
        st = _from_store(a, con)
    else:
        st = _st(a.run)
    brd = boardmod.build(st, con)
    fails, warns = boardmod.validate(brd, con, st)
    bj = store.run_dir(st["run"]) / "board.json"
    bj.write_text(json.dumps(brd, indent=1))
    if fails and not a.force_preview:
        jprint({"built": False, "failures": fails, "warnings": warns, "say": "The validator stopped the build. Fix each failure, then run board again."})
        raise SystemExit(1)
    name = f"Radar-{re.sub(r'[^a-z0-9]+', '-', st['subject'])}-{datetime.date.today().isoformat()}"
    pdf = store.BOARDS / f"{name}.pdf"
    n = 2
    while pdf.exists() and not a.overwrite:
        pdf = store.BOARDS / f"{name}-{n}.pdf"
        n += 1
    res = render.render(brd, pdf)
    con.execute("UPDATE runs SET status='board', notes=? WHERE id=?", (json.dumps({"pdf": res["pdf"]}), st["run"]))
    con.commit()
    st["board_pdf"] = res["pdf"]
    store.save_state(st["run"], st)
    props = report.proposals(st, con, brd)
    jprint({"built": True, "pdf": res["pdf"], "html": res["html"], "pages": res["pages"], "previews": res["previews"], "warnings": warns,
            "missing_thumbnails": res["missing_thumbnails"], "partial": brd["partial_reasons"],
            "reply_facts": report.facts(st, con, brd, fails if a.force_preview else [], warns),
            "ask_max_yes_or_no": [f"{p['n']}. {p['text']}" for p in props],
            "say": "Look at the preview images (first, middle, last page). First must be outlier cards, last must be the combos. Send Max the PDF. "
                   "Write the chat reply from reply_facts in this order: what ran, the numbers, the 3 biggest finds, what went well, what didn't work, then the yes/no questions. "
                   "Never soften or drop a 'didnt_work' line. Then run `python -m radar finish`."})


def _from_store(a, con):
    """A board straight from memory, with no new searches."""
    from . import yt
    subj = a.subject.lower()
    days = a.days or C.WINDOW_DAYS
    run = f"store-{re.sub(r'[^a-z0-9]+', '-', subj)}-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}"
    st = {"run": run, "subject": subj, "subjects": [subj] + [s.lower() for s in (a.also or [])], "spec": {"names": subjects.topic_names().get(subj, [subj])},
          "started_at": time.time(), "window_days": days, "from_store": True, "label_checked": True, "phase": "done", "tools": {}, "notes": [], "extra_ids": []}
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    marks = ",".join("?" * len(st["subjects"]))
    ids = [r["video_id"] for r in con.execute(f"SELECT DISTINCT l.video_id FROM labels l JOIN videos v ON v.id=l.video_id WHERE l.subject IN ({marks}) AND l.label='on' AND (v.upload_date IS NULL OR v.upload_date>=?)", (*st["subjects"], since))]
    store.save_state(run, st)
    con.execute("INSERT OR REPLACE INTO runs(id,subject,names,window_days,started_at,status) VALUES(?,?,?,?,?,?)", (run, subj, json.dumps(st["spec"]["names"]), days, st["started_at"], "store"))
    con.commit()
    yt.verify_many(ids, threads=8)
    return st


def cmd_feedback(a):
    """Max goes through a board by voice: 'number 12 is great, 30 isn't relevant'. File lines: <card no> TAB <great|relevant|no> TAB <his words>."""
    con = store.db()
    run = a.run or con.execute("SELECT id FROM runs WHERE status IN ('board','done','store') ORDER BY started_at DESC LIMIT 1").fetchone()["id"]
    subj = con.execute("SELECT subject FROM runs WHERE id=?", (run,)).fetchone()["subject"]
    n, unknown = 0, []
    for line in pathlib.Path(a.file).read_text().splitlines():
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        no, verdict, note = int(parts[0]), parts[1].lower(), (parts[2] if len(parts) > 2 else "")
        c = con.execute("SELECT video_id, section FROM cards WHERE run=? AND card_no=?", (run, no)).fetchone()
        if not c or verdict not in ("great", "relevant", "no"):
            unknown.append(parts[0])
            continue
        vid = c["video_id"]
        con.execute("INSERT INTO feedback(run,card_no,video_id,verdict,note,ts) VALUES(?,?,?,?,?,?)", (run, no, vid, verdict, note, time.time()))
        s = ("cross:" if c["section"] == "cross" else "") + subj
        stamp = datetime.date.today().isoformat()
        if verdict == "no":
            con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (vid, s, "off", f"Max, {stamp}: not relevant. {note}", "max", time.time()))
        else:
            con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (vid, s, "on", f"Max, {stamp}: {verdict}. {note}", "max", time.time()))
            if verdict == "great" and c["section"] != "cross":
                con.execute("INSERT OR IGNORE INTO known_outliers(video_id,subject,source,note,added_at) VALUES(?,?,?,?,?)", (vid, subj, "max-feedback", note, time.time()))
        n += 1
    con.commit()
    print(f"{n} of Max's calls saved for run {run} ('{subj}'). His 'no' cards never return to this subject's board; his 'great' cards must be found by every future run."
          + (f" Card numbers not on that board: {', '.join(unknown)}." if unknown else ""))


def cmd_known(a):
    con = store.db()
    if a.add:
        for vid in a.add:
            vid = vid[-11:]
            con.execute("INSERT OR IGNORE INTO videos(id, created_at) VALUES(?,?)", (vid, time.time()))
            con.execute("INSERT OR REPLACE INTO known_outliers(video_id,subject,source,note,added_at) VALUES(?,?,?,?,?)", (vid, a.subject.lower(), a.source or "max", a.note or "", time.time()))
        con.commit()
    for r in con.execute("SELECT k.*, v.title FROM known_outliers k LEFT JOIN videos v ON v.id=k.video_id WHERE (? IS NULL OR k.subject=?)", (a.subject and a.subject.lower(), a.subject and a.subject.lower())):
        print(f"{r['subject']}\t{r['video_id']}\t{r['source']}\t{r['title'] or ''}")


def cmd_missed(a):
    """Max pasted a video Radar should have caught. Find where it was lost."""
    from . import yt
    con = store.db()
    vid = re.search(r"([A-Za-z0-9_-]{11})(?:[&?].*)?$", a.video).group(1)
    subj = a.subject.lower()
    names = subjects.topic_names().get(subj, [subj])
    yt.verify_many([vid])
    yt.add_recent30([vid])
    v = dict(con.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone())
    m = store.mults(con, vid)
    hits = con.execute("SELECT s.run, s.tool, s.kind, s.query, s.ts FROM hits h JOIN searches s ON s.id=h.search_id WHERE h.video_id=? ORDER BY s.ts", (vid,)).fetchall()
    lab = con.execute("SELECT * FROM labels WHERE video_id=? AND subject=?", (vid, subj)).fetchone()
    ch = con.execute("SELECT pool, watch FROM channels WHERE channel_id=?", (v["channel_id"],)).fetchone()
    wl = {h.lower() for hs in subjects.watchlist().values() for h in hs}
    age = store.age_days(v["upload_date"])
    cause = []
    if v["yt_status"] != "ok":
        cause.append("YouTube says the video is gone or could not be read")
    if not hits:
        cause.append("no search has ever returned it (not indexed by the tools, or no search term matched)")
    if not subjects.matches(v["title"], names):
        cause.append(f"its title matches none of the names for '{subj}' ({', '.join(names)}): a name is missing")
    if not (ch and ch["pool"]) and (v["handle"] or "").lower() not in wl:
        cause.append("its channel is not in the pool or on the watch list")
    if not rule.best(m, v["views"]):
        cause.append("it fails the outlier rule: " + (", ".join(f"{t} {x:.1f}x" for t, x in m.items()) or "no multiplier") + f" at {v['views']:,} views")
    if age is not None and age > C.WINDOW_DAYS:
        cause.append(f"it is outside the 18 month window ({age} days old)")
    if v["language"] != "en":
        cause.append(f"language check: {v['lang_note']}")
    if lab and lab["label"] != "on":
        cause.append(f"it was labeled {lab['label']}: {lab['reason']}")
    con.execute("INSERT OR REPLACE INTO known_outliers(video_id,subject,source,note,added_at) VALUES(?,?,?,?,?)", (vid, subj, "max-missed", "; ".join(cause)[:300], time.time()))
    con.commit()
    jprint({"video": {k: v[k] for k in ("id", "title", "channel", "handle", "views", "upload_date", "duration_s", "language")}, "multipliers": m,
            "seen_by": [dict(h) for h in hits][-8:], "where_it_was_lost": cause or ["nothing blocks it now: it qualifies and will be on the next board"],
            "done": f"Added to the known outliers for '{subj}'. Every future run must put it on the board or record why not.",
            "say": "Tell Max where it was lost in one or two lines. Fix the cause (a missing name goes to topic_names with his yes; a channel goes to the watch list with his yes), then rerun the one search that should have caught it."})


def cmd_add(a):
    from . import yt
    st = _st()
    con = store.db()
    vid = re.search(r"([A-Za-z0-9_-]{11})(?:[&?].*)?$", a.video).group(1)
    yt.verify_many([vid])
    yt.add_recent30([vid])
    con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (vid, st["subject"], "on", "Max asked to add it", "max", time.time()))
    con.execute("INSERT OR IGNORE INTO known_outliers(video_id,subject,source,note,added_at) VALUES(?,?,?,?,?)", (vid, st["subject"], "max-add", "", time.time()))
    if vid not in st["extra_ids"]:
        st["extra_ids"].append(vid)
    st["snowballed"] = [x for x in st.get("snowballed", []) if x != vid]
    store.save_state(st["run"], st)
    con.commit()
    v = con.execute("SELECT title, views FROM videos WHERE id=?", (vid,)).fetchone()
    print(f"Added {vid} ({v['title']}, {v['views']:,} views). It passes the rule: {bool(rule.best(store.mults(con, vid), v['views']))}. Run `python -m radar next` to snowball from it, then board.")


def cmd_status(a):
    con = store.db()
    run = store.active_run()
    out = {"active_run": run, "queue": [s["subject"] for s in store.kv_get(con, "queue", [])],
           "memory": {"videos": con.execute("SELECT COUNT(*) FROM videos").fetchone()[0], "searches": con.execute("SELECT COUNT(*) FROM searches").fetchone()[0],
                      "on_topic_labels": con.execute("SELECT COUNT(*) FROM labels WHERE label='on'").fetchone()[0], "known_outliers": con.execute("SELECT COUNT(*) FROM known_outliers").fetchone()[0],
                      "pool_channels": con.execute("SELECT COUNT(*) FROM channels WHERE pool=1").fetchone()[0]},
           "subjects": [dict(r) for r in con.execute("SELECT subject, SUM(label='on') on_topic, COUNT(*) judged FROM labels GROUP BY subject ORDER BY on_topic DESC LIMIT 40")]}
    if run:
        st = store.run_state(run)
        out["run"] = {"phase": st.get("phase"), "minutes": round((time.time() - st["started_at"]) / 60, 1), "queued_calls": len(st.get("queue", [])), "tools": st.get("tools"), "notes": st.get("notes")}
    jprint(out)


def cmd_yield(a):
    con = store.db()
    rows = report.yield_rows(con, a.run)
    print("tool\tkind\truns\tcalls\trows\tnew_outliers\ton_topic\tcredits\tquery")
    for r in rows[: a.limit]:
        print(f"{r['tool']}\t{r['kind']}\t{r['runs']}\t{r['calls']}\t{r['rows']}\t{r['new_outliers'] or 0}\t{r['on_topic']}\t{int(r['credits'] or 0)}\t{r['query'][:60]}")


def cmd_approve(a):
    run = a.run or store.db().execute("SELECT id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()["id"]
    done, todo = report.approve(run, set(a.numbers))
    jprint({"written": done, "calls_to_make": todo})


def cmd_finish(a):
    run = store.active_run()
    if not run:
        print("No active run.")
        return
    jprint({"finished": run, "next": runmod.finish(run)})


def cmd_extend(a):
    st = _st()
    st["extra_time"] = True
    store.save_state(st["run"], st)
    print("Time budget lifted for this run because Max asked.")


def main():
    p = argparse.ArgumentParser(prog="radar")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--spec"); s.add_argument("--subject"); s.set_defaults(f=cmd_start)
    sub.add_parser("next").set_defaults(f=cmd_next)
    s = sub.add_parser("label-queue"); s.add_argument("--limit", type=int, default=400); s.set_defaults(f=cmd_label_queue, cross=False)
    s = sub.add_parser("cross-queue"); s.add_argument("--limit", type=int, default=60); s.set_defaults(f=cmd_label_queue, cross=True)
    s = sub.add_parser("label-import"); s.add_argument("file", nargs="?"); s.add_argument("--check", action="store_true"); s.add_argument("--check-ok", action="store_true"); s.set_defaults(f=cmd_label_import)
    sub.add_parser("label-check").set_defaults(f=cmd_label_check)
    s = sub.add_parser("cross-import"); s.add_argument("file"); s.set_defaults(f=cmd_cross_import)
    sub.add_parser("combos-help").set_defaults(f=cmd_combos_help)
    s = sub.add_parser("thumbs"); s.add_argument("-n", type=int, default=12); s.set_defaults(f=cmd_thumbs)
    s = sub.add_parser("board"); s.add_argument("--run"); s.add_argument("--from-store", action="store_true"); s.add_argument("--subject"); s.add_argument("--also", nargs="*")
    s.add_argument("--days", type=int); s.add_argument("--force-preview", action="store_true"); s.add_argument("--overwrite", action="store_true"); s.set_defaults(f=cmd_board)
    s = sub.add_parser("feedback"); s.add_argument("file"); s.add_argument("--run"); s.set_defaults(f=cmd_feedback)
    s = sub.add_parser("known"); s.add_argument("--subject"); s.add_argument("--add", nargs="*"); s.add_argument("--source"); s.add_argument("--note"); s.set_defaults(f=cmd_known)
    s = sub.add_parser("missed"); s.add_argument("video"); s.add_argument("--subject", required=True); s.set_defaults(f=cmd_missed)
    s = sub.add_parser("add"); s.add_argument("video"); s.set_defaults(f=cmd_add)
    sub.add_parser("status").set_defaults(f=cmd_status)
    s = sub.add_parser("yield"); s.add_argument("--run"); s.add_argument("--limit", type=int, default=60); s.set_defaults(f=cmd_yield)
    s = sub.add_parser("approve"); s.add_argument("numbers", type=int, nargs="+"); s.add_argument("--run"); s.set_defaults(f=cmd_approve)
    sub.add_parser("finish").set_defaults(f=cmd_finish)
    sub.add_parser("extend").set_defaults(f=cmd_extend)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
