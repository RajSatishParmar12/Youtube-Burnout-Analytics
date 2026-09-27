import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

BASE = "https://www.googleapis.com/youtube/v3"


class QuotaExceededError(RuntimeError):
    """Carry collected data to the CLI when the API quota is exhausted."""

    def __init__(self, message):
        super().__init__(message)
        self.rows = []
        self.videos = pd.DataFrame()
        self.comments = pd.DataFrame()

def _get(endpoint, params):
    started = time.monotonic()
    logger.info("Requesting %s%s ...", endpoint,
                " (next page)" if params.get("pageToken") else "")
    try:
        r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    except requests.RequestException as exc:
        # Request exception messages can contain the URL, including the API key.
        raise RuntimeError(
            f"YouTube {endpoint} request failed ({type(exc).__name__}). "
            "Check your network connection and try again."
        ) from None
    if not r.ok:
        try:
            reasons = [e.get("reason", "unknown")
                       for e in r.json().get("error", {}).get("errors", [])]
        except (ValueError, AttributeError, TypeError):
            reasons = []
        if r.status_code == 403 and any(
            reason in reasons for reason in ("quotaExceeded", "dailyLimitExceeded")
        ):
            raise QuotaExceededError(
                "YouTube quotaExceeded: collection stopped because the API quota is exhausted."
            )
        if r.status_code == 403 and endpoint == "commentThreads" and "commentsDisabled" in reasons:
            logger.warning("Comments disabled for video %s; skipping.", params.get("videoId"))
            return None, r
        if r.status_code == 404 and endpoint == "commentThreads" and "videoNotFound" in reasons:
            logger.warning(
                "Video %s is unavailable (videoNotFound); skipping remaining pages, "
                "keeping comments already collected.", params.get("videoId")
            )
            return None, r
        reason = ", ".join(reasons) or "unknown reason"
        reason = reason.replace(str(params.get("key", "")), "[REDACTED]") if params.get("key") else reason
        raise RuntimeError(
            f"YouTube {endpoint} failed (HTTP {r.status_code}: {reason}). "
            "Check your API key, YouTube Data API access, and quota."
        )
    logger.info("Received %s response in %.1fs", endpoint, time.monotonic() - started)
    return r.json(), r

