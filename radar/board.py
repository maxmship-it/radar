"""Builds the board from memory and checks it. The validator fails the build when any rule is broken.

Board shape (MAX DECIDED, Nov 19 and Nov 20, 2026), and nothing else:
  Part 1  LAST 100 DAYS              every on-topic outlier, most views first, no cap
  Part 2  100 DAYS TO 18 MONTHS      same, a video appears in one part only
  CROSS-NICHE                        at most 8 cards, left out when nothing good turns up
  last page  10 TITLE + THUMBNAIL COMBOS
Card numbers run straight through the whole board so Max can give feedback by number.
"""
import json, time, datetime, re
from . import store, config as C, rule, subjects, vph as vphmod

SECTION_ORDER = ["recent", "older", "cross", "combos"]
SECTION_NAME = {"recent": "LAST 100 DAYS", "older": "100 DAYS TO 18 MONTHS", "cross": "CROSS-NICHE", "combos": "10 TITLE + THUMBNAIL COMBOS"}


def card_videos(st, con, include_cross=False):
    subj, win = st["subject"], st["window_days"]
    foreign = bool(st["spec"].get("foreign"))
    out = []
    subs = st.get("subjects") or [subj]
    seen = set()
    for r in con.execute(f"SELECT v.*, l.reason lreason FROM videos v JOIN labels l ON l.video_id=v.id WHERE l.subject IN ({','.join('?' * len(subs))}) AND l.label='on'", subs):
        v = dict(r)
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        age = store.age_days(v["upload_date"])
        if v["yt_status"] != "ok" or (v["yt_checked_at"] or 0) < st["started_at"] or age is None or age > win or age < 0:
            continue
        if not rule.is_longform(v["duration_s"]) or v["live"] or (v["language"] != "en" and not foreign):
            continue
        b = rule.best(store.mults(con, v["id"]), v["views"])
        if not b:
            continue
        v.update(best=b, age_days=age, section="recent" if age <= C.RECENT_DAYS else "older")
        out.append(v)
    if include_cross:
        picks = []
        for r in con.execute("SELECT v.*, l.reason lreason FROM videos v JOIN labels l ON l.video_id=v.id WHERE l.subject=? AND l.label='on'", ("cross:" + subj,)):
            v = dict(r)
            age = store.age_days(v["upload_date"])
            if v["yt_status"] != "ok" or (v["yt_checked_at"] or 0) < st["started_at"] or age is None or age > C.CROSS_DAYS:
                continue
            if not rule.is_longform(v["duration_s"]) or v["language"] != "en" or v["live"]:
                continue
            b = rule.best(store.mults(con, v["id"]), v["views"], cross=True, duration_s=v["duration_s"])
            if not b or any(o["id"] == v["id"] for o in out):
                continue
            niche, _, pattern = (v["lreason"] or "").partition("|")
            v.update(best=b, age_days=age, section="cross", cross_niche=niche.strip(), pattern=pattern.strip())
            picks.append(v)
        picks.sort(key=lambda v: -(v["views"] or 0))
        out += picks[:C.CROSS_MAX_CARDS]
    return out


def _age_text(days):
    if days < 1:
        return "today"
    if days < 60:
        return f"{days} days ago"
    if days < 365:
        return f"{days // 30} months ago"
    return f"{days / 365:.1f} years ago"


