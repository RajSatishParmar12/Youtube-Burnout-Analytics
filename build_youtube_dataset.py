import argparse
from pathlib import Path
from datetime import datetime,timedelta,timezone
import pandas as pd
from youtube_api import collect_query
from burnout_core import prepare_dataset
QUERIES=["social media burnout","digital burnout","social media fatigue","digital detox","tired of social media","chronically online","creator burnout","notification fatigue"]
def build(api_key,output,days=180,videos_per_query=8,comments_per_video=80):
    after=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat().replace('+00:00','Z'); frames=[]; vframes=[]
    for q in QUERIES:
        print('Collecting:',q); videos,comments=collect_query(api_key,q,videos_per_query,comments_per_video,after)
        if not videos.empty: vframes.append(videos.assign(source_query=q))
        if not comments.empty: frames.append(comments)
    if not frames: raise RuntimeError('No comments were collected')
    raw=pd.concat(frames,ignore_index=True).drop_duplicates(subset=['comment_id']).reset_index(drop=True)
    processed=prepare_dataset(raw); processed['manual_label']=''; processed['manual_label_notes']=''
    out=Path(output); out.parent.mkdir(parents=True,exist_ok=True); processed.to_csv(out,index=False)
    if vframes: pd.concat(vframes,ignore_index=True).drop_duplicates('video_id').to_csv(out.with_name(out.stem+'_videos.csv'),index=False)
    print(f'Saved {len(processed)} unique comments to {out}')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--api-key',required=True); p.add_argument('--output',default='data/youtube_burnout_dataset.csv'); p.add_argument('--days',type=int,default=180); p.add_argument('--videos-per-query',type=int,default=8); p.add_argument('--comments-per-video',type=int,default=80); a=p.parse_args(); build(a.api_key,a.output,a.days,a.videos_per_query,a.comments_per_video)
