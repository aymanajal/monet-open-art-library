"""Build a portable, evidence-aware publishing ledger; never uploads anything."""
import argparse,json,re
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Asia/Shanghai')
THEMES=[
 ('睡莲与池塘',r'water lil|nymph|nénuphar|nenuphar|seerosen|睡莲'),
 ('麦垛与田野',r'haystack|grainstack|stack.*wheat|meule|麦垛'),
 ('伦敦与城市',r'waterloo|charing|parliament|london|londres|rouen|cath[eé]dr|saint.lazare'),
 ('雪景与冬日',r'snow|winter|neige|hiver|frost|雪'),
 ('海岸与海风',r'cliff|falaise|[ée]tretat|pourville|seashore|beach|seascape|antibes|bordighera|belle.[îi]le|sea at|sea coast'),
 ('花园与花卉',r'garden|jardin|flower|fleur|rose|rosier|iris|chrysanth|wisteria|glycine'),
 ('人物与静物',r'portrait|caricature|still.life|nature.morte|camille|woman|women|girl|boy|déjeuner|dejeuner|flesh|apples'),
 ('河流与桥影',r'seine|river|bridge|pont|argenteuil|v[eé]theuil|boat|bateau|regatta|zaan|canal|venice|venise'),
]
def theme(e):return next((t for t,p in THEMES if re.search(p,e['title'],re.I)),'其他风景待细分')
def load(p):return json.loads((ROOT/p).read_text())
def save(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def safe(s):return str(s).replace('|',' / ').replace('\n',' ')

def build(as_of=None):
 now=as_of or datetime.now(TZ)
 rows=load('catalog/artworks.json');schedule=load('posts/schedule.json');posts=schedule['posts']
 byfile={e['file']:e for e in rows};used=defaultdict(list)
 for p in posts:
  for f in p['images']:used[f].append(p)
 history=[]
 for p in posts:
  due=datetime.fromisoformat(p['schedule_at'])
  status=p['status']
  if p.get('publication_verified_at'):state='已核验发布'
  elif status=='scheduled_success':
   state='历史提交成功_到期发布未核验' if due<=now else '已提交_未来排期'
  elif status=='submission_in_progress':state='提交处理中_禁止重传'
  elif status=='submission_unknown':
   state='提交结果待核对_禁止重传'
  else:state='备稿未上传' if due>now else '备稿未上传_原日期已过需改期'
  history.append(dict(group=p['group'],title=p['title'],schedule_at=p['schedule_at'],record_status=status,
                      upload_state=state,publication_verified=bool(p.get('publication_verified_at')),
                      asset_ids=[byfile[f]['id'] for f in p['images']],images=p['images'],verification=p.get('verification','')))
 pool=defaultdict(list)
 for e in rows:
  if e['file'] not in used and e['status'] in ['approved','candidate_ready']:
   pool[theme(e)].append(e)
 # These dates are capacity placeholders, NEVER actual platform reservations.
 anchor=max(datetime.fromisoformat(p['schedule_at']) for p in posts)+timedelta(days=2)
 minimum=now.replace(hour=20,minute=0,second=0,microsecond=0)+timedelta(days=1)
 while anchor<minimum:anchor+=timedelta(days=2)
 groups=[];remainders=[];slot=anchor
 for t,es in pool.items():
  es.sort(key=lambda e:(e.get('date',''),e['id']))
  for start in range(0,len(es),5):
   batch=es[start:start+5]
   if len(batch)<5:
    remainders.extend(e['id'] for e in batch);continue
   ident=f"P{len(groups)+1:03d}"
   groups.append(dict(id=ident,theme=t,provisional_at=slot.isoformat(),status='blocked_review_not_uploaded',
      title_suggestion='莫奈｜'+t,content=None,asset_ids=[e['id'] for e in batch],images=[e['file'] for e in batch],
      needs=['逐图核对作者、作品身份和来源','与全部历史组核对馆藏编号、裁切及不同版本','人工确认五张主题与视觉风格一致','完成短文案并复核署名','确认未在平台手动上传','重新计算实际可提交日期']))
   slot+=timedelta(days=2)
 assets=[]
 pending_map={ident:g['id'] for g in groups for ident in g['asset_ids']}
 for e in rows:
  links=used.get(e['file'],[])
  if links:
   states=[next(h['upload_state'] for h in history if h['group']==p['group']) for p in links]
   state='；'.join(states)
  elif e['id'] in pending_map:state='无主库上传记录_预分组待复核'
  elif e['id'] in remainders:state='无主库上传记录_主题不足五张待补组'
  else:state='无主库上传记录_素材待复核'
  assets.append(dict(id=e['id'],title=e['title'],file=e['file'],sha256=e['sha256'],rights=e['rights'],
    review_status=e['status'],source_url=e['source_url'],upload_state=state,
    recorded_groups=[p['group'] for p in links],provisional_group=pending_map.get(e['id']),
    publication_verified=any(bool(p.get('publication_verified_at')) for p in links)))
 summary=dict(asset_files=len(rows),recorded_submitted_groups=sum(h['record_status']=='scheduled_success' for h in history),
   publication_verified_groups=sum(h['publication_verified'] for h in history),
   prepared_not_submitted_groups=sum(h['record_status']=='prepared_outside_window' for h in history),
   submission_in_progress_groups=sum(h['record_status']=='submission_in_progress' for h in history),
   submission_unknown_groups=sum(h['record_status']=='submission_unknown' for h in history),
   historical_due_unverified_groups=sum(h['upload_state']=='历史提交成功_到期发布未核验' for h in history),
   future_submitted_groups=sum(h['upload_state']=='已提交_未来排期' for h in history),
   asset_files_with_submission_record=len({f for p in posts if p['status']=='scheduled_success' for f in p['images']}),
   asset_files_without_submission_record=len(rows)-len({f for p in posts if p['status']=='scheduled_success' for f in p['images']}),
   provisional_full_groups=len(groups),provisional_group_images=sum(len(g['images']) for g in groups),
   pool_leftovers=len(remainders),review_or_license_hold_images=sum(not e['recorded_groups'] and not e['provisional_group'] and e['id'] not in remainders for e in assets),
   provisional_first=groups[0]['provisional_at'] if groups else None,provisional_last=groups[-1]['provisional_at'] if groups else None)
 platform_check=load('posts/platform_check.json')
 data=dict(schema_version=1,timezone='Asia/Shanghai',as_of=now.isoformat(),
   caveat='上传状态仅基于主库记录；未联网核验实际发布，也不能排除其他客户端手动上传。预分组日期仅为容量占位，不是实际排期承诺。',
   platform_check=platform_check,
   summary=summary,recorded_posts=history,provisional_batches=groups,partial_pool_ids=remainders,assets=assets)
 save('posts/publication_ledger.json',data)
 lines=['# 发布总表 · 换电脑从这里继续','',f'清单核对时间：{now.isoformat()}（北京时间）。',
  '', '**重要：历史“排期成功”不等于已核验发布；无主库上传记录不等于能确定从未手动发过。P开头仅为预分组，不能直接上传。**','',
  '## 状态汇总','',f"- 主库素材：{summary['asset_files']}张图像版本。",
  f"- 曾提交成功：{summary['recorded_submitted_groups']}组 / {summary['asset_files_with_submission_record']}张；其中{summary['historical_due_unverified_groups']}组已到期但未核验发布、{summary['future_submitted_groups']}组为未来排期。",
  f"- 备稿未上传：{summary['prepared_not_submitted_groups']}组。最近平台检查（{platform_check['checked_on']}）登录状态：{platform_check['login_status']}；该次新增上传{platform_check['new_uploads_this_run']}组。",
  f"- 已占用待提交/提交中：{summary['submission_in_progress_groups']}组；结果不明：{summary['submission_unknown_groups']}组。两类均禁止在其他电脑重传。",
  f"- 无提交成功记录：{summary['asset_files_without_submission_record']}张（含备稿、候选和复核区）。",
  f"- 按主题预分：{len(groups)}个五图组 / {summary['provisional_group_images']}张；另{len(remainders)}张待补同主题成组，{summary['review_or_license_hold_images']}张暂缓复核。",
  f"- 若预分组全部通过核验且连续每两天20:00发一组，占位可延续至 **{summary['provisional_last']}**；这不是平台已经排好的日期。",'',
  '[换电脑操作说明](换电脑继续.md) · [逐图上传状态](逐图上传状态.md) · [机器可读总账](publication_ledger.json)','',
  '## 已有分组：提交记录与备稿','', '| 组 | 标题 | 北京时间 | 上传记录 | 五张素材 |','|---|---|---|---|---|']
 for h in history:
  imgs='、'.join(f'[{i}](../{f})' for i,f in zip(h['asset_ids'],h['images']))
  lines.append(f"| {h['group']} | {safe(h['title'])} | {h['schedule_at']} | {h['upload_state']} | {imgs} |")
 lines+=['','## 全部候选预分组：未上传、必须先复核','','按来源题名粗分主题，尚未做逐组视觉审美核验；日期为连续占位。不能直接把846张自动初筛素材当作846件已核验的不同作品。','','| 预分组 | 主题 | 暂定时间 | 状态 | 五张素材 |','|---|---|---|---|---|']
 for g in groups:
  imgs='、'.join(f'[{i}](../{f})' for i,f in zip(g['asset_ids'],g['images']))
  lines.append(f"| {g['id']} | {g['theme']} | {g['provisional_at']} | 待复核／未上传／未写文案 | {imgs} |")
 lines+=['','## 尚未成组的同主题余图','', '、'.join(remainders) or '无','', '其他待复核、近似版本、低清和条件许可图片均已列入逐图状态表，不会丢失，也不自动排期。']
 (ROOT/'posts/发布总表.md').write_text('\n'.join(lines)+'\n')
 lines=['# 逐图上传状态','','覆盖全部素材；“无主库上传记录”必须与平台手工操作核对后，才能认定未发布。','','| 素材 | 题名 | 素材审核 | 上传状态 | 原分组 | 候选组 | 来源 |','|---|---|---|---|---|---|---|']
 for e in assets:
  lines.append(f"| [{e['id']}](../{e['file']}) | {safe(e['title'])} | {e['review_status']} | {e['upload_state']} | {','.join(map(str,e['recorded_groups']))} | {e['provisional_group'] or ''} | [来源]({e['source_url']}) |")
 (ROOT/'posts/逐图上传状态.md').write_text('\n'.join(lines)+'\n')
 inventory=load('catalog/inventory.json')
 inventory.update(scheduled_groups=summary['recorded_submitted_groups'],prepared_groups=summary['prepared_not_submitted_groups'],submission_in_progress_groups=summary['submission_in_progress_groups'],submission_unknown_groups=summary['submission_unknown_groups'])
 save('catalog/inventory.json',inventory)
 captions=['# 排期与发布文案','','每两天北京时间20:00，每组5张。scheduled_success只表示工具对含定时时间的提交返回成功，不表示已核验到期发布。']
 for p in posts:
  captions.extend(['',f"## 第{p['group']}组：{p['title']}",'',f"计划时间：{p['schedule_at']}；状态：{p['status']}",'',p['content'],''])
  captions.extend(f"- [{byfile[f]['id']}](../{f})" for f in p['images'])
 (ROOT/'posts/文案与排期.md').write_text('\n'.join(captions)+'\n')
 readme=(ROOT/'README.md').read_text()
 latest=max((h['schedule_at'] for h in history if h['record_status']=='scheduled_success'),default='无')
 public_section=f'''## 发布接续与换电脑（{now.date()}核对）

从[发布总表](posts/发布总表.md)继续：[逐图上传状态](posts/逐图上传状态.md) · [换电脑操作说明](posts/换电脑继续.md) · [完整总账](posts/publication_ledger.json)。

- 平台提交成功记录：{summary['recorded_submitted_groups']}组，最近计划时间{latest}；其中{summary['historical_due_unverified_groups']}组已到期但尚未核验实际发布。
- 未提交备稿{summary['prepared_not_submitted_groups']}组；已占用/提交中{summary['submission_in_progress_groups']}组；结果不明{summary['submission_unknown_groups']}组。禁止重传已有成功记录和结果不明的组。
- 最近检查登录状态：{platform_check['login_status']}；本轮新增成功提交{platform_check['new_uploads_this_run']}组。提交不等于到期发布。
- 其他素材预分{len(groups)}个五图候选组（{summary['provisional_group_images']}张）、{len(remainders)}张待补组、{summary['review_or_license_hold_images']}张复核暂缓；日期仅占位至{summary['provisional_last']}，不是已上传排期。
- 新电脑拉取主库并重新登录即可接续；Cookie、二维码、机器绝对路径和原始响应不进入公开仓库。

'''
 readme=re.sub(r'## 发布接续与换电脑.*?(?=## 素材统计)',lambda _:public_section,readme,flags=re.S)
 readme=re.sub(r'\| 文案分组 \|[^\n]*',f"| 文案分组 | {len(posts)}组 / {len(posts)*5}张次 |",readme)
 readme=re.sub(r'\| 平台已接受的排期 \|[^\n]*',f"| 平台提交成功的排期 | {summary['recorded_submitted_groups']}组，至{latest} |",readme)
 readme=re.sub(r'\| 平台提交成功的排期 \|[^\n]*',f"| 平台提交成功的排期 | {summary['recorded_submitted_groups']}组，至{latest} |",readme)
 readme=re.sub(r'\| 仅备稿、尚未提交 \|[^\n]*',f"| 备稿 / 提交中 / 结果不明 | {summary['prepared_not_submitted_groups']} / {summary['submission_in_progress_groups']} / {summary['submission_unknown_groups']}组 |",readme)
 readme=re.sub(r'\| 备稿 / 提交中 / 结果不明 \|[^\n]*',f"| 备稿 / 提交中 / 结果不明 | {summary['prepared_not_submitted_groups']} / {summary['submission_in_progress_groups']} / {summary['submission_unknown_groups']}组 |",readme)
 (ROOT/'README.md').write_text(readme)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
 return data

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--as-of',help='ISO8601 with timezone; optional reproducible snapshot')
 args=parser.parse_args();build(datetime.fromisoformat(args.as_of).astimezone(TZ) if args.as_of else None)
