# YouTube Digital Burnout Analyzer

A Streamlit research dashboard for exploring language and observed activity associated
with self-expressed digital burnout in YouTube comments and replies.

**Research question:** Can observable language and activity patterns in YouTube
discussions reveal signals associated with self-expressed digital burnout?

The project collects comments through the YouTube Data API, anonymizes commenter
identifiers, computes sentiment and heuristic burnout signals, and provides
interactive visualizations. Scores are research indicators, not clinical diagnoses.

## Quick start

Use Python 3.11 (the version used for local verification). Run these commands from
the project root.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Open the local address printed by Streamlit, usually `http://localhost:8501`.
These commands use the virtual environment directly; activation is optional.
For the `python` commands below, activate that environment or use its Python path.

## Load a dataset

### Extracted local data

Place the following files in `data/`:

```text
data/
  youtube_burnout_large.csv          # Comments and replies
  youtube_burnout_large_videos.csv   # Companion video metadata
```

The dashboard automatically loads this pair, joins video metadata on `video_id`,
preserves existing anonymized IDs and manual annotations, and recomputes analysis
features. No API key is needed to explore local data.

While the local source is active, changed CSV files reload on the next dashboard
interaction or refresh. Use **Collect / Upload ? Local large dataset ? Reload local
files** to force a reload. Extracted CSVs are ignored by Git and may need to be
copied into a fresh checkout or generated with the collector below.

### Upload a CSV

Choose **Collect / Upload ? Upload prepared CSV**. Required columns:

| Column | Meaning |
| --- | --- |
| `text` | Comment content |
| `timestamp` | Parseable comment timestamp, preferably ISO 8601 with timezone |

Include `user_id` for meaningful commenter histories; otherwise rows share an
anonymous identifier. Optional fields include `comment_id`, `video_id`,
`video_title`, `channel_title`, `source_query`, `comment_type`, `like_count`,
`manual_label`, and `manual_label_notes`.

Leave **User IDs are already anonymized** checked for project-generated CSVs;
uncheck it for raw identifiers. Rows with unparseable timestamps are excluded.
Video-specific charts require `video_id`. Uploads do not automatically attach the
local companion metadata file.

`synthetic_demo_only.csv` is for demonstration only, not research evidence.
`manual_annotation_template.csv` supports the manual annotation workflow.

## Collect fresh YouTube data

Use an API key from a Google Cloud project with **YouTube Data API v3** enabled.
The dashboard accepts the key under **Collect / Upload ? YouTube API**. The command
line builders require `--api-key`; the current app and builders do not automatically
read `.streamlit/secrets.toml` or environment variables.

The commands below use a placeholder. Keep actual keys out of committed files.
`.streamlit/secrets.toml.example` is a placeholder template for future configuration;
local `.streamlit/secrets.toml` files are ignored by Git.

### Large multi-query collection

```bash
python build_large_youtube_dataset.py --api-key "YOUR_API_KEY"
```

Default output is the two local dataset files listed above.

| Option | Default | Purpose |
| --- | --- | --- |
| `--output` | `data/youtube_burnout_large.csv` | Comments output; metadata uses the `_videos.csv` suffix |
| `--days` | `1095` | Video publication lookback; `0` removes the date restriction |
| `--videos-per-query` | `50` | Maximum search results per query |
| `--comments-per-video` | `250` | Maximum top-level comments per video; replies add rows |
| `--min-video-comments` | `10` | Minimum reported comments for a candidate video |
| `--search-order` | `relevance` | Also accepts `viewCount`, `date`, or `rating` |
| `--no-replies` | Off | Skip reply collection |

Collection spans multiple queries and deduplicates comment IDs. API limits and
available discussions determine the final size; requested limits are not guaranteed
row counts. If quota is exhausted, available results are saved with a `_partial`
suffix. Partial files are not automatically selected as the default dashboard pair;
upload the comments CSV to inspect them.

### Smaller collection

