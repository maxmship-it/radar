# AUDIENCE: what Max's viewers click and who buys

Short version of `data/audience_pack/` (collected 23 Nov 2026 from YouTube Studio, Test & Compare, vidIQ, Typeform, the client questionnaire and past analyses). Radar reads this before writing combos and picking cross-niche cards. If this date is more than 90 days old, say so in the "didn't work" part of the reply.

## What this file may and may not change

- It shapes only two things: which cross-niche patterns are worth picking, and how the 10 combos are written and ranked.
- It never changes which videos count as outliers (`radar/rule.py`), which outliers are on the board, how they are labeled, or their order. The on-topic test stays "is it ABOUT what Max asked for". A video his audience would not usually click is still on the board if it qualifies.
- It never overrides `DECISIONS.md`. Every combo still uses a real outlier's thumbnail from this run. A pattern from this file is never a reason to write a combo without an outlier behind it.
- Numbers here are real and may be quoted. Anything else stays [number].

## Who watches (long form, last 90 days to 21 Nov 2026)

- 161,827 subscribers. 489K monthly audience. 43% new viewers, 44% casual, 12% regular. 75% of watch time is from non-subscribers.
- Men 85%, women 14%. Age 25-34 20%, 35-44 24%, 45-54 20%, 55-64 17%, 65+ 13%. 45+ is 52% of views.
- US 46%, Australia 7%, UK 7%, Canada 6%, Germany 3%.
- Devices (watch time, 28 days): mobile 44%, TV 27%, computer 22%, tablet 7%. A thumbnail must read at phone size and on a TV.
- Channels his audience also watches: Steak and Butter Gal, Felix Harder, Shawn Baker MD, Paul Saladino MD, HomeSteadHow. Also seen that week: KenDBerryMD, Dr. Abs, Adapt Your Life (Westman).

## Where clicks come from

- Home and subscription feeds give 77% of long-form views. Suggested 10%. Search under 2%. So packaging is judged in the feed, against whatever else the viewer was offered, not as an answer to a search.
- CTR by source: search 9.7%, browse 8.9%, suggested 3.6%.
- Long-form CTR across the 27 videos since March runs 5.4% to 11.6%, median 7.7%. Impressions explain views almost fully. Bigger videos clicked better (rank correlation 0.46), with one exception: the visceral fat video reached 15.3M impressions at 5.6%.
- Since 24 Aug 2026 YouTube counts long-form "views" at about 1.7 to 2.4 times engaged views. Compare engaged views across that date.

## What his split tests say (224 tests on 67 videos, Feb to Nov 2026)

Read with care. YouTube picks winners on watch time share, not CTR. Most tests were stopped within hours on a few hundred to a few thousand views. Identical variants landed up to 13 points apart, so a gap under 13 points is a hint. Only 11 tests have a YouTube-declared winner.

Titles (share of the variant with the feature minus the others in the same test):
- "It's Boring, But It [Result]...": led 19 of 20 tests, 9.5 points ahead on average, on four of the five videos it was tried on. Rechecked from the raw file on 23 Nov 2026. The wider "[Claim], But..." family ("It Sounds INSANE, But...") led 22 of 26. Two of the three Winner badges in the screenshots went to this family. This is the strongest title signal on the channel.
- Naming the brand or organization: led 5 of 6 (hint). Naming helped in exposé titles and did nothing elsewhere in the Nov 1 analysis.
- A time promise (days, hours, "fast", "instantly"): led 22 of 34, about 3 points ahead. A small edge.
- "Exposed" or "Exposing": led 9 of 16. About even.
- Capitals, brackets, numbers, "You", warning words, first person, title length, question marks: all inside 2 points. None of these is a reason to pick one combo over another.

Thumbnails (17 tests that cleared the noise, all hints):
- One clear subject with few words wins. A real Kerrygold pack under a red WARNING beat a made-up product (22 points). One product and one face beat a busy conspiracy board (26 points).
- Before/after or side-by-side comparisons led 6 times and trailed 3. Max's face visible led 5 and trailed 2. A named real person or brand led 3 and trailed 1.
- Big text with no strong image never led and trailed 4 times. Busy collages trailed both times.
- A hard stare beat a softer look on the same image (15 points).
- Across videos, the four live thumbnails with body before/afters have lower CTR (median 6.8%), but they are all how-to topics. Topic matters more than layout.
- Light against dark: no evidence either way across 110 tests. Not a reason to choose a combo.

## Topics that pull

- Food-industry exposés: 11 videos, median 275K engaged views, about double every other group, 55% of all engaged views. The highest-CTR thumbnails name a real villain: a named doctor with "FAKE", RFK Jr. with Kerrygold, a real brand pack.
- How-to fat loss and carnivore videos have the lowest CTR on the channel. For a how-to subject, a villain or hidden-ingredient angle is worth one combo.
- Big videos draw comments angry at the industry (44% of top comments on the six biggest). Small videos draw comments about Max.

## Who buys (tie-breaker only)

Clicks come first. Between two equally clickable combos, prefer the one that also speaks to buyers.
- Clients (49): median age 54, 83% are 45+. 71% men, 29% women. Australia 37%, US 27%, UK 10%. 82% had already tried carnivore, 76% keto.
- 61% of clients ticked waist size reduction as a goal. Applicants talk about carnivore (41%), a set number of pounds (32%), muscle (25%), energy (19%).
- Description links by applicant quality: insulin 88% qualified, carnivorediet 82%, carnivorefatloss 81%, losevisceralfat 65%. Visceral fat brings volume and the weakest applicants. Insulin and stall angles bring the best.
- Women are 14% of views and about 29% of buyers. A combo that also works for a woman over 50 adds buyer value at no cost.
- Prospects who came in from a specific video closed at 53%, against 34% for everyone else.

## How to use it in a run

- Cross-niche pick: prefer patterns that match what has worked here (a "[Claim], But..." title, a named real villain, one clear subject, a two-thing comparison). Skip patterns that depend on big text alone or a busy collage.
- Combos: when two titles are equally true to the outlier, rank the one with the stronger signal above first. Use at most two "It's Boring, But..." or "[Claim], But..." titles in a set of 10, so the set stays varied. For exposés, name the real brand or body.
- The one line on his version may cite a number from this file, for example "your '[Claim], But...' titles led 22 of 26 tests".
- Hooks, intros, retention and sponsor findings are in the pack but are not for Radar. Radar never writes hooks.

## Where the detail is

`data/audience_pack/INDEX.md` lists every file. Main ones: `studio/videos_longform_lifetime.csv` (every video's impressions, CTR, views), `split_tests/split_tests.csv` (every test, one row per variant), `thumbnails/split_test_variants_studio/` (the real variant thumbnails), `studio/suggested_videos_sources_longform_365d.csv` (videos that send him viewers), `studio/youtube_search_terms_longform_365d.csv`, `icp/ICP_breakdown.md`. Files in `chats/` are past conclusions and were not re-checked, except the "It's Boring, But..." count above.
