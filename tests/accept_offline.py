"""Acceptance checks that need no connector calls. Uses a throwaway database, never the real memory.
run: python tests/accept_offline.py
"""
import os, sys, json, tempfile, pathlib, time
tmp = tempfile.mkdtemp(prefix="radar-test-")
os.environ["RADAR_DB"] = os.path.join(tmp, "test.db")
os.environ["RADAR_RUNS"] = os.path.join(tmp, "runs")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from radar import store, hook, ingest, yt, rule, subjects, run as runmod, board as boardmod, vph  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (("  | " + detail) if detail else ""))


# ---- Test 5: a made-up video id and a wrong view count never reach the board with the wrong data
REAL = "e_rtENJmpq4"
fake_result = json.dumps({"videos": [
    {"video_id": "zzzzFAKEid1", "title": "Invented Bacon Video", "channel_name": "Nobody", "view_count": 900000, "outlier_score": 12.0, "duration": 900, "upload_date": "2026-10-01"},
    {"video_id": REAL, "title": "Wrong Title Typed By A Model", "channel_name": "Wrong Channel", "view_count": 99999999, "outlier_score": 6.0, "duration": 900, "upload_date": "2026-10-01"}]})
st = {"run": "t5", "subject": "bacon", "spec": {"names": ["bacon"]}, "started_at": time.time(), "window_days": 548, "tools": {"YouTube": "up"}, "extra_ids": [], "notes": [], "label_checked": True}
store.RUNS.mkdir(parents=True, exist_ok=True)
(store.RUNS / "ACTIVE").write_text("t5")
store.save_state("t5", st)
try:
    hook.post({"tool_name": "mcp__Algrow__search_viral_videos", "tool_input": {"search": "bacon brands", "content_type": "longform", "per_page": 25}, "tool_response": fake_result})
except SystemExit:
    pass
print()
con = store.db()
runmod.verify_and_filter(st, con)
con = store.db()
f = con.execute("SELECT * FROM videos WHERE id='zzzzFAKEid1'").fetchone()
r = con.execute("SELECT * FROM videos WHERE id=?", (REAL,)).fetchone()
check("5a made-up id is marked gone by YouTube", f["yt_status"] == "gone", f"status={f['yt_status']}")
check("5b wrong view count is replaced by YouTube's", r["views"] != 99999999 and r["views"] < 5_000_000, f"views={r['views']:,}")
check("5c wrong title is replaced by YouTube's", "Wrong Title" not in (r["title"] or ""), r["title"][:50])
for vid in ("zzzzFAKEid1", REAL):
    con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (vid, "bacon", "on", "test", "model", time.time()))
con.commit()
brd = boardmod.build(st, con)
ids = [c["vid"] for s in brd["sections"] if s["key"] != "combos" for c in s["items"]]
check("5d the made-up id is not on the board", "zzzzFAKEid1" not in ids)
card = next((c for s in brd["sections"] if s["key"] != "combos" for c in s["items"] if c["vid"] == REAL), None)
check("5e the real video's card carries YouTube's numbers", card is not None and card["views"] == r["views"], f"card={card and card['views']}")

# ---- Test 6: a foreign-language video with an English title is kept off the board
rows, err = yt.search("내장지방 빼는 법", "views_year", 8)
foreign = None
for row in rows:
    yt.verify_many([row["id"]])
    v = store.db().execute("SELECT * FROM videos WHERE id=?", (row["id"],)).fetchone()
    if v["yt_status"] == "ok" and v["language"] not in ("en", "unknown") and (v["duration_s"] or 0) >= 180:
        foreign = dict(v)
        break
if foreign:
    con = store.db()
    con.execute("UPDATE videos SET title='How To Lose Visceral Fat Fast (Doctor Explains)' WHERE id=?", (foreign["id"],))   # as if a tool handed us a translated title
    con.execute("INSERT OR REPLACE INTO multipliers(video_id,tool,value,seen_at,run) VALUES(?,?,?,?,?)", (foreign["id"], "algrow", 9.0, time.time(), "t5"))
    con.execute("UPDATE videos SET views=MAX(views, 400000) WHERE id=?", (foreign["id"],))
    con.execute("INSERT OR REPLACE INTO labels(video_id,subject,label,reason,labeler,ts) VALUES(?,?,?,?,?,?)", (foreign["id"], "bacon", "on", "test", "model", time.time()))
    con.commit()
    v = dict(con.execute("SELECT * FROM videos WHERE id=?", (foreign["id"],)).fetchone())
    brd = boardmod.build(st, con)
    ids = [c["vid"] for s in brd["sections"] if s["key"] != "combos" for c in s["items"]]
    check("6a language comes from YouTube's audio, not the title", v["language"] != "en", f"{v['language']}: {v['lang_note']}")
    check("6b junk filter drops it before labeling", bool(subjects.junk_reason(v)), str(subjects.junk_reason(v)))
    check("6c it is not on the board even if labeled on", foreign["id"] not in ids)
else:
    check("6 foreign video found for the test", False, "no foreign-language test video found")

