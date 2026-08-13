#!/usr/bin/env python3

"""
GitHub Logs Collector

Outbound-only GitHub REST API polling collector for SIEM and
log-management platforms.

Security design:
- No inbound network listener.
- GitHub authentication is supplied at runtime.
- Authentication tokens are never written to collector logs.
- HTTPS certificate verification remains enabled.
- API responses are treated as untrusted structured input.
- Events are deduplicated using persistent SQLite state.
- Security endpoints that are unavailable for a repository do not
  terminate the collector.
- GitHub rate limits are handled without terminating the container.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sqlite3
import sys
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitHubCollectorError(Exception):
    """Base collector exception."""


class GitHubAuthenticationError(GitHubCollectorError):
    """GitHub authentication failed."""


class GitHubRateLimitError(GitHubCollectorError):
    """GitHub rate limit was reached."""

    def __init__(
        self,
        message: str,
        retry_after: int = 60,
    ) -> None:
        super().__init__(message)

        self.retry_after = max(
            retry_after,
            1,
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


GITHUB_USERNAME = os.getenv(
    "GITHUB_USERNAME",
    "",
).strip()

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
).strip()

GITHUB_API_URL = os.getenv(
    "GITHUB_API_URL",
    "https://api.github.com",
).rstrip("/")

POLL_INTERVAL = int(
    os.getenv(
        "POLL_INTERVAL",
        "300",
    )
)

REQUEST_TIMEOUT = int(
    os.getenv(
        "REQUEST_TIMEOUT",
        "20",
    )
)

MAX_PAGES = int(
    os.getenv(
        "MAX_PAGES",
        "10",
    )
)

LOG_FILE = Path(
    os.getenv(
        "GITHUB_LOG_FILE",
        "/var/log/github/events.jsonl",
    )
)

STATE_DATABASE = Path(
    os.getenv(
        "STATE_DATABASE",
        "/var/lib/github-logs-collector/state.db",
    )
)

LAST_SUCCESS_FILE = Path(
    os.getenv(
        "LAST_SUCCESS_FILE",
        "/var/lib/github-logs-collector/last_successful_poll",
    )
)

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


if not GITHUB_USERNAME:
    raise RuntimeError(
        "GITHUB_USERNAME is not configured"
    )

if not GITHUB_TOKEN:
    raise RuntimeError(
        "GITHUB_TOKEN is not configured"
    )

if POLL_INTERVAL < 60:
    raise RuntimeError(
        "POLL_INTERVAL must be at least 60 seconds"
    )

if REQUEST_TIMEOUT < 1:
    raise RuntimeError(
        "REQUEST_TIMEOUT must be at least 1 second"
    )

if MAX_PAGES < 1:
    raise RuntimeError(
        "MAX_PAGES must be at least 1"
    )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


logging.basicConfig(
    level=LOG_LEVEL,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "github-logs-collector"
)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


shutdown_requested = False


def handle_shutdown(
    signum: int,
    _frame: Any,
) -> None:
    global shutdown_requested

    logger.info(
        "Shutdown signal received signal=%s",
        signum,
    )

    shutdown_requested = True


signal.signal(
    signal.SIGTERM,
    handle_shutdown,
)

signal.signal(
    signal.SIGINT,
    handle_shutdown,
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def utc_timestamp() -> str:
    """
    Return current UTC timestamp in ISO 8601 format.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def sleep_interruptible(
    seconds: int,
) -> None:
    """
    Sleep while allowing container shutdown to complete promptly.
    """

    end_time = time.monotonic() + seconds

    while (
        not shutdown_requested
        and time.monotonic() < end_time
    ):
        remaining = (
            end_time
            - time.monotonic()
        )

        time.sleep(
            min(
                remaining,
                1.0,
            )
        )


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------


session = requests.Session()

session.headers.update(
    {
        "Authorization":
            f"Bearer {GITHUB_TOKEN}",

        "Accept":
            "application/vnd.github+json",

        "X-GitHub-Api-Version":
            "2022-11-28",

        "User-Agent":
            "github-logs-collector/0.2.1",
    }
)


