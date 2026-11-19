"""Board JSON -> PDF and an HTML twin. Same dark Built By Biology look as before: 1280 x 905 pages, 4 cards to a page.

Only what the new layout needs was changed: the two age parts, the capped cross-niche part, a true
views-per-hour line on every card, and one final page of combos. No cover. No log. No tables.
"""
import json, base64, pathlib, urllib.request, html, concurrent.futures as cf

BG = "#0a0a0b"; CARD = "#141416"; TXT = "#eaeaea"; MUTED = "#8a8a8a"; BLUE = "#0187fc"; LINE = "#232326"
RED = "#ff3030"; ORANGE = "#f5872b"; GREEN = "#2fb56c"; FONT = "Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
_THUMBS = {}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def k(n):
    n = n or 0
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{n / 1000:.0f}K"
    return str(n)


def badge(o):
    if o is None:
        return f"background:{LINE};color:{MUTED};"
    if o >= 10:
        return f"background:{RED};color:#fff;"
    if o >= 5:
        return f"background:{ORANGE};color:#1a0e00;"
    if o >= 3:
        return f"background:{BLUE};color:#fff;"
    return f"background:{LINE};color:{TXT};"


def thumb_uri(vid):
    if not vid:
        return ""
    if vid in _THUMBS:
        return _THUMBS[vid]
    for q in ("mqdefault", "hqdefault"):
        try:
            data = urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{q}.jpg", timeout=10).read()
            if len(data) > 2000:
                _THUMBS[vid] = "data:image/jpeg;base64," + base64.b64encode(data).decode()
                return _THUMBS[vid]
        except Exception:
            pass
    _THUMBS[vid] = ""
    return ""


def prefetch(board):
    ids = set()
    for sec in board["sections"]:
        for it in sec["items"]:
            ids.add(it.get("vid") or it.get("model_vid"))
    with cf.ThreadPoolExecutor(12) as ex:
        list(ex.map(thumb_uri, [i for i in ids if i]))
    return [i for i in ids if i and not _THUMBS.get(i)]


CSS = f"""
@page {{ size: 1280px 905px; margin:0; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:{BG}; color:{TXT}; font-family:{FONT}; }}
.page {{ width:1280px; height:905px; padding:44px 56px 40px; page-break-after:always; position:relative; overflow:hidden; }}
a {{ color:inherit; text-decoration:none; }}
.header {{ display:flex; justify-content:space-between; align-items:flex-end; }}
.htitle {{ font-weight:800; font-size:22px; letter-spacing:.02em; }}
.htitle .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; background:{BLUE}; margin-right:10px; vertical-align:1px; }}
.hmeta {{ color:{MUTED}; font-weight:600; font-size:12px; }}
.partial {{ color:{ORANGE}; font-weight:800; }}
.rule {{ height:2px; background:{BLUE}; opacity:.9; margin:12px 0 22px; }}
.grid {{ display:grid; grid-template-columns:repeat(2,1fr); grid-template-rows:repeat(2,1fr); gap:22px; height:770px; }}
.card {{ background:{CARD}; border:1px solid {LINE}; border-radius:14px; padding:14px; display:grid; grid-template-columns:300px 1fr; gap:16px; align-content:start; }}
a.thumb {{ display:block; position:relative; width:300px; aspect-ratio:16/9; grid-row:1/7; background:#000 center/cover no-repeat; border-radius:8px; overflow:hidden; }}
.rank {{ position:absolute; top:8px; left:8px; background:{BLUE}; color:#fff; font-weight:800; font-size:15px; padding:4px 10px; border-radius:6px; }}
.ob {{ position:absolute; bottom:8px; right:8px; text-align:center; padding:5px 9px; border-radius:8px; }}
.obnum {{ font-weight:900; font-size:17px; line-height:1; }}
.oblab {{ font-weight:700; font-size:9px; letter-spacing:.08em; opacity:.85; }}
.chan {{ color:{MUTED}; font-weight:700; font-size:12px; letter-spacing:.06em; text-transform:uppercase; margin:2px 0 6px; }}
.title {{ font-weight:800; font-size:19px; line-height:1.25; max-height:3.75em; overflow:hidden; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; }}
.views {{ font-weight:800; font-size:20px; margin:10px 0 2px; }}
.vph {{ font-weight:700; font-size:14px; margin:0 0 8px; color:{GREEN}; }}
.vph.na {{ color:{MUTED}; }}
.vph span {{ color:{MUTED}; font-weight:600; font-size:11px; }}
.metarow {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px; }}
.pill {{ font-weight:800; font-size:12px; padding:5px 10px; border-radius:6px; white-space:nowrap; }}
.age {{ color:{MUTED}; font-weight:600; font-size:11px; }}
.niche {{ color:{BLUE}; font-weight:800; font-size:10px; letter-spacing:.1em; text-transform:uppercase; margin-top:8px; }}
.pattern {{ font-size:12px; line-height:1.4; margin-top:3px; }}
.combos {{ display:grid; grid-template-columns:1fr 1fr; grid-template-rows:repeat(5,1fr); gap:12px 18px; height:770px; }}
.combo {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:10px 12px; display:grid; grid-template-columns:212px 1fr; gap:14px; overflow:hidden; }}
.combo .ct {{ position:relative; width:212px; aspect-ratio:16/9; background:#000 center/cover no-repeat; border-radius:6px; align-self:center; display:block; }}
.combo .cn {{ position:absolute; top:6px; left:6px; background:{BLUE}; color:#fff; font-weight:800; font-size:13px; padding:2px 8px; border-radius:5px; }}
.combo .tt {{ font-weight:800; font-size:16px; line-height:1.22; max-height:2.5em; overflow:hidden; }}
.combo .tw {{ font-weight:900; font-size:13px; color:{ORANGE}; margin-top:5px; letter-spacing:.02em; }}
.combo .tw span {{ color:{MUTED}; font-weight:700; font-size:9px; letter-spacing:.1em; margin-right:6px; }}
.combo .il {{ font-size:11.5px; line-height:1.35; margin-top:3px; max-height:2.7em; overflow:hidden; }}
.combo .mo {{ color:{MUTED}; font-size:10px; margin-top:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.foot {{ position:absolute; bottom:18px; left:56px; right:56px; display:flex; justify-content:space-between; color:{MUTED}; font-size:10px; font-weight:600; }}
"""


