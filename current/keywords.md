# KEYWORDS — Radar search terms by bucket

A sweep searches one bucket, or all three when no bucket is named. Terms are specific on purpose: the search engine ranks "calf muscles heart" far better than "health". Add a term by putting it on a new line in the right list.

Search terms are not the bucket definition. Changing a term changes what Radar searches for, not what counts as on topic.

What works (audit, 13 Oct 2026): name the product and the format the way the winning titles do ("milk brands", "brands to avoid", "fake foods").

---

## EXPOSÉ

### Keywords
brands to avoid
fake foods
changed and nobody told you
milk brands
olive oil brands
coffee brands
cheese brands
supplement brands
Costco items to avoid
McDonald's ingredients
Chick-fil-A ingredients
Costco food
ultra processed food
butter brands
egg brands
lab grown meat
Bill Gates food
FDA food
USDA dietary guidelines
food recall
imported beef
farmed salmon
artificial sweeteners
fast food exposed
seed oil restaurants
pasture raised scam
Big Food lobbying
banned in Europe

### YouTube-direct queries (yt_sweep.py, free)
brands to avoid
fake foods
don't buy
stop buying
costco
milk brands
coffee brands
olive oil
protein
restaurant secrets
food label
fast food
soda
nobody told you food

### Retired search terms
Re-tested 13 Oct with sort_by=similarity, per_page=8, over 14 and 90 days. It found nothing on topic in 16 results. Put it back by moving it up to Keywords.
food dyes

### Seed videos
https://www.youtube.com/watch?v=LZobJar3zQ8
https://www.youtube.com/watch?v=nV9KunKYFoQ

### Cross-niche
company downfall
corporate scandal
true crime documentary
history documentary
fraud exposed
consumer investigation

---

## FAT LOSS

### Keywords
belly fat
visceral fat
insulin resistance
cortisol belly fat
fat loss plateau
lose weight after 50
menopause belly fat
fatty liver
walking after eating
Ozempic side effects
metabolic rate
stubborn belly fat
fasting 72 hours
protein fat loss
sleep and belly fat
blood sugar spikes
muscle after 50
calf muscles heart
lymphatic system
GLP-1 natural

### YouTube-direct queries (yt_sweep.py, free)
belly fat
visceral fat
lose weight after 50
insulin resistance
cortisol
fat loss
second heart
walking after eating

### Seed videos
https://www.youtube.com/watch?v=6vmm1Fw3ywI
https://www.youtube.com/watch?v=EpKqHjvL2Dk

### Cross-niche
fitness over 40
doctor explains
longevity habits
sleep science
self improvement men
weight loss transformation

---

## CARNIVORE

### Keywords
carnivore diet
carnivore diet results
carnivore diet mistakes
carnivore weight loss stall
carnivore diet dairy
carnivore diet over 50
carnivore diet women
lion diet
animal based diet
keto diet mistakes
keto vs carnivore
humans carnivores
seed oils
saturated fat myth
eggs every day
cholesterol LDL
carnivore blood work
beef and butter
organ meats
fiber myth

### YouTube-direct queries (yt_sweep.py, free)
carnivore diet
carnivore
animal based diet
keto
eggs every day
cholesterol
seed oils
meat diet

### Seed videos
https://www.youtube.com/watch?v=JNg8TrVxHF4
https://www.youtube.com/watch?v=BpzOx1eNyw8

### Cross-niche
diet experiment
what I eat in a day
doctor reacts
ancestral health
longevity habits
fitness over 40

---

## CHANGELOG

2026-10-22 — Radar v2. Removed the News terms and Study queries sections (studies now live in the separate Study Finder project). Keywords, YouTube-direct queries, seed videos and cross-niche queries unchanged.

2026-10-13 — Audit fixes. EXPOSÉ: added 9 product and format terms that match the titles Radar missed (brands to avoid, fake foods, changed and nobody told you, milk/olive oil/coffee/cheese/supplement brands, Costco items to avoid). Re-tested the 6 weakest terms with similarity sort over 14 and 90 days: "food dyes" found nothing on topic and is retired from Keywords (kept as a news term). The other 5 found at least one on-topic video and stay. Added YouTube-direct queries for every bucket. FAT LOSS and CARNIVORE keyword lists unchanged; not audited for misses this time.
2026-09-24 — Rebuilt by bucket for single-chat runs. Each bucket has about 20 keywords, two seed videos, six cross-niche queries and its own PubMed queries.
