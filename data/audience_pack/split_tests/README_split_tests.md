# Split tests: read this first

Copied from the dataset README (built 22 Nov 2026). It explains how the split test files were made and their limits. In this folder, `split_tests.csv` combines sources A and B below in one table.

### 04_split_tests/
YouTube "Test & Compare" results. **YouTube picks winners on watch time share, not click-through rate.** Compare each variant to an even split: 50% for two variants, 33.3% for three.

**Read this before using any split test number.** The evidence in this folder says most of these tests were stopped by Max within hours, long before YouTube could call a result:
- Two screenshots carry YouTube's own footer: S072 "Test stopped by you. Ran from June 11, 2026 at 10:49 AM to June 11, 2026 at 12:30 PM" (1 hour 41 minutes) and S171 "Ran from June 7, 2026 at 1:54 PM to June 8, 2026 at 5:22 AM" (15 and a half hours).
- Three screenshots show the view count since the test started: 653 (S010), 964 (S129) and 2,307 (S037). Two more show "Estimated time remaining: 13 days" on a 14 day test.
- In `studio_current_tests.csv`, where a test also exists as a screenshot, its `ended_utc` is within a minute of when the screenshot was saved in 9 of 11 cases. So the pattern looks like: take the screenshot, stop the test, start the next one.

So a share in this folder is usually an early reading on a few hundred to a few thousand views, split two or three ways. Small gaps are noise. The analysis must measure the noise first (PROMPT.md says how) and must not call anything a winner unless YouTube did.

Three sources:

**A. `split_tests_from_screenshots.csv` (the main one).** 176 screenshots Max saved from YouTube Studio between 28 February and 22 November 2026, read into 499 variant rows. YouTube only keeps the latest test per video, so these screenshots are the only record of most tests.

- `screenshots/S001.jpg` to `S176.jpg`: the screenshots (JPEG copies of the originals, same pixel size).
- `variant_thumbnail_crops/S###_v#.jpg`: each variant's thumbnail, cut out of the screenshot by a script. `thumbnail_crop_quality` is exactly `full`, `partial` or `none`. Only treat `full` crops as complete thumbnails (their edges can be a few pixels off). For the rest, look at the screenshot.

**A screenshot is one reading of a test. It is not always one unique test.**
- The same test can be captured twice (for example S039 and S040 are 1.9 hours apart, S142 and S144 are 12 hours apart, same titles and thumbnails). There is no test ID. To count unique tests, group screenshots of the same video that have the same titles and the same thumbnails, and keep the latest reading.
- 11 screenshots are the same tests as rows in sources B and C: S009, S010, S023, S037, S043, S045, S069, S128, S129, S131, S176. They are flagged `same_test_also_in_studio_or_vidiq_file` = 1. Do not count them twice when combining sources.
- S095 reads 33.3 / 33.3 / 33.3. That test had only just started.

Columns:
- `screenshot_saved_local_time`: when the screenshot file was saved (NZ time). Roughly when the test was read, not when it started.
- `video_id`, `video_mapping` (exactly `confirmed`, `inferred` or `unmapped`), `video_mapping_note`. `confirmed`: the duration badge on a thumbnail was machine-read and equals the video's length. `inferred`: matched by titles and dates. An independent audit then checked the duration badge on all 165 mapped screenshots and found no conflict. Two videos share the length 16:26 (`P4yOwRN0D-w` and `pQ-uZBkSOvA`); they are told apart by test date. 11 screenshots are `unmapped` (the group "If I Only Had 2 Weeks To Kill Visceral Fat", 20 July to 3 August 2026): their thumbnails show a 17:43 video that is not in the Studio export. Ask Max which video that was, or analyze those tests without video-level data.
- `group_name`, `test_number_in_group`: the name and number Max saved the screenshot under. A group is usually one video but not always. Three screenshots were filed under another video's name and are mapped to the right video: S090 and S094 are Vital Farms tests (`nV9KunKYFoQ`), S162 is a blood work test (`P4yOwRN0D-w`). So the largest group has 17 screenshots, 16 of them on `eB8Co8FKJt0`.
- `titles_differ_between_variants`: 1 if any two variants have different titles, including a change of capital letters only. 0 means every variant had the same title, so only the thumbnails could differ. `titles_differ_only_by_capitals` = 1 marks the two tests where capitals are the only difference (S043, S170).
- `watch_time_share_pct`, `points_vs_even_split`.
- `is_top_share`: 1 for the single highest share. `top_share_is_tied` = 1 when two or more variants share the top figure (S070, S095, S135); then no row has `is_top_share`.
- `shown_as_now_visible_to_all`: the row carried "Now visible to all viewers", so this variant was the one live when the screenshot was taken.
- `winner_badge`: YouTube showed a "Winner" badge. Only 3 screenshots have one (S050, S087, S107). Every other test was running, stopped early or inconclusive when captured. Do not call a top-share variant a winner unless it has the badge. Call it the leader.
- `set_this_option_button`: a "Set this option" button was visible on that row. It appears on the row the mouse was over, including on tests that were still running. Recorded as seen. Do not use it to infer the state of a test.
- `test_status_on_screenshot`, `test_type_on_screenshot`, `views_since_test_start`, `test_status_read_by`: filled only for the 15 screenshots that show a status header or footer. Blank means the screenshot did not show it, not that it is unknown to YouTube.
- `row_note`: other text attached to the row.

