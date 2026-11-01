"""Show a portable upload payload. This command NEVER uploads or modifies state."""
import argparse,json,sys
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--group',type=int,help='existing schedule group, e.g. 23; P batches cannot be uploaded')
parser.add_argument('--as-of',help='timezone-aware ISO8601 for testing only')
args=parser.parse_args()
data=json.loads((ROOT/'posts/schedule.json').read_text())
rows={e['file']:e for e in json.loads((ROOT/'catalog/artworks.json').read_text())}
pending=[p for p in data['posts'] if p['status']=='prepared_outside_window']
if args.group is not None:
 pending=[p for p in data['posts'] if p['group']==args.group]
if not pending:sys.exit('没有可用的备稿；请查看 posts/发布总表.md。')
post=pending[0]
if post['status']!='prepared_outside_window':sys.exit('此组不是未提交备稿。禁止重传历史成功、结果不明或正在提交的分组。')
now=datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(ZoneInfo('Asia/Shanghai'))
if now.tzinfo is None:sys.exit('as-of 必须包含时区。')
due=datetime.fromisoformat(post['schedule_at'])
window_ok=now+timedelta(hours=1)<=due<=now+timedelta(days=14)
assert len(post['images'])==5 and len(post['title'])<=20 and len(post['content'])<=1000
for f in post['images']:
 assert rows[f]['status']=='approved',f+' 还未通过复核'
 assert (ROOT/f).is_file(),f
payload={k:post[k] for k in ['title','content','tags','schedule_at']}
payload['images']=[str((ROOT/f).resolve()) for f in post['images']]
print(json.dumps(dict(mode='DRY_RUN_ONLY_NOT_UPLOADED',group=post['group'],within_tool_14_day_window=window_ok,
 warning='本命令不检查登录或实际平台重复；绝不会调用发布。打印的绝对路径仅供当前电脑使用，不应提交到公开仓库。',
 payload=payload),ensure_ascii=False,indent=2))
if not window_ok:sys.exit('备稿时间不在当前工具的1小时至14天窗口内。请先人工确认改期，不会自动立即发布。')
