"""Pure helpers for current cadence; historical posts keep their actual dates."""
from datetime import timedelta

def next_slot(previous,cadence):
    if cadence.get('mode')=='weekdays_daily':
        result=previous+timedelta(days=1)
        allowed=cadence.get('weekdays',[0,1,2,3,4])
        while result.weekday() not in allowed:result+=timedelta(days=1)
        return result
    return previous+timedelta(days=2)

def cadence_label(cadence):
    return '周一至周五每日北京时间20:00，周末不发' if cadence.get('mode')=='weekdays_daily' else '每两天北京时间20:00'