def partial_reasons(st, con):
    """PARTIAL only when a required step failed. An optional lane failing is reported in chat and does not tag the board."""
    run, why = st["run"], []
    if st.get("from_store"):
        return why
    def ok(where):
        return con.execute(f"SELECT COUNT(*) c FROM searches WHERE run=? AND status IN ('ok','cached') AND {where}", (run,)).fetchone()["c"]
    if not ok("kind='pool' AND query LIKE 'Radar pool%'"):
        why.append("the Algrow pool scan did not run")
    if not ok("tool='algrow' AND kind='keyword'"):
        why.append("Algrow keyword search did not run")
    if not ok("tool='youtube' AND kind='keyword'") or st.get("yt_failed"):
        why.append("the YouTube sweep did not run")
    if not ok("tool='youtube' AND kind='uploads'"):
        why.append("the pool and watch-list upload scan did not run")
    from . import run as runmod
    unver, errored = 0, []
    ids = runmod.candidate_ids(st, con)
    old_cut = (datetime.date.today() - datetime.timedelta(days=st["window_days"] + 14)).isoformat()
    for v in (con.execute(f"SELECT * FROM videos WHERE id IN ({','.join('?' * len(ids))})", ids) if ids else []):
        if not ((v["yt_status"] not in ("ok", "gone") or (v["yt_checked_at"] or 0) < st["started_at"]) and any(rule.passes(x, v["views"]) for x in store.mults(con, v["id"]).values())):
            continue
        # skipped on purpose, not failures: junk, judged off, too short, or dated outside the window
        if subjects.junk_reason(dict(v)) or (v["duration_s"] and not rule.is_longform(v["duration_s"])) or (v["upload_date"] and v["upload_date"] < old_cut):
            continue
        lab = con.execute("SELECT label FROM labels WHERE video_id=? AND subject=?", (v["id"], st["subject"])).fetchone()
        if lab and lab["label"] != "on":
            continue
        unver += 1
        if v["yt_status"] == "error":
            errored.append(f"{v['id']} '{(v['title'] or '')[:60]}' ({v['views'] or 0:,} views)")
    if unver:
        why.append(f"{unver} candidates could not be checked on YouTube" + (f", YouTube errored on: {'; '.join(errored[:5])}" if errored else ""))
    if not (st.get("stop_reason") or "").startswith("dry"):
        why.append("the search stopped on " + (st.get("stop_reason") or "an unfinished run") + ", not on dry results")
    return why


def build(st, con):
    vids = card_videos(st, con, include_cross=True)
    secs = {k: [] for k in SECTION_ORDER}
    for v in vids:
        secs[v["section"]].append(v)
    for k in ("recent", "older", "cross"):
        secs[k].sort(key=lambda v: -(v["views"] or 0))
    no, sections = 0, []
    con.execute("DELETE FROM cards WHERE run=?", (st["run"],))
    for k in ("recent", "older", "cross"):
        items = []
        for v in secs[k]:
            no += 1
            vp = vphmod.compute(con, v)
            tool, val = v["best"]
            items.append({"no": no, "vid": v["id"], "channel": v["channel"], "handle": v["handle"], "subs": v["subs"], "title": v["title"], "views": v["views"],
                          "vph": round(vp["vph"], 1) if vp["vph"] is not None else None, "vph_src": vp["source"], "vph_why": vp.get("why"),
                          "mult": round(val, 1), "mult_src": rule.TOOL_LABEL.get(tool, tool), "mult_tool": tool,
                          "upload_date": v["upload_date"], "age_days": v["age_days"], "age": _age_text(v["age_days"]), "duration_s": v["duration_s"],
                          "language": v["language"], "niche": v.get("cross_niche"), "pattern": v.get("pattern"), "yt_checked_at": v["yt_checked_at"]})
            con.execute("INSERT OR REPLACE INTO cards(run,card_no,video_id,section) VALUES(?,?,?,?)", (st["run"], no, v["id"], k))
        if items or k != "cross":
            name = f"LAST {min(st['window_days'], C.RECENT_DAYS)} DAYS" if k == "recent" else SECTION_NAME[k]
            sections.append({"key": k, "name": name, "items": items})
    combos = []
    p = store.run_dir(st["run"]) / "combos.json"
    if p.exists():
        by_id = {c["vid"]: c for s in sections for c in s["items"]}
        for c in json.loads(p.read_text())[:C.MAX_COMBOS]:
            m = by_id.get(c.get("model_vid"))
            row = dict(title=c.get("title", ""), thumb_words=c.get("thumb_words", ""), image_line=c.get("image_line", ""), model_vid=c.get("model_vid"), depends=c.get("depends"))
            if m:
                row.update(model_no=m["no"], model_title=m["title"], model_channel=m["channel"], model_views=m["views"], model_mult=m["mult"], model_src=m["mult_src"])
            else:
                r = con.execute("SELECT * FROM videos WHERE id=?", (c.get("model_vid"),)).fetchone()
                if r:
                    b = rule.best(store.mults(con, r["id"]), r["views"]) or rule.best(store.mults(con, r["id"]), r["views"], True, r["duration_s"])
                    row.update(model_title=r["title"], model_channel=r["channel"], model_views=r["views"], model_mult=round(b[1], 1) if b else None,
                               model_src=rule.TOOL_LABEL.get(b[0], b[0]) if b else None, model_in_store=bool(b and r["yt_status"] == "ok"))
            combos.append(row)
    sections.append({"key": "combos", "name": f"{len(combos)} TITLE + THUMBNAIL COMBOS" if len(combos) != 10 else SECTION_NAME["combos"], "items": combos})
    why = partial_reasons(st, con)
    brd = {"title": f"RADAR · {st['subject'].upper()}", "subject": st["subject"], "run": st["run"], "date": datetime.date.today().strftime("%a %d %b %Y"),
           "window_days": st["window_days"], "partial": bool(why), "partial_reasons": why, "foreign": bool(st["spec"].get("foreign")),
           "started_at": st["started_at"], "bucket": st["spec"].get("bucket"), "sections": sections}
    con.commit()
    return brd


