#!/usr/bin/env python3
"""radar_log.py v4 - record every Radar search call and what each filter cut. Feeds the coverage log.

Usage (after EVERY search call, including ones that return nothing or error):
  python3 /home/claude/rp/radar_log.py --run fatloss --sweep "kw:belly fat" --tool algrow \
      --params "90d p15 sim" [--since 2026-07-24] [--cross] [--longform-only] [--error "504"] [--limit 15] <<'EOF'
  [{"id":"abc","t":"Title","ch":"Chan","cid":"UC...","subs":1000,"v":250000,"o":7.3,"r":5.1,"d":"2026-09-30","dur_s":900,"sim":40,"rank":1}]
  EOF

Input: JSON array of EVERY video the call returned (not just good ones). Missing keys allowed.
  o  = the tool's own multiplier.  r = the recent-30 multiplier if known (yt_sweep.py gives it).
  d  = the date exactly as the tool gives it (full timestamp if there is one); it is converted to UTC.
  dur_s = duration in seconds, or null if the tool gives none.  cid = channel id (UC...), if given.
  v may be a number or text like "1.2M" / "345K" / "1,234".
--longform-only: the tool already filtered to long form on its own servers (Algrow, TubeAI with minDuration 181,
  vidIQ contentType long, thumbnail searches). A missing duration is then treated as long form.
Several sub-agents may call this at the same time: every write is locked, so dedupe stays correct.

Writes in --dir (default /home/claude/radar):
  raw_<run>.tsv    every returned video
  rows_<run>.tsv   qualifiers only, deduped on id (first sweep that found it wins)
  rising_<run>.tsv 5x or more with 20,000 to 50,000 views (not qualifiers, shown as Rising)
  calls.tsv        one line per call with counts of what each filter cut
  nodur_<run>.tsv  rows with no duration and no --longform-only. Run --fill-nodur to fix them.
  check_<run>.tsv  rows with 50,000+ views but NO multiplier from any tool. Radar checks these on Algrow by title.
Rule (qualifies if o OR r passes): 3x+100K, or 5x+50K, or 2x+300K. --cross: 10x+200K and <=40 min.
Filters in order: no duration, under 3 min, outside window (--since; skipped when the date can't be read),
no multiplier, below rule, duplicate of an earlier qualifier. "Hit limit" = returned count equals --limit.

Other commands (all take --run):
  --summary [--last N] [--short]  coverage-log rows as JSON, then one line "new qualifiers in the last N calls: ..."
                                  --short prints only calls that errored, returned 0, or hit their limit (plus TOTAL).
  --list-raw [--since D] [--min-views N] [--sweep-has TEXT]  every returned video (deduped, long form, best multiplier).
  --fill-nodur                    gets missing durations with yt-dlp and logs those rows again (same sweep + "+dur").
"""
import sys, json, argparse, os, re, fcntl, subprocess, concurrent.futures as cf
from datetime import datetime, timezone

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True); ap.add_argument("--sweep", default="x")
ap.add_argument("--tool", default="algrow"); ap.add_argument("--params", default="")
ap.add_argument("--since", default=""); ap.add_argument("--cross", action="store_true")
ap.add_argument("--longform-only", action="store_true")
ap.add_argument("--error", default=""); ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--dir", default="/home/claude/radar"); ap.add_argument("--summary", action="store_true")
ap.add_argument("--last", type=int, default=10); ap.add_argument("--short", action="store_true")
ap.add_argument("--list-raw", action="store_true"); ap.add_argument("--min-views", type=int, default=0)
ap.add_argument("--sweep-has", default=""); ap.add_argument("--fill-nodur", action="store_true")
ap.add_argument("--full", action="store_true", help="the tool's whole result filled its page (use on the last batch when piping a big result in batches)")
a = ap.parse_args()
D = a.dir; os.makedirs(D, exist_ok=True)
HERE = os.path.abspath(__file__)


