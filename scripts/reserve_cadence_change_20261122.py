"""Reserve the explicitly requested weekday cadence and existing Sunday move.

Does not edit the platform or claim rescheduling success.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];path=ROOT/'posts/schedule.json'
data=json.loads(path.read_text());p=next(p for p in data['posts'] if p['group']==32)
assert p['status']=='scheduled_success' and p['schedule_at']=='2026-11-22T20:00:00+08:00'
data['cadence']=dict(mode='weekdays_daily',weekdays=[0,1,2,3,4],hour=20,minute=0,timezone='Asia/Shanghai',effective_from='2026-11-22T00:00:00+08:00',requested_on='2026-11-22',user_instruction='改成周一到周五 日更吧')
p['status']='submission_in_progress';p['verification']='已在主库占用改期：将周日笔记移到周一；不是重传，等待平台保存与列表复核'
p['post_id']='6af53784000000002b03349e'
p['reschedule_attempt']=dict(status='in_progress',started_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),old_schedule_at=p['schedule_at'],new_schedule_at='2026-11-23T20:00:00+08:00',evidence='Creator note-management DOM shows exact title, post ID and pending 2026-11-22 20:00')
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Reserved group32 reschedule; cadence changed locally. No platform mutation yet.')
