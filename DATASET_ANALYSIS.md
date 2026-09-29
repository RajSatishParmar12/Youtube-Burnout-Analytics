# Extracted YouTube dataset analysis

Snapshot analyzed on 24 September 2026 from `data/youtube_burnout_large.csv`
and `data/youtube_burnout_large_videos.csv`. Dashboard features were recomputed
using `burnout_core.py`; these figures describe the full unfiltered sample.

| Measure | Result |
| --- | ---: |
| Comments and replies | 40,327 |
| Distinct anonymized user IDs | 30,990 |
| Videos with collected comments | 138 |
| Video metadata records | 184 |
| Top-level comments | 14,802 |
| Replies | 25,525 (63.3%) |
| Keyword or first-person pattern matches | 2,036 (5.05%) |
| First-person pattern matches | 58 (0.14%) |
| Average signal score | 5.30 / 100 |
| Low signal | 39,495 (97.94%) |
| Emerging signal | 809 (2.01%) |
| Elevated signal | 23 (0.06%) |
| High signal | 0 |
| Missing comment text | 3 |
| Duplicate comment IDs | 0 |
| Nonempty manual labels | 0 |

Comment timestamps range from 15 October 2023 to 23 September 2026 (UTC).
The metadata table includes videos without collected comments, so its row count
should not be used as the number of discussions analyzed.

## What stands out

The large Low band is a real feature of this heuristic analysis, not a fixed chart.
The score histogram makes variation within that band visible. Searching for burnout
videos does not mean every comment expresses burnout; most comments do not match
the selected language patterns. The 58 first-person matches are a narrower language
measure and must not be interpreted as 58 diagnosed people.

Replies account for nearly two thirds of rows. This makes conversation context
important and means rows are not independent participants. Use the comment-type
filter to compare top-level comments with replies.

Collection is uneven across queries: `chronically online` contributes 7,114 comments,
while `content creator burnout` contributes only 10. Compare both counts and match
rates, retaining a minimum sample size. Query labels identify collection provenance;
they are not mutually exclusive semantic categories.

Mean sentiment is approximately +0.201 on VADER's -1 to +1 scale. Sentiment alone
does not establish burnout. Because negative sentiment contributes directly to the
signal score, the sentiment-score scatter is descriptive rather than an independent
validation of the scoring method.

There are no manual labels for evaluation. Keyword labels and score bands describe
this selected sample; they do not estimate population burnout prevalence.

## Visualization choices

Overview shows counts alongside distributions, with coverage and quality details.
Analyze shows overlapping phrase counts and query rates with denominators in hover
labels. The scatter uses at most 4,000 reproducibly sampled points; other aggregate
charts use all filtered rows. Videos highlights which discussions dominate collection.
Timeline places volume beside match rates so sparse periods can be recognized; UTC
activity patterns are not evidence of local sleep disruption.

Every analytical page reads the active session dataset and applies the sidebar
filters. Local file changes trigger a reload on the next interaction. Activity
history is calculated before filters are applied. The seven-day calculation now
normalizes timestamps to nanoseconds explicitly so pandas timestamp resolution
does not distort the window.
