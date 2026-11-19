#!/usr/bin/env python3
"""yt_sweep.py v4 - Radar's free YouTube-direct sweep (no MCP calls, no credits).

Searches YouTube itself (sorted by views) and/or reads watch-list channels, then works out
each candidate's multiplier against its channel's recent uploads, and applies Radar's rule.

Usage:
  python3 yt_sweep.py --since 2026-09-29 --out /home/claude/yt "brands to avoid" "fake foods" ...
  python3 yt_sweep.py --since 2026-07-15 --out /home/claude/yt --channels @AustraliaFoodExposed @ConsumerExposed-ghz
Options: --depth N (results per query, default 60), --min-views (default 50000), --max-fetch (default 200),
  --all-time (sorted by views with no date filter, for "top of all time"; pass --since 2005-01-01 with it)
Windows over 30 days search twice per query (this month AND this year, both sorted by views), because a
year-wide view sort fills up with old videos and pushes recent ones out.

Writes in --out:
  yt_rows.tsv   every candidate checked: id, title, channel, channel_id, views, date, dur_min,
                recent_avg, multiplier_recent, n_baseline, source, qualifies (y / near / n)
  yt_log.tsv    one line per query or channel: returned, fetch_failed, no_duration, under_3min, under_view_floor,
                outside_window, below_rule, kept, error
  yt_rows.json  the same candidates in radar_log.py input format (o = null, r = multiplier_recent),
                ready to pipe into radar_log.py so every source lands in one rows file
Prints the log and the qualifying rows.
Rule: (mult>=3 and views>=100000) or (mult>=5 and views>=50000) or (mult>=2 and views>=300000); long-form only (>=3 min).
"near" = views 50000-300000 at mult 2-3, or mult>=5 with views 20000-50000.
multiplier_recent = views / MEDIAN views of the channel's latest 30 uploads, excluding this one
(median, so one old viral hit doesn't hide a new breakout). Needs at least 10 other uploads, else blank.
Notes: video pages need the mweb client (plain requests hit YouTube's bot check). 403s are retried once.
"""
import sys, json, argparse, subprocess, urllib.parse, os, statistics, concurrent.futures as cf, datetime

ap = argparse.ArgumentParser()
ap.add_argument("queries", nargs="*")
ap.add_argument("--since", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--channels", nargs="*", default=[])
ap.add_argument("--depth", type=int, default=60)
ap.add_argument("--min-views", type=int, default=50000)
ap.add_argument("--max-fetch", type=int, default=200)
ap.add_argument("--all-time", action="store_true", help="search sorted by views with no date filter (topic mode: top of all time). Use with --since 2005-01-01")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
since = a.since.replace("-", "")
days = (datetime.date.today() - datetime.date.fromisoformat(a.since)).days
SP_MONTH, SP_YEAR = "CAMSBAgEEAE%3D", "CAMSBAgFEAE%3D"   # sort by views + this month / this year
SPS = [SP_MONTH] if days <= 30 else [SP_MONTH, SP_YEAR]
if a.all_time: SPS = ["CAMSAhAB"]   # sort by views, videos only, any date
BASE = ["yt-dlp", "--no-check-certificates", "--no-warnings", "-q"]
MWEB = ["--extractor-args", "youtube:player_client=mweb", "--ignore-no-formats-error", "--skip-download"]

def run(args, tries=2):
    err = ""
    for _ in range(tries):
        try:
            p = subprocess.run(BASE + args, capture_output=True, text=True, timeout=180)
        except (subprocess.TimeoutExpired, OSError) as e:
            err = f"timeout or OS error: {type(e).__name__}"; continue
        if p.returncode == 0 and p.stdout.strip():
            try: return json.loads(p.stdout), ""
            except Exception as e: err = f"bad json: {e}"
        else:
            err = (p.stderr.strip().splitlines() or ["no output"])[-1][:160]
    return None, err

log, cand = [], {}
def add_log(src, **k):
    row = dict(source=src, returned=0, fetch_failed=0, no_duration=0, under_3min=0, under_view_floor=0, outside_window=0, below_rule=0, kept=0, error="")
    row.update(k); log.append(row); return row

# 1. searches
def search(q):
    ents, errs, ids = [], [], set()
    for sp in SPS:
        recent_sp = (sp == SP_MONTH)
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q) + "&sp=" + sp
        d, err = run(["--flat-playlist", "-I", f"1:{a.depth}", "-J", url])
        if err: errs.append(err)
        for e in (d or {}).get("entries") or []:
            if e and e.get("id") and e["id"] not in ids:
                ids.add(e["id"]); e["_month"] = recent_sp; ents.append(e)
    return q, ents, " | ".join(errs)
with cf.ThreadPoolExecutor(4) as ex:
    for q, ents, err in ex.map(search, a.queries):
        L = add_log("q:" + q, returned=len(ents), error=err)
        for e in ents:
            if not e or not e.get("id"): continue
            dur = e.get("duration")
            if dur is None: L["no_duration"] += 1
            elif dur < 180: L["under_3min"] += 1; continue
            if (e.get("view_count") or 0) < min(20000, a.min_views): L["under_view_floor"] += 1; continue
            c = cand.setdefault(e["id"], dict(id=e["id"], title=e.get("title", ""), views=e.get("view_count") or 0, dur=dur, src=[], ch_id=e.get("channel_id"), month=False))
            c["src"].append("q:" + q); c["month"] = c["month"] or e.get("_month", False)

# 2. watch-list channels
def chan(h):
    url = f"https://www.youtube.com/{h}/videos" if h.startswith("@") else f"https://www.youtube.com/channel/{h}/videos"
    d, err = run(["--flat-playlist", "-I", "1:31", "-J", url])
    return h, d, err
