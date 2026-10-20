"""Harvest the complete current Wikidata P170=Q296/P18 candidate set, checking file rights.

Requires Pillow and NumPy for image validation and perceptual screening.
Public-domain / CC0 files and explicitly licensed CC BY / BY-SA files are archived.
Conditional licenses remain in review and must not be automatically scheduled.
Existing files are preserved. The default download is a 1280px working rendition,
or a smaller source image; full-resolution source URLs are retained separately.
"""
import concurrent.futures,hashlib,html,json,re,subprocess,sys,time
from collections import defaultdict,Counter
from pathlib import Path
from urllib.parse import urlencode,urlparse,unquote
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache';CACHE.mkdir(exist_ok=True)
RUN='20261020-global'
HEADERS=['-A','MonetOpenArtLibrary/1.0 (https://github.com/aymanajal/monet-open-art-library)']
def log(*args):print(*args,flush=True)
def get(url,json_data=False,timeout=35,retries=2):
    last=''
    for attempt in range(retries+1):
        p=subprocess.run(['curl','-L','--fail','--silent','--show-error','--connect-timeout','10','--max-time',str(timeout),*HEADERS,url],capture_output=True)
        if p.returncode==0:
            try:return json.loads(p.stdout) if json_data else p.stdout
            except Exception as e:last=str(e)
        else:last=p.stderr.decode(errors='replace')[:220]
        if attempt<retries:
            time.sleep(15*(attempt+1) if '429' in last else 2*(attempt+1))
    raise RuntimeError(last)
def atomic_json(path,data):
    tmp=path.with_suffix('.partial');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def commons(**kw):return get('https://commons.wikimedia.org/w/api.php?'+urlencode(dict(action='query',format='json',**kw)),True)
def clean(value):
    value=re.sub(r'<(?:div|span)[^>]*style=["\'][^"\']*display:\s*none[^"\']*["\'][^>]*>.*?</(?:div|span)>','',value,flags=re.S|re.I)
    return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',value))).strip()
def phash(path,crop=False):
    with Image.open(path) as im:
        im=im.convert('L')
        if crop:im=im.crop((im.width*.04,im.height*.04,im.width*.96,im.height*.96))
        a=np.asarray(im.resize((32,32)),dtype=float)
    d=np.cos(np.pi*(2*np.arange(32)+1)*np.arange(8)[:,None]/64)
    v=(d@a@d.T).flatten()[1:];mid=np.median(v)
    return sum(int(x>mid)<<i for i,x in enumerate(v))

query_path=CACHE/'wikidata_monet_20261020.json'
if not query_path.exists():
    q='SELECT ?item ?image ?collection ?inventory ?date WHERE { ?item wdt:P170 wd:Q296; wdt:P18 ?image. OPTIONAL { ?item wdt:P195 ?collection. } OPTIONAL { ?item wdt:P217 ?inventory. } OPTIONAL { ?item wdt:P571 ?date. } }'
    atomic_json(query_path,get('https://query.wikidata.org/sparql?'+urlencode(dict(query=q,format='json')),True,90))
bindings=json.loads(query_path.read_text())['results']['bindings']
by_title={}
for r in bindings:
    file_title='File:'+unquote(r['image']['value'].split('Special:FilePath/',1)[1]).replace('_',' ')
    value=by_title.setdefault(file_title,dict(works=set(),collections=set(),inventories=set(),dates=set()))
    value['works'].add(r['item']['value'].rsplit('/',1)[1])
    for src,target in [('collection','collections'),('inventory','inventories'),('date','dates')]:
        if src in r:
            source_value=r[src]['value']
            if src=='collection':
                source_value=source_value.rsplit('/',1)[-1]
                if not re.fullmatch(r'Q[0-9]+',source_value):continue
            value[target].add(source_value)
log('DISCOVERED',len({r['item']['value'] for r in bindings}),'works',len(by_title),'images')

# Fetch labels only for collections. Artwork titles are recorded from the corresponding Commons file.
labels_path=CACHE/'collection_labels.json'
labels=json.loads(labels_path.read_text()) if labels_path.exists() else {}
collection_ids=sorted({v for r in by_title.values() for v in r['collections']} - set(labels))
for off in range(0,len(collection_ids),50):
    ids=collection_ids[off:off+50]
    try:
        data=get('https://www.wikidata.org/w/api.php?'+urlencode(dict(action='wbgetentities',format='json',ids='|'.join(ids),props='labels',languages='en|zh|fr')),True)
        for ident,entity in data['entities'].items():
            ls=entity.get('labels',{});labels[ident]=next((ls[l]['value'] for l in ['en','zh','fr'] if l in ls),ident)
        atomic_json(labels_path,labels)
    except Exception as e:log('LABEL WARNING',str(e))
    time.sleep(1)

