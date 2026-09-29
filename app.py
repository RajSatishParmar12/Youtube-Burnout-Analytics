import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import spearmanr
from typing import Protocol, cast
from datetime import datetime, timedelta, timezone
from burnout_core import prepare_dataset
from dataset_loader import load_large_dataset, COMMENTS_PATH, VIDEOS_PATH
from youtube_api import collect_query


class ClearableCache(Protocol):
    def clear(self) -> None: ...


st.set_page_config(page_title="YouTube Digital Burnout Signal Analysis", page_icon="🧭", layout="wide")
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

st.title("YouTube Digital Burnout Signal Analysis")
st.caption("Identifying linguistic and activity signals associated with self-expressed digital burnout in YouTube discussions. Research signals, not clinical diagnoses.")
page = st.sidebar.radio(
    "Navigate",
    [
        "Overview",
        "Analyze",
        "Videos",
        "Timeline",
        "Collect / Upload",
        "Methodology & Ethics",
    ],
)
st.sidebar.caption(f"Active source: {st.session_state.source}")

if page == "Collect / Upload":
    st.header("Collect / Upload — YouTube Data")
    st.caption("Load the prepared YouTube dataset, upload a prepared CSV, or collect a smaller sample through the YouTube API.")
    mode = st.radio("Data source", ["Local large dataset", "Upload prepared CSV", "YouTube API"])
    if mode == "Local large dataset":
        st.write("Load the extracted comments and their companion video metadata.")
        st.code("data/youtube_burnout_large.csv\ndata/youtube_burnout_large_videos.csv")
        if st.button("Reload local files", type="primary"):
            try:
                cast(ClearableCache, cached_large_dataset).clear()
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

