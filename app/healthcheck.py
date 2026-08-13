#!/usr/bin/env python3

"""
Docker health check for GitHub Logs Collector.

A healthy collector must have completed a successful GitHub polling
cycle within the configured maximum age.

This detects conditions where the main Python process is still running
but polling has stalled or repeatedly failed.
"""

from __future__ import annotations

import os
import sys

from datetime import datetime, timezone
from pathlib import Path


POLL_INTERVAL = int(
    os.getenv(
        "POLL_INTERVAL",
        "300",
    )
)

LAST_SUCCESS_FILE = Path(
    os.getenv(
        "LAST_SUCCESS_FILE",
        "/var/lib/github-logs-collector/last_successful_poll",
    )
)

HEALTH_MAX_AGE = int(
    os.getenv(
        "HEALTH_MAX_AGE",
        str(
            max(
                POLL_INTERVAL * 3,
                300,
            )
        ),
    )
)


def fail(
    message: str,
) -> None:
    print(
        f"UNHEALTHY: {message}"
    )

    sys.exit(1)


def main() -> None:

    if not LAST_SUCCESS_FILE.is_file():
        fail(
            "successful poll state file does not exist"
        )

    try:
        timestamp_text = (
            LAST_SUCCESS_FILE
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

    except OSError as exc:
        fail(
            f"cannot read successful poll state: {exc}"
        )

    if not timestamp_text:
        fail(
            "successful poll timestamp is empty"
        )

    try:
        last_success = (
            datetime.fromisoformat(
                timestamp_text
            )
        )

    except ValueError:
        fail(
            "successful poll timestamp is invalid"
        )

    if last_success.tzinfo is None:
        fail(
            "successful poll timestamp has no timezone"
        )

    now = datetime.now(
        timezone.utc
    )

    age = (
        now
        - last_success.astimezone(
            timezone.utc
        )
    ).total_seconds()

    if age < -60:
        fail(
            "successful poll timestamp is unexpectedly in the future"
        )

    if age > HEALTH_MAX_AGE:
        fail(
            (
                f"last successful poll was "
                f"{int(age)} seconds ago; "
                f"maximum allowed is "
                f"{HEALTH_MAX_AGE} seconds"
            )
        )

    print(
        (
            "HEALTHY: "
            f"last successful poll "
            f"{int(age)} seconds ago"
        )
    )


if __name__ == "__main__":
    main()
