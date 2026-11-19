# LESSONS

What broke, and what fixed it. Radar reads this at the start of every run. Where a fix lives in code, the file is named, so nobody has to remember it.

## Missing outliers
- Nov 18: a bacon board had 17 cards; 17 known bacon outliers were missing. Nothing was remembered between runs and TubeAI failed silently. FIX: memory first (`store/radar.db`), known outliers checked by the validator, a dead tool is named in the first line and its fallback runs.
- Nov 16: Steak and Butter Gal and Ben Azadi videos were missed though both channels were tracked. FIX: every run reads the upload list of every pool and watch-list channel straight from YouTube and title-matches it (`run.free_phase`).
- Nov 18: searches hit a fixed 4-page cap while still finding outliers. FIX: page until a page adds fewer than 3 new outliers. Safety cap 12 pages, reported when hit.
- Packaging runs only searched 5 to 8 phrases. FIX: one pipeline, same depth for every request.
- 3 to 8 minute videos depended on TubeAI. FIX: YouTube direct is a required step on every run and runs extra queries when TubeAI is down.

## Wrong numbers
- Nov 18: 46% of cards showed lifetime average as "VPH". FIX: `radar/vph.py` only accepts a 24 hour gain (Algrow, vidIQ, Algrow daily, or two own snapshots 6 to 72 hours apart). Otherwise "VPH n/a".
- Nov 16: VPH from two counts 15 minutes apart gave 26,061 an hour. FIX: snapshots under 6 hours apart are never used.
- VPH lookups by exact title found almost nothing. FIX: always by video id.

## Bad data
- Helpers re-typed rows and invented video ids (11 fake ids on Nov 18). FIX: a hook saves every raw connector result to disk and code files the rows. The model only sees a one-line receipt. Every card is checked on YouTube; a made-up id comes back "gone".
- A Korean video with an auto-translated English title reached a board. FIX: language comes from YouTube's audio language, never from a title.
- Loose labeling let nitric oxide videos and a soup recipe onto a bacon board. FIX: the test is "about what Max asked for"; unsure means off; a second pass re-judges the 20 biggest.

## Tools
- TubeAI returns nothing for phrases over two words, and pages of 50 fail. FIX: the guard refuses both.
- Algrow thumbnail search by text description returned nothing in 34 tries. FIX: the guard refuses it. Use `video_url`.
- Algrow allows 30 calls a minute across everything. FIX: one shared limiter in the hook sleeps and retries. A routine throttle never drops the tool.
- Five runs at once shared every limit. FIX: one run at a time, the rest queue.
- Every board was tagged PARTIAL. FIX: PARTIAL only when a required step failed.
- vidIQ failed on an old sign-in after an account change. FIX: preflight tests every tool before it is relied on.

## Learned during the Nov 19, 2026 rebuild
- yt-dlp's `mweb` client now gets "Sign in to confirm you're not a bot" from cloud servers. The default client works signed out. `radar/yt.py` uses the default client.
- YouTube sometimes answers a video page only partly when many are requested at once (no duration, no audio language). `yt._one` retries, and anything still partial gets a second look one at a time.
- yt-dlp returns an empty stub for an id that does not exist. `yt._one` treats a stub as "gone" after checking YouTube's oEmbed.
- vidIQ answers in formatted text, not data. `ingest.vidiq_answer_rows` reads the blocks. vidIQ's outlier search already returns views per hour on every row, so most cards need no extra vidIQ lookup.
- A very large connector result (the 310-channel pool folder, 300-row pool scans) is saved to a file by the harness and only a pointer comes back. `ingest.to_obj` follows the pointer.
- Worker threads must never write to the database while the main thread holds it: the upload scan froze for 10 minutes. Threads fetch, one place writes (`yt.uploads_many`).
- When the 18-month search for a name is not a full page, the separate 100-day search adds nothing. It now runs only when the wide search overflowed. This halves the Algrow calls.
- Stale notes in the old instructions: vidIQ is 6,000 credits a month (not 2,000). Algrow is free per call but has daily caps and paid overage.
- The Algrow "Radar pool" folder had 310 channels on Nov 19, not the 126 in the Oct 22 copy. The live folder is now read at the start of a run and is the only truth.
- Algrow's "videos like this one" search (`video_url`) is capped at 40 calls a day, then $0.20 each, and every page counts. The first bacon test paged those searches and used 34 in one run. The guard stopped Algrow on the "34 of 40" notice before anything was charged. FIX: one page per seed (50 rows), at most 6 seeds a run, Radar stops at 36 a day (`radar/limits.py`, enforced in the hook). vidIQ seed searches carry more of the snowball.
- A "heads up" limit notice must not switch a whole tool off. Only a charge, billing or quota-exceeded message does.
- Lifting the 30 minute budget is Max's call. Radar never runs `extend` on its own.

## Learned during the Nov 19, 2026 five-board session (Costco, fruit, high protein junk food, coffee, signs you're losing fat). NOT fixed in code yet
- The cloud environment has no setup script, so `yt-dlp` was missing and preflight said "DOWN at the start: YouTube". Installing it (`pip install yt-dlp`) and re-running the tool check fixed it. A setup script (`pip install -q yt-dlp`) was saved to the radar environment on Nov 19 with Max's approval. It is unproven until a fresh session starts, so still check `python -c "import yt_dlp"` before `start`.
- Language check lets foreign videos through. From this server YouTube gives no audio language and no caption list, so `yt.detect_language` falls back to the description, which YouTube auto-translates to English. 16 foreign videos reached the fruit on-topic list and 11 reached coffee (Hindi, Urdu, Spanish, Portuguese, French, Italian, Vietnamese, Kannada, Indonesian). WORKAROUND: after labeling, sheet every on-topic thumbnail and label off anything whose thumbnail text or channel is not English. The Costco board was built before this was seen.
- Follow-up round terms are built from stemmed title words and are often junk ("stor failed", "thing buying", "doctor explain", "bbc world", "senior health", "fat even"). They page up to 12 times and ate the last third of four runs. Four of five boards stopped on the 30 minute limit and got no cross-niche pass.
- A broad on-topic label widens everything after it. Labeling Costco deal roundups on, "best fruit before bed" videos on, and "clove in coffee" videos on sent the snowball and the rounds after deals, senior health and cloves.
- A bare name that is also a common word floods the queue: "scale" pulled RC and diecast scale models, "fruit" pulled kids' songs and Blox Fruits, "coffee" pulled jazz playlists and Cars & Coffee.
- The report proposes dropping the preflight health-check searches ("Drop the algrow search 'carnivore diet'"). They are not subject searches. Never approve those.
- Algrow has a second daily cap the guard does not watch: 300 "viral video search" calls a day, then $0.05 a call. Five boards in one day reached 296. The guard only stops Algrow after a charge. The "videos like this one" cap (36) was used up by the first board, so boards 2 to 5 got 0 seeds.
- Algrow returned "Invalid or inactive API key" on 4 paging calls in the Costco run and then recovered. Algrow's same-format search errors with 404 when it has not read a video's title format yet.
- Running `python -m radar board` twice writes a second copy with "-2" in the name (it happened on Costco). Run it once.
- A helper for the search loop works and keeps the main chat small, but a search phase takes 16 to 23 minutes with 300 to 500 candidates to label after it, so labeling has to be fast to leave time for rounds.