# ---- Test 4: the validator catches layout breaks
brd = boardmod.build(st, con)
fails, warns = boardmod.validate(brd, con, st)
check("4a a clean board passes", not [f for f in fails if "known outlier" not in f], "; ".join(fails)[:200])
bad = json.loads(json.dumps(brd))
bad["sections"].insert(0, {"key": "cover", "name": "COVER", "items": []})
check("4b an extra section fails the build", any("sections are" in f for f in boardmod.validate(bad, con, st)[0]))
bad = json.loads(json.dumps(brd))
for s in bad["sections"]:
    for c in s["items"]:
        if c.get("vid") == REAL:
            c["views"] = 5
check("4c a card whose views differ from YouTube's fails the build", any("YouTube's own" in f for f in boardmod.validate(bad, con, st)[0]))
check("4d the rule: 2.9x at 250K fails, 3x at 100K passes, 5x at 50K passes, 2x at 300K passes",
      not rule.passes(2.9, 250000) and rule.passes(3, 100000) and rule.passes(5, 50000) and rule.passes(2, 300000) and not rule.passes(4.9, 60000))

# ---- Test 3 (unit part): views per hour is never a lifetime average
con.execute("DELETE FROM gains"); con.execute("DELETE FROM snapshots WHERE video_id=?", (REAL,)); con.commit()
v = dict(con.execute("SELECT * FROM videos WHERE id=?", (REAL,)).fetchone())
check("3a no 24 hour source -> VPH n/a, never lifetime average", vph.compute(con, v)["vph"] is None)
con.execute("INSERT INTO gains VALUES(?,?,?,?)", (REAL, time.time(), 961 / 23.0, "algrow-24h")); con.commit()
x = vph.compute(con, v)
check("3b a video gaining 961 views in 23 days shows about 2 an hour, not 34", x["vph"] is not None and x["vph"] < 3, f"{x['vph']:.2f}/hr from {x['source']}")
con.execute("DELETE FROM gains"); now = time.time()
con.execute("INSERT INTO snapshots VALUES(?,?,?,?)", (REAL, now - 20 * 60, v["views"] - 6500, "youtube"))
con.execute("INSERT INTO snapshots VALUES(?,?,?,?)", (REAL, now, v["views"], "youtube")); con.commit()
check("3c two counts 20 minutes apart are never used", vph.compute(con, v)["vph"] is None)
con.execute("INSERT INTO gains VALUES(?,?,?,?)", (REAL, time.time(), v["views"] * 3, "vidiq-vph")); con.commit()
check("3d a 24 hour gain larger than total views is thrown out", vph.compute(con, v)["vph"] is None)

# ---- Test 8: three subjects at once run one after another
(store.RUNS / "ACTIVE").write_text("")
a = runmod.start({"subject": "eggs", "names": ["eggs"]})
b = runmod.start({"subject": "seed oils", "names": ["seed oils"]})
c = runmod.start({"subject": "butter", "names": ["butter"]})
check("8a the first starts, the next two queue", "run" in a and b.get("queued") and c.get("queued") and c["position"] == 2, f"{b.get('say', '')[:60]}")
nxt = runmod.finish(a["run"])
check("8b finishing one starts the next in line", nxt and "seed-oils" in nxt.get("run", ""), str(nxt)[:80])

# ---- guard checks (no network)
import subprocess
def guard(tool, inp):
    p = subprocess.run([sys.executable, str(pathlib.Path(hook.__file__)), "pre"], input=json.dumps({"tool_name": tool, "tool_input": inp}), capture_output=True, text=True, env=os.environ)
    return "deny" in p.stdout, p.stdout[:160]
check("guard: Algrow thumbnail search by text is refused", guard("mcp__Algrow__search_by_thumbnail", {"q": "red arrow"})[0])
check("guard: TubeAI phrase over two words is refused", guard("mcp__TubeAI__explore_videos", {"search": "is bacon bad for you", "limit": 25})[0])
check("guard: TubeAI page of 50 is refused", guard("mcp__TubeAI__explore_videos", {"search": "bacon", "limit": 50})[0])
check("guard: image generation is refused", guard("mcp__vidIQ__vidiq_generate_thumbnail", {})[0])
check("guard: deleting an Algrow folder is refused", guard("mcp__Algrow__delete_folder", {"folder": "Radar pool"})[0])
check("guard: saving into a folder that is not Radar's is refused", guard("mcp__Algrow__save_channels", {"folder": "Channel Update", "channel_ids": ["UCx"]})[0])
os.environ.pop("CLAUDE_CODE_REMOTE_SESSION_ID", None)
saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("CLAUDE_CODE_REMOTE")}
try:
    yt.guard(); off = False
except yt.NotCloud:
    off = True
os.environ.update(saved)
check("privacy: YouTube-direct refuses to run outside a cloud session", off)

bad = [r for r in results if not r[1]]
print(f"\n{len(results) - len(bad)} of {len(results)} passed." + (" FAILED: " + "; ".join(r[0] for r in bad) if bad else ""))
sys.exit(1 if bad else 0)
