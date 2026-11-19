"""Seed memory from a past Radar board (the HTML of a published board page).

Code reads the cards out of the HTML. Every seeded video becomes a known outlier for the subject, so each
future run must put it on the board or record why not. Nothing here is trusted as fact: titles, views and
dates are re-read from YouTube before a seeded video can become a card.

usage: python -m radar.seed <board.html> --subject "bacon" [--source "Radar Board - Bacon"]
"""
import re, sys, time, html, argparse
from . import store

SKIP = re.compile(r"CROSS|OFF.?TOPIC|RISING|ANY MULTIPLIER|ALL TIME|REPACKAGE|UNSORTED|ALREADY COVERED|WHAT TO MAKE|TITLE|CONCEPT|LOG|FORMATS", re.I)
TOOLS = {"algrow": "algrow", "tubeai": "tubeai", "vidiq": "vidiq", "recent-30": "recent30", "recent30": "recent30"}


def parse(text):
    """-> [(section name, video id, {tool: multiplier})]"""
    out = []
    pages = re.split(r'<div class="page">', text)
    for pg in pages[1:]:
        m = re.search(r'class="htitle">(?:<span class="dot"></span>)?(.*?)</div>', pg, re.S)
        sec = html.unescape(re.sub(r"<.*?>", "", m.group(1))).strip() if m else ""
        for card in re.split(r'<div class="card">', pg)[1:]:
            v = re.search(r'href="https://(?:youtu\.be/|www\.youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})"', card)
            if not v:
                continue
            mults = {}
            for val, tool in re.findall(r'([\d.]+)(?:&times;|×)\s*([A-Za-z0-9-]+)', card):
                t = TOOLS.get(tool.lower())
                if t:
                    mults[t] = float(val)
            out.append((sec, v.group(1), mults))
    return out


def run(path, subject, source):
    rows = parse(open(path, encoding="utf-8").read())
    con = store.db()
    n_known = n_mem = 0
    seen = set()
    for sec, vid, mults in rows:
        if vid in seen:
            continue
        seen.add(vid)
        if not con.execute("SELECT 1 FROM videos WHERE id=?", (vid,)).fetchone():
            con.execute("INSERT INTO videos(id, created_at, first_run) VALUES(?,?,?)", (vid, time.time(), "seed:" + source))
            n_mem += 1
        for tool, val in mults.items():
            con.execute("INSERT OR IGNORE INTO multipliers(video_id,tool,value,seen_at,run) VALUES(?,?,?,?,?)", (vid, tool, val, time.time(), "seed:" + source))
        if not SKIP.search(sec):
            con.execute("INSERT OR IGNORE INTO known_outliers(video_id,subject,source,note,added_at) VALUES(?,?,?,?,?)", (vid, subject.lower(), "seed:" + source, sec[:80], time.time()))
            n_known += 1
    con.commit()
    secs = {}
    for sec, vid, _ in rows:
        secs[sec] = secs.get(sec, 0) + 1
    print(f"{source}: {len(seen)} videos read from {len(secs)} sections. {n_mem} new to memory. {n_known} set as known outliers for '{subject}'.")
    for s, n in secs.items():
        print(f"   {'skip ' if SKIP.search(s) else 'known'}  {n:>4}  {s}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path"); ap.add_argument("--subject", required=True); ap.add_argument("--source", default="past board")
    a = ap.parse_args()
    run(a.path, a.subject, a.source)
