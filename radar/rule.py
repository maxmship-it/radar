"""The outlier rule. Code decides. A model never does.

MAX DECIDED: a video is an outlier if any one is true, on any tool's multiplier or on recent-30:
  3x+ with 100,000+ views, 5x+ with 50,000+ views, 2x+ with 300,000+ views.
Long form only (3 minutes or more). Cross-niche: 10x+, 200,000+ views, 40 minutes or less.
"""
MIN_LONGFORM_S = 180
MIN_VIEWS_ANY = 50_000          # no branch of the rule passes under this, so searches never ask for less
CROSS_MAX_S = 40 * 60
TOOL_LABEL = {"algrow": "Algrow", "algrow-pool": "Algrow", "tubeai": "TubeAI", "vidiq": "vidIQ", "recent30": "recent-30"}
# best-trusted first when two tools both qualify a video
TOOL_ORDER = ["algrow", "algrow-pool", "recent30", "tubeai", "vidiq"]


def passes(mult, views):
    if mult is None or views is None:
        return False
    return (mult >= 3 and views >= 100_000) or (mult >= 5 and views >= 50_000) or (mult >= 2 and views >= 300_000)


def cross_passes(mult, views, duration_s):
    return mult is not None and views is not None and mult >= 10 and views >= 200_000 and (duration_s is None or duration_s <= CROSS_MAX_S)


def best(mults, views, cross=False, duration_s=None):
    """mults: {tool: value}. Returns (tool, value) of the multiplier the card should show, or None.
    Picks a tool that actually qualifies the video, most trusted tool first."""
    ok = []
    for tool, val in (mults or {}).items():
        good = cross_passes(val, views, duration_s) if cross else passes(val, views)
        if good:
            ok.append((TOOL_ORDER.index(tool) if tool in TOOL_ORDER else 99, tool, val))
    if not ok:
        return None
    ok.sort()
    return ok[0][1], ok[0][2]


def is_longform(duration_s):
    return duration_s is not None and duration_s >= MIN_LONGFORM_S