def known_outlier_report(st, con, brd):
    """Every known outlier for the subject is on the board, or has a recorded reason. Anything else is a miss."""
    on_board = {c["vid"] for s in brd["sections"] if s["key"] != "combos" for c in s["items"]}
    out = []
    for k in con.execute("SELECT * FROM known_outliers WHERE subject=?", (st["subject"],)):
        vid = k["video_id"]
        if vid in on_board:
            out.append((vid, "on board", None))
            continue
        v = con.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
        lab = con.execute("SELECT label, reason FROM labels WHERE video_id=? AND subject=?", (vid, st["subject"])).fetchone()
        reason = None
        if lab and lab["label"] != "on":
            reason = f"labeled {lab['label']}: {lab['reason']}"      # a recorded call stands; no need to re-check the video
        elif v and subjects.junk_reason(dict(v)):
            reason = "dropped by the junk filter: " + subjects.junk_reason(dict(v))
        elif v and v["yt_status"] == "gone":
            reason = "deleted or private"
        elif v and v["yt_status"] == "ok" and (v["yt_checked_at"] or 0) >= st["started_at"]:
            age = store.age_days(v["upload_date"])
            if age is not None and age > st["window_days"]:
                reason = f"outside the window ({age} days old)"
            elif not rule.is_longform(v["duration_s"]):
                reason = "under 3 minutes"
            elif v["language"] != "en":
                reason = f"not English ({v['lang_note']})"
            elif not rule.best(store.mults(con, vid), v["views"]):
                m = store.mults(con, vid)
                reason = "no longer passes the rule (" + (", ".join(f"{rule.TOOL_LABEL.get(t, t)} {x:.1f}x" for t, x in m.items()) or "no multiplier from any tool") + f" at {v['views']:,} views)"
            elif lab and lab["label"] != "on":
                reason = f"labeled {lab['label']}: {lab['reason']}"
        out.append((vid, "reason" if reason else "MISS", reason))
    return out


