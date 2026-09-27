"""Load the extracted comments and their companion video metadata."""
from pathlib import Path
import pandas as pd
from burnout_core import prepare_dataset

DATA_DIR = Path(__file__).resolve().parent / "data"
COMMENTS_PATH = DATA_DIR / "youtube_burnout_large.csv"
VIDEOS_PATH = DATA_DIR / "youtube_burnout_large_videos.csv"


def load_large_dataset():
    comments = pd.read_csv(COMMENTS_PATH, dtype={"user_id": str, "video_id": str})
    videos = pd.read_csv(VIDEOS_PATH, dtype={"video_id": str})
    if "video_id" not in comments or "video_id" not in videos:
        raise ValueError("Both dataset files require a video_id column")
    videos = videos.drop_duplicates("video_id")
    # Keep comment-level provenance and add the extra video context.
    extra_columns = [c for c in videos if c == "video_id" or c not in comments]
    comments = comments.merge(videos[extra_columns], on="video_id", how="left", validate="many_to_one")
    return prepare_dataset(comments, anonymized=True), videos