candidates_path=CACHE/'global_candidates.json'
candidates=json.loads(candidates_path.read_text()) if candidates_path.exists() else {}
titles=sorted(by_title)
for off in range(0,len(titles),20):
    batch=titles[off:off+20]
    if all(t in candidates and candidates[t].get('metadata_version')==2 for t in batch):continue
    try:
        data=commons(prop='imageinfo',titles='|'.join(batch),iiprop='url|extmetadata|size',iiurlwidth='1280')
        normalized={x['to']:x['from'] for x in data.get('query',{}).get('normalized',[])}
        for p in data.get('query',{}).get('pages',{}).values():
            t=p['title'];original=normalized.get(t,t)
            if original not in by_title:
                original=next((x for x in batch if x.replace('_',' ')==t.replace('_',' ')),t)
            if original not in by_title:continue
            if not p.get('imageinfo'):
                candidates[original]=dict(file_title=t,status='unavailable_metadata',wikidata={k:sorted(v) for k,v in by_title[original].items()});continue
            i=p['imageinfo'][0];meta=i.get('extmetadata',{})
            value=lambda k:clean(meta.get(k,{}).get('value',''))
            rights=value('LicenseShortName')
            pd=bool(re.search('public domain|CC0',rights,re.I)) and value('NonFree').lower() not in ['true','1']
            candidates[original]=dict(file_title=t,pageid=p['pageid'],title=value('ObjectName') or t[5:],artist=value('Artist'),license=rights,license_url=value('LicenseUrl'),source_url=i['descriptionurl'],original_url=i['url'],download_url=i.get('thumburl',i['url']),size=i.get('size'),copyrighted=value('Copyrighted'),attribution_required=value('AttributionRequired'),wikidata={k:sorted(v) for k,v in by_title[original].items()},status='eligible' if pd else 'rights_not_cleared')
            c=candidates[original]
            c.update(metadata_version=2,attribution=value('Attribution'),credit=value('Credit'),usage_terms=value('UsageTerms'))
            if value('NonFree').lower() not in ['true','1'] and re.fullmatch(r'CC BY(?:-SA)? [234]\.0|CC BY-SA 2\.5',rights) and re.match(r'https?://creativecommons.org/licenses/by(?:-sa)?/',c['license_url']):
                c['status']='eligible_conditional'
        atomic_json(candidates_path,candidates)
        log('METADATA',min(off+20,len(titles)),'/',len(titles),'eligible',sum(v.get('status')=='eligible' for v in candidates.values()))
    except Exception as e:log('METADATA FAILED',off,str(e))
    time.sleep(1)

if '--metadata-only' in sys.argv:raise SystemExit(0)

entries=json.loads((ROOT/'catalog/artworks.json').read_text());ids={r['id']:r for r in entries}
sha_index={r['sha256']:r for r in entries};visual=[]
for e in entries:
    try:visual.append((phash(ROOT/e['file']),phash(ROOT/e['file'],True),e['id']))
    except Exception as ex:log('EXISTING IMAGE WARNING',e['id'],str(ex))
run_path=CACHE/(RUN+'-state.json')
state=json.loads(run_path.read_text()) if run_path.exists() else {}
new_rows=[]
for value in state.values():
    if value.get('entry'):
        e=value['entry'];new_rows.append(e);sha_index[e['sha256']]=e
        try:visual.append((phash(ROOT/e['file']),phash(ROOT/e['file'],True),e['id']))
        except:pass
public_candidates=[]
for t,c in candidates.items():
    public_candidates.append({k:v for k,v in c.items() if k not in []})
(ROOT/'catalog/research').mkdir(exist_ok=True)
atomic_json(ROOT/'catalog/research/global_candidates_20261020.json',public_candidates)

def downloader(c):
    key='Commons_'+str(c['pageid'])
    urls=[c['download_url']]
    parsed=urlparse(c['original_url'])
    if parsed.netloc=='upload.wikimedia.org' and '/commons/' in parsed.path:
        relative=parsed.path.split('/commons/',1)[1]
        if not relative.startswith('thumb/'):
            urls.append('https://thumb.wikimedia.org/wikipedia/commons/thumb/'+relative+'/1280px-'+relative.rsplit('/',1)[1])
    if c.get('size',0)<4000000:urls.append(c['original_url'])
    last=''
    for url in dict.fromkeys(urls):
        try:
            blob=get(url,False,35,1)
            temp=CACHE/(key+'.download');temp.write_bytes(blob)
            with Image.open(temp) as im:im.load();fmt=im.format;w,h=im.size
            if fmt not in ['JPEG','PNG','WEBP','TIFF','GIF']:raise ValueError('unsupported image format')
            if min(w,h)<1:raise ValueError('invalid image dimensions')
            return dict(candidate=c,key=key,temp=str(temp),format=fmt,width=w,height=h,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob),download_url=url)
        except Exception as e:last=str(e).replace(str(ROOT),'.')
    return dict(candidate=c,key=key,error=last)

work=[]
for c in candidates.values():
    if c.get('status') not in ['eligible','eligible_conditional']:continue
    key='Commons_'+str(c['pageid'])
    if key in ids:
        ids[key]['wikidata_ids']=sorted(set(ids[key].get('wikidata_ids',[]))|set(c['wikidata']['works']))
        if not state.get(key,{}).get('entry'):state[key]=dict(status='already_in_library')
        continue
    if state.get(key,{}).get('status') in ['downloaded','identical_existing']:continue
    work.append(c)