```bash
python build_youtube_dataset.py --api-key "YOUR_API_KEY" --output data/youtube_burnout_dataset.csv --days 180 --videos-per-query 8 --comments-per-video 80
```

This creates a comments CSV and companion `_videos.csv`. Upload its comments CSV
to explore it without replacing the large default dataset.

## Dashboard pages

| Page | What you can explore |
| --- | --- |
| **Overview** | Sample coverage, score bands and distribution, sentiment, monthly volume, and data quality |
| **Analyze** | Matched phrases, sentiment versus score, query match rates, searchable comments, and filtered CSV export |
| **Videos** | Largest collected discussions, per-video match rates, and available video metadata |
| **Timeline** | Monthly/weekly volume and match rates, UTC posting heatmap, and observed commenter histories |
| **Collect / Upload** | Reload local data, upload a CSV, or collect live comments |
| **Methodology** | Scoring definitions, interpretation, and sampling limitations |

Sidebar filters select dates, collection queries, comment types, and signal bands.
Empty multiselects include all values. Analytical charts use the filtered active
dataset; activity features retain the full active dataset's observed history.
The sentiment-score scatter displays up to 4,000 reproducibly sampled points.
The comments table shows up to 500 rows; its export includes all filtered text matches.

## Analysis and interpretation

VADER supplies sentiment features. Keywords and first-person patterns supply weak
language labels. The signal score combines language, sentiment, UTC posting hour,
and observed comment bursts and gaps into a 0?100 scale.

| Band | Score |
| --- | --- |
| Low | 0?25 |
| Emerging | >25?50 |
| Elevated | >50?75 |
| High | >75?100 |

For the extracted snapshot analyzed on 24 September 2026:

- **40,327** comments and replies from **30,990** distinct anonymized user IDs.
- **138** videos with comments; **184** records in the companion metadata table.
- **5.05%** match a keyword or first-person pattern; **97.94%** fall in the Low band.

These are snapshot results, not fixed dashboard values. See
[Dataset analysis](DATASET_ANALYSIS.md) for findings and
[Dataset guide](DATASET_GUIDE.md) for collection and annotation notes.

The sample is selected through search and API limits, not representative of all
YouTube users. Related replies are not independent participants. Weak labels are
not ground truth, and sentiment is itself a score input. UTC posting hours do not
establish local sleep habits. Anonymized IDs do not remove identifying information
that may appear in comment text. Review data before sharing it.

## Project structure

```text
app.py                          Streamlit dashboard and filtering
burnout_core.py                 Text features, activity features, and scoring
dataset_loader.py              Default CSV loading and video metadata join
youtube_api.py                 YouTube API collection and error handling
build_large_youtube_dataset.py Large multi-query collector
build_youtube_dataset.py       Smaller dataset builder
data/                          Local extracted datasets (ignored by Git)
requirements.txt               Python dependencies
DATASET_ANALYSIS.md             Snapshot findings and chart interpretation
DATASET_GUIDE.md                Collection and annotation guidance
manual_annotation_template.csv Annotation template
synthetic_demo_only.csv        Demonstration data
.streamlit/secrets.toml.example Placeholder configuration example
```

## Troubleshooting

- **Missing local CSVs:** add both default files, run the large collector, or select
  an upload/API source under Collect / Upload.
- **Missing Python packages:** install requirements with the same virtual environment
  used to launch Streamlit.
- **No comments after filtering:** widen the date range or clear sidebar selections.
- **No user timeline:** at least three selected comments must share a user ID.
- **API quota exhausted:** inspect any saved partial collection and retry once quota
  is available. The default dashboard does not automatically load partial files.
- **An old dataset is displayed:** confirm the active source, then reload local files.
  An uploaded dataset remains active until you switch sources.

## Repository hygiene

The ignore rules exclude virtual environments, Python caches, local secrets,
extracted datasets, exports, logs, and editor state. Source files, documentation,
the secrets example, demo CSV, and annotation template remain trackable.
Ignoring a path does not remove files already tracked by Git.