base = {}
with cf.ThreadPoolExecutor(4) as ex:
    for h, d, err in ex.map(chan, a.channels):
        ents = [e for e in ((d or {}).get("entries") or []) if e and e.get("id")]
        L = add_log("ch:" + h, returned=len(ents), error=err)
        if d: base[d.get("channel_id") or d.get("id")] = ents
        for e in ents[:31]:
            if (e.get("duration") or 999) < 180: L["under_3min"] += 1; continue
            if (e.get("view_count") or 0) < min(20000, a.min_views): L["under_view_floor"] += 1; continue
            c = cand.setdefault(e["id"], dict(id=e["id"], title=e.get("title", ""), views=e.get("view_count") or 0, dur=e.get("duration"), src=[], ch_id=d.get("channel_id"), month=True))
            c["src"].append("ch:" + h)

# 3. metadata for the biggest candidates (date, duration, channel)
# videos found by a "this month" search or a watch-list channel are checked first, so year-old giants can't crowd out new breakouts
todo = sorted(cand.values(), key=lambda c: (not c.get("month"), -c["views"]))[: a.max_fetch]
add_log("fetch-cap", returned=len(cand), kept=len(todo), error=(f"only the first {a.max_fetch} of {len(cand)} candidates were checked" if len(cand) > a.max_fetch else ""))
def meta(c):
    d, err = run(MWEB + ["-J", "https://www.youtube.com/watch?v=" + c["id"]])
    return c, d, err
with cf.ThreadPoolExecutor(4) as ex:
    for c, d, err in ex.map(meta, todo):
        c["err"] = err
        if d:
            c.update(date=d.get("upload_date") or "", views=d.get("view_count") or c["views"], dur=d.get("duration") or c["dur"],
                     ch_id=d.get("channel_id") or c["ch_id"], channel=d.get("channel") or "", live=d.get("was_live") or d.get("is_live"),
                     subs=d.get("channel_follower_count"))

# 4. channel baselines (latest 30 uploads)
need = {c["ch_id"] for c in todo if c.get("ch_id") and c.get("date", "") >= since and c["ch_id"] not in base}
with cf.ThreadPoolExecutor(4) as ex:
    for h, d, err in ex.map(chan, need):
        base[h] = [e for e in ((d or {}).get("entries") or []) if e and e.get("id")]

# 5. apply the rule
rows = []
src_log = {r["source"]: r for r in log}
for c in todo:
    srcs = c["src"]
    def bump(k):
        for s in srcs: src_log[s][k] += 1
    if not c.get("date"): bump("fetch_failed"); continue
    if c["date"] < since: bump("outside_window"); continue
    if (c.get("dur") or 0) < 180 or c.get("live"): bump("under_3min"); continue
    others = [e.get("view_count") for e in base.get(c["ch_id"], []) if e.get("id") != c["id"] and e.get("view_count") is not None][:30]
    avg = statistics.median(others) if len(others) >= 10 else None   # tiny channels with few uploads give silly multipliers
    m = round(c["views"] / avg, 2) if avg else None
    v = c["views"]
    q = "n"
    if m is not None:
        if (m >= 3 and v >= 100000) or (m >= 5 and v >= 50000) or (m >= 2 and v >= 300000): q = "y"
        elif (50000 <= v < 300000 and 2 <= m < 3) or (m >= 5 and 20000 <= v < 50000): q = "near"
    if q == "y": bump("kept")
    else: bump("below_rule")
    rows.append([c["id"], c["title"], c.get("channel", ""), c.get("ch_id") or "", v, c["date"], round((c.get("dur") or 0) / 60, 1),
                 round(avg) if avg else "", m if m is not None else "", len(others), "; ".join(srcs), q, c.get("subs") or ""])

hdr = ["id", "title", "channel", "channel_id", "views", "date", "dur_min", "recent_avg", "multiplier_recent", "n_baseline", "source", "qualifies", "subs"]
with open(os.path.join(a.out, "yt_rows.tsv"), "w") as f:
    f.write("\t".join(hdr) + "\n")
    for r in sorted(rows, key=lambda r: (r[11] != "y", -(r[8] or 0) if r[8] != "" else 0)):
        f.write("\t".join(str(x).replace("\t", " ") for x in r) + "\n")
lh = ["source", "returned", "fetch_failed", "no_duration", "under_3min", "under_view_floor", "outside_window", "below_rule", "kept", "error"]
with open(os.path.join(a.out, "yt_log.tsv"), "w") as f:
    f.write("\t".join(lh) + "\n")
    for r in log: f.write("\t".join(str(r[k]) for k in lh) + "\n")
for r in log: print(" | ".join(f"{k} {r[k]}" for k in lh if r[k] not in ("", 0)) or r["source"])
print(f"checked {len(todo)} of {len(cand)} candidates (cap --max-fetch {a.max_fetch})")
json_rows = [dict(id=r[0], t=r[1], ch=r[2], cid=r[3], subs=(r[12] or None), v=r[4], o=None,
                  r=(r[8] if r[8] != "" and not a.all_time else None),   # recent-30 means nothing for an old video
                  d=(f"{r[5][:4]}-{r[5][4:6]}-{r[5][6:8]}" if len(r[5]) == 8 else r[5]),
                  dur_s=int(round(float(r[6]) * 60)) if r[6] != "" else None, rank=i) for i, r in enumerate(rows, 1)]
with open(os.path.join(a.out, "yt_rows.json"), "w") as f:
    json.dump(json_rows, f)
for r in rows:
    if r[11] in ("y", "near"): print(r[11], r[0], r[1][:70], r[2][:24], r[4], r[5], f"x{r[8]}", r[10][:40])
# END yt_sweep.py v4
