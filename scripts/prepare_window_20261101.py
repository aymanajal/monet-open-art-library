"""Record the completed source/visual review and RESERVE six scheduled submissions.

Run only after inspecting comparison sheets from review_window_20261101.py.
Does not call any social platform. The reservation must be committed/pushed first.
"""
import json,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
def save(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert '--visual-review-confirmed' in sys.argv,'Human/agent visual comparison is required'
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
rows=load('catalog/artworks.json');byid={e['id']:e for e in rows}
proof=load('.cache/window_20261101/source_checks.json');byproof={e['id']:e for e in proof}
batches={25:['151580852','54675310','57012077','82342345','31697395'],26:['189209668','7377095','7296068','7298555','2327199'],27:['34059825','36198971','130728880','81086731','21925466'],28:['81751002','139615640','21864201','29920532','8859184']}
texts={
25:('莫奈的冬日｜雪落无声','雪地不是一片白。蓝灰的阴影、微暖的天空和零星的人影，让莫奈的冬日有了安静的层次。五幅雪景，一起慢慢看。'),
26:('莫奈的鲁昂｜一座教堂的光','同一座教堂，在不同光线里呈现不同颜色。把这五幅鲁昂大教堂放在一起看，石墙也像在呼吸。'),
27:('莫奈的海岸｜悬崖与潮声','海浪、礁石和高高的崖岸，在莫奈笔下有不同的蓝与灰。风看不见，却能从水面和笔触里感受到。'),
28:('莫奈的杨树｜风与倒影','树干向上生长，倒影把颜色留在水里。秋色、薄云和微风，让五幅杨树风景有了不同的节奏。')}
schedule=load('posts/schedule.json');posts=schedule['posts']
assert len(posts)==24 and all(p['status']=='prepared_outside_window' for p in posts if p['group'] in [23,24])
used={f for p in posts for f in p['images']}
for group,ids in batches.items():
 images=[]
 for i in ids:
  e=byid['Commons_'+i];p=byproof[e['id']]
  assert e['status']=='candidate_ready' and e['file'] not in used
  assert p['license'] in ['Public domain','CC0']
  e['status']='approved';e['notes']='2026-11-01发布前核对来源声明、作品条目、历史版本和主题画面；未发现与既有组重复'
  e['review_verification']=dict(checked_at=now,source_url=p['source_url'],source_revision_id=p['source_revision_id'],
   creator_evidence=p['source_artist'],rights_evidence=p['license'],wikidata_ids=e.get('wikidata_ids',[]),
   inventory_numbers=e.get('source_metadata',{}).get('inventory_numbers',[]),
   identity_check='Source file title/creator and indexed work identity checked; no shared known work IDs with 120 existing scheduled/prepared files',
   historical_comparison='SHA-256, full/cropped pHash against all 120 existing files; visually compared image and three nearest historical candidates; distinct compositions/source identities',
   nearest_historical=p['nearest_historical'],visual_theme_review='Five images inspected together; coherent subject; no added frames or cropping applied',group=group)
  e['groups']=sorted(set(e.get('groups',[])+[group]));images.append(e['file']);used.add(e['file'])
 title,content=texts[group]
 content+='\n\n图片来源：Wikimedia Commons；'+('公共领域及 CC0 开放图像。' if group==26 else '公共领域开放图像。')
 posts.append(dict(group=group,title=title,content=content,tags=['莫奈','印象派','艺术分享'],images=images,
   schedule_at=f'2026-11-{8+(group-25)*2:02d}T20:00:00+08:00',status='prepared_outside_window',verification='来源与历史版本已核对；尚未提交平台'))
for p in posts:
 if p['group'] not in range(23,29):continue
 assert p['status']=='prepared_outside_window'
 p.update(status='submission_in_progress',verification='已在主库占用本组，等待本次定时提交结果；其他电脑禁止重传')
 p['submission_attempt']=dict(attempt_id=f"window-20261101-group-{p['group']}",reserved_at=now,planned_schedule_at=p['schedule_at'])
save('catalog/artworks.json',rows);save('posts/schedule.json',schedule)
save('posts/platform_check.json',dict(checked_on='2026-11-01',checked_at=now,timezone='Asia/Shanghai',login_status='logged_in',
 evidence='check_login_status returned 已登录; get_my_profile returned 36 notes with no matching six new titles; scheduled/private list not covered',
 new_uploads_this_run=0,actual_publication_checked=False,tool_version='v2.5.0',schedule_min_hours=1,schedule_max_days=14))
(ROOT/'docs/reviews').mkdir(exist_ok=True)
save('docs/reviews/20261101_source_checks.json',dict(checked_at=now,scope='20 selected images for groups25-28, primary Commons file metadata/revision evidence; no current-museum attribution asserted',images=proof))
print('Prepared and reserved groups 23-28; source review recorded for 20 files. Commit/push before uploading.')
