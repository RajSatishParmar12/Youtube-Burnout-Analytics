import re, hashlib, numpy as np, pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
A=SentimentIntensityAnalyzer()
TERMS=[
    "burned out", "burnt out", "burnout", "exhausted",
    "drained", "tired of", "overwhelmed", "too much social media",
    "too much screen time", "chronically online", "doomscrolling",
    "information overload", "notification fatigue", "content overload",
    "social media fatigue", "taking a break", "need a break",
    "digital detox", "logging off", "quit social media",
    "leaving social media", "engagement pressure", "posting pressure",
    "keep posting", "creator burnout", "stay relevant", "constant posting"
    ]
PATTERNS=[
    r"\bi('?m| am) (so )?(burned|burnt) out\b",
    r"\bi('?m| am) exhausted\b",
    r"\bi need a break\b",
    r"\bi('?m| am) taking a break\b",
    r"\bi can'?t keep up\b",
    r"\bi('?m| am) tired of (being )?(online|social media)\b",
    r"\bi need (a )?digital detox\b"
    ]
def h(v): 
    return hashlib.sha256(str(v).encode()).hexdigest()[:12] if pd.notna(v) else "anonymous"

def analyze_text(text):
    text="" if pd.isna(text) else str(text); 
    low=text.lower(); m=sorted(set(t for t in TERMS if t in low)); 
    s=A.polarity_scores(text)["compound"]; 
    selfx=int(any(re.search(p,low) for p in PATTERNS))
    return {
        "sentiment_score":s,
        "negative_sentiment":max(0,-s),
        "burnout_keyword_count":len(m),
        "matched_terms":", ".join(m),
        "self_expressed_burnout":selfx,
        "weak_burnout_label":int(selfx or len(m)>0),
        "text_length":len(text),
        "word_count":len(text.split())
        }

def prepare_dataset(df, *, anonymized=False):
    out=df.copy();
    if "text" not in out or "timestamp" not in out: raise ValueError("Dataset requires text and timestamp columns")

    if "user_id" not in out: out["user_id"]="anonymous"

    if not anonymized: out["user_id"]=out["user_id"].map(h)

    metrics=pd.DataFrame([analyze_text(x) for x in out["text"]], columns=list(analyze_text("").keys()))
    out=out.drop(columns=metrics.columns, errors="ignore").reset_index(drop=True)
    out=pd.concat([out,metrics],axis=1)
    out["timestamp"]=pd.to_datetime(out["timestamp"],errors="coerce",utc=True); 
    out=out.dropna(subset=["timestamp"]).sort_values(["user_id","timestamp"])
    out["hour"]=out["timestamp"].dt.hour; 
    out["is_late_night"]=out["hour"].isin([0,1,2,3,4,5]).astype(int)
    out["hours_since_previous_observed_comment"]=out.groupby("user_id")["timestamp"].diff().dt.total_seconds()/3600
    out["days_since_previous_observed_comment"]=out["hours_since_previous_observed_comment"]/24
    counts=[]
    for uid,g in out.groupby("user_id",sort=False):
        g=g.sort_values("timestamp"); ts=g["timestamp"].astype("datetime64[ns, UTC]").astype("int64").to_numpy(); 
        seven=7*24*3600*1_000_000_000
        arr=np.searchsorted(ts,ts,side="right")-np.searchsorted(ts,ts-seven,side="left"); 
        counts += list(pd.Series(arr,index=g.index).items())
    
    roll=pd.Series({i:v for i,v in counts}); 
    out["observed_comments_last_7_days"]=roll.reindex(out.index).fillna(1).astype(int)
    keywords=np.clip(out["burnout_keyword_count"]/3,0,1); 
    burst=np.clip((out["observed_comments_last_7_days"]-3)/7,0,1); 
    gap=np.clip(out["days_since_previous_observed_comment"].fillna(0)/7,0,1)
    score=40*keywords+22*out["negative_sentiment"]+23*out["self_expressed_burnout"]+8*out["is_late_night"]+4*burst+3*gap
    out["burnout_signal_score"]=np.round(np.clip(score,0,100),1); 
    out["signal_band"]=pd.cut(out["burnout_signal_score"],[-1,25,50,75,101],labels=["Low","Emerging","Elevated","High"]).astype(str)
    return out
