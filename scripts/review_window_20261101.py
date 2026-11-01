"""Fetch source evidence and render PRIVATE comparison sheets; never publishes."""
import hashlib,html,json,re,subprocess
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image,ImageDraw,ImageOps
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.cache/window_20261101';CACHE.mkdir(parents=True,exist_ok=True)
BATCHES={
25:['151580852','54675310','57012077','82342345','31697395'],
26:['189209668','7377095','7296068','7298555','2327199'],
27:['34059825','36198971','130728880','81086731','21925466'],
28:['81751002','139615640','21864201','29920532','8859184']}
entries=json.loads((ROOT/'catalog/artworks.json').read_text());byid={e['id']:e for e in entries}
posts=json.loads((ROOT/'posts/schedule.json').read_text())['posts']
historical=[byid[next(e['id'] for e in entries if e['file']==f)] for p in posts for f in p['images']]
selected=[byid['Commons_'+i] for batch in BATCHES.values() for i in batch]
assert len({e['id'] for e in selected})==20
known_qids={q for e in historical for q in e.get('wikidata_ids',[])}
for e in selected:
 assert e['status']=='candidate_ready'
 assert e['sha256'] not in {a['sha256'] for a in historical}
 assert not set(e.get('wikidata_ids',[]))&known_qids,e['id']

url='https://commons.wikimedia.org/w/api.php?'+urlencode(dict(action='query',format='json',pageids='|'.join(e['id'].split('_')[1] for e in selected),prop='imageinfo|revisions',iiprop='extmetadata|url',rvprop='ids|timestamp|content',rvslots='main'))
p=subprocess.run(['curl','--fail','-sS','--max-time','90','-A','MonetOpenArtLibrary/1.0',url],capture_output=True,check=True)
data=json.loads(p.stdout)
(CACHE/'source_response.json').write_text(json.dumps(data,ensure_ascii=False))
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s))).strip()
def phash(path,crop=False):
 with Image.open(path) as im:
  im=im.convert('L')
  if crop:im=im.crop((im.width*.04,im.height*.04,im.width*.96,im.height*.96))
  a=np.asarray(im.resize((32,32)),dtype=float)
 d=np.cos(np.pi*(2*np.arange(32)+1)*np.arange(8)[:,None]/64)
 v=(d@a@d.T).flatten()[1:];mid=np.median(v)
 return sum(int(x>mid)<<i for i,x in enumerate(v))
hashes={e['id']:(phash(ROOT/e['file']),phash(ROOT/e['file'],True)) for e in historical+selected}
evidence=[]
for e in selected:
 page=data['query']['pages'][e['id'].split('_')[1]];info=page['imageinfo'][0];meta=info['extmetadata']
 value=lambda k:clean(meta.get(k,{}).get('value',''))
 assert re.search('Claude Monet',value('Artist'),re.I),e['id']
 assert re.search('public domain|CC0',value('LicenseShortName'),re.I),e['id']
 assert hashlib.sha256((ROOT/e['file']).read_bytes()).hexdigest()==e['sha256']
 a,b=hashes[e['id']]
 neighbors=sorted((min((a^hashes[h['id']][0]).bit_count(),(b^hashes[h['id']][1]).bit_count()),h['id']) for h in historical)[:3]
 rev=page['revisions'][0]
 evidence.append(dict(id=e['id'],source_url=info['descriptionurl'],source_revision_id=rev['revid'],source_revision_timestamp=rev['timestamp'],
  source_title=value('ObjectName'),source_artist=value('Artist'),license=value('LicenseShortName'),
  inventory=value('AccessionNumber'),institution=value('Institution'),credit=value('Credit'),
  wikidata_ids=e.get('wikidata_ids',[]),nearest_historical=[dict(id=i,distance=d) for d,i in neighbors]))
evidence_by={e['id']:e for e in evidence}
(CACHE/'source_checks.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
for number,ids in BATCHES.items():
 sheet=Image.new('RGB',(1200,1125),'white');draw=ImageDraw.Draw(sheet)
 for row,number_id in enumerate(ids):
  ident='Commons_'+number_id
  neighbors=evidence_by[ident]['nearest_historical']
  compare=[(ident,'NEW')]+[(n['id'],'distance '+str(n['distance'])) for n in neighbors]
  for col,(i,label) in enumerate(compare):
   e=byid[i]
   with Image.open(ROOT/e['file']) as im:thumb=ImageOps.contain(im.convert('RGB'),(285,190))
   x=col*300;y=row*225;sheet.paste(thumb,(x+(290-thumb.width)//2,y))
   draw.text((x+4,y+192),i,fill='black');draw.text((x+4,y+208),label,fill='black')
 out=CACHE/f'group_{number}_comparison.jpg';sheet.save(out,quality=90);print(out)
print(json.dumps([dict(id=e['id'],title=e['source_title'],license=e['license'],inventory=e['inventory'],nearest=e['nearest_historical'][0]) for e in evidence],ensure_ascii=False,indent=2))
