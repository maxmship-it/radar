# HOW A RUN GOES

All commands run from the repo root. One pipeline for every kind of request. Only the subject and the extras change.

## 0. What Max said -> what to do

- A bucket ("fat loss", "carnivore", "exposé") or "what's working": the subject is the bucket. Names and search terms come from that bucket's lists in `data/keywords.md`. No bucket named: queue all three.
- A named subject ("eggs", "everything on seed oils"): that subject and its names.
- "Run on this" with draft titles, a script, an outline or a link to his own video: the subject plus his angle. Put his drafts in the spec under `drafts`. They steer the combos. The search is the same full search.
- "You missed this" with a link: `python -m radar missed <link> --subject <subject>`. Tell him where it was lost in one or two lines, fix the cause with his yes, rerun the one search that should have caught it.
- "Add this" with a link: `python -m radar add <link>`, then `next`, then `board`.
- "Show me everything on X from the last N weeks": `python -m radar board --from-store --subject X --days <N*7>`. No new searches. Use `python -m radar status` to see which subjects are in memory; add related ones with `--also`.
- Feedback on a board by card number ("12 is great, 30 isn't relevant"): write a file with one line per card, `<number> TAB <great|relevant|no> TAB <his words>`, then `python -m radar feedback <file>`.
- "Yes to 1 and 3" after a board's questions: `python -m radar approve 1 3`.
- Several subjects at once: `start` each one. The first runs, the rest queue and start one after another when you `finish`.

## 1. Write the spec and start

Look the subject up in `data/topic_names.md`. If it is there, use every name on its line. If not, work out the names people really put in titles. Then write `runs/<subject>-spec.json`:

```json
{"subject": "bacon",
 "names": ["bacon", "nitrites", "nitrates", "processed meat", "deli meat", "cured meat"],
 "algrow": ["bacon health", "bacon brands", "is bacon bad for you", "processed meat"],
 "tubeai": ["bacon", "nitrites", "deli meat"],
 "vidiq": ["bacon health nitrates", "processed meat health risks", "bacon brands to avoid"],
 "youtube": ["bacon", "bacon bad for you", "bacon brands", "processed meat"],
 "format_words": ["brands", "every day"],
 "drafts": [],
 "bucket": "EXPOSÉ"}
```

Each tool has its own dialect:
- `algrow`: specific phrases. Pair a bare word with a health or food word ("bacon" alone returns Roblox).
- `tubeai`: one or two words only. Longer phrases return nothing and the guard refuses them.
- `vidiq`: the 3 strongest descriptions of what the video is about. It matches meaning, not only titles. 5 credits a call.
- `youtube`: every name, as people type it. Free. This is the safety net for 3 to 8 minute videos.
- `names`: used to match titles from the pool, upload lists and memory. Include every wording.

`python -m radar start --spec runs/<subject>-spec.json`

## 2. Search

Loop `python -m radar next` until it stops returning calls. Either do it yourself or hand it to one helper with `docs/collector.md`. Never more than one helper at a time.

What `next` does, in order: preflight (one cheap known-answer search per tool; say its first line to Max right away), memory first, YouTube's own search, the upload lists of every pool and watch-list channel, the Algrow pool scan, keyword search per tool across 18 months (and again limited to 100 days when the wide search overflowed), paging until dry, snowball from the top on-topic outliers, the uploads of every channel with an on-topic outlier, new rounds from words in the outlier titles, cross-niche (at most 15 calls), views per hour.

It stops on dry results or at 30 minutes, whichever comes first, and records which.

## 3. Label

When `next` returns `label`: `python -m radar label-queue`, write a file of `<id> TAB <on|off|borderline> TAB <one-line reason>`, `python -m radar label-import <file>`, then `next`.

When it returns `label-check`: `python -m radar label-check` shows the 20 highest-view videos labeled this run. Judge each again from scratch. Import changes with `--check`, or `python -m radar label-import --check-ok` if none change.

When it returns `cross-pick`: `python -m radar cross-queue`, read `data/audience.md` first, pick at most 8, file of `<id> TAB <niche> TAB <the pattern rewritten for Max's subject>`, `python -m radar cross-import <file>`. If nothing really transfers, pick none.

## 4. Combos

`python -m radar combos-help` lists the cards. `python -m radar thumbs` saves the real thumbnails of the top cards: look at them with Read before writing. Read `data/audience.md` for what his viewers click and who buys; it ranks and shapes the combos, and every combo still comes from a real outlier on this board. Write `runs/<run>/combos.json`. Up to 10. Fewer if 10 honest ones are not there.

## 5. Board, reply, finish

`python -m radar board` builds, validates, renders the PDF and the HTML twin into `boards/`, and prints `reply_facts` and the yes/no questions. If the validator fails, fix the cause and run it again. Look at the three preview images. Send Max the PDF. Write the reply from `reply_facts`.

`python -m radar finish` closes the run and starts the next queued one. Then commit and push.

## Other commands

- `python -m radar status`: what is running, what is queued, what memory holds.
- `python -m radar yield`: what each search cost and what it found. Show Max a short version when he asks.
- `python -m radar known --subject X`: the videos every run on X must find.
- `python -m radar extend`: lift the 30 minute budget for this run. Only when Max asks.
