"""Subjects, the names people use for them, and the junk filter that runs before any model judges anything."""
import re, json
from . import store

BUCKETS = {"expose": "EXPOSÉ", "exposé": "EXPOSÉ", "fat loss": "FAT LOSS", "fatloss": "FAT LOSS", "carnivore": "CARNIVORE"}
STOP = set("""a an the and or of to in on for with from by at is are was be it this that these those you your i my we our they
them his her its as if so do does did not no yes how why what when who which will can should would could never ever always
every all any more most than then into out up down over under after before again just only very really actually here there
about me he she vs get got have has had i'm don't it's you're that's video new best worst top one two three things ways
day days year years week weeks eat eating ate food foods stop start""".split())
JUNK_TITLE = re.compile(r"\b(roblox|minecraft|fortnite|mm2|brookhaven|gta ?\d|gameplay|speedrun|lyrics?|official (music )?video|nursery|kids song|"
                        r"cocomelon|asmr|mukbang|no talking|anime|trailer|full movie|live stream|livestream|among us|fnaf|pokemon|bedtime stor)", re.I)
JUNK_NICHE = re.compile(r"^(gaming|music|kids_family|kids|animation_anime|animation|anime|movies_tv|relaxation_ambient|comedy_memes|pets_animals|animals & pets)", re.I)


def _sections(path):
    out, cur, sub = {}, None, None
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            cur, sub = line[3:].strip(), None
            out[cur] = {}
        elif line.startswith("### ") and cur:
            sub = line[4:].strip()
            out[cur][sub] = []
        elif cur and sub and line.strip() and not line.startswith(("#", "---", "Re-tested")):
            out[cur][sub].append(line.strip())
    return out


def keywords():
    return _sections(store.DATA / "keywords.md")


def topic_names():
    """data/topic_names.md: one line per subject -> 'subject: name, name, name'"""
    p = store.DATA / "topic_names.md"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                out[k.strip().lower()] = [x.strip() for x in v.split(",") if x.strip()]
    return out


def watchlist():
    """{bucket: [@handles]} from data/watchlist.md"""
    out, cur = {}, None
    for line in (store.DATA / "watchlist.md").read_text().splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur and line.strip().startswith("@"):
            out[cur].append(line.strip().split()[0])
    return out


def stem(w):
    w = w.lower()
    for suf in ("ies", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def words(text):
    return [stem(w) for w in re.findall(r"[a-zA-Z0-9']+", (text or "").lower())]


def matches(title, names):
    """True when every word of at least one name is in the title."""
    tw = set(words(title))
    for n in names:
        nw = [w for w in words(n) if w not in STOP] or words(n)
        if nw and all(w in tw for w in nw):
            return True
    return False


def junk_reason(v):
    """Obvious junk, dropped in code so a model only labels real candidates. v: dict of a video row."""
    if v.get("duration_s") is not None and v["duration_s"] < 180:
        return "under 3 minutes"
    if v.get("live"):
        return "livestream replay"
    if v.get("language") and v["language"] != "en":
        return f"not English ({v.get('lang_note') or v['language']})"
    if v.get("niche") and JUNK_NICHE.match(v["niche"]):
        return f"niche: {v['niche']}"
    if JUNK_TITLE.search(v.get("title") or ""):
        return "junk title (gaming, music, kids or similar)"
    letters = [c for c in (v.get("title") or "") if c.isalpha()]
    if letters and sum(1 for c in letters if ord(c) > 0x24F) / len(letters) > 0.3:
        return "title is not in English"
    return None


def new_terms(titles, used, k=6):
    """Search terms for the next round, built from words in the outlier titles found so far."""
    from collections import Counter
    usedw = set()
    for u in used:
        usedw.update(words(u))
    uni, bi = Counter(), Counter()
    for t in titles:
        ws = [w for w in words(t) if w not in STOP and len(w) > 2 and not w.isdigit()]
        for w in set(ws):
            uni[w] += 1
        for a, b in set(zip(ws, ws[1:])):
            bi[(a, b)] += 1
    out = []
    for (a, b), n in bi.most_common(40):
        if n >= 2 and not (a in usedw and b in usedw):
            out.append(f"{a} {b}")
    for w, n in uni.most_common(40):
        if n >= 3 and w not in usedw and not any(w in t.split() for t in out):
            out.append(w)
    return out[:k]
