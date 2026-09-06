"""Command-line entry point: validate crontab files from the shell."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .parser import lint_crontab


def _validate_file(path: str, fields: int) -> bool:
    try:
        with open(path, "r") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"{path}: {exc.strerror}", file=sys.stderr)
        return False

    entries, errors = lint_crontab(text, fields=fields)
    if errors:
        for error in errors:
            print(f"{path}: {error}", file=sys.stderr)
        return False

    noun = "entry" if len(entries) == 1 else "entries"
    print(f"{path}: OK ({len(entries)} {noun})")
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cronlint",
        description="Validate crontab files and report syntax errors with the exact line and column.",
    )
    parser.add_argument("files", nargs="+", help="crontab file(s) to validate")
    parser.add_argument(
        "--fields",
        type=int,
        choices=(5, 6, 7),
        default=5,
        help="schedule fields per entry before the command: 5 (standard), "
        "6 (leading seconds field), or 7 (seconds and a trailing year field). Default 5.",
    )
    args = parser.parse_args(argv)

    all_valid = True
    for path in args.files:
        if not _validate_file(path, args.fields):
            all_valid = False

    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
