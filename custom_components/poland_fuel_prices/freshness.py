"""Bounded cached data and server-requested retry delays."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

CACHE_MAX_AGE = timedelta(hours=24)
POLL_INTERVAL = timedelta(hours=1)
ERROR_INTERVAL = timedelta(minutes=5)


def snapshot_age(data, now):
    try:
        fetched = datetime.fromisoformat(data['last_success'])
        if fetched.tzinfo is None:
            return None
        age = now - fetched
        return age if age >= timedelta(0) else None
    except (KeyError, TypeError, ValueError):
        return None


def usable_snapshot(data, now):
    age = snapshot_age(data, now)
    return age is not None and age <= CACHE_MAX_AGE


def fetch_status(data, now):
    if data.get('ok'):
        return 'ok'
    return 'stale' if usable_snapshot(data, now) else 'error'


def retry_after_seconds(value, now):
    """Support both HTTP Retry-After formats without retrying before requested."""
    if not value:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0, (when - now).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
