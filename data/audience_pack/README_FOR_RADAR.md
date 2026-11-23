# Radar_Audience: start here

Data pack for Radar, the tool that finds YouTube outliers and suggests titles and thumbnails for @max.german (channel ID UCsOkHWfiPFN3Pt7f9DwMSww). Collected 23 Nov 2026. Every file is listed in `INDEX.md`.

## What Radar is for
Radar's job is **getting people to click on Max's videos**. Weigh the data in this order:

1. **YouTube data first (`studio/`, `split_tests/`, `thumbnails/`).** Who watches, what they click, which titles and thumbnails won, where views come from, what they search, which other channels they watch.
2. **Buyer data second (`icp/`).** Who applies for and buys Built By Biology coaching. Use it as a tie-breaker. When two packages look equally clickable, prefer the one more likely to pull a 45 to 65 viewer who could become a client.
3. **Past conclusions last (`chats/`).** Findings Claude wrote in earlier sessions. Useful as hypotheses. Every file is marked "PAST CONCLUSIONS" and none were re-checked today.

## Rules for using this data
- **Use engaged views, not views,** for any comparison across time. YouTube changed view counting on 24 Aug 2026, so long-form "views" since then run about 1.7 to 2.4 times engaged views.
- **Split tests are noisy.** Most were stopped within hours. Identical thumbnails landed up to 13 points apart. YouTube picks winners on **watch time share, not click-through rate**. Read `split_tests/README_split_tests.md` before using any share.
- Only 11 tests have a winner declared by YouTube. Everything else in `leader_top_share` is a leader, not a winner.
- **Long form only** unless a file says otherwise. Shorts were filtered out in the fresh Studio exports.
- Money is in NZD.
- No client or applicant names, emails, phone numbers or payment details are in this pack.

## Headline numbers (long form)
- Lifetime: 19.1M views, 17.2M engaged views, 162.5M impressions, 7.04% CTR, 6:14 average view duration (`studio/videos_longform_lifetime.csv`).
- Last 365 days by traffic source (engaged views): Browse features 77.3%, Suggested 9.5%, Direct 4.5%, Other YouTube features 1.8%, Channel pages 1.7%, Search 1.7% (`studio/traffic_sources_longform_365d.csv`).
- Search CTR is 9.69%, Browse 8.94%, Suggested 3.59%.
- Top search terms (365 days): "max german", "carnivore diet", "carnivore", "mcdonald's", "vital farms", "10 eggs a day" (`studio/youtube_search_terms_longform_365d.csv`).
- Viewers (90 days, long form): 85.0% male. 35–44 is the biggest age band at 23.8%. 45+ is 51.7%. US 45.8%, Australia 6.6%, UK 6.5%, Canada 5.5%.
- Channels the audience also watches: Steak and Butter Gal, Felix Harder, Shawn Baker MD, Paul Saladino MD, HomeSteadHow (`studio/audience_tab_2026-11-23.md`).

## What is not in this pack, and why
- **The raw split test PNGs** (ab-test-images-22-November-2026.zip, 145 MB, 177 images). The same 176 screenshots are here as resized JPGs in `split_tests/screenshots/`. One original file in that zip is empty.
- **Video transcripts.** They are in channel-audit-handoff.zip on Max's Mac (Downloads) if Radar needs hooks.
- **Files from older chats (Sep to early Nov 2026).** They are no longer in Downloads. Their conclusions were copied into `chats/` instead. The 12-month Studio export from 1 Nov is superseded by the fresh lifetime export here.
- **Fathom call transcripts.** The Nov 21 Sales Call Analysis already covers 98 calls. Its conclusions are in `chats/`.
