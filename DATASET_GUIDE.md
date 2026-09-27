# YouTube Digital Burnout Dataset Guide

The default dashboard dataset is `data/youtube_burnout_large.csv`, with video context from `data/youtube_burnout_large_videos.csv`. The loader preserves anonymized user IDs and manual annotations, recalculates analysis features, and joins video metadata without duplicating comment rows. Existing comment titles and source queries are preserved.

Use `build_large_youtube_dataset.py --api-key "YOUR_KEY"` to rebuild this pair. Use `build_youtube_dataset.py` for a smaller fresh collection. This is better than a fixed third-party CSV because it preserves provenance, timestamps, engagement, video context, and reproducibility.

Recommended search queries: social media burnout; digital burnout; social media fatigue; digital detox; tired of social media; chronically online; creator burnout; notification fatigue.

Aim for roughly 2,000–5,000 unique comments. Deduplicate by `comment_id`.

Core fields: `comment_id`, hashed `user_id`, `timestamp`, `updated_at`, `text`, `like_count`, `reply_count`, `video_id`, `video_title`, `channel_title`, `source_query`.

Derived fields include sentiment, burnout keywords, self-expressed burnout flag, weak label, late-night flag, observed comment gaps, observed comments in 7 days, and signal score.

For evaluation, manually label 300–500 comments: `1` burnout-related, `0` not burnout-related, `uncertain` ambiguous. Do not treat `weak_burnout_label` as ground truth.

Run:
```bash
python build_youtube_dataset.py --api-key "YOUR_KEY" --output data/youtube_burnout_dataset.csv --days 180 --videos-per-query 8 --comments-per-video 80
```
