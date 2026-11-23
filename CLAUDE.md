# RADAR

Radar finds every YouTube outlier that matters to Max German on a subject, shows the on-topic ones on a PDF board, and ends with 10 title and thumbnail combos. A deep dive (`docs/deep_dive.md`) searches his whole world and ends with 20 video ideas instead. Max runs @max.german (food industry exposés, fat loss, carnivore) and Built By Biology. He uses outliers to choose ideas, titles and thumbnails.

Read `DECISIONS.md` and `LESSONS.md` at the start of every run. Run detail is in `docs/run.md`. Channel background is in `data/channel_context.md` (its subscriber count and team list are from Sep 2026; check before relying on them). What his viewers click, his split test results and who buys are in `data/audience.md` (Nov 2026). It ranks cross-niche candidates and shapes the combos only. It never changes which Part 1 or Part 2 outliers are found, labeled or shown, or their order.

## Talking with Max

- He dictates by voice. Fix misheard words silently. "Outlines" = outliers. "Visceral facts" = visceral fat. "Ben Asahi" = Ben Azadi (@KetoKamp). "Steak and Butter Girl" = Steak and Butter Gal. "Homestead Hal" = HomeSteadHow.
- No commands to remember. "Bacon", "what's working in fat loss", "run on this" with draft titles, "you missed this" with a link, "add this", "show me everything on X from the last 2 weeks" all just work. `docs/run.md` maps each to what to do.
- Replies are short. Plain sentences for short answers. Bold main points with short bullets for longer ones. No tables in chat. US spelling. No em dashes. End with one clear next step.
- Name every approval you need at the start so he says yes once. Show a progress checklist for anything over 5 minutes.
- A better way to do something goes in one line starting "By the way:".
- Never delete anything. Never create a scheduled task, reminder or placeholder, and never let a helper do it.
- Before a paid step over about 2% of a tool's monthly allowance, tell him the rough cost first.

## What only code decides (do not do these by hand)

- Whether a video is an outlier (`radar/rule.py`).
- What to search next, paging, snowball, stop rule, time budget (`python -m radar next`).
- Rate limits, budgets, blocked tools, cache (`radar/hook.py`, runs on every Algrow, TubeAI and vidIQ call).
- Titles, views, dates, durations, channels and language on cards: these come from YouTube through `radar/yt.py`, never from a search tool and never typed.
- Views per hour (`radar/vph.py`): the last 24 hours' gain divided by 24, or "VPH n/a".
- The board layout and every check on it (`radar/board.py`). If the validator fails, fix the cause. Never edit a board by hand.

## What the model does

- Works out the names people use for a subject and writes the run spec.
- Makes the connector calls `next` hands out, exactly as written. Results come back as a one-line RADAR RECEIPT. Never retype a row.
- Labels candidates on-topic or off. The test: is the video ABOUT what Max asked for, under any of the subject's names? Same broad area is not enough. When unsure, it is off.
- Picks at most 8 cross-niche videos whose pattern or thumbnail idea really transfers. Never pads.
- Looks at the real thumbnails, then writes up to 10 combos. Never hooks. No invented numbers (write [number]). Exposé titles never say "carnivore".
- Writes the chat reply from `reply_facts`: what ran, the numbers, the 3 biggest finds, what went well, what didn't work, then the yes/no questions. Never softens or drops a "didn't work" line.

## Hard rules

- YouTube is only ever searched from a cloud session, signed out, with no cookies. Never run Radar's YouTube steps on Max's own computer. Never pass cookies or sign in. (`radar/yt.py` enforces this.)
- YouTube only. Long form only (3 minutes or more). English unless Max asks for a foreign-language run.
- One run at a time. More requests go in the queue. A run stops at 30 minutes (a deep dive at 60) and delivers what it has.
- Helpers, if used, follow `docs/collector.md` (they run searches and nothing else) or, in a deep dive, `docs/labeler.md` (they label and nothing else). One at a time. Sonnet, never the cheapest model.
- Never touch anything outside this repo. Max's script system and thumbnail studio are separate projects.
- Never edit `data/topic_names.md`, `data/watchlist.md` or `DECISIONS.md` without his yes. After a yes, write the change yourself with `python -m radar approve`. Never ask him to paste.
- After every run: commit and push, so memory (`store/radar.db`) and the board are never lost.