def num(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = str(x).strip().replace(",", "").replace("×", "").replace("x", "").replace(" views", "").strip()
    m = re.fullmatch(r"([\d.]+)\s*([KkMmBb]?)", s)
    if not m: return None
    try: v = float(m.group(1))
    except ValueError: return None
    return v * {"k": 1e3, "m": 1e6, "b": 1e9}.get(m.group(2).lower(), 1)


def clean(s): return re.sub(r"[\t\r\n]+", " ", str(s if s is not None else "")).strip()
def sv(x): return "" if x is None or str(x) == "None" else clean(x)


def utc_day(d):
    d = clean(d)
    try:
        if "T" in d: return datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
    except Exception: pass
    if re.fullmatch(r"\d{8}", d): return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if re.fullmatch(r"\d{10}(\.\d+)?", d): return datetime.fromtimestamp(float(d), timezone.utc).date().isoformat()
    return d[:10]


def is_date(d): return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or ""))


def passes(m, v):
    return m is not None and v is not None and ((m >= 3 and v >= 100000) or (m >= 5 and v >= 50000) or (m >= 2 and v >= 300000))


# ---------------- summary ----------------
if a.summary:
    rows = [["Search", "Tool", "Returned", "Cut: no duration", "Cut: under 3 min", "Cut: outside window",
             "Cut: below rule", "Duplicates", "New qualifiers", "No multiplier", "Hit limit", "Error"]]
    tot = [0] * 8; kept_seq = []; shown = []
    p_calls = f"{D}/calls.tsv"
    if os.path.exists(p_calls):
        for line in open(p_calls, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 13 or p[0] != a.run: continue
            nomult = p[14] if len(p) > 14 else "0"
            row = [p[1][:48], p[2]] + p[4:11] + [nomult, p[11] or "-", (p[12] or "-")[:48]]
            tot = [t + int(x or 0) for t, x in zip(tot, p[4:11] + [nomult])]
            kept_seq.append(int(p[10]))
            if not a.short or p[12] or p[4] == "0" or (p[11] and int(p[10] or 0) >= 3): shown.append(row)
    rows += shown
    rows.append(["TOTAL", "", *map(str, tot), "", ""])
    print(json.dumps(rows, ensure_ascii=False))
    last = kept_seq[-a.last:]
    print(f"new qualifiers in the last {len(last)} calls: {sum(last)} | calls so far: {len(kept_seq)} | qualifiers so far: {sum(kept_seq)}"
          + (f" | calls hidden by --short: {len(kept_seq) - len(shown)} (--short shows errors, empty calls, and full pages that still found 3+ new)" if a.short else ""))
    sys.exit(0)

# ---------------- list raw ----------------
if a.list_raw:
    best = {}
    p_raw = f"{D}/raw_{a.run}.tsv"
    if os.path.exists(p_raw):
        for line in open(p_raw, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) < 14 or (a.sweep_has and a.sweep_has not in p[1]): continue
            v = num(p[8])
            if v is None: continue
            dur = num(p[12])
            if dur is not None and dur < 180: continue
            if v < a.min_views or (a.since and is_date(p[11]) and p[11] < a.since): continue
            ms = [x for x in (num(p[9]), num(p[10])) if x is not None]
            m = max(ms) if ms else None
            cur = best.get(p[4])
            if cur is None or (m or 0) > (cur[1] or 0): best[p[4]] = (p, m)
    print("id\ttitle\tchannel\tviews\tbest_multiplier\tdate\tsweep\ttool")
    for vid, (p, m) in sorted(best.items(), key=lambda kv: -(num(kv[1][0][8]) or 0)):
        print("\t".join([vid, p[5][:80], p[6][:28], p[8], f"{m:.2f}" if m is not None else "", p[11], p[1][:40], p[2]]))
    sys.exit(0)

# ---------------- fill missing durations ----------------
if a.fill_nodur:
    nf = f"{D}/nodur_{a.run}.tsv"
    if not os.path.exists(nf): print("no nodur file: nothing to fill"); sys.exit(0)
    rows = [l.rstrip("\n").split("\t") for l in open(nf, encoding="utf-8") if l.strip()]
    os.replace(nf, nf + ".done")

    def dur(vid):
        try:
            p = subprocess.run(["yt-dlp", "--no-warnings", "-q", "--extractor-args", "youtube:player_client=mweb", "--ignore-no-formats-error",
                                "--skip-download", "--print", "%(duration)s\t%(was_live)s", f"https://www.youtube.com/watch?v={vid}"],
                               capture_output=True, text=True, timeout=90)
            d_, live = (p.stdout.strip().split("\t") + [""])[:2]
            return vid, (float(d_) if d_ not in ("", "NA", "None") else None), live == "True"
        except Exception:
            return vid, None, False
    with cf.ThreadPoolExecutor(8) as ex: got = {v: (d_, live) for v, d_, live in ex.map(dur, [r[0] for r in rows])}
    groups = {}
    for r in rows:   # id, title, channel, views, o, r, date, sweep, tool, since, cross, cid, subs
        r += [""] * (13 - len(r))
        d_, live = got.get(r[0], (None, False))
        if live: d_ = 1.0   # livestream replays are dropped as "under 3 min"
        groups.setdefault((r[7], r[8], r[9], r[10]), []).append(dict(id=r[0], t=r[1], ch=r[2], v=r[3] or None, o=r[4] or None, r=r[5] or None,
                                                                     d=r[6], dur_s=d_, cid=r[11] or None, subs=r[12] or None))
    for (sw, tool, since, cross), items in groups.items():
        cmd = [sys.executable, HERE, "--run", a.run, "--dir", D, "--sweep", sw + "+dur", "--tool", tool, "--params", "durations from yt-dlp"]
        if since: cmd += ["--since", since]
        if cross == "cross": cmd += ["--cross"]
        p = subprocess.run(cmd, input=json.dumps(items), capture_output=True, text=True)
        print(f"{sw}+dur: {p.stdout.strip()}")
    print(f"filled {sum(1 for v in got.values() if v[0])} of {len(rows)} durations")
    sys.exit(0)

# ---------------- log one call ----------------
raw = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
try:
    rows = json.loads(raw) if raw else []
    if isinstance(rows, dict): rows = [rows]
except json.JSONDecodeError as e:
    rows = []; a.error = (a.error + " | " if a.error else "") + f"bad JSON piped in: {e}"

lock = open(f"{D}/.lock", "w")
fcntl.flock(lock, fcntl.LOCK_EX)
try:
    qf = f"{D}/rows_{a.run}.tsv"; seen = set()
    if os.path.exists(qf):
        for line in open(qf, encoding="utf-8"):
            if line.strip(): seen.add(line.split("\t", 1)[0])
    rise_f = f"{D}/rising_{a.run}.tsv"; rise_seen = set()
    if os.path.exists(rise_f):
        for line in open(rise_f, encoding="utf-8"):
            if line.strip(): rise_seen.add(line.split("\t", 1)[0])
    c = dict(nodur=0, short=0, window=0, thresh=0, dup=0, kept=0, assumed=0, nomult=0, nodate=0)
    with open(f"{D}/raw_{a.run}.tsv", "a", encoding="utf-8") as rf, open(qf, "a", encoding="utf-8") as qfh, \
            open(rise_f, "a", encoding="utf-8") as risef:
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict): continue
            o, rr, v, dur = num(r.get("o")), num(r.get("r")), num(r.get("v")), num(r.get("dur_s"))
            d = utc_day(r.get("d")); vid = clean(r.get("id"))
            # raw: run, sweep, tool, rank, id, title, channel, subs, views, o, r, date, dur_s, sim, cid
            rf.write("\t".join([a.run, a.sweep, a.tool, str(r.get("rank", i)), vid, clean(r.get("t")), clean(r.get("ch")),
                                sv(r.get("subs")), str(int(v)) if v is not None else sv(r.get("v")), sv(r.get("o")), sv(r.get("r")), d,
                                sv(r.get("dur_s")), sv(r.get("sim")), sv(r.get("cid"))]) + "\n")
            if dur is None:
                if a.longform_only:
                    c["assumed"] += 1; dur = 600.0
                else:
                    c["nodur"] += 1
                    with open(f"{D}/nodur_{a.run}.tsv", "a", encoding="utf-8") as nf:
                        nf.write("\t".join([vid, clean(r.get("t")), clean(r.get("ch")), str(int(v)) if v is not None else "", sv(r.get("o")),
                                            sv(r.get("r")), d, a.sweep, a.tool, a.since, "cross" if a.cross else "",
                                            sv(r.get("cid")), sv(r.get("subs"))]) + "\n")
                    continue
            if dur < 180: c["short"] += 1; continue
            if not is_date(d): c["nodate"] += 1
            elif a.since and d < a.since: c["window"] += 1; continue
            if o is None and rr is None:
                c["nomult"] += 1
                if v is not None and v >= 50000 and not a.cross and not a.tool.endswith("-thumb"):
                    with open(f"{D}/check_{a.run}.tsv", "a", encoding="utf-8") as cfh:
                        cfh.write("\t".join([vid, clean(r.get("t")), clean(r.get("ch")), str(int(v)), d, a.sweep, a.tool]) + "\n")
                continue
            if a.cross:
                ok = o is not None and v is not None and o >= 10 and v >= 200000 and dur <= 2400
            else:
                ok = passes(o, v) or passes(rr, v)
            if not ok:
                best = max([x for x in (o, rr) if x is not None], default=None)
                if not a.cross and best is not None and v is not None and best >= 5 and 20000 <= v < 50000 and vid not in rise_seen:
                    rise_seen.add(vid)
                    risef.write("\t".join([vid, clean(r.get("t")), clean(r.get("ch")), sv(r.get("subs")), str(int(v)),
                                           f"{best:.2f}", d, f"{dur/60:.1f}", a.sweep, a.tool]) + "\n")
                c["thresh"] += 1; continue
            if vid in seen: c["dup"] += 1; continue
            seen.add(vid); c["kept"] += 1
            # rows: id, title, channel, subs, views, o, r, date, dur_min, sweep, tool, cid
            qfh.write("\t".join([vid, clean(r.get("t")), clean(r.get("ch")), sv(r.get("subs")), str(int(v)),
                                 f"{o:.2f}" if o is not None else "", f"{rr:.2f}" if rr is not None else "", d,
                                 f"{dur/60:.1f}", a.sweep, a.tool, sv(r.get("cid"))]) + "\n")
    hit = "yes" if a.full or (a.limit and len(rows) >= a.limit) else ""
    with open(f"{D}/calls.tsv", "a", encoding="utf-8") as cfile:
        # calls: run, sweep, tool, params, returned, nodur, short, window, thresh, dup, kept, hit, error, assumed, nomult, nodate
        cfile.write("\t".join([a.run, a.sweep, a.tool, a.params[:60], str(len(rows)), str(c["nodur"]), str(c["short"]), str(c["window"]),
                               str(c["thresh"]), str(c["dup"]), str(c["kept"]), hit, clean(a.error), str(c["assumed"]),
                               str(c["nomult"]), str(c["nodate"])]) + "\n")
finally:
    fcntl.flock(lock, fcntl.LOCK_UN); lock.close()

print(f"returned {len(rows)} | nodur {c['nodur']} short {c['short']} window {c['window']} nomult {c['nomult']} thresh {c['thresh']} dup {c['dup']} "
      f"| new {c['kept']} | assumed-long {c['assumed']} | unreadable-date {c['nodate']} | limit-hit {hit or 'no'} | error {a.error or '-'}")
# END radar_log.py v4
