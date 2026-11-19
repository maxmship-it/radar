#!/usr/bin/env python3
"""
render_board.py v3 — renders a Radar board (sweep, topic or packaging) to PDF and HTML.

Input: a JSON file with this shape (all sections optional):
{
  "title": "RADAR BOARD",
  "date": "Tue 23 Sep 2026",
  "summary": {"status": "complete" | "partial", "notes": ["tools connected", "sweeps skipped", "rotation group"]},
  "sections": [
    {"kind": "cards", "name": "LAST 14 DAYS — OUTLIERS", "meta": "Outlier = views ÷ channel avg", "items": [
       {"rank": 1, "channel": "...", "subs": 209000, "title": "...", "views": 1363000,
        "outlier": 67.2, "outlier_src": "Algrow", "recent": 41.0, "age": "13 days ago", "vid": "KxpN-EWsMYw", "note": "optional one-liner"}
       outlier = the tool's multiplier, outlier_src = which tool, recent = recent-30 median multiplier (all optional)
    ]},
    {"kind": "packaging", "name": "CROSS-NICHE PACKAGING", "items": [ ...same as cards, plus "format": "..." ]},
    {"kind": "repackage", "name": "ALREADY COVERED — REPACKAGE", "items": [
       {"mine_vid": "...", "mine_title": "...", "mine_views": 465000, "mine_age": "3 months ago",
        "their_vid": "...", "their_channel": "...", "their_title": "...", "their_outlier": 2.24, "sugg": "..."}
    ]},
    {"kind": "ideas", "name": "WHAT TO MAKE NEXT", "items": [
       {"title": "...", "thumb": "...", "bucket": "exposé|optimisation|carnivore", "colour": "GREEN|BLUE|RED|YELLOW",
        "why_now": "...", "evidence": ["..."]}      ("hook" is optional and only shown if present)
    ]},
    {"kind": "table", "name": "TITLE FORMATS", "columns": ["Format","Hits","Channels","Best x","Example"], "rows": [[...]]},
    {"kind": "list", "name": "AUDIENCE QUESTIONS", "items": ["...", "..."]},
    {"kind": "titles", "name": "TITLE OPTIONS", "items": [
       {"title": "...", "why": "...", "vid": "model video id", "model_title": "...", "model_channel": "...", "model_views": 250000, "model_outlier": 6.1}
    ]},
    {"kind": "concepts", "name": "THUMBNAIL CONCEPTS", "items": [
       {"name": "Concept A", "text": "words on the thumbnail", "describe": "one line on the image", "vids": ["id1","id2","id3"]}
    ]},
    {"kind": "log", "name": "COVERAGE LOG", "rows": [["Sweep","Returned","Qualifying","Notes"], [...]], "lines": ["one line", "..."]}
  ]
}

Usage: python3 render_board.py board.json out.pdf
Thumbnails are fetched from i.ytimg.com (mqdefault, 320x180, small enough that big boards stay under the 16 MB artifact limit) and embedded as base64. Needs playwright (pip install playwright && playwright install chromium).
"""
import sys, json, base64, math, pathlib, urllib.request, html, concurrent.futures as cf

# ---- Built By Biology tokens ----
BG="#0a0a0b"; CARD="#141416"; TXT="#eaeaea"; MUTED="#8a8a8a"; BLUE="#0187fc"; LINE="#232326"
RED="#ff3030"; ORANGE="#f5872b"; FONT="Inter, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
COLOUR={"RED":"#ff3030","YELLOW":"#f5b81c","GREEN":"#2fb56c","BLUE":"#0187fc"}

def esc(s): return html.escape(str(s if s is not None else ""))
def k(n):
    n=n or 0
    if n>=1_000_000: return f"{n/1_000_000:.1f}".rstrip('0').rstrip('.')+"M"
    if n>=1000: return f"{n/1000:.0f}K"
    return str(n)
def views(n): return f"{(n or 0):,}"
def badge(o):
    if o is None: return f"background:{LINE};color:{MUTED};"
    if o>=10: return f"background:{RED};color:#fff;"
    if o>=5:  return f"background:{ORANGE};color:#1a0e00;"
    if o>=3:  return f"background:{BLUE};color:#fff;"
    return f"background:{LINE};color:{TXT};"
def thumb_uri(vid):
    if not vid: return ""
    if vid in _THUMBS: return _THUMBS[vid]
    for q in ("mqdefault","hqdefault"):
        try:
            data=urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/{q}.jpg",timeout=8).read()
            if len(data)>2000:
                _THUMBS[vid]="data:image/jpeg;base64,"+base64.b64encode(data).decode(); return _THUMBS[vid]
        except Exception: pass
    _THUMBS[vid]=""; return ""
