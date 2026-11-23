# DEEP DIVE: 20 video ideas

Max says "deep dive", "give me 20 ideas", "what should I make next" or similar. Radar searches his whole world, puts every on-topic outlier on the board, and ends with 20 idea pages. Decided by Max on Nov 23, 2026.

## What he gets

- Part 1: every outlier in his world from the last 100 days, most views first.
- Part 2: 100 days to 18 months, same.
- Cross-niche: at most 8 cards, as in a topic run.
- 20 VIDEO IDEAS, two to a page. Each idea has:
  - the topic in 1 to 4 words ("Creatine", "Seed oils in restaurants")
  - exactly 3 titles, each on a different real outlier's thumbnail, with one line on what to change on that thumbnail so it fits the title
  - "Related outliers": the card numbers behind the idea. They are links that jump back to the cards, in the PDF and the HTML twin.
  - a tag: YOUR VIEW ON FILE, FITS YOUR VIEWS, or YOUR VIEW? (at most 5), plus REMAKE when it remakes one of his past winners
- Topics only. Never talking points, angles inside the video, or hooks.

## Who does what (keeps token use down)

Cheap, repeatable work goes to Sonnet helpers. Judgment stays with the main model. One helper at a time, never the cheapest model.

- **Sonnet collector** (`docs/collector.md`, Agent with `model: "sonnet"`): the `next` loop and every connector call. It sees one-line receipts only.
- **Sonnet labeler** (`docs/labeler.md`, Agent with `model: "sonnet"`): every `label` step. A deep dive can have hundreds of candidates.
- **Main model**: the spec, the label-check (20 rows), the cross-niche pick, reading Max's opinions, the 20 ideas, the reply.
- Code does everything else: searching order, the outlier rule, YouTube checks, the board and its checks. Thumbnails come as contact sheets (`thumbs --sheet`, 20 to an image) so the main model reads a few images, not a hundred.

## Steps

1. **Spec.** Copy `data/deep_dive_spec.json` to `runs/deep-dive-spec.json`. Add up to 6 fresh search terms if Max named a focus or something is trending. Keep `"mode": "ideas"`. Start: `python -m radar start --spec runs/deep-dive-spec.json`. The run gets 60 minutes. Tell Max the rough cost first: about 80 to 100 vidIQ credits (of 6,000 a month), Algrow and TubeAI within their free daily caps.
2. **Search.** Hand the loop to one Sonnet collector with `docs/collector.md`. It stops on `label`, `label-check`, `cross-pick` or `done` and replies with that JSON.
3. **Label.** On `label`: hand it to one Sonnet labeler with `docs/labeler.md`. On `label-check`: do it yourself (`python -m radar label-check`), it is 20 rows. On `cross-pick`: do it yourself as in a topic run, reading `data/audience.md` first. Then hand the loop back to the collector. Repeat until `done`.
4. **Max's views.** Read his opinions live from Google Drive, file "02 Opinions" in the Company Brain (file id `1DxwfhTMuVsP-G2tVci8aA6ashIKGtkWNNfqsIqAFEvg`). Also use the canon in `data/channel_context.md`. If Drive cannot be reached, say so in the reply and use the canon only.
5. **Ideas.** `python -m radar ideas-help` lists every card and his top 30 past videos. `python -m radar thumbs --sheet -n 60` saves contact sheets; Read them before writing. Read `data/audience.md`. Write `runs/<run>/ideas.json`. Rules:
   - Every idea must fit his views. `written` = it rests on a line in 02 Opinions or the canon. `common sense` = it clearly follows from them (for example "foods to avoid" when the foods are ones he is against). `check` = his view is unknown; at most 5, and never invent a view for him.
   - Spread the 20 across his three buckets and across fresh topics and remakes. Remakes of his past winners are welcome (`remake_of` = his video id).
   - Rank by evidence: how many and how big the outliers behind the topic are, then what `data/audience.md` says his viewers click and who buys.
   - Each title sits on a different card's thumbnail where possible. The change line says what to change on that thumbnail for this title, under 120 characters.
   - No invented numbers (write [number]). No em dashes. Exposé titles never say "carnivore". Never hooks.
6. **Board.** `python -m radar board`. Fix any validator failure at its cause. Send Max the PDF and the HTML twin. Write the reply from `reply_facts` as in a topic run. Then `python -m radar finish`, commit and push.