How it was read and checked:
- Two independent readings: a vision model read every row, and Tesseract OCR read every row. They were compared row by row.
- In every one of the 176 screenshots the shares sum to 100 (within 0.15). That is a built-in check on the share numbers.
- OCR disagreed on some rows (it misreads a leading 5 as 9 and "I" as "|"). Each real disagreement was checked by eye against the screenshot and the vision reading was right every time.
- An independent audit then re-read 72 screenshots (203 rows) by eye and found no difference in any share, row count or flag, and ran its own OCR pass on all 176.
- The 11 tests that also exist in sources B and C agree on every share.
- Title punctuation (curly or straight apostrophes, "…" or "...") is best effort. Normalize before comparing titles.
- One screenshot in Max's zip was an empty file and is not here ("The #1 Most Toxic Thing 99% of People Eat Daily", Test 1).

**B. `studio_current_tests.csv`.** The 48 tests YouTube Studio holds today, one per video, as returned by vidIQ's Studio read on 22 November 2026. 120 variant rows. Includes 2024 and 2025 tests that have no screenshots.
- `status` and `result` are what that read returned: `winner`, `inconclusive`, `notEnoughData`, or blank. Given the early-stop pattern above, read `completed` plus `inconclusive` as "ended without a call", often because it was stopped early. One test (`BpzOx1eNyw8`) has a blank result and no shares: it ran for 25 seconds.
- 8 tests have a declared winner. All 8 are 2025 tests on videos outside the 27.
- `watch_time_share_pct` is Studio's 1-decimal figure. `watch_time_share_precise` is vidIQ's 4-decimal figure for the same test.
- `studio_variant_images/<videoId>_<A|B|C>.jpg`: the real variant thumbnails from YouTube (101 images). They are 480x360 with black bars above and below; crop to the middle 480x270 before showing them. 19 variant rows have no image: the 14 rows of title-only tests, and variant A of 5 thumbnail tests where Studio returned none.
- `started_utc` and `ended_utc` come from vidIQ. They fit the early-stop pattern, but they have not been confirmed against YouTube for every test. Use them as rough.

**C. `vidiq_saved_tests.csv`.** vidIQ's saved copy of 50 tests (the 48 above plus 2 earlier tests on videos that were later re-tested). Has the title variants for title tests.
- `vidiq_result_state` is vidIQ's own field and sometimes disagrees with Studio. On 7 tests (`r3RcjuirxY4`, `VGuL_-mkNCg`, `EKGsQFs09Ig`, `v2NQkn_aZk4`, `E8MvxYz7AN8`, `pN69S3UDj_g`, `ZDqNxcORLjg`) vidIQ left it blank but flagged a variant as winner, while Studio says inconclusive. On 4 tests (`vAGjJP8WeDQ`, `g0kBPmTnFG4`, `Wdq19PHmTT8`, `Lp9sZasr9vI`) vidIQ is blank and Studio says inconclusive. Where they differ, use source B.