def validate(brd, con, st):
    """Returns (failures, warnings). Any failure stops the render."""
    fails, warns = [], []
    keys = [s["key"] for s in brd["sections"]]
    if keys != [k for k in SECTION_ORDER if k in keys] or keys[:2] != ["recent", "older"] or keys[-1] != "combos" or set(keys) - set(SECTION_ORDER):
        fails.append(f"sections are {keys}; they must be recent, older, (cross), combos and nothing else")
    seen, nos = set(), []
    for s in brd["sections"]:
        if s["key"] == "combos":
            continue
        last = None
        for c in s["items"]:
            nos.append(c["no"])
            if c["vid"] in seen:
                fails.append(f"{c['vid']} appears twice")
            seen.add(c["vid"])
            if last is not None and (c["views"] or 0) > last:
                fails.append(f"{s['name']} is not sorted by views at card {c['no']}")
            last = c["views"] or 0
            v = con.execute("SELECT * FROM videos WHERE id=?", (c["vid"],)).fetchone()
            if not v or v["yt_status"] != "ok" or (v["yt_checked_at"] or 0) < brd["started_at"]:
                fails.append(f"card {c['no']} {c['vid']} was not verified on YouTube in this run")
                continue
            if c["title"] != v["title"] or c["views"] != v["views"] or c["upload_date"] != v["upload_date"]:
                fails.append(f"card {c['no']} does not carry YouTube's own title, views and date")
            if not rule.is_longform(v["duration_s"]):
                fails.append(f"card {c['no']} is under 3 minutes")
            if v["language"] != "en" and not brd["foreign"]:
                fails.append(f"card {c['no']} is not English")
            cross = s["key"] == "cross"
            m = store.mults(con, c["vid"])
            good = rule.cross_passes(m.get(c["mult_tool"]), v["views"], v["duration_s"]) if cross else rule.passes(m.get(c["mult_tool"]), v["views"])
            if not good:
                fails.append(f"card {c['no']} does not pass the {'cross-niche bar' if cross else 'outlier rule'} on {c['mult_src']}")
            lab = con.execute("SELECT label FROM labels WHERE video_id=? AND subject=?", (c["vid"], ("cross:" if cross else "") + brd["subject"])).fetchone()
            if not lab or lab["label"] != "on":
                fails.append(f"card {c['no']} is not labeled on-topic")
            age = store.age_days(v["upload_date"])
            want = "cross" if cross else ("recent" if age <= C.RECENT_DAYS else "older")
            if s["key"] != want or (not cross and age > brd["window_days"]) or (cross and age > C.CROSS_DAYS):
                fails.append(f"card {c['no']} is {age} days old and sits in the wrong section")
            if c["vph"] is not None and c["vph_src"] not in vphmod.SOURCE_LABEL.values():
                fails.append(f"card {c['no']} shows views per hour from a source that is not allowed")
            if c["vph"] is not None and c["vph"] * 24 > (v["views"] or 0):
                fails.append(f"card {c['no']} shows a 24 hour gain larger than its total views")
        if s["key"] == "cross" and len(s["items"]) > C.CROSS_MAX_CARDS:
            fails.append("the cross-niche section has more than 8 cards")
    if nos != list(range(1, len(nos) + 1)):
        fails.append("card numbers do not run 1, 2, 3 straight through the board")
    combos = brd["sections"][-1]["items"] if brd["sections"] and brd["sections"][-1]["key"] == "combos" else []
    if len(combos) > C.MAX_COMBOS:
        fails.append("more than 10 combos")
    if not combos:
        warns.append("no combos were written")
    used = {}
    for i, c in enumerate(combos, 1):
        if not c.get("model_vid") or not (c.get("model_no") or c.get("model_in_store")):
            fails.append(f"combo {i} is not modeled on a real video that passed the rule")
        if not c.get("title"):
            fails.append(f"combo {i} has no title")
        if len(c.get("image_line", "")) >= 100:
            fails.append(f"combo {i}: the image line is {len(c['image_line'])} characters; it must be under 100")
        txt = f"{c.get('title', '')} {c.get('thumb_words', '')} {c.get('image_line', '')}"
        if "—" in txt or "–" in txt:
            fails.append(f"combo {i} uses an em dash")
        if (brd.get("bucket") or "").upper().startswith("EXPOS") and re.search(r"carnivore", c.get("title", ""), re.I):
            fails.append(f"combo {i}: an exposé title says 'carnivore'")
        if len(c.get("thumb_words", "").split()) > 5:
            warns.append(f"combo {i}: thumbnail words run long ({c['thumb_words']})")
        used[c.get("model_vid")] = used.get(c.get("model_vid"), 0) + 1
    if combos and max(used.values()) > 2:
        warns.append("several combos lean on the same outlier; spread them out")
    n_cross_cards = sum(len(s["items"]) for s in brd["sections"] if s["key"] == "cross")
    cross_ids = {c["vid"] for s in brd["sections"] if s["key"] == "cross" for c in s["items"]}
    if n_cross_cards >= 3 and sum(1 for c in combos if c.get("model_vid") in cross_ids) < 3 and combos:
        warns.append("fewer than 3 combos are modeled on a cross-niche outlier")
    for vid, status, reason in known_outlier_report(st, con, brd):
        if status == "MISS":
            fails.append(f"known outlier {vid} is missing from the board with no recorded reason")
    if not st.get("label_checked") and not st.get("from_store"):
        fails.append("the second-pass label check on the 20 highest-view videos has not been done")
    return fails, warns
