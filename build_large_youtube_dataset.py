import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from youtube_api import collect_query, QuotaExceededError

ANALYZER = SentimentIntensityAnalyzer()

QUERIES = [
    "social media burnout",
    "digital burnout",
    "social media fatigue",
    "digital detox",
    "tired of social media",
    "chronically online",
    "creator burnout",
    "content creator burnout",
    "instagram burnout",
    "youtube burnout",
    "tiktok burnout",
    "doomscrolling burnout",
    "social media exhaustion",
    "social media overwhelmed",
    "taking a break from social media",
    "quit social media",
]

BURNOUT_TERMS = [
    "burnout", "burned out", "burnt out", "exhausted", "drained",
    "need a break", "taking a break", "digital detox", "chronically online",
    "doomscrolling", "social media fatigue", "too much social media",
    "tired of social media", "overwhelmed", "logging off", "quit social media",
    "deleting social media", "content creator burnout", "posting pressure",
    "engagement pressure", "notification fatigue",
]

def hash_user(x):
    x = "" if pd.isna(x) else str(x)
    return hashlib.sha256(x.encode()).hexdigest()[:12] if x else "anonymous"

def add_features(df):
    out = df.copy()
    out["user_id"] = out["user_id"].map(hash_user)
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)

    def text_features(text):
        text = "" if pd.isna(text) else str(text)
        low = text.lower()
        sentiment = ANALYZER.polarity_scores(text)["compound"]
        hits = sorted({t for t in BURNOUT_TERMS if t in low})
        return pd.Series({
            "sentiment_score": sentiment,
            "negative_sentiment": max(0.0, -sentiment),
            "burnout_keyword_count": len(hits),
            "matched_terms": ", ".join(hits),
            "weak_burnout_label": int(len(hits) > 0),
            "text_length": len(text),
            "word_count": len(text.split()),
        })

    feats = out["text"].apply(text_features)
    out = pd.concat([out, feats], axis=1)

    out["hour"] = out["timestamp"].dt.hour
    out["is_late_night"] = out["hour"].isin([0,1,2,3,4,5]).astype(int)

    out = out.sort_values(["user_id", "timestamp"])
    out["hours_since_previous_observed_comment"] = (
        out.groupby("user_id")["timestamp"].diff().dt.total_seconds()/3600
    )

    out["manual_label"] = ""
    out["manual_label_notes"] = ""
    return out

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    p = argparse.ArgumentParser()
    p.add_argument("--api-key", required=True)
    p.add_argument("--output", default="data/youtube_burnout_large.csv")
    p.add_argument("--days", type=int, default=1095,
                   help="How far back to search. Default 3 years.")
    p.add_argument("--videos-per-query", type=int, default=50)
    p.add_argument("--comments-per-video", type=int, default=250)
    p.add_argument("--min-video-comments", type=int, default=10)
    p.add_argument("--search-order", choices=["relevance","viewCount","date","rating"],
                   default="relevance")
    p.add_argument("--no-replies", action="store_true")
    args = p.parse_args()

    published_after = None
    if args.days > 0:
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=args.days)
        ).isoformat().replace("+00:00","Z")

    all_comments = []
    all_videos = []
    quota_exhausted = False

    for idx, query in enumerate(QUERIES, 1):
        print(f"[{idx}/{len(QUERIES)}] {query}", flush=True)
        try:
            videos, comments = collect_query(
                api_key=args.api_key,
                query=query,
                max_videos=args.videos_per_query,
                max_top_comments_per_video=args.comments_per_video,
                published_after=published_after,
                search_order=args.search_order,
                min_video_comments=args.min_video_comments,
                include_replies=not args.no_replies,
            )
        except QuotaExceededError as exc:
            quota_exhausted = True
            print(f"{exc} Saving available results...", flush=True)
            videos, comments = exc.videos, exc.comments
        if not videos.empty:
            all_videos.append(videos)
        if not comments.empty:
            all_comments.append(comments)
            print(f"  collected {len(comments):,} comments/replies", flush=True)
        else:
            print("  no usable comments returned", flush=True)
        if quota_exhausted:
            break

    if not all_comments:
        if quota_exhausted:
            print("No comments collected before quota exhaustion; no output written.")
            return
        raise RuntimeError("No YouTube comments were collected.")

    raw = pd.concat(all_comments, ignore_index=True)
    raw = raw.drop_duplicates(subset=["comment_id"]).reset_index(drop=True)

    print(f"Adding features to {len(raw):,} unique comments/replies...", flush=True)
    final = add_features(raw)

    out = Path(args.output)
    if quota_exhausted:
        out = out.with_name(out.stem + "_partial" + out.suffix)
    out.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out, index=False)

    if all_videos:
        videos = pd.concat(all_videos, ignore_index=True)
        videos = videos.drop_duplicates(subset=["video_id"])
        videos.to_csv(out.with_name(out.stem + "_videos.csv"), index=False)

    print("\nPARTIAL DATASET — quota exhausted" if quota_exhausted else "\nDONE")
    print(f"Unique comments/replies: {len(final):,}")
    print(f"Unique anonymized users: {final['user_id'].nunique():,}")
    print(f"Videos represented: {final['video_id'].nunique():,}")
    print(f"Weak burnout matches: {final['weak_burnout_label'].sum():,}")
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
