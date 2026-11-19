#!/usr/bin/env python3
"""build_board.py v4 - turns Radar's logged rows plus your labels and writing into the board JSON for render_board.py.

You never type video cards by hand. You write two small files:

labels.tsv (one line per qualifying video, tab separated, no header):
  <video id> <TAB> <label> <TAB> <flags> <TAB> <note>
  label: EXPOSÉ | FAT LOSS | CARNIVORE | TOPIC | OFF   (OFF = off-topic, still shown, in a compact table)
  flags: comma list, may be empty. new = new channel breakout (under 100K subs, not in the pool or watch list)
  note:  one short line shown on the card, may be empty
  Every qualifier in rows_<run>.tsv should have a line. Any you miss are not dropped: they go in an "UNSORTED" table.

editorial.json (only the parts you write; every key optional):
{
 "title": "RADAR BOARD — FAT LOSS", "date": "Thu 22 Oct 2026",
 "status": "complete" | "partial", "notes": ["...cover lines..."],
 "topic": "eggs",                                  (topic and package modes: names the main section)
 "formats_map": {"<id>": "title format line"},     (cross-niche cards: one line naming the format)
 "formats_table": {"columns": [...], "rows": [[...]]},
 "recent_any": ["id", ...],                         (topic mode: on-topic, last 90 days, any multiplier)
 "top_all_time": ["id", ...],                       (topic mode)
 "evidence": ["id", ...],                           (package mode: extra cards to show as evidence)
 "repackage": [{"mine_vid","mine_title","mine_views","mine_age","their_vid","sugg"}],
 "ideas": [{"title","thumb","bucket","colour","why_now","evidence":[...]}],
 "titles": [{"title","why","vid"}],                (model details are filled in from the logged rows)
 "concepts": [{"name","text","describe","vids":[...]}],
 "log_lines": ["Tools: ...", "Stop rule: ...", "Pool additions: ...", "Watch-list proposals: ..."]
}

Usage:
  python3 build_board.py --mode sweep|topic|package --run RUN [--dir /home/claude/radar] \
      [--yt YT_DIR [YT_DIR2]] [--mine mine.json] [--catalogue catalogue.json] \
      --labels labels.tsv --editorial editorial.json --out board.json [--window 90]
repackage items need only mine_vid, their_vid and sugg: titles, views and ages are filled from --mine / --catalogue
and the logged rows. A card's multiplier is always labelled with the tool that produced that number.
Any video id you reference (ideas, titles, concepts, repackage, recent_any, top_all_time, evidence) is looked up in
rows_, rising_ and raw_ for the run, and in yt_rows.tsv. Ids that can't be found are listed in a warning line.
"""
import argparse, json, os, sys, datetime, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--mode", required=True, choices=["sweep", "topic", "package"])
ap.add_argument("--run", required=True); ap.add_argument("--dir", default="/home/claude/radar")
ap.add_argument("--yt", nargs="*", default=[]); ap.add_argument("--labels", required=True)
ap.add_argument("--mine", default="", help="JSON list of Max's uploads [{id,t,v,d}] (from the yt-dlp uploads command)")
ap.add_argument("--catalogue", default="", help="catalogue.json (Max's older uploads)")
ap.add_argument("--editorial", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--window", type=int, default=90)
a = ap.parse_args()
D = a.dir; TODAY = datetime.date.today()
ed = json.load(open(a.editorial, encoding="utf-8")) if os.path.exists(a.editorial) else {}


def f(x):
    try: return float(x)
    except Exception: return None


def age(d):
    try: n = (TODAY - datetime.date.fromisoformat(d[:10])).days
    except Exception: return ""
    if n < 1: return "today"
    if n == 1: return "1 day ago"
    if n < 14: return f"{n} days ago"
    if n < 60: return f"{n // 7} weeks ago"
    if n < 730: return f"{n // 30} months ago"
    return f"{n // 365} years ago"


def days(d):
    try: return (TODAY - datetime.date.fromisoformat(d[:10])).days
    except Exception: return 9999


SRC = {"algrow": "Algrow", "algrow-pool": "Algrow", "tubeai": "TubeAI", "vidiq": "vidIQ", "youtube": "", "ytdirect": ""}
info = {}   # id -> dict(channel, subs, title, views, o, r, date, tool, sweep)


def put(vid, **k):
    cur = info.setdefault(vid, {})
    for key, val in k.items():
        if val not in (None, "", "None") and cur.get(key) in (None, "", "None"):
            cur[key] = val
            if key == "o": cur["o_tool"] = k.get("tool", "")
    for key in ("o", "r", "views"):
        if k.get(key) not in (None, "", "None") and f(k[key]) is not None and (f(cur.get(key)) or 0) < f(k[key]):
            cur[key] = k[key]
            if key == "o": cur["o_tool"] = k.get("tool", "")   # the label always names the tool that gave the number shown


def read(path):
    return [l.rstrip("\n").split("\t") for l in open(path, encoding="utf-8")] if os.path.exists(path) else []


# rows: id, title, channel, subs, views, o, r, date, dur_min, sweep, tool
rows = read(f"{D}/rows_{a.run}.tsv")
for p in rows:
    if len(p) >= 11: put(p[0], title=p[1], channel=p[2], subs=p[3], views=p[4], o=p[5], r=p[6], date=p[7], sweep=p[9], tool=p[10])
# rising: id, title, channel, subs, views, best, date, dur_min, sweep, tool
rising = read(f"{D}/rising_{a.run}.tsv")
for p in rising:
    if len(p) >= 10: put(p[0], title=p[1], channel=p[2], subs=p[3], views=p[4], date=p[6], sweep=p[8], tool=p[9],
                         **({"r": p[5]} if p[9] == "youtube" else {"o": p[5]}))
# raw: run, sweep, tool, rank, id, title, channel, subs, views, o, r, date, dur_s, sim
for p in read(f"{D}/raw_{a.run}.tsv"):
    if len(p) >= 14: put(p[4], title=p[5], channel=p[6], subs=p[7], views=p[8], o=p[9], r=p[10], date=p[11], sweep=p[1], tool=p[2])
yt_warn = []
for ydir in a.yt:
    if not os.path.exists(os.path.join(ydir, "yt_rows.tsv")):
        yt_warn.append(f"YouTube-direct folder {ydir} has no yt_rows.tsv: that sweep did not finish"); continue
    for p in read(os.path.join(ydir, "yt_rows.tsv"))[1:]:
        if len(p) >= 12:
            d = p[5]; d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
            put(p[0], title=p[1], channel=p[2], views=p[4], r=p[8], date=d, tool="youtube", sweep=p[10],
                subs=(p[12] if len(p) > 12 else ""))

missing = set()


def card(vid, rank=None, note=None, fmt=None):
    i = info.get(vid)
    if not i: missing.add(vid); return None
    tool = i.get("tool", "")
    c = {"rank": rank or "", "channel": i.get("channel", ""), "subs": int(f(i["subs"])) if f(i.get("subs")) else None,
         "title": i.get("title", ""), "views": int(f(i.get("views")) or 0), "age": age(i.get("date", "")), "vid": vid}
    if f(i.get("o")) is not None:
        ot = i.get("o_tool") or tool
        c["outlier"] = round(f(i["o"]), 2); c["outlier_src"] = SRC.get(ot, ot)
    if f(i.get("r")) is not None: c["recent"] = round(f(i["r"]), 2)
    if note: c["note"] = note
    if fmt: c["format"] = fmt
    return c


def best(vid):
    i = info.get(vid, {})
    return max([x for x in (f(i.get("o")), f(i.get("r"))) if x is not None], default=0)


labels = {}
for p in read(a.labels):
    if p and p[0].strip():
        p += [""] * (4 - len(p))
        lab_ = p[1].strip().upper().replace("EXPOSE", "EXPOSÉ").replace("EXPOSÉÉ", "EXPOSÉ").replace("FATLOSS", "FAT LOSS")
        lab_ = {"OPT": "FAT LOSS", "OPTIMISATION": "FAT LOSS", "OPTIMIZATION": "FAT LOSS", "CARN": "CARNIVORE", "EXP": "EXPOSÉ"}.get(lab_, lab_)
        labels[p[0].strip()] = dict(label=lab_, flags={x.strip() for x in p[2].split(",") if x.strip()}, note=p[3].strip())

qual_ids = [p[0] for p in rows if len(p) >= 11]
# a qualifier is cross-niche only if EVERY lane that returned it was a cross lane (so parallel order can't move it)
lanes = {}
for p in read(f"{D}/raw_{a.run}.tsv"):
    if len(p) >= 5: lanes.setdefault(p[4], set()).add(p[1].lower().startswith("cross"))
cross_ids = [p[0] for p in rows if len(p) >= 11 and lanes.get(p[0], {p[9].lower().startswith("cross")}) == {True}]
core_ids = [v for v in qual_ids if v not in cross_ids]


def cards_section(name, meta, ids, notes_from_labels=True, fmts=None, cap=None):
    ids = sorted(dict.fromkeys(ids), key=lambda v: -best(v))
    if cap: ids = ids[:cap]
    items = []
    for n, v in enumerate(ids, 1):
        L = labels.get(v, {})
        note = L.get("note") if notes_from_labels else None
        lab = L.get("label")
        if lab and lab not in ("TOPIC", "OFF") and a.mode == "sweep":
            note = f"{lab}" + (f" · {note}" if note else "")
        c = card(v, n, note, (fmts or {}).get(v))
        if c: items.append(c)
    return {"kind": "cards", "name": name, "meta": meta, "items": items} if items else None


def table_section(name, ids):
    ids = sorted(dict.fromkeys(ids), key=lambda v: -best(v))
    rows_t = []
    for v in ids:
        i = info.get(v)
        if not i: missing.add(v); continue
        rows_t.append([i.get("title", "")[:90], i.get("channel", ""), f"{int(f(i.get('views')) or 0):,}",
                       f"{best(v):.1f}x", age(i.get("date", "")), f"youtu.be/{v}"])
    return {"kind": "table", "name": name, "columns": ["Title", "Channel", "Views", "Best x", "Age", "Link"], "rows": rows_t} if rows_t else None


rule = "3x+100K, 5x+50K or 2x+300K · longform"
sections = []; rise_more = []
on = [v for v in core_ids if labels.get(v, {}).get("label") not in (None, "OFF")]
off = [v for v in core_ids if labels.get(v, {}).get("label") == "OFF"]
unsorted = [v for v in core_ids if v not in labels]   # cross-niche rows have their own section

if a.mode == "sweep":
    new = [v for v in on if "new" in labels[v]["flags"]]
    l14 = [v for v in on if v not in new and days(info.get(v, {}).get("date", "")) <= 14]
    l90 = [v for v in on if v not in new and v not in l14]
    sections.append(cards_section("LAST 14 DAYS — OUTLIERS", rule, l14))
    if a.window > 14 or l90:
        buckets = [b for b in ("EXPOSÉ", "FAT LOSS", "CARNIVORE") if any(labels[v]["label"] == b for v in l90)]
        if len(buckets) > 1:   # all-bucket sweep: one section per bucket, then anything labelled TOPIC
            for b in buckets:
                sections.append(cards_section(f"LAST {a.window} DAYS — {b}", rule, [v for v in l90 if labels[v]["label"] == b]))
            sections.append(cards_section(f"LAST {a.window} DAYS — OTHER ON-TOPIC", rule,
                                          [v for v in l90 if labels[v]["label"] not in buckets]))
        else:
            sections.append(cards_section(f"LAST {a.window} DAYS — OUTLIERS", rule, l90))
    sections.append(cards_section("NEW CHANNEL BREAKOUTS", "under 100K subs, not tracked yet", new))
    rise = [p[0] for p in rising if labels.get(p[0], {}).get("label") != "OFF"]
    sections.append(cards_section("RISING", "5x or more on 20K to 50K views · not qualifiers", rise, cap=8))
    rise_more = sorted(dict.fromkeys(rise), key=lambda v: -best(v))[8:]
    sections.append(cards_section("CROSS-NICHE PACKAGING", "10x+200K · other niches, for formats and thumbnails",
                                  cross_ids, notes_from_labels=False, fmts=ed.get("formats_map", {})))
elif a.mode == "topic":
    t = (ed.get("topic") or "THE TOPIC").upper()
    sections.append(cards_section(f"OUTLIERS ON {t}", rule + " · 12 months", on))
    sections.append(cards_section(f"RECENT ON {t}, ANY MULTIPLIER", "last 90 days · 20K+ views · not already shown above",
                                  [v for v in ed.get("recent_any", []) if v not in on]))
    rise = [p[0] for p in rising if labels.get(p[0], {}).get("label") != "OFF"]
    sections.append(cards_section("RISING", "5x or more on 20K to 50K views", rise, cap=8))
    rise_more = sorted(dict.fromkeys(rise), key=lambda v: -best(v))[8:]
    sections.append(cards_section(f"TOP OF ALL TIME ON {t}", "by views", ed.get("top_all_time", []), notes_from_labels=False))
    sections.append(cards_section("CROSS-NICHE PACKAGING", "other niches, for formats", cross_ids, notes_from_labels=False, fmts=ed.get("formats_map", {})))
else:
    if ed.get("concepts"):
        sections.append({"kind": "concepts", "name": "THUMBNAIL CONCEPTS", "items": ed["concepts"]})
    if ed.get("titles"):
        items = []
        for t_ in ed["titles"]:
            v = t_.get("vid"); i = info.get(v, {}) if v else {}
            if v and not i: missing.add(v)
            items.append(dict(title=t_.get("title", ""), why=t_.get("why", ""), vid=v, model_title=i.get("title", ""),
                              model_channel=i.get("channel", ""), model_views=int(f(i.get("views")) or 0),
                              model_outlier=round(best(v), 2) if v else None))
        sections.append({"kind": "titles", "name": "TITLE OPTIONS", "items": items})
    sections.append(cards_section("THE EVIDENCE", rule, list(on) + ed.get("evidence", [])))
    sections.append(cards_section("CROSS-NICHE FORMATS", "other niches", cross_ids, notes_from_labels=False, fmts=ed.get("formats_map", {})))

if ed.get("formats_table"):
    ft = ed["formats_table"]; sections.append({"kind": "table", "name": "TITLE FORMATS", "columns": ft.get("columns", []), "rows": ft.get("rows", [])})
if a.mode != "package" and rise_more: sections.append(table_section("MORE RISING", rise_more))
sections.append(table_section("OFF-TOPIC OUTLIERS", off))
sections.append(table_section("UNSORTED (no label given)", unsorted))
mine = {}
for src_ in (a.catalogue, a.mine):
    if src_ and os.path.exists(src_):
        try:
            for m in json.load(open(src_, encoding="utf-8")):
                if m.get("id"):
                    cur_ = mine.setdefault(m["id"], {})
                    for k_, v_ in m.items():
                        if v_ not in (None, ""): cur_[k_] = v_   # later source fills in, never blanks out
        except Exception as e: yt_warn.append(f"could not read {src_}: {e}")
if ed.get("repackage"):
    rp = []
    for it in ed["repackage"]:
        m = mine.get(it.get("mine_vid"), {})
        if m:
            it.setdefault("mine_title", m.get("t", "")); it.setdefault("mine_views", int(f(m.get("v")) or 0))
            if m.get("d"): it.setdefault("mine_age", age(str(m["d"])))
        elif it.get("mine_vid"): yt_warn.append(f"repackage: {it['mine_vid']} not found in Max's uploads list or catalogue")
        i = info.get(it.get("their_vid"), {})
        if it.get("their_vid") and not i: missing.add(it["their_vid"])
        rp.append({**it, "their_title": it.get("their_title") or i.get("title", ""), "their_channel": it.get("their_channel") or i.get("channel", ""),
                   "their_outlier": it.get("their_outlier") or round(best(it.get("their_vid")), 2),
                   "their_src": (lambda i_: (SRC.get(i_.get("o_tool") or i_.get("tool", ""), "") if f(i_.get("o")) is not None and (f(i_.get("o")) or 0) >= (f(i_.get("r")) or 0) else "recent-30"))(i)})
    sections.append({"kind": "repackage", "name": "ALREADY COVERED — REPACKAGE", "items": rp})
if ed.get("ideas"):
    sections.append({"kind": "ideas", "name": "WHAT TO MAKE NEXT", "items": ed["ideas"]})
for c in ed.get("concepts", []):
    for v in c.get("vids", []):
        if v not in info: missing.add(v)

here = os.path.dirname(os.path.abspath(__file__))
summ = subprocess.run([sys.executable, os.path.join(here, "radar_log.py"), "--run", a.run, "--dir", D, "--summary"],
                      capture_output=True, text=True)
try: log_rows = json.loads(summ.stdout.splitlines()[0])
except Exception: log_rows = [["Search", "Note"], ["(no calls logged)", summ.stderr[-200:]]]
lines = list(ed.get("log_lines", [])) + yt_warn
for ydir in a.yt:
    yl = read(os.path.join(ydir, "yt_log.tsv"))
    for p in yl[1:]:
        lines.append(f"YouTube-direct ({os.path.basename(ydir.rstrip('/'))}) {p[0]}: " +
                     ", ".join(f"{h} {x}" for h, x in zip(yl[0][1:], p[1:]) if x not in ("", "0")))
if summ.stdout.count("\n") >= 1: lines.append(summ.stdout.splitlines()[1])
if missing: lines.append("Build warning: these ids were referenced but not found in the logged rows: " + ", ".join(sorted(missing)))
sections.append({"kind": "log", "name": "COVERAGE LOG", "rows": log_rows, "lines": lines})

board = {"title": ed.get("title", "RADAR BOARD"), "date": ed.get("date", TODAY.strftime("%a %d %b %Y")),
         "summary": {"status": ed.get("status", "complete"), "notes": ed.get("notes", [])},
         "sections": [s for s in sections if s]}
json.dump(board, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
n_cards = sum(len(s.get("items", [])) for s in board["sections"] if s["kind"] == "cards")
print(f"board written: {a.out} | sections {len(board['sections'])} | cards {n_cards} | off-topic {len(off)} | unsorted {len(unsorted)} | missing ids {len(missing)}"
      + (f": {', '.join(sorted(missing))}" if missing else ""))
for w in yt_warn: print("WARNING:", w)
# END build_board.py v4
