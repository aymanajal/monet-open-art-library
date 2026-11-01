"""Submit ONE explicitly reserved post. No retries; ambiguous results block re-upload."""
import argparse,hashlib,json,re,subprocess,sys,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];TZ=ZoneInfo('Asia/Shanghai')
def run(*args):return subprocess.check_output(args,cwd=ROOT,text=True).strip()
def load(p):return json.loads((ROOT/p).read_text())
def save(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--group',type=int,required=True);parser.add_argument('--submit',action='store_true');args=parser.parse_args()
assert args.submit,'Explicit --submit is required'
assert not run('git','status','--porcelain'),'Commit all reviewed changes before submitting'
head=run('git','rev-parse','HEAD');remote=run('git','ls-remote','origin','refs/heads/main').split()[0]
assert head==remote,'Reservation is not current on GitHub; stop before uploading'
data=load('posts/schedule.json');p=next(p for p in data['posts'] if p['group']==args.group)
assert p['status']=='submission_in_progress' and p.get('submission_attempt'),'No active reservation; refuse resubmission'
assert not p['submission_attempt'].get('called_at'),'This attempt was already called; verify platform before retry'
now=datetime.now(TZ);due=datetime.fromisoformat(p['schedule_at'])
assert now+timedelta(hours=1)<=due<=now+timedelta(days=14),'Do not fall back to immediate publication'
assets={e['file']:e for e in load('catalog/artworks.json')}
assert len(p['images'])==5 and len(p['title'])<=20 and len(p['content'])<=1000
for f in p['images']:
 assert assets[f]['status']=='approved' and (ROOT/f).is_file()
 assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==assets[f]['sha256']
 assert sum(f in other['images'] for other in data['posts'])==1,'Repeated file in recorded posts'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));endpoint='http://127.0.0.1:18060/mcp'
headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
init=dict(jsonrpc='2.0',id=1,method='initialize',params=dict(protocolVersion='2024-11-05',capabilities={},clientInfo=dict(name='monet-library',version='1')))
r=opener.open(urllib.request.Request(endpoint,data=json.dumps(init).encode(),headers=headers),timeout=15)
headers['Mcp-Session-Id']=r.headers['Mcp-Session-Id'];r.read()
def call(name,arguments):
 req=dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name=name,arguments=arguments))
 with opener.open(urllib.request.Request(endpoint,data=json.dumps(req).encode(),headers=headers),timeout=420) as response:return response.read()
login=json.loads(call('check_login_status',{}))
login_text=' '.join(c.get('text','') for c in login.get('result',{}).get('content',[]))
assert '未登录' not in login_text and '已登录' in login_text,'Login must be verified before publishing'
payload={k:p[k] for k in ['title','content','tags','schedule_at']}
payload.update(images=[str((ROOT/f).resolve()) for f in p['images']],is_original=False,visibility='公开可见')
stamp=datetime.now(TZ).isoformat();p['submission_attempt'].update(called_at=stamp,reservation_commit=head)
# Persist the attempt BEFORE sending the mutation; a crash is never silently retried.
save('posts/schedule.json',data)
cache=ROOT/'.cache';cache.mkdir(exist_ok=True)
status='submission_unknown';digest=None;post_id=None;reason='transport_or_unrecognized_response'
try:
 raw=call('publish_content',payload);digest=hashlib.sha256(raw).hexdigest()
 (cache/f'publish_response_group_{args.group}.json').write_bytes(raw)
 result=json.loads(raw);body=result.get('result',{})
 text=' '.join(c.get('text','') for c in body.get('content',[]) if c.get('type')=='text')
 if not body.get('isError') and not result.get('error') and re.search(r'发布成功|排期成功|定时发布成功',text) and not re.search(r'发布失败|排期失败|未成功',text):
  status='scheduled_success';reason='publish_content returned explicit success for scheduled request'
  match=re.search(r'(?:PostID|post_id|note_id)[\s\"\':：=]+([a-fA-F0-9]{24})',text)
  if match:post_id=match.group(1)
except Exception:
 reason='Transport failed or result ambiguous; inspect platform before any retry'
p.update(status=status,verification='工具明确返回发布成功（请求含定时时间）；不等同于已核验到期发布' if status=='scheduled_success' else '提交结果不明；禁止重传，先核对平台')
p['submission_attempt'].update(finished_at=datetime.now(TZ).isoformat(),outcome=status,response_sha256=digest,evidence=reason)
if post_id:p['post_id']=post_id
save('posts/schedule.json',data)
check=load('posts/platform_check.json');check.update(checked_at=datetime.now(TZ).isoformat(),login_status='logged_in',
 new_uploads_this_run=sum(x['status']=='scheduled_success' and x.get('submission_attempt',{}).get('attempt_id','').startswith('window-20261101-') for x in data['posts']))
save('posts/platform_check.json',check)
run(sys.executable,'scripts/build_publication_ledger.py');run(sys.executable,'scripts/verify_library.py');run('git','diff','--check')
run('git','add','posts','catalog/inventory.json','README.md')
run('git','commit','--quiet','-m',f"Record scheduled submission outcome for group {args.group}: {status}")
run('git','push','origin','main')
assert run('git','rev-parse','HEAD')==run('git','ls-remote','origin','refs/heads/main').split()[0]
print(json.dumps(dict(group=args.group,status=status,schedule_at=p['schedule_at'],title=p['title'],post_id=post_id,remote_sha=run('git','rev-parse','HEAD')),ensure_ascii=False))
if status!='scheduled_success':sys.exit(2)