# ---------------------------------------------------------------------------
# SQLite state
# ---------------------------------------------------------------------------


def initialise_database() -> sqlite3.Connection:
    """
    Open the persistent collector state database.

    Security:
    Only event IDs and collector state are stored here.
    Authentication credentials are never persisted.
    """

    STATE_DATABASE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        STATE_DATABASE
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_events (
            source TEXT NOT NULL,
            event_id TEXT NOT NULL,
            processed_at TEXT NOT NULL,
            PRIMARY KEY (source, event_id)
        )
        """
    )

    connection.commit()

    return connection


DB = initialise_database()


def event_seen(
    source: str,
    event_id: str,
) -> bool:
    """
    Return True if an event has already been processed.
    """

    row = DB.execute(
        """
        SELECT 1
        FROM processed_events
        WHERE source = ?
          AND event_id = ?
        """,
        (
            source,
            event_id,
        ),
    ).fetchone()

    return row is not None


def mark_event_seen(
    source: str,
    event_id: str,
) -> None:
    """
    Record an event as successfully processed.
    """

    DB.execute(
        """
        INSERT OR IGNORE INTO processed_events
        (
            source,
            event_id,
            processed_at
        )
        VALUES (?, ?, ?)
        """,
        (
            source,
            event_id,
            utc_timestamp(),
        ),
    )

    DB.commit()


# ---------------------------------------------------------------------------
# JSONL output
# ---------------------------------------------------------------------------


def write_event(
    event: dict[str, Any],
) -> None:
    """
    Append one compact JSON object to the JSONL event stream.
    """

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    line = json.dumps(
        event,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as log_handle:
        log_handle.write(
            line + "\n"
        )


def record_successful_poll() -> None:
    """
    Update persistent health state after a complete successful poll.
    """

    LAST_SUCCESS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    LAST_SUCCESS_FILE.write_text(
        utc_timestamp() + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# GitHub rate-limit handling
# ---------------------------------------------------------------------------


def calculate_retry_after(
    response: requests.Response,
) -> int:
    """
    Calculate how long to wait after GitHub rate limiting.
    """

    retry_after = response.headers.get(
        "Retry-After"
    )

    if retry_after:
        try:
            return max(
                int(retry_after),
                1,
            )

        except ValueError:
            pass

    reset = response.headers.get(
        "X-RateLimit-Reset"
    )

    if reset:
        try:
            reset_timestamp = int(
                reset
            )

            now = int(
                time.time()
            )

            return max(
                reset_timestamp
                - now
                + 1,
                1,
            )

        except ValueError:
            pass

    # GitHub recommends backing off when a secondary
    # limit is encountered without a usable reset value.
    return 60


def response_is_rate_limited(
    response: requests.Response,
) -> bool:
    """
    Determine whether a 403/429 response represents rate limiting.
    """

    if response.status_code == 429:
        return True

    if response.status_code != 403:
        return False

    remaining = response.headers.get(
        "X-RateLimit-Remaining"
    )

    if remaining == "0":
        return True

    if response.headers.get(
        "Retry-After"
    ):
        return True

    return False


# ---------------------------------------------------------------------------
# GitHub REST API
# ---------------------------------------------------------------------------


def github_get(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    """
    Perform a GitHub REST API GET request.

    Security:
    - TLS verification remains enabled.
    - Authentication headers are never logged.
    - Response bodies are not logged automatically.
    """

    url = (
        f"{GITHUB_API_URL}{endpoint}"
    )

    response = session.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    remaining = response.headers.get(
        "X-RateLimit-Remaining"
    )

    limit = response.headers.get(
        "X-RateLimit-Limit"
    )

    reset = response.headers.get(
        "X-RateLimit-Reset"
    )

    logger.debug(
        "GitHub API "
        "status=%s "
        "rate_limit=%s "
        "rate_remaining=%s "
        "rate_reset=%s "
        "endpoint=%s",
        response.status_code,
        limit,
        remaining,
        reset,
        endpoint,
    )

    if response.status_code == 401:
        raise GitHubAuthenticationError(
            "GitHub authentication failed"
        )

    if response_is_rate_limited(
        response
    ):
        retry_after = (
            calculate_retry_after(
                response
            )
        )

        raise GitHubRateLimitError(
            (
                "GitHub API rate limit reached "
                f"status={response.status_code}"
            ),
            retry_after=retry_after,
        )

    response.raise_for_status()

    return response


# ---------------------------------------------------------------------------
# Identity verification
# ---------------------------------------------------------------------------


def verify_identity() -> None:
    """
    Confirm that the access token authenticates as GITHUB_USERNAME.
    """

    response = github_get(
        "/user"
    )

    user = response.json()

    if not isinstance(
        user,
        dict,
    ):
        raise GitHubCollectorError(
            "Unexpected GitHub identity response"
        )

    authenticated_login = str(
        user.get(
            "login",
            "",
        )
    ).strip()

    if not authenticated_login:
        raise GitHubCollectorError(
            "GitHub identity response did not contain login"
        )

    if (
        authenticated_login.lower()
        != GITHUB_USERNAME.lower()
    ):
        raise GitHubCollectorError(
            (
                "Authenticated GitHub account "
                "does not match GITHUB_USERNAME"
            )
        )

    logger.info(
        "Authenticated to GitHub as %s",
        authenticated_login,
    )


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------


def get_repositories() -> list[dict[str, Any]]:
    """
    Enumerate repositories visible to the authenticated account.
    """

    repositories: list[
        dict[str, Any]
    ] = []

    for page in range(
        1,
        MAX_PAGES + 1,
    ):

        response = github_get(
            "/user/repos",
            params={
                "visibility": "all",
                "affiliation":
                    "owner,collaborator,organization_member",
                "per_page": 100,
                "page": page,
                "sort": "updated",
            },
        )

        batch = response.json()

        if not isinstance(
            batch,
            list,
        ):
            raise GitHubCollectorError(
                "Unexpected repository API response"
            )

        repositories.extend(
            item
            for item in batch
            if isinstance(
                item,
                dict,
            )
        )

        if len(batch) < 100:
            break

    return repositories


# ---------------------------------------------------------------------------
# Account activity collection
# ---------------------------------------------------------------------------


def collect_account_events() -> int:
    """
    Collect authenticated-user GitHub activity.

    GitHub may return events already observed during earlier poll cycles;
    SQLite state prevents duplicate JSONL output.
    """

    collected = 0

    for page in range(
        1,
        MAX_PAGES + 1,
    ):

        response = github_get(
            (
                f"/users/"
                f"{GITHUB_USERNAME}"
                f"/events"
            ),
            params={
                "per_page": 100,
                "page": page,
            },
        )

        events = response.json()

        if not isinstance(
            events,
            list,
        ):
            raise GitHubCollectorError(
                "Unexpected account events response"
            )

        # Oldest first produces chronological JSONL output
        # within the fetched batch.
        for event in reversed(
            events
        ):

            if not isinstance(
                event,
                dict,
            ):
                continue

            event_id = str(
                event.get(
                    "id",
                    "",
                )
            ).strip()

            if not event_id:
                continue

            source = (
                "github_account_event"
            )

            if event_seen(
                source,
                event_id,
            ):
                continue

            actor = (
                event.get(
                    "actor"
                )
                or {}
            )

            repo = (
                event.get(
                    "repo"
                )
                or {}
            )

            output = {
                "@timestamp":
                    event.get(
                        "created_at"
                    )
                    or utc_timestamp(),

                "collector": {
                    "name":
                        "github-logs-collector",

                    "mode":
                        "poll",
                },

                "source": {
                    "type":
                        "github",

                    "dataset":
                        "account_event",
                },

                "github": {
                    "event_id":
                        event_id,

                    "event":
                        event.get(
                            "type"
                        ),

                    "repository":
                        repo.get(
                            "name"
                        )
                        if isinstance(
                            repo,
                            dict,
                        )
                        else None,

                    "actor":
                        actor.get(
                            "login"
                        )
                        if isinstance(
                            actor,
                            dict,
                        )
                        else None,

                    "public":
                        event.get(
                            "public"
                        ),
                },

                "payload":
                    event,
            }

            write_event(
                output
            )

            mark_event_seen(
                source,
                event_id,
            )

            collected += 1

        if len(events) < 100:
            break

    return collected


# ---------------------------------------------------------------------------
# Repository security collection
# ---------------------------------------------------------------------------


SECURITY_ENDPOINTS = {
    "dependabot":
        "dependabot/alerts",

    "code_scanning":
        "code-scanning/alerts",

    "secret_scanning":
        "secret-scanning/alerts",
}


def collect_security_endpoint(
    repository_name: str,
    alert_type: str,
    endpoint: str,
) -> int:
    """
    Collect one type of security alert from one repository.

    403 and 404 are treated as an unavailable feature or insufficient
    permission for that repository rather than as a collector failure.
    """

    collected = 0

    for page in range(
        1,
        MAX_PAGES + 1,
    ):

        try:
            response = github_get(
                (
                    f"/repos/"
                    f"{repository_name}/"
                    f"{endpoint}"
                ),
                params={
                    "per_page": 100,
                    "page": page,
                    "state": "open",
                },
            )

        except requests.HTTPError as exc:

            status = (
                exc.response.status_code
                if exc.response
                is not None
                else None
            )

            if status in (
                403,
                404,
            ):
                logger.info(
                    "Skipping unavailable security API "
                    "repository=%s "
                    "type=%s "
                    "status=%s",
                    repository_name,
                    alert_type,
                    status,
                )

                return collected

            raise

        alerts = response.json()

        if not isinstance(
            alerts,
            list,
        ):
            logger.warning(
                "Unexpected security API response "
                "repository=%s "
                "type=%s",
                repository_name,
                alert_type,
            )

            return collected

        for alert in alerts:

            if not isinstance(
                alert,
                dict,
            ):
                continue

            number = alert.get(
                "number"
            )

            if number is None:
                continue

            event_id = (
                f"{repository_name}:"
                f"{alert_type}:"
                f"{number}"
            )

            source = (
                "github_security_alert"
            )

            if event_seen(
                source,
                event_id,
            ):
                continue

            output = {
                "@timestamp":
                    alert.get(
                        "created_at"
                    )
                    or utc_timestamp(),

                "collector": {
                    "name":
                        "github-logs-collector",

                    "mode":
                        "poll",
                },

                "source": {
                    "type":
                        "github",

                    "dataset":
                        "security_alert",
                },

                "github": {
                    "event_id":
                        event_id,

                    "event":
                        alert_type,

                    "repository":
                        repository_name,

                    "alert_number":
                        number,

                    "state":
                        alert.get(
                            "state"
                        ),
                },

                "payload":
                    alert,
            }

            write_event(
                output
            )

            mark_event_seen(
                source,
                event_id,
            )

            collected += 1

        if len(alerts) < 100:
            break

    return collected


def collect_security_alerts(
    repository: dict[str, Any],
) -> int:
    """
    Collect all supported security alert categories for one repository.
    """

    full_name = str(
        repository.get(
            "full_name",
            "",
        )
    ).strip()

    if not full_name:
        return 0

    collected = 0

    for (
        alert_type,
        endpoint
    ) in SECURITY_ENDPOINTS.items():

        if shutdown_requested:
            break

        try:
            collected += (
                collect_security_endpoint(
                    full_name,
                    alert_type,
                    endpoint,
                )
            )

        except GitHubRateLimitError:
            # Rate limits must propagate to the poll loop so
            # the entire collector backs off.
            raise

        except requests.RequestException as exc:
            logger.warning(
                "Security API request failed "
                "repository=%s "
                "type=%s "
                "error=%s",
                full_name,
                alert_type,
                type(exc).__name__,
            )

        except Exception:
            # One problematic repository or security API must
            # not terminate the entire collection cycle.
            logger.exception(
                "Security collector failed "
                "repository=%s "
                "type=%s",
                full_name,
                alert_type,
            )

    return collected


# ---------------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------------


def poll() -> None:
    """
    Run one complete GitHub collection cycle.
    """

    logger.info(
        "Starting polling cycle"
    )

    account_events = (
        collect_account_events()
    )

    repositories = (
        get_repositories()
    )

    security_events = 0

    for repository in repositories:

        if shutdown_requested:
            break

        security_events += (
            collect_security_alerts(
                repository
            )
        )

    if shutdown_requested:
        return

    record_successful_poll()

    logger.info(
        "Poll complete "
        "account_events=%d "
        "repositories=%d "
        "security_events=%d",
        account_events,
        len(repositories),
        security_events,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Main collector loop.

    Runtime API failures are logged and retried rather than terminating
    the container.
    """

    logger.info(
        "GitHub Logs Collector starting"
    )

    # Authentication is retried instead of allowing a temporary
    # GitHub/network failure to cause a Docker restart loop.
    while not shutdown_requested:

        try:
            verify_identity()
            break

        except GitHubRateLimitError as exc:
            logger.warning(
                "GitHub rate limited during authentication; "
                "retrying in %ss",
                exc.retry_after,
            )

            sleep_interruptible(
                exc.retry_after
            )

        except GitHubAuthenticationError as exc:
            logger.error(
                "%s; retrying in 60s",
                exc,
            )

            sleep_interruptible(
                60
            )

        except requests.RequestException as exc:
            logger.error(
                "GitHub connection failure during authentication "
                "error=%s; retrying in 60s",
                type(exc).__name__,
            )

            sleep_interruptible(
                60
            )

        except Exception:
            logger.exception(
                "GitHub identity verification failed; "
                "retrying in 60s"
            )

            sleep_interruptible(
                60
            )

    if shutdown_requested:
        return

    logger.info(
        "Starting GitHub polling collector interval=%ss",
        POLL_INTERVAL,
    )

    while not shutdown_requested:

        cycle_started = time.monotonic()

        try:
            poll()

        except GitHubRateLimitError as exc:
            logger.warning(
                "GitHub API rate limit reached; "
                "backing off for %ss",
                exc.retry_after,
            )

            sleep_interruptible(
                exc.retry_after
            )

            continue

        except GitHubAuthenticationError:
            logger.error(
                "GitHub authentication failed during polling; "
                "retrying in 60s"
            )

            sleep_interruptible(
                60
            )

            continue

        except requests.Timeout:
            logger.warning(
                "GitHub API request timed out; "
                "polling will continue"
            )

        except requests.RequestException as exc:
            logger.warning(
                "GitHub API communication failure "
                "error=%s; polling will continue",
                type(exc).__name__,
            )

        except sqlite3.Error:
            logger.exception(
                "SQLite state operation failed; "
                "polling will continue"
            )

        except OSError:
            logger.exception(
                "Filesystem operation failed; "
                "polling will continue"
            )

        except Exception:
            # Last-resort safety net:
            # a single unexpected polling error must not terminate
            # the long-running collector process.
            logger.exception(
                "Collector polling cycle failed; "
                "polling will continue"
            )

        if shutdown_requested:
            break

        elapsed = int(
            time.monotonic()
            - cycle_started
        )

        wait_time = max(
            POLL_INTERVAL - elapsed,
            1,
        )

        sleep_interruptible(
            wait_time
        )

    logger.info(
        "GitHub Logs Collector stopped"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":

    try:
        main()

    finally:
        try:
            DB.close()

        except Exception:
            pass

        session.close()
