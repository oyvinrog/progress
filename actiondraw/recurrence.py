"""Shared local-time reminder recurrence rules."""
import math
import time
from datetime import datetime, timedelta


def repeat_rule(value, anchor):
    if value is None or value == {}:
        return None
    if not isinstance(value, dict):
        raise ValueError('Invalid recurrence')
    interval, unit = value.get('interval'), value.get('unit')
    if type(interval) is not int or not 1 <= interval <= 1000000 or unit not in ('minutes', 'hours', 'days', 'weeks'):
        raise ValueError('Invalid recurrence interval or unit')
    if not math.isfinite(anchor):
        raise ValueError('Invalid recurrence anchor')
    rule = dict(interval=interval, unit=unit, anchor=anchor)
    try:
        next_occurrence(rule, anchor)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError('Recurrence exceeds supported dates') from exc
    return rule


def load_repeat(value, anchor):
    try:
        return repeat_rule(value, float(value.get('anchor', anchor)) if isinstance(value, dict) else anchor)
    except (ValueError, TypeError, OverflowError):
        return None


def repeat_text(rule):
    if not rule:
        return ''
    n, unit = rule['interval'], rule['unit']
    return f"Every {n} {unit if n != 1 else unit[:-1]}"


def _local_timestamp(value):
    # Explicit DST candidates choose the earlier fold; gaps normalize forward.
    candidates = [time.mktime((*value.timetuple()[:8], dst)) for dst in (0, 1, -1)]
    exact = [ts for ts in candidates if datetime.fromtimestamp(ts) == value]
    if exact:
        return min(exact)
    forward = [ts for ts in candidates if datetime.fromtimestamp(ts) > value]
    return min(forward) if forward else max(candidates)


def next_occurrence(rule, now):
    anchor, n, unit = rule['anchor'], rule['interval'], rule['unit']
    if unit in ('minutes', 'hours'):
        step = n * (60 if unit == 'minutes' else 3600)
        return anchor + max(1, math.floor((now - anchor) / step) + 1) * step
    start = datetime.fromtimestamp(anchor)
    days = n * (7 if unit == 'weeks' else 1)
    count = max(1, (datetime.fromtimestamp(now).date() - start.date()).days // days)
    while True:
        candidate = _local_timestamp(start + timedelta(days=count * days))
        if candidate > now:
            return candidate
        count += 1


def occurrence_window(rule, scheduled, start, end):
    """Return (first, count, step) within [start, end); step is elapsed seconds or None.

    Count minute/hour schedules arithmetically so calendar counts never expand
    thousands of rows. Daily/weekly windows are small civil-date ranges.
    """
    first = scheduled if scheduled >= start else next_occurrence(rule, start - 0.000001)
    if first >= end:
        return first, 0, None
    if rule['unit'] in ('minutes', 'hours'):
        step = rule['interval'] * (60 if rule['unit'] == 'minutes' else 3600)
        return first, math.ceil((end - first) / step), step
    count, stamp = 0, first
    while stamp < end:
        count += 1
        stamp = next_occurrence(rule, stamp)
    return first, count, None
