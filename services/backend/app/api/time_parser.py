import re
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def _start_of_week(dt: datetime) -> datetime:
    monday = dt - timedelta(days=dt.weekday())
    return _start_of_day(monday)


_PATTERNS = [
    (re.compile(r'지난\s*(\d+)\s*일'), 'LAST_N_DAYS_A'),
    (re.compile(r'(\d+)\s*일\s*전'),   'LAST_N_DAYS_B'),
    (re.compile(r'오늘'),              'TODAY'),
    (re.compile(r'어제'),              'YESTERDAY'),
    (re.compile(r'저번\s*주|지난\s*주'), 'LAST_WEEK'),
    (re.compile(r'이번\s*주'),         'THIS_WEEK'),
    (re.compile(r'지난\s*달'),         'LAST_MONTH'),
    (re.compile(r'이번\s*달'),         'THIS_MONTH'),
]


def parse_time_expression(
    query: str,
) -> tuple[str, datetime | None, datetime | None, str | None]:
    now = _now()

    for pattern, key in _PATTERNS:
        m = pattern.search(query)
        if not m:
            continue

        cleaned = pattern.sub('', query).strip()
        cleaned = re.sub(r'^[\s,?!]+|[\s,?!]+$', '', cleaned)

        if key == 'LAST_N_DAYS_A':
            n = int(m.group(1))
            start = _start_of_day(now - timedelta(days=n))
            return cleaned, start, now, f"지난 {n}일 필터 적용됨"

        if key == 'LAST_N_DAYS_B':
            n = int(m.group(1))
            start = _start_of_day(now - timedelta(days=n))
            return cleaned, start, now, f"지난 {n}일 필터 적용됨"

        if key == 'TODAY':
            return cleaned, _start_of_day(now), now, "오늘 필터 적용됨"

        if key == 'YESTERDAY':
            yesterday = now - timedelta(days=1)
            return cleaned, _start_of_day(yesterday), _end_of_day(yesterday), "어제 필터 적용됨"

        if key == 'THIS_WEEK':
            return cleaned, _start_of_week(now), now, "이번 주 필터 적용됨"

        if key == 'LAST_WEEK':
            last_monday = _start_of_week(now) - timedelta(weeks=1)
            last_sunday = _end_of_day(last_monday + timedelta(days=6))
            return cleaned, last_monday, last_sunday, "저번 주 필터 적용됨"

        if key == 'THIS_MONTH':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return cleaned, start, now, "이번 달 필터 적용됨"

        if key == 'LAST_MONTH':
            first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_of_this - timedelta(seconds=1)
            last_month_start = last_month_end.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            return cleaned, last_month_start, _end_of_day(last_month_end), "지난 달 필터 적용됨"

    return query, None, None, None