_THUMBS={}
def prefetch(board):
    ids=set()
    for sec in board.get("sections",[]):
        for it in sec.get("items",[]) or []:
            if isinstance(it,dict):
                for key in ("vid","mine_vid","their_vid"):
                    if it.get(key): ids.add(it[key])
                for v in it.get("vids",[]) or []: ids.add(v)
    with cf.ThreadPoolExecutor(12) as ex: list(ex.map(thumb_uri, ids))

CSS=f"""
@page {{ size: 1280px 905px; margin:0; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:{BG}; color:{TXT}; font-family:{FONT}; }}
.page {{ width:1280px; height:905px; padding:44px 56px 40px; page-break-after:always; position:relative; overflow:hidden; }}
a {{ color:inherit; text-decoration:none; }}
a.thumb {{ display:block; }}
td a {{ color:{BLUE}; }}
.header {{ display:flex; justify-content:space-between; align-items:flex-end; }}
.htitle {{ font-weight:800; font-size:22px; letter-spacing:.02em; }}
.htitle .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; background:{BLUE}; margin-right:10px; vertical-align:1px; }}
.hmeta {{ color:{MUTED}; font-weight:600; font-size:12px; }}
.rule {{ height:2px; background:{BLUE}; opacity:.9; margin:12px 0 22px; }}
.grid {{ display:grid; grid-template-columns:repeat(2,1fr); grid-template-rows:repeat(2,1fr); gap:22px; height:770px; }}
.card {{ background:{CARD}; border:1px solid {LINE}; border-radius:14px; padding:14px; display:grid; grid-template-columns:300px 1fr; gap:16px; align-content:start; }}
.thumb {{ position:relative; width:300px; aspect-ratio:16/9; grid-row:1/6; background:#000 center/cover no-repeat; border-radius:8px; overflow:hidden; }}
.rank {{ position:absolute; top:8px; left:8px; background:{BLUE}; color:#fff; font-weight:800; font-size:15px; padding:4px 10px; border-radius:6px; }}
.ob {{ position:absolute; bottom:8px; right:8px; text-align:center; padding:5px 9px; border-radius:8px; }}
.obnum {{ font-weight:900; font-size:17px; line-height:1; }}
.oblab {{ font-weight:700; font-size:9px; letter-spacing:.08em; opacity:.85; }}
.chan {{ color:{MUTED}; font-weight:700; font-size:12px; letter-spacing:.06em; text-transform:uppercase; margin:2px 0 6px; }}
.title {{ font-weight:800; font-size:19px; line-height:1.25; max-height:3.75em; overflow:hidden; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; }}
.views {{ font-weight:800; font-size:20px; margin:10px 0 8px; }}
.metarow {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px; }}
.pill {{ font-weight:800; font-size:12px; padding:5px 10px; border-radius:6px; white-space:nowrap; }}
.age {{ color:{MUTED}; font-weight:600; font-size:11px; }}
.note {{ color:{MUTED}; font-size:12px; margin-top:10px; line-height:1.4; }}
.fmt {{ color:{BLUE}; font-weight:700; font-size:11px; margin-top:8px; }}
.recall-ok {{ border:1px solid #2fb56c; color:#2fb56c; background:rgba(47,181,108,.08); padding:14px 18px; border-radius:10px; font-weight:700; }}
.recall-bad {{ border:2px solid {RED}; color:{RED}; background:rgba(255,48,48,.08); padding:14px 18px; border-radius:10px; font-weight:700; }}
.world {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.witem {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:14px 16px; }}
.wtype {{ font-size:10px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; color:{BLUE}; }}
.wtype.unv {{ color:{ORANGE}; }}
.wsrc {{ color:{MUTED}; font-size:11px; margin:4px 0 8px; }}
.wclaim {{ font-weight:700; font-size:14px; line-height:1.35; }}
.wangle {{ font-size:12px; margin-top:8px; line-height:1.4; }}
.wtitles {{ margin-top:8px; font-size:12px; line-height:1.5; color:{TXT}; }}
.wtitles span {{ color:{BLUE}; font-weight:800; margin-right:6px; }}
.rp {{ display:grid; grid-template-columns:1fr 60px 1fr; gap:12px; align-items:center; background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:12px; margin-bottom:14px; }}
.rp .side {{ display:flex; gap:12px; align-items:center; }}
.rp .side .t {{ width:150px; aspect-ratio:16/9; background:#000 center/cover no-repeat; border-radius:6px; flex:none; }}
.rp .arrow {{ text-align:center; color:{BLUE}; font-weight:900; font-size:26px; }}
.rp .lbl {{ color:{MUTED}; font-size:10px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
.rp .tt {{ font-weight:700; font-size:12px; line-height:1.3; margin-top:3px; }}
.rp .vv {{ color:{MUTED}; font-size:11px; margin-top:3px; }}
.sugg {{ grid-column:1/-1; background:rgba(1,135,252,.08); border-left:3px solid {BLUE}; padding:8px 12px; border-radius:0 8px 8px 0; font-size:12px; line-height:1.4; }}
.ideas {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.idea {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:14px 16px; }}
.idea .t {{ font-weight:800; font-size:15px; line-height:1.3; }}
.idea .tags {{ margin:8px 0; display:flex; gap:8px; }}
.tag {{ font-size:10px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; padding:3px 8px; border-radius:5px; border:1px solid; }}
.idea .row {{ font-size:12px; line-height:1.45; margin-top:5px; }}
.idea .row b {{ color:{MUTED}; font-weight:700; margin-right:6px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ text-align:left; color:{MUTED}; font-weight:800; font-size:10px; letter-spacing:.08em; text-transform:uppercase; padding:8px 10px; border-bottom:1px solid {LINE}; }}
td {{ padding:8px 10px; border-bottom:1px solid {LINE}; vertical-align:top; }}
ul.list {{ columns:2; column-gap:40px; font-size:13px; line-height:1.5; padding-left:18px; }}
.tline {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:12px 16px; margin-bottom:12px; }}
.tt2 {{ font-weight:800; font-size:18px; line-height:1.3; }}
.why {{ color:{TXT}; font-size:12px; margin:6px 0 8px; line-height:1.4; }}
.model {{ display:flex; gap:12px; align-items:center; color:{MUTED}; font-size:11px; }}
.model .mt {{ width:120px; aspect-ratio:16/9; background:#000 center/cover no-repeat; border-radius:6px; flex:none; }}
.concept {{ background:{CARD}; border:1px solid {LINE}; border-radius:14px; padding:22px 26px; }}
.cname {{ color:{BLUE}; font-weight:800; font-size:12px; letter-spacing:.1em; text-transform:uppercase; }}
.ctext {{ font-weight:900; font-size:34px; margin:10px 0; }}
.cdesc {{ font-size:15px; line-height:1.45; margin-bottom:18px; }}
.crow {{ display:flex; gap:16px; }}
.crow .ct {{ width:360px; aspect-ratio:16/9; background:#000 center/cover no-repeat; border-radius:8px; }}
ul.loglines {{ font-size:12px; line-height:1.5; margin-top:16px; padding-left:18px; }}
.foot {{ position:absolute; bottom:18px; left:56px; right:56px; display:flex; justify-content:space-between; color:{MUTED}; font-size:10px; font-weight:600; }}
"""

