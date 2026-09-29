import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta, timezone
from burnout_core import prepare_dataset
from dataset_loader import load_large_dataset, COMMENTS_PATH, VIDEOS_PATH
from youtube_api import collect_query

st.set_page_config(page_title="YouTube Digital Burnout", page_icon="??", layout="wide")
BANDS = ["Low", "Emerging", "Elevated", "High"]
COLORS = {"Low": "#38b2ac", "Emerging": "#e9b44c", "Elevated": "#ef8354", "High": "#ce4266"}

@st.cache_data(show_spinner="Analyzing the extracted comments?")
def cached_large_dataset(signature):
    return load_large_dataset()

def local_signature():
    return (COMMENTS_PATH.stat().st_mtime_ns, VIDEOS_PATH.stat().st_mtime_ns)

def use_large_dataset():
    signature = local_signature()
    df, videos = cached_large_dataset(signature)
    st.session_state.update(df=df, videos=videos, source="Local large dataset", signature=signature)

def chart(fig):
    fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=55, b=10), height=380)
    st.plotly_chart(fig, width="stretch")

def trend_table(df, frequency):
    return (df.set_index("timestamp").resample(frequency)
            .agg(comments=("text", "size"), matches=("weak_burnout_label", "sum"),
                 average_score=("burnout_signal_score", "mean"))
            .assign(match_rate=lambda x: x.matches.div(x.comments.where(x.comments.gt(0))).mul(100))
            .reset_index())

if "source" not in st.session_state:
    st.session_state.update(df=pd.DataFrame(), videos=pd.DataFrame(), source="Local large dataset", signature=None)
if st.session_state.source == "Local large dataset":
    try:
        if st.session_state.signature != local_signature():
            use_large_dataset()
    except (OSError, ValueError) as exc:
        st.warning(f"Local files could not be refreshed: {exc}")

st.title("YouTube : Digital burnout")
st.caption("Explore language and observed activity in YouTube discussions. Research signals, not clinical diagnoses.")
page = st.sidebar.radio("Navigate", ["Overview", "Analyze", "Videos", "Timeline", "Collect / Upload", "Methodology"])
st.sidebar.caption(f"Active source: {st.session_state.source}")

if page == "Collect / Upload":
    mode = st.radio("Data source", ["Local large dataset", "Upload prepared CSV", "YouTube API"])
    if mode == "Local large dataset":
        st.write("Load the extracted comments and their companion video metadata.")
        st.code("data/youtube_burnout_large.csv\ndata/youtube_burnout_large_videos.csv")
        if st.button("Reload local files", type="primary"):
            try:
                cached_large_dataset.clear()
                use_large_dataset()
                st.success(f"Loaded {len(st.session_state.df):,} comments.")
            except (OSError, ValueError) as exc:
                st.error(str(exc))
        st.caption("While this source is active, file changes are picked up on the next dashboard interaction or refresh.")
    elif mode == "Upload prepared CSV":
        upload = st.file_uploader("Comments CSV", type="csv")
        anonymized = st.checkbox("User IDs are already anonymized", value=True)
        if upload is not None and st.button("Use CSV", type="primary"):
            try:
                df = prepare_dataset(pd.read_csv(upload, dtype={"user_id": str}), anonymized=anonymized)
                st.session_state.update(df=df, videos=pd.DataFrame(), source=f"Upload: {upload.name}")
                st.success(f"Loaded {len(df):,} valid dated comments.")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
    else:
        key = st.text_input("YouTube API key", type="password")
        query = st.text_input("Search query", "social media burnout")
        c1, c2, c3 = st.columns(3)
        nv = c1.slider("Videos", 1, 25, 8)
        nc = c2.slider("Comments/video", 10, 100, 60, 10)
        days = c3.slider("Video age (days)", 7, 365, 180)
        if st.button("Fetch and analyze", type="primary"):
            if not key:
                st.error("Add a YouTube API key.")
            else:
                try:
                    after = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat().replace("+00:00", "Z")
                    videos, raw = collect_query(key, query, nv, nc, after)
                    if raw.empty:
                        st.warning("No comments returned.")
                    else:
                        st.session_state.update(df=prepare_dataset(raw), videos=videos, source=f"YouTube API: {query}")
                        st.success(f"Loaded {len(raw):,} comments.")
                except Exception as exc:
                    st.error(f"YouTube API error: {exc}")
    st.stop()

