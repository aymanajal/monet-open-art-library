"""Record the observed successful UPDATE and independent management-list check."""
import json,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

assert '--platform-list-confirmed' in sys.argv
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'posts/schedule.json'
data=json.loads(path.read_text());p=next(p for p in data['posts'] if p['group']==32)
assert p['status']=='submission_in_progress' and p['reschedule_attempt']['status']=='in_progress'
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
event=dict(old_schedule_at=p['schedule_at'],new_schedule_at=p['reschedule_attempt']['new_schedule_at'],checked_at=now,post_id='6af53784000000002b03349e',operation='edit_existing_not_reupload',evidence='Creator update page showed 更新成功; independently reopened management list showed exactly one matching card, same post ID, 定时发布 2026-11-23 20:00; pool group33 still 2026-11-24 20:00')
p.setdefault('reschedule_history',[]).append(event);p['schedule_at']=event['new_schedule_at'];p['status']='scheduled_success'
p['verification']='平台更新成功，并重新打开定时列表确认同一笔记已改至2026-11-23 20:00；不是重传，也不等于到期发布核验'
p['reschedule_attempt'].update(status='scheduled_success',finished_at=now,evidence=event['evidence'])
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Group32 rescheduled to Monday 2026-11-23 20:00, same platform post ID; group33 remains Tuesday.')