log('DOWNLOAD QUEUE',len(work),'new files; existing catalog',len(entries))
def checkpoint():atomic_json(run_path,state)
completed=0
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    for result in executor.map(downloader,work):
        key=result['key'];c=result['candidate'];completed+=1
        if 'error' in result:
            state[key]=dict(status='download_failed',error=result['error'],source_url=c['source_url']);log('DOWNLOAD FAILED',key,result['error'][:100]);checkpoint();continue
        digest=result['sha256'];temp=Path(result['temp'])
        if digest in sha_index:
            match=sha_index[digest];match['wikidata_ids']=sorted(set(match.get('wikidata_ids',[]))|set(c['wikidata']['works']))
            state[key]=dict(status='identical_existing',matched_id=match['id'],sha256=digest);checkpoint();continue
        h1,h2=phash(temp),phash(temp,True)
        best=min(((min((h1^a).bit_count(),(h2^b).bit_count()),ident) for a,b,ident in visual),default=(63,None))
        artist=c['artist'];notes=[];status='approved'
        if best[0]<=8:
            status='review_near_duplicate';notes.append(f"视觉近似{best[1]}，距离{best[0]}；不能据此认定同一作品")
        if not re.search(r'Claude\s+Monet',artist,re.I) or re.search('attributed|after |copy|d’après|d.après|follower',artist,re.I):
            status='review_metadata';notes.append('创作者说明需人工复核；Wikidata候选署名Q296')
        if re.search('detail|frame|DSC|IMG_|infrared|x-ray|radiograph',c['file_title'],re.I):
            status='review_version';notes.append('文件名提示局部、带框或其他拍摄版本')
        if min(result['width'],result['height'])<400:
            status='review_low_resolution';notes.append('短边低于400像素')
        if c['status']=='eligible_conditional':
            status='review_license';notes.append('CC BY/BY-SA附带署名与许可义务；未核对发布方案前禁止自动排期')
        category='artworks' if status=='approved' else 'review'
        ext={'JPEG':'jpg','PNG':'png','WEBP':'webp','TIFF':'tif','GIF':'gif'}[result['format']]
        rel=f'assets/{category}/commons/{key}.{ext}'
        dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True);temp.replace(dest)
        wd=c['wikidata'];e=dict(id=key,title=c['title'],date='; '.join(wd['dates']),museum='; '.join(labels.get(q,q) for q in wd['collections']) or 'Collection not specified in source index',source_url=c['source_url'],rights=c['license'],status=status,notes='; '.join(notes),file=rel,sha256=digest,width=result['width'],height=result['height'],bytes=result['bytes'],wikidata_ids=wd['works'],groups=[],source_metadata=dict(creator=artist,inventory_numbers=wd['inventories'],collection_ids=wd['collections'],original_url=c['original_url'],download_url=result['download_url'],attribution_required=c['attribution_required'],license_url=c['license_url'],harvest=RUN))
        e['source_metadata'].update(attribution=c.get('attribution',''),credit=c.get('credit',''),usage_terms=c.get('usage_terms',''),rendition='1280px working rendition, or smaller source')
        if best[0]<=8:e['similar_to']=best[1]
        new_rows.append(e);visual.append((h1,h2,key));sha_index[digest]=e
        state[key]=dict(status='downloaded',entry=e);checkpoint()
        if completed%10==0:log('PROGRESS',completed,'/',len(work),'downloaded',len(new_rows),'failed',sum(v.get('status')=='download_failed' for v in state.values()))

existing_ids={e['id'] for e in entries}
entries.extend(r for r in new_rows if r['id'] not in existing_ids)
atomic_json(ROOT/'catalog/artworks.json',entries)
checkpoint()
summary=dict(run=RUN,candidate_works=len({r['item']['value'] for r in bindings}),candidate_image_links=len(by_title),metadata_resolved=len(candidates),rights_eligible=sum(v.get('status')=='eligible' for v in candidates.values()),rights_not_cleared=sum(v.get('status')=='rights_not_cleared' for v in candidates.values()),downloaded_new_files=len(new_rows),state_counts=dict(Counter(v['status'] for v in state.values())),new_status_counts=dict(Counter(r['status'] for r in new_rows)),catalog_records=len(entries),unresolved_metadata=[t for t in by_title if t not in candidates],failed_downloads=[dict(id=k,**v) for k,v in state.items() if v.get('status')=='download_failed'])
atomic_json(ROOT/'catalog/research/global_harvest_20261020.json',summary)
outcomes=[]
for c in candidates.values():
    ident='Commons_'+str(c.get('pageid','unknown'));s=state.get(ident,{})
    outcomes.append(dict(id=ident,source_url=c.get('source_url'),status=s.get('status',c['status']),matched_id=s.get('matched_id'),file=s.get('entry',{}).get('file',ids.get(ident,{}).get('file')),error=s.get('error')))
atomic_json(ROOT/'catalog/research/global_download_outcomes_20261020.json',outcomes)
log('DONE',json.dumps(summary,ensure_ascii=False))
