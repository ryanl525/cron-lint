"""Validating parser for cron schedule expressions and crontab-style files.

The standard `crontab -e` error message ("there is an error in crontab file:
syntax error") tells you nothing about where the problem is. This parser
tracks the exact line and column of every token so a caller can point at the
offending character directly.
"""

from __future__ import annotations

import re
from collections import namedtuple
from dataclasses import dataclass
from typing import List, Tuple, Union

FieldSpec = namedtuple("FieldSpec", ["name", "min", "max", "names"])

MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

WEEKDAY_ABBR = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}

# 7 is a common alias for Sunday in addition to 0.
FIELD_SPECS: Tuple[FieldSpec, ...] = (
    FieldSpec("minute", 0, 59, None),
    FieldSpec("hour", 0, 23, None),
    FieldSpec("day of month", 1, 31, None),
    FieldSpec("month", 1, 12, MONTH_ABBR),
    FieldSpec("day of week", 0, 7, WEEKDAY_ABBR),
)

_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")
_FULL_DIGITS_RE = re.compile(r"\d+\Z")


@dataclass(frozen=True)
class Star:
    """The `*` wildcard: every value is allowed."""


@dataclass(frozen=True)
class Value:
    n: int


@dataclass(frozen=True)
class Range:
    start: int
    end: int


@dataclass(frozen=True)
class Step:
    base: Union[Star, Range, Value]
    step: int


@dataclass(frozen=True)
class ListExpr:
    items: Tuple[Union[Star, Range, Value, Step], ...]


FieldNode = Union[Star, Value, Range, Step, ListExpr]
ScheduleFields = Tuple[FieldNode, FieldNode, FieldNode, FieldNode, FieldNode]


@dataclass(frozen=True)
class CronEntry:
    lineno: int
    fields: ScheduleFields
    command: str


class CronSyntaxError(ValueError):
    """A cron expression is invalid, with the exact position of the problem."""

    def __init__(self, message: str, lineno: int, column: int, line_text: str):
        self.lineno = lineno
        self.column = column
        self.line_text = line_text
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        pointer = " " * (self.column - 1) + "^"
        return (
            f"line {self.lineno}, column {self.column}: {self.message}\n"
            f"  {self.line_text}\n"
            f"  {pointer}"
        )


def _error(lineno: int, column: int, line_text: str, message: str) -> CronSyntaxError:
    return CronSyntaxError(message, lineno, column, line_text)


def _parse_value_token(
    text: str, col: int, spec: FieldSpec, line_text: str, lineno: int
) -> int:
    if spec.names:
        resolved = spec.names.get(text.upper())
        if resolved is not None:
            return resolved
    if not _FULL_DIGITS_RE.match(text):
        raise _error(lineno, col, line_text, f"invalid value {text!r} in {spec.name} field")
    value = int(text)
    if not (spec.min <= value <= spec.max):
        raise _error(
            lineno,
            col,
            line_text,
            f"{value} is out of range for {spec.name} (expected {spec.min}-{spec.max})",
        )
    return value


def _parse_range(text: str, col: int, spec: FieldSpec, line_text: str, lineno: int) -> Range:
    idx = text.index("-")
    start_text, end_text = text[:idx], text[idx + 1 :]
    if not start_text or not end_text:
        raise _error(lineno, col, line_text, f"invalid range {text!r} in {spec.name} field")
    start = _parse_value_token(start_text, col, spec, line_text, lineno)
    end = _parse_value_token(end_text, col + idx + 1, spec, line_text, lineno)
    if start > end:
        raise _error(
            lineno,
            col,
            line_text,
            f"range start ({start}) is greater than range end ({end}) in {spec.name} field",
        )
    return Range(start, end)


def _parse_base(
    text: str, col: int, spec: FieldSpec, line_text: str, lineno: int
) -> Union[Star, Range, Value]:
    if text == "*":
        return Star()
    if "-" in text:
        return _parse_range(text, col, spec, line_text, lineno)
    return Value(_parse_value_token(text, col, spec, line_text, lineno))


def _parse_step_item(
    text: str, col: int, spec: FieldSpec, line_text: str, lineno: int
) -> Union[Star, Range, Value, Step]:
    if "/" not in text:
        return _parse_base(text, col, spec, line_text, lineno)

    idx = text.index("/")
    base_text, step_text = text[:idx], text[idx + 1 :]
    step_col = col + idx + 1
    if not base_text:
        raise _error(lineno, col, line_text, f"missing value before '/' in {spec.name} field")
    if not step_text:
        raise _error(lineno, step_col, line_text, f"missing step value after '/' in {spec.name} field")
    if not _FULL_DIGITS_RE.match(step_text):
        raise _error(lineno, step_col, line_text, f"invalid step value {step_text!r}")
    step = int(step_text)
    if step <= 0:
        raise _error(lineno, step_col, line_text, "step value must be a positive integer")
    base = _parse_base(base_text, col, spec, line_text, lineno)
    return Step(base, step)


def _parse_field(text: str, col: int, spec: FieldSpec, line_text: str, lineno: int) -> FieldNode:
    if text == "":
        raise _error(lineno, col, line_text, f"empty {spec.name} field")

    items = []
    pos = 0
    for part in text.split(","):
        item_col = col + pos
        if part == "":
            raise _error(
                lineno, item_col, line_text, f"empty item in {spec.name} field (check for stray commas)"
            )
        items.append(_parse_step_item(part, item_col, spec, line_text, lineno))
        pos += len(part) + 1

    if len(items) == 1:
        return items[0]
    return ListExpr(tuple(items))


def _tokenize(line: str):
    return [(m.group(), m.start() + 1) for m in re.finditer(r"\S+", line)]


def _parse_fields(field_tokens, line_text: str, lineno: int) -> ScheduleFields:
    return tuple(
        _parse_field(tok_text, tok_col, spec, line_text, lineno)
        for (tok_text, tok_col), spec in zip(field_tokens, FIELD_SPECS)
    )


def parse_schedule(text: str, *, lineno: int = 1) -> ScheduleFields:
    """Parse a bare 5-field cron schedule, e.g. "*/15 8-17 * * 1-5"."""
    tokens = _tokenize(text)
    if len(tokens) < 5:
        raise _error(
            lineno, len(text) + 1, text, f"expected 5 fields, found {len(tokens)}"
        )
    if len(tokens) > 5:
        extra_text, extra_col = tokens[5]
        raise _error(
            lineno, extra_col, text, f"expected 5 fields, found extra token {extra_text!r}"
        )
    return _parse_fields(tokens, text, lineno)


def parse_crontab(text: str) -> List[CronEntry]:
    """Parse a crontab-style file: comments, env assignments, and entries.

    Returns a list of CronEntry. Raises CronSyntaxError on the first invalid
    entry, pointing at the exact line and column.
    """
    entries = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _ENV_ASSIGNMENT_RE.match(stripped):
            continue

        tokens = _tokenize(line)
        if len(tokens) < 6:
            raise _error(
                lineno,
                len(line) + 1,
                line,
                f"expected 5 schedule fields and a command, found {len(tokens)} field(s)",
            )

        fields = _parse_fields(tokens[:5], line, lineno)
        command_col = tokens[5][1]
        command = line[command_col - 1 :]
        entries.append(CronEntry(lineno=lineno, fields=fields, command=command))

    return entries
