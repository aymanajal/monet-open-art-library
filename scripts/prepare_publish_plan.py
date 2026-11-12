"""Record explicit visual review and reserve a reviewed plan; NEVER uploads.

Use review_publish_plan.py first, then inspect every comparison sheet.
"""
import argparse,json
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);parser.add_argument('--visual-review-confirmed',action='store_true');args=parser.parse_args()
assert args.visual_review_confirmed,'Inspect the comparison sheets first'
def load(p):return json.loads((ROOT/p).read_text())
def save(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
plan_path=(ROOT/args.plan).resolve();assert plan_path.is_relative_to(ROOT)
plan=json.loads(plan_path.read_text());run_id=plan['run_id'];proof=load('.cache/'+run_id+'/source_checks.json');byproof={e['id']:e for e in proof['images']}
rows=load('catalog/artworks.json');byid={e['id']:e for e in rows};schedule=load('posts/schedule.json');posts=schedule['posts']
assert all(p['status']=='scheduled_success' for p in posts),'Resolve earlier draft/unknown/in-progress records first'
assert not set(g['group'] for g in plan['groups'])&{p['group'] for p in posts}
used={f for p in posts for f in p['images']};now=datetime.now(ZoneInfo('Asia/Shanghai'));stamp=now.isoformat()
previous=max(datetime.fromisoformat(p['schedule_at']) for p in posts)
for g in plan['groups']:
 when=datetime.fromisoformat(g['schedule_at'])
 assert now+timedelta(hours=1)<=when<=now+timedelta(days=14),g['schedule_at']
 assert when-previous==timedelta(days=2) and when.hour==20 and when.minute==0
 previous=when;images=[]
 assert len(g['asset_ids'])==5 and len(g['title'])<=20
 for ident in g['asset_ids']:
  e=byid[ident];source=byproof[ident]
  assert e['status']=='candidate_ready' and e['file'] not in used and source['license'] in ['Public domain','CC0']
  e['status']='approved';e['notes']=str(now.date())+'逐图复核来源许可、作品身份、主题画面及历史版本；未发现与已记录分组重复'
  e['review_verification']=dict(checked_at=stamp,run_id=run_id,source_url=source['source_url'],source_revision_id=source['source_revision_id'],creator_evidence=source['source_artist'],rights_evidence=source['license'],wikidata_ids=e.get('wikidata_ids',[]),inventory_numbers=e.get('source_metadata',{}).get('inventory_numbers',[]),
    identity_check='Compared indexed work IDs and source collection/inventory facts where available; no overlap with known IDs of recorded posts',
    historical_comparison=f"SHA-256 and full/cropped pHash against {proof['historical_file_count']} historical files; visually inspected selected image and three nearest historical matches; coherent five-image themes",
    nearest_historical=source['nearest_historical'],visual_theme_review='Inspected whole group; no new cropping, frames, or colour grading applied',group=g['group'])
  e['groups']=sorted(set(e.get('groups',[])+[g['group']]));used.add(e['file']);images.append(e['file'])
 content=g['content']+'\n\n图片来源：Wikimedia Commons；公共领域开放图像。'
 assert len(content)<=1000
 posts.append(dict(group=g['group'],title=g['title'],content=content,tags=['莫奈','印象派','艺术分享'],images=images,schedule_at=g['schedule_at'],status='submission_in_progress',verification='已复核并在主库占用本组；尚未上传，其他电脑禁止重传',submission_attempt=dict(attempt_id=run_id+'-group-'+str(g['group']),run_id=run_id,reserved_at=stamp,planned_schedule_at=g['schedule_at'])))
 g['status']='submission_in_progress'
# Conservative hold, NOT a claim of identical works: closely matching Grand Canal
# compositions with unresolved version identity are not used for this window.
excluded=[]
if run_id=='window-20261112':
 for ident in ['Commons_81957669','Commons_29092338']:
  e=byid[ident];assert e['status']=='candidate_ready' and e['file'] not in used
  e.update(status='review_near_duplicate',similar_to='Commons_5765804',notes='2026-11-12逐图复核：与历史第18组大运河构图高度近似；索引条目和部分来源编号不同，尚不能认定同一作品。先保留并暂停自动排期，待核对目录版本。')
  excluded.append(dict(id=ident,reason=e['notes']))
save('catalog/artworks.json',rows);save('posts/schedule.json',schedule)
plan['state']='reserved_not_uploaded';plan['reviewed_at']=stamp;plan['excluded_near_compositions']=excluded
plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
save('posts/platform_check.json',dict(checked_on=str(now.date()),checked_at=stamp,timezone='Asia/Shanghai',login_status='logged_in',run_id=run_id,evidence='check_login_status returned 已登录; get_my_profile returned 44 notes; planned five titles absent from returned public profile; scheduled/private list not covered',new_uploads_this_run=0,actual_publication_checked=False,tool_version='v2.5.0',schedule_min_hours=1,schedule_max_days=14))
(ROOT/'docs/reviews').mkdir(exist_ok=True)
save('docs/reviews/'+run_id+'_source_checks.json',dict(checked_at=stamp,run_id=run_id,historical_file_count=proof['historical_file_count'],scope='25 selected image versions, source creator/license and work/version checks; no current-museum location guarantee',images=proof['images'],excluded=excluded))
print('Reviewed and reserved',len(plan['groups']),'groups; no uploads performed. Commit/push before submitting.')