def search_videos(
    api_key,
    query,
    max_videos=50,
    published_after=None,
    order="relevance",
    relevance_language="en",
):
    """
    Collect multiple pages of video search results.
    order: relevance | viewCount | date | rating
    """
    rows = []
    page_token = None

    while len(rows) < max_videos:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(50, max_videos - len(rows)),
            "key": api_key,
            "order": order,
            "relevanceLanguage": relevance_language,
            "safeSearch": "moderate",
        }
        if published_after:
            params["publishedAfter"] = published_after
        if page_token:
            params["pageToken"] = page_token

        data, _ = _get("search", params)
        if not data:
            break

        for item in data.get("items", []):
            s = item["snippet"]
            rows.append({
                "video_id": item["id"]["videoId"],
                "video_title": s.get("title", ""),
                "video_description": s.get("description", ""),
                "channel_id": s.get("channelId", ""),
                "channel_title": s.get("channelTitle", ""),
                "video_published_at": s.get("publishedAt", ""),
                "source_query": query,
                "search_order": order,
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return pd.DataFrame(rows).drop_duplicates("video_id") if rows else pd.DataFrame()

def fetch_video_statistics(api_key, video_ids):
    if not video_ids:
        return pd.DataFrame()

    rows = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        params = {
            "part": "statistics",
            "id": ",".join(batch),
            "key": api_key,
        }
        data, _ = _get("videos", params)
        if not data:
            continue
        for item in data.get("items", []):
            s = item.get("statistics", {})
            rows.append({
                "video_id": item.get("id"),
                "view_count": int(s.get("viewCount", 0) or 0),
                "video_like_count": int(s.get("likeCount", 0) or 0),
                "video_comment_count": int(s.get("commentCount", 0) or 0),
            })
    return pd.DataFrame(rows, columns=[
        "video_id", "view_count", "video_like_count", "video_comment_count"
    ])

def fetch_all_replies(api_key, parent_id, video_meta, top_comment_id, max_replies=200):
    rows = []
    page_token = None

    while len(rows) < max_replies:
        params = {
            "part": "snippet",
            "parentId": parent_id,
            "maxResults": min(100, max_replies - len(rows)),
            "textFormat": "plainText",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data, _ = _get("comments", params)
        except QuotaExceededError as exc:
            exc.rows = rows
            raise
        if not data:
            break

        for item in data.get("items", []):
            s = item["snippet"]
            rows.append({
                "platform": "youtube",
                "comment_id": item.get("id", ""),
                "parent_comment_id": top_comment_id,
                "comment_type": "reply",
                "user_id": s.get("authorChannelId", {}).get(
                    "value", s.get("authorDisplayName", "anonymous")
                ),
                "timestamp": s.get("publishedAt"),
                "updated_at": s.get("updatedAt"),
                "text": s.get("textDisplay", ""),
                "like_count": s.get("likeCount", 0),
                "reply_count": 0,
                **video_meta,
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return rows

def fetch_comments(
    api_key,
    video_id,
    video_title="",
    channel_title="",
    source_query="",
    max_top_comments=300,
    comment_order="relevance",
    include_replies=True,
    max_replies_per_thread=100,
):
    """
    Fetch top-level comment threads across pages and optionally all replies.
    """
    rows = []
    page_token = None

    video_meta = {
        "video_id": video_id,
        "video_title": video_title,
        "channel_title": channel_title,
        "source_query": source_query,
    }

    while len([r for r in rows if r["comment_type"] == "top_level"]) < max_top_comments:
        current_top = len([r for r in rows if r["comment_type"] == "top_level"])
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, max_top_comments - current_top),
            "textFormat": "plainText",
            "order": comment_order,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data, resp = _get("commentThreads", params)
        except QuotaExceededError as exc:
            exc.rows = rows
            raise
        if not data:
            break

        for item in data.get("items", []):
            thread = item["snippet"]
            top = thread["topLevelComment"]
            s = top["snippet"]

            rows.append({
                "platform": "youtube",
                "comment_id": top.get("id", ""),
                "parent_comment_id": "",
                "comment_type": "top_level",
                "user_id": s.get("authorChannelId", {}).get(
                    "value", s.get("authorDisplayName", "anonymous")
                ),
                "timestamp": s.get("publishedAt"),
                "updated_at": s.get("updatedAt"),
                "text": s.get("textDisplay", ""),
                "like_count": s.get("likeCount", 0),
                "reply_count": thread.get("totalReplyCount", 0),
                **video_meta,
            })

            if include_replies and thread.get("totalReplyCount", 0) > 0:
                try:
                    replies = fetch_all_replies(
                        api_key,
                        parent_id=top.get("id", ""),
                        video_meta=video_meta,
                        top_comment_id=top.get("id", ""),
                        max_replies=max_replies_per_thread,
                    )
                except QuotaExceededError as exc:
                    exc.rows = rows + exc.rows
                    raise
                rows.extend(replies)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return pd.DataFrame(rows)

def collect_query(
    api_key,
    query,
    max_videos=50,
    max_top_comments_per_video=250,
    published_after=None,
    search_order="relevance",
    min_video_comments=10,
    include_replies=True,
):
    videos = search_videos(
        api_key=api_key,
        query=query,
        max_videos=max_videos,
        published_after=published_after,
        order=search_order,
    )

    if videos.empty:
        return videos, pd.DataFrame()

    stats = fetch_video_statistics(api_key, videos["video_id"].tolist())
    videos = videos.merge(stats, on="video_id", how="left")

    # Focus collection on videos that can actually yield useful comment volume.
    videos["video_comment_count"] = videos["video_comment_count"].fillna(0)
    candidates = videos[videos["video_comment_count"] >= min_video_comments].copy()
    candidates = candidates.sort_values(
        ["video_comment_count", "view_count"], ascending=False
    )
    logger.info("Found %d videos; %d meet the minimum comment count.", len(videos), len(candidates))

    frames = []
    for index, (_, row) in enumerate(candidates.iterrows(), 1):
        logger.info("Video %d/%d: %s (%s)", index, len(candidates), row["video_title"], row["video_id"])
        try:
            df = fetch_comments(
                api_key=api_key,
                video_id=row["video_id"],
                video_title=row["video_title"],
                channel_title=row["channel_title"],
                source_query=query,
                max_top_comments=max_top_comments_per_video,
                comment_order="relevance",
                include_replies=include_replies,
                max_replies_per_thread=100,
            )
        except QuotaExceededError as exc:
            if exc.rows:
                frames.append(pd.DataFrame(exc.rows))
            exc.videos = videos
            exc.comments = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            raise
        if not df.empty:
            frames.append(df)
        logger.info("Video %d/%d complete: %d comments/replies", index, len(candidates), len(df))

    comments = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return videos, comments
