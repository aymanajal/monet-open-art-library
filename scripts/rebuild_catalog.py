"""Rebuild the public inventory and indexes from the canonical JSON catalog."""
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text())
def save(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
rows=load('catalog/artworks.json')
work_index=defaultdict(list)
labels=load('.cache/collection_labels.json') if (ROOT/'.cache/collection_labels.json').exists() else {}
for e in rows:
    for q in e.get('wikidata_ids',[]):work_index[q].append(e['id'])
for e in rows:
    if e.get('source_metadata',{}).get('harvest')!='20261020-global':continue
    meta=e['source_metadata']
    # These four pages explicitly declare Creator:Claude Monet in their
    # Art photo template, but omit a photographer and API Artist is blank.
    # This restores only the artwork attribution, never invents a photographer.
    if e['id'] in {'Commons_179011799','Commons_79292612','Commons_79326290','Commons_79433157'} and not meta.get('creator'):
        meta['creator']='Claude Monet (artwork; photographer not specified)'
        meta['creator_evidence']='Commons file wikitext explicitly contains Creator:Claude Monet; checked 2026-10-20'
        meta['photographer_not_specified']=True
        e['notes']+='; 源页明确作品作者为莫奈，但未指定摄影者，署名与摄影许可需复核'
    qids=[q for q in meta.get('collection_ids',[]) if q.startswith('Q') and q[1:].isdigit()]
    meta['collection_ids']=qids
    meta['collection_names']=[labels.get(q,q) for q in qids]
    meta['collection_caveat']='Wikidata collection statements may include historical owners; not a verified present museum location.'
    e['museum']='Index collections (not verified current location): '+('; '.join(meta['collection_names']) or 'unspecified')
    shared=sorted({other for q in e.get('wikidata_ids',[]) for other in work_index[q] if other!=e['id']})
    if shared:e['same_work_candidates']=shared
    if e['status']=='approved':
        e['status']='review_version' if shared else 'candidate_ready'
        e['notes']=('同一Wikidata条目还关联其他图像版本，需核对作品身份' if shared else '来源许可与图像文件通过自动初筛；题名、馆藏和作品身份未逐件人工核验')
    if e['status'].startswith('review_') and '/artworks/' in e['file']:
        old=ROOT/e['file'];relative=e['file'].replace('/artworks/','/review/')
        new=ROOT/relative;new.parent.mkdir(parents=True,exist_ok=True)
        old.replace(new);e['file']=relative
save('catalog/artworks.json',rows)
fields=['id','title','date','museum','rights','status','notes','file','sha256','width','height','bytes','source_url','groups','wikidata_ids','source_metadata']
with (ROOT/'catalog/artworks.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
    for e in rows:writer.writerow({k:json.dumps(e[k],ensure_ascii=False) if isinstance(e.get(k),(dict,list)) else e.get(k,'') for k in fields})
previews=sorted(p for p in (ROOT/'previews').rglob('*') if p.is_file())
files=[ROOT/e['file'] for e in rows]+previews
(ROOT/'catalog/files.sha256').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}\n' for p in sorted(files)))
inventory=load('catalog/inventory.json')
inventory.update(asset_records=len(rows),unique_artwork_image_files=len({e['sha256'] for e in rows}),previews=len(previews),total_unique_image_files=len(files),bytes=sum(p.stat().st_size for p in files),status_counts=dict(Counter(e['status'] for e in rows)),source_counts=dict(Counter(e['id'].split('_')[0] for e in rows)),wikidata_work_ids=len(work_index))
save('catalog/inventory.json',inventory)
def cell(s):return str(s).replace('|',' / ').replace('\n',' ')
lines=['# 全部图片目录','','approved为原批已核验记录；candidate_ready仅通过自动初筛。review条目保留完整文件和来源，暂不自动排期。图片版本数不等于不同作品数。','','| ID | 作品 | 状态 | 图片 | 来源 |','|---|---|---|---|---|']
for e in rows:lines.append(f"| {e['id']} | {cell(e['title'])} | {e['status']} | [查看](../{e['file']}) | [来源]({e['source_url']}) |")
(ROOT/'catalog/全部图片目录.md').write_text('\n'.join(lines)+'\n')
credit=['# CC BY / BY-SA 图像署名与许可','','下列图像仅作带条件授权归档，未自动进入发布计划。作品作者与摄影者可能不是同一人；使用时逐件查看来源页，保留署名、许可链接，并遵守相同方式共享等条件。工作图仅缩放，未作内容修改。','','| 文件 | 来源提供的作者/摄影者 | 指定署名 / Credit | 许可 | 来源 |','|---|---|---|---|---|']
for e in rows:
    if e['status']!='review_license':continue
    m=e['source_metadata'];credit.append(f"| [{e['id']}](../{e['file']}) | {cell(m.get('creator',''))} | {cell(m.get('attribution') or m.get('credit') or m.get('creator',''))} | [{cell(e['rights'])}]({m['license_url']}) | [页面]({e['source_url']}) |")
(ROOT/'docs/CC图像署名.md').write_text('\n'.join(credit)+'\n')
candidate_file=ROOT/'catalog/research/global_candidates_20261020.json'
if candidate_file.exists():
    candidates=load('catalog/research/global_candidates_20261020.json')
    counts=Counter(c.get('status') for c in candidates)
    new=[e for e in rows if e.get('source_metadata',{}).get('harvest')=='20261020-global']
    result=load('catalog/research/global_harvest_20261020.json')
    result.update(rights_eligible=counts['eligible'],rights_eligible_conditional=counts['eligible_conditional'],rights_not_cleared=counts['rights_not_cleared'],downloaded_new_files=len(new),new_status_counts=dict(Counter(e['status'] for e in new)),catalog_records=len(rows))
    save('catalog/research/global_harvest_20261020.json',result)
    outcome_path=ROOT/'catalog/research/global_download_outcomes_20261020.json'
    if outcome_path.exists():
        outcomes=load('catalog/research/global_download_outcomes_20261020.json');byid={e['id']:e for e in rows}
        for o in outcomes:
            e=byid.get(o.get('matched_id') or o['id'])
            if e:o['file']=e['file']
        save('catalog/research/global_download_outcomes_20261020.json',outcomes)
    report=f'''# 2026-10-20 公开资源扩充

## 本轮可复核范围

从 Wikidata 查询创作者为 Claude Monet（Q296）且存在图像（P18）的条目，完整处理当次返回的 {result['candidate_works']} 个作品条目、{result['candidate_image_links']} 个图像链接。图像从 Wikimedia Commons 下载，并逐文件保存来源页、许可、原图链接与哈希。

- 公有领域 / CC0 候选图像：{counts['eligible']}。
- CC BY / CC BY-SA 带条件授权候选图像：{counts['eligible_conditional']}。
- 本轮新增本地图像文件：{len(new)}（不是不同作品数量）。
- 主库现有图像版本：{len(rows)}。
- 下载失败：{len(result['failed_downloads'])}；未解析的元数据链接：{len(result['unresolved_metadata'])}。详情见[机器报告](../catalog/research/global_harvest_20261020.json)。

下载的是平台提供的 1280px 工作图，或尺寸更小的源文件，不等于已归档全部最高分辨率原图。原图 URL 保存在 `source_metadata.original_url`。重复链接、相同 SHA-256 文件不重复占用空间；不同裁切、拍摄、色调版本予以保留。

## 使用边界

1. 这是本次索引快照的覆盖范围，不是全球莫奈作品全集，也不代表所有博物馆公开图像已被穷尽。
2. Wikidata 的创作者和图像关联属于发现线索，不是作品鉴定。自动初筛通过为 `candidate_ready`；作品题名、当前馆藏和历史归属尚需逐件人工核对。
3. 索引中的 collection 可能包括历史收藏者，不能直接当作当前所在博物馆。没有可解析收藏实体时保留 unspecified，不猜测。
4. pHash 只筛选近似候选，不能认定作品相同或不同。关联同一 Wikidata 条目的其他版本另列 `same_work_candidates`，后续排期必须连同历史分组检查。
5. CC BY / BY-SA 图片放入 `review_license`，详见[逐图署名](CC图像署名.md)。不得在不满足署名、许可链接或相同方式共享要求时直接发布。
6. 本轮未改动历史发布计划，未将新增素材自动提交到小红书或抖音。

## 来源与复现

- [Wikidata Query Service](https://query.wikidata.org/)
- [Wikidata 结构化数据许可](https://www.wikidata.org/wiki/Wikidata:Licensing)
- [Commons 对外使用说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)
- [逐文件候选清单](../catalog/research/global_candidates_20261020.json)

`scripts/harvest_public_monet.py` 保存查询和下载逻辑（需要 Pillow、NumPy、curl）；`scripts/rebuild_catalog.py` 重建衍生台账；`scripts/verify_library.py` 校验文件与排期引用。下载缓存被 Git 忽略。
'''
    (ROOT/'docs/20261020资源扩充.md').write_text(report)
print(json.dumps(inventory,ensure_ascii=False,indent=2))
