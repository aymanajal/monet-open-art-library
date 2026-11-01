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
ledger_path=ROOT/'posts/publication_ledger.json'
if ledger_path.exists():
    from datetime import datetime,timedelta
    ledger=load('posts/publication_ledger.json')
    byid={e['id']:e for e in entries}
    assert len(ledger['assets'])==len(entries)
    assert {a['id'] for a in ledger['assets']}==set(byid),'ledger does not cover whole library'
    for a in ledger['assets']:
        original=byid[a['id']]
        assert a['file']==original['file'] and a['sha256']==original['sha256'],a['id']
        assert a['review_status']==original['status'],a['id']
    old={p['group']:p for p in posts}
    assert {p['group'] for p in ledger['recorded_posts']}==set(old)
    for p in ledger['recorded_posts']:
        assert p['record_status']==old[p['group']]['status'],('rebuild ledger after state change',p['group'])
        assert p['images']==old[p['group']]['images'] and p['schedule_at']==old[p['group']]['schedule_at']
    allocated=set(used);previous=None
    for batch in ledger['provisional_batches']:
        assert batch['status']=='blocked_review_not_uploaded'
        assert len(batch['images'])==5 and len(batch['asset_ids'])==5
        when=datetime.fromisoformat(batch['provisional_at'])
        assert when.hour==20 and when.minute==0 and when.utcoffset()==timedelta(hours=8)
        if previous:assert when-previous==timedelta(days=2)
        previous=when
        for ident,f in zip(batch['asset_ids'],batch['images']):
            assert byid[ident]['file']==f and f not in allocated,(batch['id'],ident)
            assert byid[ident]['status'] in ['approved','candidate_ready']
            allocated.add(f)
    for ident in ledger['partial_pool_ids']:
        f=byid[ident]['file'];assert f not in allocated;allocated.add(f)
    assert ledger['summary']['asset_files']==len(entries)
for p in ROOT.rglob('*'):
    if '.git' in p.parts or '.cache' in p.parts:continue
    assert p.name!='cookies.json' and not p.name.endswith('.pem') and '二维码' not in p.name,p
    if p.is_file() and p.suffix in ['.md','.json','.csv','.py']:
        assert ('/'+'Users/') not in p.read_text(encoding='utf-8-sig'),p
print(f'OK: {len(entries)} image records; {len(posts)} groups; {len(used)} unique scheduled/prepared images.')
