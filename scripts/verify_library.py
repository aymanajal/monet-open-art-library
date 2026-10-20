"""Verify asset hashes, catalog links and schedule references using the standard library."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/name).read_text())
entries=load('catalog/artworks.json')
assert len({e['id'] for e in entries})==len(entries),'duplicate catalog IDs'
catalog_files={e['file'] for e in entries}
for e in entries:
    p=ROOT/e['file']
    assert p.is_file(),e['file']
    assert p.stat().st_size==e['bytes'],e['id']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'],e['id']
    assert e['source_url'].startswith('https://'),e['id']
    assert e['rights'] and e['status'],e['id']
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
for line in (ROOT/'catalog/files.sha256').read_text().splitlines():
    digest,path=line.split('  ',1)
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
for p in ROOT.rglob('*'):
    if '.git' in p.parts:continue
    assert p.name!='cookies.json' and not p.name.endswith('.pem') and '二维码' not in p.name,p
    if p.is_file() and p.suffix in ['.md','.json','.csv','.py']:
        assert ('/'+'Users/') not in p.read_text(encoding='utf-8-sig'),p
print(f'OK: {len(entries)} image records; {len(posts)} groups; {len(used)} unique scheduled/prepared images.')