def header(name, meta, date, pg, total, partial):
    tag = '<span class="partial">PARTIAL RUN</span> &nbsp;|&nbsp; ' if partial else ""
    return (f'<div class="header"><div class="htitle"><span class="dot"></span>{esc(name)}</div>'
            f'<div class="hmeta">{tag}{esc(meta)} &nbsp;|&nbsp; {esc(date)} &nbsp;|&nbsp; Page {pg}/{total}</div></div><div class="rule"></div>')


def foot():
    return ('<div class="foot"><div>BUILT BY BIOLOGY · RADAR</div><div>Outlier = views ÷ what that channel usually gets, tool named on each card · '
            'Views per hour = views gained in the last 24 hours ÷ 24</div></div>')


def card(d):
    url = f"https://www.youtube.com/watch?v={d['vid']}"
    m = d.get("mult")
    if d.get("vph") is not None:
        vph = f'<div class="vph">{d["vph"]:,.0f} views per hour <span>{esc(d.get("vph_src"))}</span></div>'
    else:
        vph = '<div class="vph na">VPH n/a</div>'
    extra = ""
    if d.get("niche") or d.get("pattern"):
        extra = f'<div class="niche">{esc(d.get("niche") or "cross-niche")}</div><div class="pattern">{esc(d.get("pattern"))}</div>'
    subs = (" &middot; " + k(d.get("subs")) + " SUBS") if d.get("subs") else ""
    return f"""<div class="card"><a class="thumb" href="{url}" style="background-image:url('{thumb_uri(d["vid"])}')">
      <div class="rank">{d["no"]}</div>
      <div class="ob" style="{badge(m)}"><div class="obnum">{m:.1f}&times;</div><div class="oblab">OUTLIER</div></div></a>
      <div class="chan">{esc(d.get("channel"))}{subs}</div>
      <a class="title" href="{url}">{esc(d.get("title"))}</a>
      <div class="views">{(d.get("views") or 0):,} views</div>
      {vph}
      <div class="metarow"><span class="pill" style="{badge(m)}">&#9889; {m:.1f}&times; {esc(d.get("mult_src"))}</span><span class="age">{esc(d.get("age"))}</span></div>{extra}</div>"""


def combo(i, c):
    url = f"https://www.youtube.com/watch?v={c.get('model_vid')}"
    mo = f"Modeled on{' card ' + str(c['model_no']) if c.get('model_no') else ''}: {esc(c.get('model_channel'))} &middot; {(c.get('model_views') or 0):,} views"
    if c.get("model_mult") is not None:
        mo += f" &middot; {c['model_mult']:.1f}&times; {esc(c.get('model_src'))}"
    return f"""<div class="combo"><a class="ct" href="{url}" style="background-image:url('{thumb_uri(c.get("model_vid"))}')"><div class="cn">{i}</div></a>
      <div><div class="tt">{esc(c.get("title"))}</div>
      <div class="tw"><span>THUMBNAIL</span>{esc(c.get("thumb_words"))}</div>
      <div class="il">{esc(c.get("image_line"))}</div>
      <div class="mo">{mo}</div></div></div>"""


def render_html(board):
    pages = []
    for sec in board["sections"]:
        if sec["key"] == "combos":
            if sec["items"]:
                body = "".join(combo(i, c) for i, c in enumerate(sec["items"], 1))
                pages.append((sec["name"], "Your title · thumbnail words · your image · the real outlier it is modeled on", f'<div class="combos">{body}</div>'))
            continue
        n = len(sec["items"])
        meta = f"{n} outlier{'s' if n != 1 else ''} · most views first"
        if sec["key"] == "cross":
            meta = "Other niches · formats and thumbnail ideas that transfer"
        for i in range(0, n, 4):
            pages.append((sec["name"], meta, f'<div class="grid">{"".join(card(d) for d in sec["items"][i:i + 4])}</div>'))
        if n == 0:
            pages.append((sec["name"], "0 outliers in this window", '<div class="grid"></div>'))
    total = len(pages)
    out = "".join(f'<div class="page">{header(p[0], p[1], board["date"], i, total, board.get("partial"))}{p[2]}{foot()}</div>' for i, p in enumerate(pages, 1))
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(board['title'])}</title><style>{CSS}</style></head><body>{out}</body></html>", total


def render(board, pdf_path):
    missing = prefetch(board)
    html_out, total = render_html(board)
    pdf_path = pathlib.Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(html_out)
    script = pathlib.Path(__file__).with_name("render_pdf.js")
    import subprocess
    r = subprocess.run(["node", str(script), str(html_path.resolve()), str(pdf_path.resolve())], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise SystemExit("PDF render failed: " + r.stderr[-800:])
    previews = json.loads(r.stdout.strip().splitlines()[-1])
    return {"pdf": str(pdf_path), "html": str(html_path), "pages": total, "previews": previews, "missing_thumbnails": missing}