if page == "Methodology & Ethics":
    st.header("Methodology & Ethics")

    st.markdown("""
### Research objective

**Research question:** Can observable language and activity patterns in YouTube comments reveal signals associated with self-expressed digital burnout?

The project analyzes publicly available YouTube comments and replies. It identifies observable linguistic and activity signals associated with expressions of digital exhaustion, overload, withdrawal, and related experiences. The system does **not** diagnose burnout or any mental-health condition.

### Data source

The dashboard uses **YouTube-only** data.

Comments are collected from YouTube search contexts and associated videos. Search queries are treated as **collection contexts**, not as exclusive topic categories. API limits and the availability of comments influence which discussions are represented.

Each comment/reply is treated as an observed record. User identifiers used for analysis are anonymized.

### Linguistic signals

The system looks for burnout-related expressions such as:

- burnout / burnt out / burned out
- exhausted / drained / overwhelmed
- tired of being online or social media
- chronically online
- doomscrolling
- digital detox
- taking a break / need a break
- logging off / leaving social media / quitting social media
- creator and posting pressure

The `matched_terms` field records detected language matches. These are **heuristic indicators**, not ground-truth burnout labels.

### Sentiment analysis

Sentiment is calculated using VADER.

- Positive: sentiment score above 0.05
- Neutral: between -0.05 and 0.05
- Negative: below -0.05

Sentiment is one input to the composite signal score, so its relationship with the score is expected.

### Composite signal score

The observed signal score combines:

- burnout-related keywords: up to 40 points
- negative sentiment: 22 points
- first-person/self-expression patterns: 23 points
- UTC posting hour: 8 points
- observed activity bursts: 4 points
- observed posting gaps: 3 points

Signal bands are:

- **Low:** below 25
- **Emerging:** 25–49
- **Elevated:** 50–74
- **High:** 75+

The score is an **explainable research heuristic**, not a clinical or psychological measurement.

### Dashboard analysis

#### Analyze page

The Analyze page contains three main visualizations:

1. **Collection Query vs Burnout-Language Match Rate**  
   Shows the percentage of collected comments containing at least one detected burnout-related language match for each search context.

2. **Average Burnout Signal by Language Match**  
   Compares the average composite signal score for comments with detected burnout-related language and comments without a detected language match. This is descriptive because language matching is itself part of the score.

3. **Most Frequently Matched Burnout-Related Terms**  
   Shows which detected expressions occur most frequently in the selected comments.

The page also provides filtered comments and CSV export.

#### Timeline page

The Timeline page contains three visualizations:

1. **Observed Comment Volume Over Time**  
   Shows the number of comments collected in each monthly or weekly period.

2. **Burnout-Language Match Rate Over Time**  
   Shows how the proportion of comments containing detected burnout-related language varies across time periods.

3. **Comment Activity by Day & Hour**  
   Shows when collected comments were posted using UTC day and hour.

These charts describe the collected sample. They do not establish that burnout itself increased or decreased over time.

### Statistical analysis

Spearman rank correlation may be reported as a **descriptive statistical result** when examining the relationship between sentiment and the composite signal score.

Because sentiment is already a component of the composite score, this correlation is **not independent validation**.

For independent evaluation, manually annotate a representative sample and compare the heuristic labels with human labels using:

- precision
- recall
- F1-score
- confusion matrix

Where possible, use more than one annotator and document disagreements.

### Limitations

- YouTube comments are not representative of all social-media users.
- Search and API limits affect the collected sample.
- A comment containing burnout-related language does not necessarily mean the author is experiencing burnout.
- Absence of a language match does not mean absence of burnout.
- Replies are related observations and may not be equivalent to top-level comments.
- Activity features describe **observed activity within the collected YouTube sample**, not a user's complete online behaviour.
- UTC timestamps do not reveal commenters' local time zones.
- Empty time periods indicate no collected observations, not absence of discussion.
- The composite score has not been clinically validated.

### Ethics

- Do not use the score to diagnose individuals.
- Do not use it to target, contact, punish, or profile individual users.
- Do not infer private or sensitive attributes.
- Keep user identifiers anonymized.
- Prefer aggregate findings over individual-level conclusions.
- Follow YouTube platform requirements and applicable institutional research-ethics requirements.
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
st.caption(f"{st.session_state.source} • {len(df):,} of {len(full):,} comments • all charts use the filters shown at left")
if df.empty and page != "Analyze":
    st.info("No comments match these filters. Widen the date range or clear a selection.")
    st.stop()
df["sentiment"] = "Neutral"
df.loc[df.sentiment_score > .05, "sentiment"] = "Positive"
df.loc[df.sentiment_score < -.05, "sentiment"] = "Negative"

if page == "Overview":
    st.header("Overview — YouTube Burnout Signals at a Glance")
    st.subheader("What does the collected sample look like?")
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
        chart(px.pie(counts, names="Sentiment", values="Comments", color="Sentiment",
                     color_discrete_map={"Positive":"#38b2ac", "Neutral":"#a0aec0", "Negative":"#ce4266"},
                     title="Emotional tone of the comments", hole=0.35))
    with b:
        monthly = trend_table(df, "MS")
        monthly_fig = px.line(monthly, x="timestamp", y="comments", markers=True, title="Collected comments by month",
                              labels={"timestamp":"Comment month (UTC)", "comments":"Comments"})
        monthly_fig.update_traces(hovertemplate="%{x|%B %Y}<br>Comments: %{y:,}<extra></extra>")
        month_ticks = monthly.timestamp
        month_labels = [""] * len(month_ticks)
        for index, date in enumerate(month_ticks):
            if date.month == 1 or index == 0:
                month_labels[index] = str(date.year)
        monthly_fig.update_xaxes(tickmode="array", tickvals=month_ticks, ticktext=month_labels)
        chart(monthly_fig)
    st.caption("Counts describe the collected sample. A higher monthly point can reflect collection coverage or a popular thread.")
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
    st.header("Analyze — Language & Signal Patterns")
    st.subheader("Where burnout-related language appears and how the signals behave")

    def empty_figure(title, message):
        figure = go.Figure()
        figure.update_layout(title=title, xaxis={"visible": False}, yaxis={"visible": False})
        figure.add_annotation(text=message, x=.5, y=.5, xref="paper", yref="paper", showarrow=False)
        return figure

    st.markdown("### Summary Metrics")
    metric_cols = st.columns(3)
    metric_cols[0].metric("Rows", f"{len(df):,}")
    if df.empty:
        metric_cols[1].metric("Average Signal", "—")
        metric_cols[2].metric("Language Match Rate", "—")
    else:
        metric_cols[1].metric("Average Signal", f"{df.burnout_signal_score.mean():.1f}/100")
        metric_cols[2].metric("Language Match Rate", f"{df.weak_burnout_label.mean():.1%}")

    st.markdown("### 1. Collection Query vs Burnout-Language Match Rate")
    st.caption("Percentage of collected comments containing at least one burnout-related language match. Search queries describe collection contexts; these rates do not show that a topic causes burnout.")
    if df.empty:
        chart(empty_figure("Collection Query vs Burnout-Language Match Rate", "No comments match the current filters."))
    elif "source_query" not in df.columns:
        chart(empty_figure("Collection Query vs Burnout-Language Match Rate", "This dataset does not include a source_query column."))
    else:
        query_data = df.assign(
            _query=df.source_query.fillna("").astype(str).str.strip().replace("", "Unspecified query"),
            _has_match=df.matched_terms.fillna("").astype(str).str.strip().ne(""),
        )
        query_summary = query_data.groupby("_query", dropna=False).agg(
            Comments=("text", "size"), Matches=("_has_match", "sum")
        )
        query_summary["Match rate (%)"] = query_summary.Matches / query_summary.Comments * 100
        query_summary["Rate label"] = query_summary["Match rate (%)"].map(lambda value: f"{value:.1f}%")
        query_summary = query_summary.sort_values("Match rate (%)", ascending=False).reset_index()
        query_fig = px.bar(
            query_summary, x="Match rate (%)", y="_query", orientation="h", text="Rate label",
            hover_data={"Comments": True, "Matches": True, "Rate label": False},
            labels={"_query": "Collection query"},
            title="Collection Query vs Burnout-Language Match Rate",
            color_discrete_sequence=["#5674c0"],
            category_orders={"_query": query_summary["_query"].tolist()},
        )
        query_fig.update_traces(textposition="outside", cliponaxis=False)
        query_fig.update_yaxes(autorange="reversed")
        query_fig.update_xaxes(title="Match rate (%)", rangemode="tozero")
        chart(query_fig)

    st.markdown("### 2. Average Burnout Signal by Language Match")
    st.caption("Comparison of the composite signal score for comments with and without detected burnout-related language. Because matched language is one component of the score, this is descriptive and not independent validation.")
    if df.empty:
        chart(empty_figure("Average Burnout Signal by Language Match", "No comments match the current filters."))
    else:
        group_names = ["Burnout-related language", "No burnout-language match"]
        has_match = df.matched_terms.fillna("").astype(str).str.strip().ne("")
        comparison = df.assign(
            _language_group=has_match.map({True: group_names[0], False: group_names[1]})
        )
        comparison_summary = comparison.groupby("_language_group").agg(
            n=("text", "size"), average_score=("burnout_signal_score", "mean")
        ).reindex(group_names)
        comparison_summary["n"] = comparison_summary["n"].fillna(0).astype(int)
        y_labels = [f"{name} (n={int(comparison_summary.loc[name, 'n']):,})" for name in group_names]
        comparison_fig = go.Figure()
        colors = ["#5674c0", "#38b2ac"]
        for index, (name, y_label) in enumerate(zip(group_names, y_labels)):
            average = comparison_summary.loc[name, "average_score"]
            count = int(comparison_summary.loc[name, "n"])
            if pd.notna(average):
                comparison_fig.add_trace(go.Scatter(
                    x=[0, average], y=[y_label, y_label], mode="lines",
                    line={"color": "#CBD5E0", "width": 3}, hoverinfo="skip", showlegend=False,
                ))
                comparison_fig.add_trace(go.Scatter(
                    x=[average], y=[y_label], mode="markers+text", text=[f"{average:.1f}"],
                    textposition="middle right", cliponaxis=False,
                    marker={"size": 18, "color": colors[index]},
                    customdata=[[count]],
                    hovertemplate="%{y}<br>Average signal: %{x:.1f}/100<br>Comments (n): %{customdata[0]:,}<extra></extra>",
                    showlegend=False,
                ))
        comparison_fig.update_layout(
            title="Average Burnout Signal by Language Match",
            xaxis={"title": "Average burnout signal score (/100)", "range": [0, 100], "rangemode": "tozero"},
            yaxis={"title": "", "categoryorder": "array", "categoryarray": y_labels, "autorange": "reversed"},
        )
        chart(comparison_fig)

    st.markdown("### 3. Most Frequently Matched Burnout-Related Terms")
    st.caption("Frequently detected expressions related to exhaustion, online overload, withdrawal, and digital fatigue.")
    if df.empty:
        chart(empty_figure("Most Frequently Matched Burnout-Related Terms", "No comments match the current filters."))
    else:
        term_counts = (
            df.matched_terms.fillna("").astype(str).str.split(",").explode().str.strip()
        )
        term_counts = term_counts[term_counts.ne("")].value_counts().head(15)
        if term_counts.empty:
            chart(empty_figure("Most Frequently Matched Burnout-Related Terms", "No matched burnout-related terms in this selection."))
        else:
            term_data = term_counts.rename_axis("Term").reset_index(name="Occurrences")
            term_fig = px.treemap(
                term_data, path=["Term"], values="Occurrences",
                color="Occurrences", color_continuous_scale="Blues",
                title="Most Frequently Matched Burnout-Related Terms",
            )
            term_fig.update_traces(
                textinfo="label+value",
                hovertemplate="<b>%{label}</b><br>Occurrences: %{value:,}<extra></extra>",
            )
            chart(term_fig)

    st.markdown("### Filtered Comments")
    search = st.text_input("Find text in comments")
    rows = df[df.text.fillna('').str.contains(search, case=False, regex=False)] if search else df
    fields = [c for c in ["timestamp", "text", "video_title", "comment_type", "matched_terms", "sentiment_score", "burnout_signal_score", "signal_band", "manual_label"] if c in rows]
    st.dataframe(rows.sort_values("burnout_signal_score", ascending=False)[fields].head(500), width="stretch", hide_index=True)
    st.caption(f"Showing up to 500 highest-scoring comments of {len(rows):,} text matches. Export includes all matching rows.")
    st.download_button("Download filtered analyzed comments", rows.to_csv(index=False).encode(), "youtube_burnout_filtered.csv", "text/csv")

    with st.expander("Optional statistical metric: Spearman correlation"):
        corr_data = df[["sentiment_score", "burnout_signal_score"]].dropna()
        if (len(corr_data) >= 3 and corr_data.sentiment_score.nunique() > 1
                and corr_data.burnout_signal_score.nunique() > 1):
            # Two one-dimensional inputs produce a scalar coefficient and p-value.
            rho, p_value = cast(
                tuple[float, float],
                spearmanr(corr_data.sentiment_score, corr_data.burnout_signal_score),
            )
            magnitude = abs(rho)
            if magnitude < .1:
                strength = "negligible"
            elif magnitude < .3:
                strength = "weak"
            elif magnitude < .5:
                strength = "moderate"
            else:
                strength = "strong"
            if magnitude < .1:
                interpretation = "The association is negligible, with no clear direction, in this filtered sample."
            else:
                direction = "positive" if rho > 0 else "negative"
                interpretation = f"There is a {strength} {direction} monotonic association in this filtered sample."
            metric_a, metric_b = st.columns(2)
            metric_a.metric("Spearman rank correlation (?)", f"{rho:+.3f}")
            metric_b.metric("p-value", "< 0.001" if p_value < .001 else f"{p_value:.3g}")
            st.caption(f"{interpretation} Based on {len(corr_data):,} filtered comments. Descriptive only: sentiment is part of the composite burnout signal score, so this is not independent validation.")
        elif df.empty:
            st.info("Spearman correlation is unavailable because no comments match the current filters.")
        else:
            st.info("Spearman correlation needs at least three paired observations and variation in both variables.")


elif page == "Videos":
    st.header("Videos — Discussion Context")
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
    st.header("Timeline — Changes in the Collected Discussion")
    st.subheader("How activity and burnout-related language vary over time")
    st.caption(
        "These charts describe activity and burnout-related language in the collected YouTube sample. "
        "They do not measure burnout at the individual level."
    )

    frequency = st.radio(
        "Time interval",
        ["Monthly", "Weekly"],
        horizontal=True,
    )

    trend = trend_table(df, "MS" if frequency == "Monthly" else "W-MON")

    # 1. Observed comment volume — line chart
    st.markdown("### 1. Observed Comment Volume")
    st.caption(
        "Number of comments collected in each time period. Changes can reflect collection coverage "
        "or differences in discussion activity."
    )

    volume_fig = px.line(
        trend,
        x="timestamp",
        y="comments",
        markers=True,
        labels={
            "timestamp": "Period (UTC)",
            "comments": "Comments",
        },
        title="Observed Comment Volume Over Time",
    )
    volume_fig.update_traces(
        hovertemplate="%{x|%b %Y}<br>Comments: %{y:,}<extra></extra>"
    )
    chart(volume_fig)

    # 2. Language-match rate — line + markers
    st.markdown("### 2. Burnout-Language Match Rate Over Time")
    st.caption(
        "Share of collected comments containing at least one detected burnout-related language match. "
        "This shows variation in the collected sample, not a rise or fall in burnout itself."
    )

    rate_fig = px.line(
        trend,
        x="timestamp",
        y="match_rate",
        markers=True,
        labels={
            "timestamp": "Period (UTC)",
            "match_rate": "Language match rate (%)",
        },
        title="Burnout-Language Match Rate Over Time",
    )
    rate_fig.update_traces(
        hovertemplate="%{x|%b %Y}<br>Match rate: %{y:.1f}%<extra></extra>"
    )
    rate_fig.update_yaxes(rangemode="tozero")
    chart(rate_fig)

    # 3. Comment activity by day and hour — heatmap
    st.markdown("### 3. Comment Activity by Day & Hour")
    st.caption(
        "Number of collected comments by weekday and UTC posting hour. "
        "UTC timestamps do not reveal commenters' local time zones."
    )

    heat = pd.crosstab(
        df.timestamp.dt.dayofweek,
        df.timestamp.dt.hour,
    ).reindex(
        index=range(7),
        columns=range(24),
        fill_value=0,
    )
    heat.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    heat_fig = px.imshow(
        heat,
        aspect="auto",
        color_continuous_scale="Teal",
        labels={
            "x": "Hour (UTC)",
            "y": "Day",
            "color": "Comments",
        },
        title="When Were the Comments Posted?",
    )
    chart(heat_fig)

    st.caption(
        "Time patterns describe when comments were observed in this dataset; they should not be interpreted "
        "as evidence of local late-night behaviour or individual wellbeing."
    )
