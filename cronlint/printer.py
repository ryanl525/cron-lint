"""Turn parsed cron fields back into a plain-English description."""

from __future__ import annotations

from .parser import ListExpr, Range, ScheduleFields, Star, Step, Value

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

WEEKDAY_NAMES = [
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
]


def _describe_item(node) -> str:
    if isinstance(node, Value):
        return str(node.n)
    if isinstance(node, Range):
        return f"{node.start}-{node.end}"
    if isinstance(node, Step):
        base = "*" if isinstance(node.base, Star) else _describe_item(node.base)
        return f"{base}/{node.step}"
    raise TypeError(f"unexpected node in list: {node!r}")


def _describe_unit(node, name: str) -> str:
    if isinstance(node, Star):
        return f"every {name}"
    if isinstance(node, Value):
        return f"{name} {node.n}"
    if isinstance(node, Range):
        return f"{name}s {node.start} through {node.end}"
    if isinstance(node, Step):
        if isinstance(node.base, Star):
            return f"every {node.step} {name}s"
        return f"every {node.step} {name}s starting at {_describe_unit(node.base, name)}"
    if isinstance(node, ListExpr):
        return f"{name}s " + ", ".join(_describe_item(item) for item in node.items)
    raise TypeError(f"unknown field node: {node!r}")


def _weekday_name(n: int) -> str:
    return WEEKDAY_NAMES[n % 7]


def _describe_weekday_unit(node) -> str:
    if isinstance(node, Star):
        return "every day of the week"
    if isinstance(node, Value):
        return _weekday_name(node.n)
    if isinstance(node, Range):
        return f"{_weekday_name(node.start)} through {_weekday_name(node.end)}"
    if isinstance(node, Step):
        if isinstance(node.base, Star):
            return f"every {node.step} days of the week"
        return f"every {node.step} days of the week starting at {_describe_weekday_unit(node.base)}"
    if isinstance(node, ListExpr):
        return ", ".join(_describe_weekday_unit(item) for item in node.items)
    raise TypeError(f"unknown field node: {node!r}")


def _month_name(n: int) -> str:
    return MONTH_NAMES[n - 1]


def _describe_month_unit(node) -> str:
    if isinstance(node, Star):
        return "every month"
    if isinstance(node, Value):
        return _month_name(node.n)
    if isinstance(node, Range):
        return f"{_month_name(node.start)} through {_month_name(node.end)}"
    if isinstance(node, Step):
        if isinstance(node.base, Star):
            return f"every {node.step} months"
        return f"every {node.step} months starting at {_describe_month_unit(node.base)}"
    if isinstance(node, ListExpr):
        return ", ".join(_describe_month_unit(item) for item in node.items)
    raise TypeError(f"unknown field node: {node!r}")


def _describe_time(minute, hour) -> str:
    if isinstance(minute, Value) and isinstance(hour, Value):
        return f"at {hour.n:02d}:{minute.n:02d}"
    return f"at {_describe_unit(minute, 'minute')}, {_describe_unit(hour, 'hour')}"


def describe(fields: ScheduleFields) -> str:
    """Render a human-readable sentence for a parsed schedule.

    Day-of-month and day-of-week are combined with "or" rather than "and"
    because that is how cron itself evaluates them when both are restricted.
    """
    minute, hour, day, month, weekday = fields

    clauses = [_describe_time(minute, hour)]

    day_restricted = not isinstance(day, Star)
    weekday_restricted = not isinstance(weekday, Star)
    if day_restricted and weekday_restricted:
        clauses.append(
            f"on {_describe_unit(day, 'day')}, or on {_describe_weekday_unit(weekday)}"
        )
    elif day_restricted:
        clauses.append(f"on {_describe_unit(day, 'day')}")
    elif weekday_restricted:
        clauses.append(f"on {_describe_weekday_unit(weekday)}")

    if not isinstance(month, Star):
        clauses.append(f"in {_describe_month_unit(month)}")

    return ", ".join(clauses)