def header(name, meta, date, pg, total):
    return f'<div class="header"><div class="htitle"><span class="dot"></span>{esc(name)}</div><div class="hmeta">{esc(meta)} &nbsp;|&nbsp; {esc(date)} &nbsp;|&nbsp; Page {pg}/{total}</div></div><div class="rule"></div>'

def foot():
    return f'<div class="foot"><div>BUILT BY BIOLOGY · RADAR</div><div>Outlier = views ÷ what that channel usually gets · tool named on each card · recent-30 = vs its last 30 uploads</div></div>'

def num(x):
    return x if isinstance(x,(int,float)) else None

def card(d):
    o1=num(d.get("outlier")); o2=num(d.get("recent"))
    ob=max([x for x in (o1,o2) if x is not None], default=None)
    obtxt=f"{ob:.1f}&times;" if ob is not None else "n/a"
    src=esc(d.get("outlier_src") or "")
    pills=""
    if o1 is not None: pills+=f'<span class="pill" style="{badge(o1)}">&#9889; {o1:.1f}&times; {src}</span>'
    if o2 is not None: pills+=f'<span class="pill" style="{badge(o2)}">{o2:.1f}&times; recent-30</span>'
    if not pills: pills=f'<span class="pill" style="{badge(None)}">no multiplier</span>'
    fmt=f'<div class="fmt">{esc(d["format"])}</div>' if d.get("format") else ""
    note=f'<div class="note">{esc(d["note"])}</div>' if d.get("note") else ""
    url=f"https://youtu.be/{d.get('vid')}" if d.get("vid") else "#"
    return f"""<div class="card"><a class="thumb" href="{url}" style="background-image:url('{thumb_uri(d.get("vid"))}')">
      <div class="rank">{d.get("rank","")}</div>
      <div class="ob" style="{badge(ob)}"><div class="obnum">{obtxt}</div><div class="oblab">OUTLIER</div></div></a>
      <div class="chan">{esc(d.get("channel",""))}{(" &middot; "+k(d.get("subs"))+" SUBS") if d.get("subs") else ""}</div>
      <a class="title" href="{url}">{esc(d.get("title",""))}</a>
      <div class="views">{views(d.get("views"))} views</div>
      <div class="metarow">{pills}<span class="age">{esc(d.get("age",""))}</span></div>{fmt}{note}</div>"""

