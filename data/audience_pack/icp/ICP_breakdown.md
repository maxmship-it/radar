# Who watches, who applies, who buys

**Secondary data for Radar.** Radar's main job is to find packaging that gets @max.german videos clicked. The YouTube files in `../studio/` and `../split_tests/` come first. Use this file as a tie-breaker: when two packages look equally strong for clicks, prefer the one that pulls more of the buyer profile below.

Collected 23 Nov 2026. No names, emails, phone numbers or payment details are in this folder. Only counts and percentages.

## Sources
- **YouTube viewers:** Studio Advanced mode, long-form videos only, last 90 days (24 Aug to 21 Nov 2026). Files `../studio/viewer_age_longform_90d.csv`, `viewer_gender_longform_90d.csv`, `geography_longform_90d.csv`.
- **Applicants:** Typeform "Built By Biology" application (form KKAFvad8), exported 23 Nov 2026. 448 responses from 28 May to 23 Nov 2026. 15 test entries removed, leaving **433**. 356 reached the "Qualified" ending, which means they said yes to being able to invest. Earlier versions of the form did not ask age, sex or watch time, so those questions have about 166 answers.
- **Paying clients:** Coaching Questionnaire responses (Google Form, the file Max sent on 23 Nov 2026). **49 clients**, 7 May to 21 Nov 2026.
- **Sales calls:** Past conclusions from `../chats/past_conclusions_Sales_Call_Analysis_2026-11-21.md` (98 first calls in Fathom, matched to Stripe). Fathom was not re-read today.

## The three groups side by side

**Sex**
- YouTube viewers: 85.0% male, 14.4% female
- Applicants (n=166): 72.9% male, 27.1% female
- Clients (n=48): 70.8% male, 29.2% female
- Women are about 14% of views but nearly 30% of buyers, so they convert at roughly double their share of the audience.

**Age**
- YouTube viewers: 35–44 is the biggest band (23.8%). 45+ is 51.7% of views. 55+ is 30.5%.
- Applicants (n=160): median 47. 45+ is 56%. 55+ is 33%.
- Clients (n=48): median 54. 45+ is 83%. 55+ is 48%.
- Under 45 is 48% of views and only 17% of clients.

**Country**
- YouTube viewers: US 45.8%, Australia 6.6%, UK 6.5%, Canada 5.5%, Germany 3.4%, NZ 1.4%
- Applicants who gave a country (n=394): US 40.9%, Australia 13.2%, UK 10.2%, NZ 8.1%, Canada 5.1%, Germany 2.8%
- Clients (n=49, read from the time zone they wrote): Australia 36.7%, US 26.5%, UK 10.2%, rest of world 10.2%, Europe 6.1%, NZ 4.1%, Canada 4.1%
- Australia is 6.6% of views and 36.7% of clients. Sales calls run on NZ hours, which likely explains part of this.

## What applicants say (433 applications)
Keyword search across three answers: biggest struggle, what success looks like in 90 days, and what they tried before. Full table in `typeform_theme_counts.csv`, split by qualified and disqualified. Counts are approximate. A few matches are false positives, for example "can't stomach it".

- **Carnivore mentioned: 178 (41.1%).** 122 named it in their biggest struggle.
- **Named a number of lbs or kg to lose: 138 (31.9%).**
- **Muscle, strength or tone: 109 (25.2%).**
- **Lose weight or fat, in general words: 102 (23.6%).**
- **Gym or exercise mentioned: 87 (20.1%).**
- **Energy or fatigue: 83 (19.2%).**
- **Keto or low carb: 82 (18.9%).**
- **Consistency, discipline or motivation: 74 (17.1%).** Higher among disqualified applicants (23.4%) than qualified (15.7%).
- **Fasting, IF or OMAD: 67 (15.5%).**
- **Time, busy or work: 65 (15.0%).**
- **Cravings, sugar, snacking or food noise: 58 (13.4%).**
- **Belly fat, stomach, waist or visceral: 56 (12.9%).** 20 (4.6%) put it in their biggest struggle. 49 of the 56 were qualified.
- **Visceral fat named by name: 13 (3.0%).**
- **Plateau or stall: 31 (7.2%).**
- **Accountability or coaching wanted: 31 (7.2%).**
- **Sleep: 30 (6.9%).**
- **Joint pain, injury or inflammation: 27 (6.2%).** All 27 were qualified.
- **Blood sugar, diabetes or insulin: 23 (5.3%).**
- **Regained the weight or yo-yo: 23 (5.3%).**
- **Confused or overwhelmed by information: 21 (4.8%).**
- Hormones, bloating, alcohol, eating out, blood pressure or cholesterol, GLP-1 drugs, menopause, testosterone and fatty liver were each under 3%.