if page == "Methodology":
    st.markdown("""
### What the charts measure
Each row is an observed comment or reply. Keyword matches and first-person patterns
are heuristic labels; they are not verified burnout cases. Sentiment uses VADER:
negative below 0.05, positive above 0.05, and neutral in between.

The score combines keywords (up to 40 points), negative sentiment (22), first-person
patterns (23), UTC posting hour (8), observed activity bursts (4), and gaps (3).
Bands are Low 25, Emerging 50, Elevated 75, and High >75.
Sentiment and keywords are inputs to the score, so their association with it is expected.

### How to interpret comparisons
Search queries are collection provenance, not exclusive topic labels. Comments and
videos were selected through search and API limits; rates describe this sample only.
Replies within a discussion are related observations. Empty time bins indicate no
collected comments, not an absence of discussion on YouTube. Edge periods may be partial.
UTC posting times cannot establish a commenter's local sleep habits.

Filters change every chart and export. Activity features are calculated on the full
active dataset before filtering to retain observed history. Local CSV changes reload on
the next interaction. Manual labels are needed for independent validation.
""")
    st.stop()

full = st.session_state.df
if full.empty:
    st.info("Load comments in Collect / Upload to begin.")
    st.stop()

st.sidebar.subheader("Filter comments")
start, end = full.timestamp.min().date(), full.timestamp.max().date()
dates = st.sidebar.date_input("Comment dates (UTC)", value=(start, end), min_value=start, max_value=end)
df = full.copy()
if len(dates) == 2:
    df = df[df.timestamp.ge(pd.Timestamp(dates[0], tz="UTC")) & df.timestamp.lt(pd.Timestamp(dates[1], tz="UTC") + pd.Timedelta(days=1))]
for column, label in [("source_query", "Search queries"), ("comment_type", "Comment types")]:
    if column in full:
        selected = st.sidebar.multiselect(label, sorted(full[column].dropna().unique()))
        if selected:
            df = df[df[column].isin(selected)]
bands = st.sidebar.multiselect("Signal bands", BANDS)
if bands:
    df = df[df.signal_band.isin(bands)]
st.sidebar.caption("Empty selections include all values.")
st.caption(f"{st.session_state.source} ? {len(df):,} of {len(full):,} comments ? all charts use the filters shown at left")
if df.empty:
    st.info("No comments match these filters. Widen the date range or clear a selection.")
    st.stop()
df["sentiment"] = "Neutral"
df.loc[df.sentiment_score > .05, "sentiment"] = "Positive"
df.loc[df.sentiment_score < -.05, "sentiment"] = "Negative"