def cell(c):
    c=str(c if c is not None else "")
    if c.startswith("youtu.be/") or c.startswith("https://youtu.be/"):
        u=c if c.startswith("http") else "https://"+c
        return f'<a href="{esc(u)}">{esc(c.replace("https://",""))}</a>'
    return esc(c[:120])
def paginate(items, per): return [items[i:i+per] for i in range(0,len(items),per)] or [[]]

def render(board):
    date=board.get("date",""); pages=[]
    # recall page
    rc=board.get("summary",board.get("recall",{"status":"complete","notes":[]}))
    cls="recall-ok" if rc.get("status") in ("complete","clean") else "recall-bad"
    head="RUN SUMMARY: every sweep ran." if rc.get("status") in ("complete","clean") else "RUN SUMMARY: PARTIAL RUN, see below for what was skipped."
    notes="".join(f"<div style='font-weight:600;margin-top:6px'>{esc(n)}</div>" for n in rc.get("notes",[]))
    pages.append(("__cover__", f'<div class="{cls}">{head}{notes}</div>'))
    for sec in board.get("sections",[]):
        kind=sec.get("kind"); name=sec.get("name",""); meta=sec.get("meta","")
        if kind in ("cards","packaging"):
            for chunk in paginate(sec.get("items",[]),4):
                pages.append((name, meta, f'<div class="grid">{"".join(card(d) for d in chunk)}</div>'))
        elif kind=="world":
            for chunk in paginate(sec.get("items",[]),4):
                body=""
                for it in chunk:
                    unv=" unv" if it.get("unverified") else ""
                    t=esc(it.get("type","")).upper()+(" · UNVERIFIED" if it.get("unverified") else "")
                    titles="".join(f'<div><span>{i+1}</span>{esc(x)}</div>' for i,x in enumerate(it.get("titles",[])))
                    body+=f'<div class="witem"><div class="wtype{unv}">{t}</div><div class="wsrc">{esc(it.get("source",""))}</div><div class="wclaim">{esc(it.get("claim",""))}</div><div class="wangle"><b style="color:{MUTED}">Angle</b> &nbsp;{esc(it.get("angle",""))}</div><div class="wtitles">{titles}</div></div>'
                pages.append((name, meta, f'<div class="world">{body}</div>'))
        elif kind=="repackage":
            for chunk in paginate(sec.get("items",[]),3):
                body=""
                for it in chunk:
                    body+=f"""<div class="rp">
                      <div class="side"><div class="t" style="background-image:url('{thumb_uri(it.get("mine_vid"))}')"></div><div><div class="lbl">Yours</div><div class="tt">{esc(it.get("mine_title"))}</div><div class="vv">{views(it.get("mine_views"))} views &middot; {esc(it.get("mine_age",""))}</div></div></div>
                      <div class="arrow">&rarr;</div>
                      <div class="side"><div class="t" style="background-image:url('{thumb_uri(it.get("their_vid"))}')"></div><div><div class="lbl">{esc(it.get("their_channel",""))} &middot; {(num(it.get("their_outlier")) or 0):.1f}&times; {esc(it.get("their_src",""))}</div><div class="tt">{esc(it.get("their_title"))}</div></div></div>
                      <div class="sugg">{esc(it.get("sugg",""))}</div></div>"""
                pages.append((name, meta, body))
        elif kind=="ideas":
            for chunk in paginate(sec.get("items",[]),6):
                body=""
                for it in chunk:
                    c=COLOUR.get(str(it.get("colour","")).upper(),BLUE)
                    ev="; ".join(it.get("evidence",[]))
                    body+=f"""<div class="idea"><div class="t">{esc(it.get("title"))}</div>
                      <div class="tags"><span class="tag" style="color:{BLUE};border-color:{BLUE}">{esc(it.get("bucket",""))}</span><span class="tag" style="color:{c};border-color:{c}">{esc(it.get("colour",""))}</span></div>
                      <div class="row"><b>Thumb</b>{esc(it.get("thumb",""))}</div>
                      {f'<div class="row"><b>Hook</b>{esc(it.get("hook"))}</div>' if it.get("hook") else ""}
                      <div class="row"><b>Why now</b>{esc(it.get("why_now",""))}</div>
                      <div class="row"><b>Evidence</b>{esc(ev)}</div></div>"""
                pages.append((name, meta, f'<div class="ideas">{body}</div>'))
        elif kind=="table":
            cols=sec.get("columns",[]); rows=sec.get("rows",[])
            for chunk in paginate(rows,12):
                th="".join(f"<th>{esc(c)}</th>" for c in cols)
                tr="".join("<tr>"+"".join(f"<td>{cell(c)}</td>" for c in r)+"</tr>" for r in chunk)
                pages.append((name, meta, f"<table><tr>{th}</tr>{tr}</table>"))
        elif kind=="list":
            for chunk in paginate(sec.get("items",[]),30):
                pages.append((name, meta, "<ul class='list'>"+"".join(f"<li>{esc(x)}</li>" for x in chunk)+"</ul>"))
        elif kind=="titles":
            for chunk in paginate(sec.get("items",[]),5):
                body=""
                for n,it in enumerate(chunk):
                    mo=num(it.get("model_outlier"))
                    model=f'{esc(it.get("model_title",""))} &middot; {esc(it.get("model_channel",""))} &middot; {views(it.get("model_views"))} views' + (f' &middot; {mo:.1f}&times;' if mo is not None else "")
                    body+=f"""<div class="tline"><div class="tt2">{esc(it.get("title"))}</div><div class="why">{esc(it.get("why",""))}</div>
                      <div class="model"><div class="mt" style="background-image:url('{thumb_uri(it.get("vid"))}')"></div><div>Modeled on: {model}</div></div></div>"""
                pages.append((name, meta, body))
        elif kind=="concepts":
            for it in sec.get("items",[]):
                thumbs="".join(f'<div class="ct" style="background-image:url(\'{thumb_uri(v)}\')"></div>' for v in it.get("vids",[])[:3])
                body=f"""<div class="concept"><div class="cname">{esc(it.get("name",""))}</div><div class="ctext">{esc(it.get("text",""))}</div>
                  <div class="cdesc">{esc(it.get("describe",""))}</div><div class="crow">{thumbs}</div></div>"""
                pages.append((name, meta, body))
        elif kind=="log":
            rows=sec.get("rows",[]); lines=sec.get("lines",[])
            th="".join(f"<th>{esc(c)}</th>" for c in rows[0]) if rows else ""
            body=rows[1:]
            chunks=paginate(body,12) if body else [[]]
            for i,chunk in enumerate(chunks):
                tr="".join("<tr>"+"".join(f"<td>{esc(str(c)[:48])}</td>" for c in r)+"</tr>" for r in chunk)
                tbl=f"<table><tr>{th}</tr>{tr}</table>" if rows else ""
                pages.append((name, meta, tbl))
            for chunk in paginate(lines,10):   # log lines get their own pages so they never overflow
                if chunk: pages.append((name, meta, "<ul class='loglines'>"+"".join(f"<li>{esc(x)}</li>" for x in chunk)+"</ul>"))
    total=len(pages); out=""
    for i,p in enumerate(pages,1):
        if p[0]=="__cover__":
            out+=f'<div class="page">{header(board.get("title","RADAR BOARD"),"Built By Biology",date,i,total)}{p[1]}{foot()}</div>'
        else:
            out+=f'<div class="page">{header(p[0],p[1],date,i,total)}{p[2]}{foot()}</div>'
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(board.get('title','Radar Board'))}</title><style>{CSS}</style></head><body>{out}</body></html>"

def main():
    src, dst = sys.argv[1], sys.argv[2]
    board=json.load(open(src)); prefetch(board); html_out=render(board)
    tmp=pathlib.Path(dst).with_suffix(".html"); tmp.write_text(html_out)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":905})
        pg.goto(tmp.resolve().as_uri()); pg.wait_for_timeout(500)
        pg.pdf(path=dst, width="1280px", height="905px", print_background=True, margin={"top":"0","bottom":"0","left":"0","right":"0"})
        prev=[]
        for i,el in enumerate(pg.query_selector_all(".page"),1):   # small previews so the pages can be checked by eye
            pth=str(pathlib.Path(dst).with_suffix(""))+f"-p{i:02d}.jpg"; el.screenshot(path=pth, type="jpeg", quality=55); prev.append(pth)
        b.close()
    print("wrote", dst, "and", tmp)
    print(f"{len(prev)} page previews: {prev[0]} ... {prev[-1]}" if prev else "no previews")

if __name__=="__main__": main()
# END render_board.py v3
