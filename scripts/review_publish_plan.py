"""Fetch primary source evidence and render private visual comparison sheets.

Requires Pillow/NumPy/curl. Does NOT approve images, reserve posts or upload.
"""
import argparse,hashlib,html,json,re,subprocess
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image,ImageDraw,ImageOps
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
plan_path=(ROOT/args.plan).resolve();assert plan_path.is_relative_to(ROOT)
plan=json.loads(plan_path.read_text());run_id=plan['run_id'];assert re.fullmatch(r'window-\d{8}',run_id)
cache=ROOT/'.cache'/run_id;cache.mkdir(parents=True,exist_ok=True)
entries=json.loads((ROOT/'catalog/artworks.json').read_text());byid={e['id']:e for e in entries};byfile={e['file']:e for e in entries}
posts=json.loads((ROOT/'posts/schedule.json').read_text())['posts']
historical=[byfile[f] for p in posts for f in p['images']]
selected=[byid[i] for g in plan['groups'] for i in g['asset_ids']]
assert len(selected)==len({e['id'] for e in selected})==len(plan['groups'])*5
known_qids={q for e in historical for q in e.get('wikidata_ids',[])}
inventories={(e.get('source_metadata',{}).get('collection_ids',[])[0] if e.get('source_metadata',{}).get('collection_ids') else '',inv):e['id'] for e in historical for inv in e.get('source_metadata',{}).get('inventory_numbers',[])}
for e in selected:
 assert e['status']=='candidate_ready',e['id']
 assert e['sha256'] not in {x['sha256'] for x in historical}
 assert not set(e.get('wikidata_ids',[]))&known_qids,e['id']
 for c in e.get('source_metadata',{}).get('collection_ids',[]):
  for inv in e.get('source_metadata',{}).get('inventory_numbers',[]):assert (c,inv) not in inventories,(e['id'],inventories.get((c,inv)))
pages={}
for off in range(0,len(selected),20):
 batch=selected[off:off+20]
 url='https://commons.wikimedia.org/w/api.php?'+urlencode(dict(action='query',format='json',pageids='|'.join(e['id'].split('_')[1] for e in batch),prop='imageinfo|revisions',iiprop='extmetadata|url',rvprop='ids|timestamp|content',rvslots='main'))
 p=subprocess.run(['curl','--fail','-sS','--max-time','90','-A','MonetOpenArtLibrary/1.0',url],capture_output=True,check=True)
 d=json.loads(p.stdout);pages.update(d['query']['pages'])
(cache/'source_response.json').write_text(json.dumps(pages,ensure_ascii=False))
def clean(s):
 s=re.sub(r'<(?:div|span)[^>]*style=["\'][^"\']*display:\s*none[^"\']*["\'][^>]*>.*?</(?:div|span)>','',s,flags=re.S|re.I)
 return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s))).strip()
def phash(p,crop=False):
 with Image.open(p) as im:
  im=im.convert('L')
  if crop:im=im.crop((im.width*.04,im.height*.04,im.width*.96,im.height*.96))
  a=np.asarray(im.resize((32,32)),dtype=float)
 d=np.cos(np.pi*(2*np.arange(32)+1)*np.arange(8)[:,None]/64);v=(d@a@d.T).flatten()[1:];mid=np.median(v)
 return sum(int(x>mid)<<i for i,x in enumerate(v))
hashes={e['id']:(phash(ROOT/e['file']),phash(ROOT/e['file'],True)) for e in historical+selected}
evidence=[]
for e in selected:
 page=pages[e['id'].split('_')[1]];info=page['imageinfo'][0];meta=info['extmetadata'];value=lambda k:clean(meta.get(k,{}).get('value',''))
 assert re.search('Claude Monet',value('Artist'),re.I),e['id']
 assert not re.search('after |copy|follower|attributed',value('Artist'),re.I),e['id']
 assert value('LicenseShortName') in ['Public domain','CC0'],e['id']
 assert value('NonFree').lower() not in ['true','1']
 assert hashlib.sha256((ROOT/e['file']).read_bytes()).hexdigest()==e['sha256']
 a,b=hashes[e['id']];neighbors=sorted((min((a^hashes[h['id']][0]).bit_count(),(b^hashes[h['id']][1]).bit_count()),h['id']) for h in historical)[:3]
 rev=page['revisions'][0];wikitext=rev['slots']['main']['*']
 source_fields={key:clean(m.group(1)) for key in ['accession number','institution','artist','title'] if (m:=re.search(r'\|[ \t]*'+key+r'[ \t]*=[ \t]*([^\n]+)',wikitext,re.I)) and not m.group(1).lstrip().startswith('|')}
 evidence.append(dict(id=e['id'],source_url=info['descriptionurl'],source_revision_id=rev['revid'],source_revision_timestamp=rev['timestamp'],source_title=value('ObjectName'),source_artist=value('Artist'),license=value('LicenseShortName'),source_fields=source_fields,inventory_numbers=e.get('source_metadata',{}).get('inventory_numbers',[]),wikidata_ids=e.get('wikidata_ids',[]),nearest_historical=[dict(id=i,distance=d) for d,i in neighbors]))
byproof={p['id']:p for p in evidence}
(cache/'source_checks.json').write_text(json.dumps(dict(run_id=run_id,historical_file_count=len(historical),images=evidence),ensure_ascii=False,indent=2)+'\n')
for g in plan['groups']:
 sheet=Image.new('RGB',(1200,1125),'white');draw=ImageDraw.Draw(sheet)
 for row,ident in enumerate(g['asset_ids']):
  compare=[(ident,'NEW')]+[(n['id'],'distance '+str(n['distance'])) for n in byproof[ident]['nearest_historical']]
  for col,(i,label) in enumerate(compare):
   e=byid[i]
   with Image.open(ROOT/e['file']) as im:thumb=ImageOps.contain(im.convert('RGB'),(285,190))
   x=col*300;y=row*225;sheet.paste(thumb,(x+(290-thumb.width)//2,y));draw.text((x+4,y+192),i,fill='black');draw.text((x+4,y+208),label,fill='black')
 out=cache/f"group_{g['group']}_comparison.jpg";sheet.save(out,quality=90)
 print('SHEET',out.relative_to(ROOT),flush=True)
print(json.dumps([dict(id=e['id'],title=e['source_title'],rights=e['license'],nearest=e['nearest_historical'][0]) for e in evidence],ensure_ascii=False))