if page == "Overview":
    st.subheader("The sample at a glance")
    cols = st.columns(5)
    values = [("Comments", f"{len(df):,}"), ("Observed users", f"{df.user_id.nunique():,}"),
              ("Videos with comments", f"{df.video_id.nunique():,}" if "video_id" in df else "?"),
              ("Language match rate", f"{df.weak_burnout_label.mean():.1%}"),
              ("Average signal / 100", f"{df.burnout_signal_score.mean():.1f}")]
    for col, (label, value) in zip(cols, values):
        col.metric(label, value)
    st.info(f"{int(df.weak_burnout_label.sum()):,} comments match a keyword or first-person pattern; "
            f"{int(df.self_expressed_burnout.sum()):,} match the narrower first-person patterns. "
            f"{df.signal_band.eq('Low').mean():.1%} fall in the Low signal band.")
    a, b = st.columns(2)
    with a:
        counts = df.signal_band.value_counts().reindex(BANDS, fill_value=0).rename_axis("Signal band").reset_index(name="Comments")
        chart(px.bar(counts, x="Signal band", y="Comments", color="Signal band", color_discrete_map=COLORS,
                 text_auto=True, title="How strong are the observed signals?"))
    with b:
        chart(px.histogram(df, x="burnout_signal_score", nbins=40, title="Score distribution: beyond the four bands",
                           labels={"burnout_signal_score": "Signal score / 100"}, color_discrete_sequence=["#5674c0"]))
    a, b = st.columns(2)
    with a:
        counts = df.sentiment.value_counts().rename_axis("Sentiment").reset_index(name="Comments")
        chart(px.bar(counts, x="Sentiment", y="Comments", color="Sentiment", text_auto=True,
                     color_discrete_map={"Positive":"#38b2ac", "Neutral":"#a0aec0", "Negative":"#ce4266"}, title="Emotional tone of the comments"))
    with b:
        monthly = trend_table(df, "MS")
        chart(px.bar(monthly, x="timestamp", y="comments", title="Collected comments by month",
                     labels={"timestamp":"Comment month (UTC)", "comments":"Comments"}))
    st.caption("Counts describe the collected sample. A larger monthly bar can reflect collection coverage or a popular thread.")
    with st.expander("Dataset coverage and quality"):
        st.write(f"Comment dates: {df.timestamp.min():%d %b %Y} to {df.timestamp.max():%d %b %Y} (UTC).")
        st.write(f"Missing or blank text: {int(df.text.fillna('').str.strip().eq('').sum()):,}. "
                 f"Manually labeled rows: {int(df.get('manual_label', pd.Series(dtype=str)).fillna('').astype(str).str.strip().ne('').sum()):,}.")
        if "comment_id" in df:
            st.write(f"Duplicate comment IDs: {int(df.comment_id.duplicated().sum()):,}.")
        st.write(f"Companion metadata contains {len(st.session_state.videos):,} videos; some have no collected comments.")
        if "comment_type" in df:
            st.dataframe(df.comment_type.value_counts().rename("Comments"), width="stretch")

elif page == "Analyze":
    st.subheader("Language, topics, and individual comments")
    a, b = st.columns(2)
    with a:
        terms = df.matched_terms.fillna('').str.split(', ').explode()
        terms = terms[terms.ne('')].value_counts().head(15).sort_values().rename_axis("Term").reset_index(name="Comments")
        if terms.empty:
            st.info("No keyword matches in this selection.")
        else:
            chart(px.bar(terms, x="Comments", y="Term", orientation="h", title="Most frequently matched phrases"))
        st.caption("A comment can match several phrases; counts overlap.")
    with b:
        sample = df.sample(min(4000, len(df)), random_state=42)
        chart(px.scatter(sample, x="sentiment_score", y="burnout_signal_score", color="signal_band",
                         color_discrete_map=COLORS, opacity=.45, hover_data=["matched_terms"],
                         labels={"sentiment_score":"Sentiment (negative ? positive)", "burnout_signal_score":"Signal score / 100"},
                         title="Sentiment and signal strength"))
        st.caption(f"Showing {len(sample):,} sampled points. Sentiment is a score input, so this is not independent evidence.")
    if "source_query" in df:
        summary = df.groupby("source_query").agg(Comments=("text","size"), Matches=("weak_burnout_label","sum"))
        summary["Match rate (%)"] = summary.Matches / summary.Comments * 100
        minimum = st.number_input("Minimum comments per query", min_value=1, value=30)
        summary = summary[summary.Comments >= minimum].sort_values("Match rate (%)").reset_index()
        chart(px.bar(summary, x="Match rate (%)", y="source_query", orientation="h", hover_data=["Comments","Matches"],
                     labels={"source_query":"Collection query"}, title="Language match rates across collection queries"))
        st.caption("Rates use all selected comments per query. Small groups are unstable; queries are not exclusive topics.")
    search = st.text_input("Find text in comments")
    rows = df[df.text.fillna('').str.contains(search, case=False, regex=False)] if search else df
    fields = [c for c in ["timestamp","text","video_title","comment_type","matched_terms","sentiment_score","burnout_signal_score","signal_band","manual_label"] if c in rows]
    st.dataframe(rows.sort_values("burnout_signal_score", ascending=False)[fields].head(500), width="stretch", hide_index=True)
    st.caption(f"Showing up to 500 highest-scoring comments of {len(rows):,} text matches. Export includes all matching rows.")
    st.download_button("Download filtered analyzed comments", rows.to_csv(index=False).encode(), "youtube_burnout_filtered.csv", "text/csv")