## How applicants found Max
- **How long they've watched (n=166):** over a year 36.1%, several months 30.7%, found him this week 22.3%, under a month 10.8%.
- **Which description link they clicked (`typeform_applications_by_video_link.csv`):**
  - carnivorefatloss: 53 applications, 81.1% qualified
  - carnivorediet: 51, 82.4% qualified
  - insulin: 43, 88.4% qualified
  - losevisceralfat: 40, 65.0% qualified
  - visceralfat: 6, 66.7% qualified
  - No UTM tag: 240, 84.6% qualified
- The visceral fat links bring volume but the lowest qualified rate. The insulin link has the highest.
- **Applications by month:** May 39, Jun 97, Jul 47, Aug 81, Sep 71, Oct 52, Nov 46 (to the 23rd).
- **Occupation groups (`typeform_occupation_groups.csv`):** retired 14.1%, office or professional 18.2%, trades 7.4%, business owners 6.5%, healthcare 3.7%, students 3.0%. 39.5% were too short or unclear to group.
- **Priority score (0 to 10, n=166):** median 9, mean 8.6.
- **Can make independent money decisions about their health:** 151 yes, 15 no.

## What paying clients say (49 clients)
Full table in `clients_questionnaire_aggregates.csv`.

**Outcome target they ticked (several allowed)**
- Body fat % reduction: 41 (83.7%)
- Weight loss: 34 (69.4%)
- **Waist size reduction: 30 (61.2%)**
- Fit into a specific piece of clothing: 9 (18.4%)

**Diets tried before (several allowed)**
- Carnivore 40 (81.6%), Keto 37 (75.5%), Intermittent fasting 30 (61.2%), Calorie counting 26 (53.1%), Vegan 10, Paleo 9, Mediterranean 9, Macros counting 7
- Which worked best, in their own words: carnivore 30, keto or low carb 15, fasting 7

**Themes across their goal, why now, 12-month goal, #1 obstacle and extra notes**
- Time, work or travel: 33 (67.3%)
- Named a number of lbs or kg: 19 (38.8%)
- Consistency, discipline or motivation: 17 (34.7%)
- Muscle or strength: 17 (34.7%)
- Health scare, doctor, blood work or medication: 16 (32.7%)
- Fit into clothes, appearance or confidence: 16 (32.7%)
- Energy or feeling better: 15 (30.6%)
- Family, kids, grandkids or partner: 14 (28.6%)
- Mentioned the videos or YouTube as the trigger: 12 (24.5%)
- Cravings, sugar or emotional eating: 12 (24.5%)
- Age or a birthday milestone: 10 (20.4%)
- Belly fat, stomach, waist or visceral in their own words: 9 (18.4%). Visceral by name: 3.
- Plateau or stall: 7 (14.3%)
- A dated event like a wedding or trip: 6 (12.2%)

**Other**
- Preferred meals per day: 2 meals 29, 3 meals 10, 1 meal 8, 4 meals 1
- Median sleep quality 6 of 10. Median stress 5 of 10. Median cooking skill 7 of 10.
- Respond better to: a mix 31, harder pushes 14, gentle accountability 4

## From the sales calls (past conclusions, 21 Nov 2026)
- 98 first sales calls, 39 clients, 40% close rate.
- **Prospects who came in from a specific video closed at 53%, against 34% for everyone else.**
- Prospects outside the US closed at 46%. People already eating carnivore closed at 50%.
- People in their 40s and 50s and people with pure fat-loss goals closed above average.

## What this means for Radar (packaging)
These are hints from the numbers above. They are not tested rules.
- Clicks come first. A package that wins a split test but only pulls under-35 men is still a win for the channel.
- Between two equal packages, prefer the one aimed at a 45 to 65 viewer, with carnivore already in their life, trying to lose a set amount of fat, and stalled or short on time.
- Waist and belly fat matter more to buyers (61% picked waist size reduction) than the 13% who write "belly" in an application suggests.
- Women convert at about double their share of views. A package that also works for women 50+ adds buyer value without costing clicks from men.
