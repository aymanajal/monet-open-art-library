"""Verify asset hashes, catalog links and schedule references using the standard library."""
import csv,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/name).read_text())
entries=load('catalog/artworks.json')
assert len({e['id'] for e in entries})==len(entries),'duplicate catalog IDs'
catalog_files={e['file'] for e in entries}
actual_files={str(p.relative_to(ROOT)) for p in (ROOT/'assets').rglob('*') if p.is_file() and p.name!='.DS_Store'}
assert actual_files==catalog_files,('unregistered or missing assets',actual_files^catalog_files)
assert len({e['sha256'] for e in entries})==len(entries),'byte-identical assets must share one catalog file'
for e in entries:
    p=ROOT/e['file']
    assert p.is_file(),e['file']
    assert p.stat().st_size==e['bytes'],e['id']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'],e['id']
    assert e['source_url'].startswith('https://'),e['id']
    assert e['rights'] and e['status'],e['id']
    if e['status']=='review_license':
        assert e.get('source_metadata',{}).get('license_url','').startswith('https://creativecommons.org/licenses/'),e['id']
        assert e['source_metadata'].get('creator') or e['source_metadata'].get('attribution'),e['id']
with (ROOT/'catalog/artworks.csv').open(encoding='utf-8-sig',newline='') as f:
    assert {r['id'] for r in csv.DictReader(f)}=={e['id'] for e in entries},'CSV/JSON catalog mismatch'
posts=load('posts/schedule.json')['posts']
assert len({p['group'] for p in posts})==len(posts),'duplicate groups'
used=set()
for p in posts:
    assert len(p['images'])==5,p['group']
    assert len(p['title'])<=20,p['group']
    for f in p['images']:
        assert f in catalog_files,(p['group'],f)
        assert f not in used,('reused image file',p['group'],f)
        used.add(f)
manifest=set()
for line in (ROOT/'catalog/files.sha256').read_text().splitlines():
    digest,path=line.split('  ',1)
    manifest.add(path)
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
assert catalog_files<=manifest,'catalog file missing from checksum manifest'
for p in ROOT.rglob('*'):
    if '.git' in p.parts or '.cache' in p.parts:continue
    assert p.name!='cookies.json' and not p.name.endswith('.pem') and '二维码' not in p.name,p
    if p.is_file() and p.suffix in ['.md','.json','.csv','.py']:
        assert ('/'+'Users/') not in p.read_text(encoding='utf-8-sig'),p
print(f'OK: {len(entries)} image records; {len(posts)} groups; {len(used)} unique scheduled/prepared images.')