elif page == "Videos":
    st.subheader("Which discussions shape the sample?")
    if "video_id" not in df:
        st.info("This dataset has no video IDs.")
        st.stop()
    videos = df.groupby("video_id").agg(comments=("text","size"), matches=("weak_burnout_label","sum"), average_score=("burnout_signal_score","mean"))
    videos["match_rate"] = videos.matches / videos.comments * 100
    for column in ["video_title", "channel_title", "view_count", "video_like_count"]:
        if column in df:
            videos[column] = df.groupby("video_id")[column].first()
    videos = videos.reset_index()
    videos["title"] = videos.get("video_title", videos.video_id).fillna(videos.video_id)
    top = videos.nlargest(15, "comments").sort_values("comments")
    # IDs distinguish videos that happen to have identical titles.
    top["Video"] = top.title.str.slice(0, 48) + " ? " + top.video_id
    chart(px.bar(top, x="comments", y="Video", orientation="h", hover_data=["title", "match_rate"],
                 labels={"comments":"Collected comments"}, title="Largest discussions in the selected sample"))
    minimum = st.number_input("Minimum comments per video", min_value=1, value=30)
    eligible = videos[videos.comments >= minimum]
    chart(px.scatter(eligible, x="comments", y="match_rate", size="comments", hover_name="title",
                     labels={"comments":"Collected comments", "match_rate":"Language match rate (%)"}, title="Discussion size and language match rate"))
    st.caption("Collected comments are a subset of each video's discussion. Views and likes are metadata snapshots, not filtered comment totals.")
    st.dataframe(videos.sort_values("comments", ascending=False), width="stretch", hide_index=True)

elif page == "Timeline":
    st.subheader("Change over time")
    frequency = st.radio("Time interval", ["Monthly", "Weekly"], horizontal=True)
    trend = trend_table(df, "MS" if frequency == "Monthly" else "W-MON")
    a, b = st.columns(2)
    with a:
        chart(px.bar(trend, x="timestamp", y="comments", labels={"timestamp":"Period (UTC)","comments":"Comments"}, title="Observed comment volume"))
    with b:
        chart(px.line(trend, x="timestamp", y="match_rate", markers=True, hover_data=["comments","matches"],
                      labels={"timestamp":"Period (UTC)","match_rate":"Language match rate (%)"}, title="Language matches as a share of comments"))
    st.caption("Weekly dates mark periods ending Monday. Gaps have no observations; first and last periods may be incomplete.")
    heat = pd.crosstab(df.timestamp.dt.dayofweek, df.timestamp.dt.hour).reindex(index=range(7), columns=range(24), fill_value=0)
    heat.index = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    chart(px.imshow(heat, aspect="auto", color_continuous_scale="Teal", labels={"x":"Hour (UTC)","y":"Day","color":"Comments"}, title="When were the comments posted?"))
    st.caption("Posting times are UTC, not the commenters' local time zones.")
    counts = df.user_id.value_counts()
    users = counts[counts >= 3].index.tolist()
    if users:
        uid = st.selectbox("User with at least three selected comments", users)
        user = df[df.user_id == uid].sort_values("timestamp")
        chart(px.line(user, x="timestamp", y="burnout_signal_score", markers=True, hover_data=["matched_terms"],
                      labels={"timestamp":"Comment time (UTC)","burnout_signal_score":"Signal score / 100"}, title="One user's observed comments"))
        st.dataframe(user[["timestamp","text","burnout_signal_score"]], width="stretch", hide_index=True)
        st.caption("Connected points show observed comments only, not a continuous measure of wellbeing.")
    else:
        st.info("No user has at least three comments in this selection.")
