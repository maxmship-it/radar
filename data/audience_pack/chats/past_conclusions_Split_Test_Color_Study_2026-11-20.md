# PAST CONCLUSIONS: Split test color study, first pass

Source: chat "YouTube dark mode usage stats", 19 to 20 Nov 2026 (https://claude.ai/chat/3df24077-3ad2-4273-9abb-46c769324d99), color-study-pack.zip
Data covers: 156 split tests, Feb to Nov 2026
Collected: 23 Nov 2026

Conclusions Claude wrote in an earlier session. Not re-checked today.

---

# Max's split tests: color properties against results

Hint only. See the caveats at the top of `split_test_analysis.py`.

## Thumbnail-only tests (cleanest): 37 tests with one clear winner

| Metric | Tests where it differs | Top variant won | Win rate | Chance | p | Spearman with share |
|---|---|---|---|---|---|---|
| l_mean | 29 | 8 | 28% | 41% | 0.181 | -0.15 |
| bright_share | 28 | 11 | 39% | 39% | 1.000 | -0.08 |
| dark_share | 31 | 12 | 39% | 40% | 0.857 | +0.13 |
| chroma_mean | 30 | 11 | 37% | 41% | 0.711 | -0.04 |
| colorfulness | 27 | 9 | 33% | 41% | 0.548 | -0.11 |
| warm_share | 30 | 13 | 43% | 41% | 0.850 | +0.11 |
| cool_share | 19 | 7 | 37% | 42% | 0.813 | -0.14 |
| share_red | 23 | 6 | 26% | 40% | 0.202 | -0.16 |
| share_orange | 27 | 10 | 37% | 40% | 0.846 | +0.19 |
| share_yellow | 14 | 8 | 57% | 38% | 0.169 | +0.12 |
| share_green | 7 | too few | | | | |
| share_cyan | 0 | too few | | | | |
| share_blue | 10 | 4 | 40% | 43% | 1.000 | -0.13 |
| share_purple | 2 | too few | | | | |
| share_pink | 2 | too few | | | | |
| share_white | 24 | 10 | 42% | 40% | 1.000 | +0.01 |
| share_black | 31 | 12 | 39% | 40% | 0.857 | +0.10 |
| edge_l | 30 | 14 | 47% | 41% | 0.571 | -0.10 |
| edge_contrast_dark | 26 | 13 | 50% | 40% | 0.415 | -0.10 |
| edge_contrast_light | 33 | 14 | 42% | 40% | 0.861 | +0.09 |

## Title + thumbnail tests (title changed too): 73 tests with one clear winner

| Metric | Tests where it differs | Top variant won | Win rate | Chance | p | Spearman with share |
|---|---|---|---|---|---|---|
| l_mean | 55 | 18 | 33% | 34% | 0.890 | -0.01 |
| bright_share | 56 | 20 | 36% | 34% | 0.887 | -0.05 |
| dark_share | 60 | 21 | 35% | 34% | 0.889 | -0.07 |
| chroma_mean | 58 | 21 | 36% | 34% | 0.780 | -0.04 |
| colorfulness | 59 | 16 | 27% | 34% | 0.334 | -0.11 |
| warm_share | 65 | 22 | 34% | 34% | 1.000 | +0.00 |
| cool_share | 51 | 17 | 33% | 34% | 1.000 | +0.02 |
| share_red | 56 | 18 | 32% | 34% | 0.886 | -0.10 |
| share_orange | 55 | 24 | 44% | 34% | 0.153 | +0.14 |
| share_yellow | 41 | 12 | 29% | 34% | 0.634 | -0.09 |
| share_green | 24 | 8 | 33% | 33% | 1.000 | +0.17 |
| share_cyan | 1 | too few | | | | |
| share_blue | 33 | 14 | 42% | 34% | 0.356 | +0.05 |
| share_purple | 1 | too few | | | | |
| share_pink | 0 | too few | | | | |
| share_white | 58 | 19 | 33% | 34% | 0.888 | -0.04 |
| share_black | 63 | 21 | 33% | 34% | 1.000 | -0.06 |
| edge_l | 61 | 25 | 41% | 34% | 0.278 | +0.08 |
| edge_contrast_dark | 50 | 21 | 42% | 34% | 0.235 | +0.10 |
| edge_contrast_light | 63 | 17 | 27% | 34% | 0.287 | -0.10 |

## Both kinds together: 110 tests with one clear winner

| Metric | Tests where it differs | Top variant won | Win rate | Chance | p | Spearman with share |
|---|---|---|---|---|---|---|
| l_mean | 84 | 26 | 31% | 36% | 0.358 | -0.04 |
| bright_share | 84 | 31 | 37% | 36% | 0.813 | -0.05 |
| dark_share | 91 | 33 | 36% | 36% | 1.000 | -0.01 |
| chroma_mean | 88 | 32 | 36% | 36% | 1.000 | -0.05 |
| colorfulness | 86 | 25 | 29% | 36% | 0.216 | -0.11 |
| warm_share | 95 | 35 | 37% | 36% | 0.914 | +0.02 |
| cool_share | 70 | 24 | 34% | 36% | 0.805 | -0.01 |
| share_red | 79 | 24 | 30% | 35% | 0.411 | -0.12 |
| share_orange | 82 | 34 | 41% | 36% | 0.353 | +0.16 |
| share_yellow | 55 | 20 | 36% | 35% | 0.886 | -0.04 |
| share_green | 31 | 11 | 35% | 35% | 1.000 | +0.14 |
| share_cyan | 1 | too few | | | | |
| share_blue | 43 | 18 | 42% | 36% | 0.520 | +0.01 |
| share_purple | 3 | too few | | | | |
| share_pink | 2 | too few | | | | |
| share_white | 82 | 29 | 35% | 36% | 1.000 | -0.03 |
| share_black | 94 | 33 | 35% | 36% | 0.917 | -0.02 |
| edge_l | 91 | 39 | 43% | 36% | 0.189 | +0.03 |
| edge_contrast_dark | 76 | 34 | 45% | 36% | 0.117 | +0.05 |
| edge_contrast_light | 96 | 31 | 32% | 36% | 0.452 | -0.04 |

With 20 metrics tested, about one will show p < 0.05 by luck alone. Treat a single low p value as a lead to check, not a finding.


---

## Context written in the same pack (claims to check, not settled facts)

## Dark mode: the "80%" figure is not a YouTube number

`CLAUDE.md` in this repo says "80% of his viewers use it". That line is unverified. What a first pass found:

- YouTube has never published its dark theme share.
- The 80% traces to a March 2020 reader poll on Android Authority (2,514 votes, 81.9%). It is a self-selected poll of Android enthusiasts about their phones, not about YouTube. Stats sites and thumbnail blogs repeated it, some crediting it to Google.
- Better-sourced numbers are far apart. A Nielsen Norman Group survey of 115 mobile users split roughly a third dark, a third light, a third both. Google's Chrome data in Dec 2021 put dark-preferring traffic near 22%. Android Authority's 2026 rerun had about 73% always-dark among 3,110 of its readers.
- People do not change a YouTube setting. YouTube's default is "Use device theme", so it follows the phone or computer, including scheduled dark mode at night.
- YouTube's CEO said in Feb 2025 that TV is the top device for YouTube watch time in the US. As far as we know the TV app has only a dark interface. Confirm that.
- Working estimate, not measured: about 65% of thumbnail views on a dark background for a US-heavy audience, range 55 to 75%.

Sources to re-check: androidauthority.com/dark-mode-survey-results-1090716, androidauthority.com/dark-mode-survey-results-3682352, nngroup.com/articles/dark-mode-users-issues, web.dev/case-studies/terra-dark-mode, YouTube CEO Neal Mohan's "Our big bets for 2025" letter, 9to5google.com/2019/11/22/youtube-android-device-theme.

What this means for the study: a thumbnail color has to work on YouTube dark (`#0f0f0f`), on the TV interface, and on YouTube light (`#ffffff`). Dark comes first. Light cannot be ignored.

Tighten this in the study with Max's own device split (TV, mobile, desktop, tablet) if vidIQ gives it.

## Max's own theory: light beats dark

Max says that in his split tests "light thumbnails seem to beat the dark ones", and reads that as light thumbnails standing out on a dark feed.

A first measured pass on his 156 tests (in `data/split-tests/preliminary_findings.md`) does not back this up yet:

- In 29 thumbnail-only tests where average lightness differed, the lightest variant won 8 times (28%). Chance was 41%.
- The variant whose outer frame contrasted most with the dark feed won a little more often than chance (45% against 36% across 76 tests). That gap is well within noise.
- No color property reached significance.
- The old Ascent app tagged 10 usable tests as dark against light backgrounds. Measured by the outer frame, the lightest variant won 4, the darkest won 5 and a middle one won 1. A coin flip.

This was a quick pass with crude measures. "Light" to Max may mean a light background, a bright face, or a white card, not the average of all pixels. Test his theory properly: sort his tests by eye into light-background against dark-background pairs, measure the background alone, and report what you find either way. He asked for his split tests to carry less weight than the outlier data because the variants differ in many ways at once.

## How YouTube picks a split test winner

Test & Compare ranks variants by watch time share, not click-through rate. A thumbnail that gets fewer clicks from people who watch longer can win. Keep that in mind when reading his tests. Check YouTube's help page for the current wording.

