#!/usr/bin/env python3

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


COLLECTOR_NAME = "github-logs-collector"
COLLECTOR_VERSION = "0.2.3"


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
# Environment helpers
# ---------------------------------------------------------------------------


def env_bool(
    name: str,
    default: bool,
) -> bool:
    """Read a strict boolean environment variable."""

    raw = os.getenv(
        name,
        "true" if default else "false",
    ).strip().lower()

    if raw in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if raw in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise RuntimeError(
        f"{name} must be true or false"
    )


def env_int(
    name: str,
    default: int,
    minimum: int,
) -> int:
    """Read and validate an integer environment variable."""

    try:
        value = int(
            os.getenv(
                name,
                str(default),
            )
        )

    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be an integer"
        ) from exc

    if value < minimum:
        raise RuntimeError(
            f"{name} must be at least {minimum}"
        )

    return value


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

POLL_INTERVAL = env_int(
    "POLL_INTERVAL",
    300,
    60,
)

REQUEST_TIMEOUT = env_int(
    "REQUEST_TIMEOUT",
    20,
    1,
)

MAX_PAGES = env_int(
    "MAX_PAGES",
    10,
    1,
)

ACTIONS_MAX_RUNS_PER_REPOSITORY = env_int(
    "ACTIONS_MAX_RUNS_PER_REPOSITORY",
    20,
    1,
)

LOG_FILE = Path(
    os.getenv(
        "GITHUB_LOG_FILE",
        "/var/log/github/events.jsonl",
    )
)

COLLECTOR_LOG_FILE = Path(
    os.getenv(
        "COLLECTOR_LOG_FILE",
        "/var/log/github/collector.jsonl",
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

GITHUB_ACCOUNT_EVENTS_ENABLED = env_bool(
    "GITHUB_ACCOUNT_EVENTS_ENABLED",
    True,
)

GITHUB_SECURITY_ALERTS_ENABLED = env_bool(
    "GITHUB_SECURITY_ALERTS_ENABLED",
    True,
)

GITHUB_ACTIONS_ENABLED = env_bool(
    "GITHUB_ACTIONS_ENABLED",
    True,
)

GITHUB_ACTION_FAILURE_DETAILS_ENABLED = env_bool(
    "GITHUB_ACTION_FAILURE_DETAILS_ENABLED",
    True,
)

GITHUB_REPOSITORY_SECURITY_STATE_ENABLED = env_bool(
    "GITHUB_REPOSITORY_SECURITY_STATE_ENABLED",
    True,
)

COLLECTOR_OPERATIONAL_LOG_ENABLED = env_bool(
    "COLLECTOR_OPERATIONAL_LOG_ENABLED",
    True,
)


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
    COLLECTOR_NAME
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
    """Return current UTC timestamp in ISO 8601 format."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def sleep_interruptible(
    seconds: int,
) -> None:
    """Sleep while still allowing prompt container shutdown."""

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


def safe_dict(
    value: Any,
) -> dict[str, Any]:
    """Return a dictionary for untrusted structured input."""

    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def safe_list(
    value: Any,
) -> list[Any]:
    """Return a list for untrusted structured input."""

    if isinstance(
        value,
        list,
    ):
        return value

    return []


def build_event(
    *,
    timestamp: str | None,
    dataset: str,
    github: dict[str, Any] | None = None,
    event: dict[str, Any] | None = None,
    payload: Any = None,
) -> dict[str, Any]:
    """Build the common SIEM-oriented event envelope."""

    output: dict[str, Any] = {
        "@timestamp":
            timestamp
            or utc_timestamp(),

        "collector": {
            "name":
                COLLECTOR_NAME,

            "version":
                COLLECTOR_VERSION,

            "mode":
                "poll",
        },

        "source": {
            "type":
                "github",

            "dataset":
                dataset,
        },
    }

    if event:
        output["event"] = event

    if github:
        output["github"] = github

    if payload is not None:
        output["payload"] = payload

    return output


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
            f"{COLLECTOR_NAME}/{COLLECTOR_VERSION}",
    }
)


# ---------------------------------------------------------------------------
# SQLite state
# ---------------------------------------------------------------------------


def initialise_database() -> sqlite3.Connection:
    """
    Open the persistent collector state database.

    Security:
    Only event IDs and non-secret collector state are persisted.
    Authentication credentials are never stored.
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

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS collector_state (
            state_key TEXT PRIMARY KEY,
            state_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
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
    """Return True if an event has already been processed."""

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
    """Record an event as successfully processed."""

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


def get_state(
    state_key: str,
) -> Any | None:
    """Read JSON state from persistent collector storage."""

    row = DB.execute(
        """
        SELECT state_value
        FROM collector_state
        WHERE state_key = ?
        """,
        (
            state_key,
        ),
    ).fetchone()

    if row is None:
        return None

    try:
        return json.loads(
            row[0]
        )

    except (
        TypeError,
        json.JSONDecodeError,
    ):
        logger.warning(
            "Invalid collector state key=%s; replacing baseline",
            state_key,
        )

        return None


def set_state(
    state_key: str,
    value: Any,
) -> None:
    """Persist JSON state."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    DB.execute(
        """
        INSERT INTO collector_state
        (
            state_key,
            state_value,
            updated_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(state_key)
        DO UPDATE SET
            state_value = excluded.state_value,
            updated_at = excluded.updated_at
        """,
        (
            state_key,
            encoded,
            utc_timestamp(),
        ),
    )

    DB.commit()


# ---------------------------------------------------------------------------
# JSONL output
# ---------------------------------------------------------------------------


def append_jsonl(
    path: Path,
    event: dict[str, Any],
) -> None:
    """Append one compact JSON object to a JSONL file."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    line = json.dumps(
        event,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as log_handle:
        log_handle.write(
            line + "\n"
        )


def write_event(
    event: dict[str, Any],
) -> None:
    """Append one event to the main SIEM event stream."""

    append_jsonl(
        LOG_FILE,
        event,
    )


def write_new_event(
    source: str,
    event_id: str,
    output: dict[str, Any],
) -> bool:
    """
    Write a new event and mark it processed only after a successful write.
    """

    if event_seen(
        source,
        event_id,
    ):
        return False

    write_event(
        output
    )

    mark_event_seen(
        source,
        event_id,
    )

    return True


def write_operational_event(
    level: str,
    event_name: str,
    message: str,
    **details: Any,
) -> None:
    """
    Write collector operational telemetry to a separate JSONL stream.

    This stream is suitable for SIEM health/error monitoring without mixing
    collector runtime problems into GitHub activity telemetry.
    """

    if not COLLECTOR_OPERATIONAL_LOG_ENABLED:
        return

    output: dict[str, Any] = {
        "@timestamp":
            utc_timestamp(),

        "collector": {
            "name":
                COLLECTOR_NAME,

            "version":
                COLLECTOR_VERSION,

            "mode":
                "poll",
        },

        "source": {
            "type":
                "collector",

            "dataset":
                "operational",
        },

        "log": {
            "level":
                level.lower(),

            "event":
                event_name,
        },

        "message":
            message,
    }

    if details:
        output["details"] = details

    try:
        append_jsonl(
            COLLECTOR_LOG_FILE,
            output,
        )

    except OSError:
        logger.exception(
            "Failed to write collector operational event"
        )


def record_successful_poll() -> None:
    """Update persistent health state after a complete successful poll."""

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
    """Calculate how long to wait after GitHub rate limiting."""

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

    return 60


def response_is_rate_limited(
    response: requests.Response,
) -> bool:
    """Determine whether a 403/429 response represents rate limiting."""

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


def github_optional_get(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> requests.Response | None:
    """
    Query an optional endpoint.

    HTTP 403/404 are treated as disabled/unavailable/insufficient-read-access
    for that repository. Rate-limit 403 responses have already been converted
    to GitHubRateLimitError by github_get().
    """

    try:
        return github_get(
            endpoint,
            params=params,
        )

    except requests.HTTPError as exc:
        status = (
            exc.response.status_code
            if exc.response is not None
            else None
        )

        if status in {
            403,
            404,
        }:
            return None

        raise


# ---------------------------------------------------------------------------
# Identity verification
# ---------------------------------------------------------------------------


def verify_identity() -> None:
    """Confirm that the token authenticates as GITHUB_USERNAME."""

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

    write_operational_event(
        "info",
        "github_authentication_success",
        "GitHub API authentication succeeded",
        github_username=authenticated_login,
    )


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------


def get_repositories() -> list[dict[str, Any]]:
    """Enumerate repositories visible to the authenticated account."""

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
                "visibility":
                    "all",

                "affiliation":
                    "owner,collaborator,organization_member",

                "per_page":
                    100,

                "page":
                    page,

                "sort":
                    "updated",
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

    Existing event types include PushEvent, PullRequestEvent, IssuesEvent,
    IssueCommentEvent, CreateEvent, DeleteEvent, ReleaseEvent, ForkEvent,
    WatchEvent, and any other event types GitHub returns for the account.
    """

    if not GITHUB_ACCOUNT_EVENTS_ENABLED:
        return 0

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
                "per_page":
                    100,

                "page":
                    page,
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

        # Oldest first within the fetched batch.
        for item in reversed(
            events
        ):
            if not isinstance(
                item,
                dict,
            ):
                continue

            event_id = str(
                item.get(
                    "id",
                    "",
                )
            ).strip()

            if not event_id:
                continue

            actor = safe_dict(
                item.get(
                    "actor"
                )
            )

            repo = safe_dict(
                item.get(
                    "repo"
                )
            )

            org = safe_dict(
                item.get(
                    "org"
                )
            )

            payload = safe_dict(
                item.get(
                    "payload"
                )
            )

            output = build_event(
                timestamp=(
                    item.get(
                        "created_at"
                    )
                    or utc_timestamp()
                ),
                dataset="account_event",
                github={
                    "event_id":
                        event_id,

                    "event":
                        item.get(
                            "type"
                        ),

                    "repo":
                        repo.get(
                            "name"
                        ),

		    "repository":
                        repo.get(
                            "name"
                        ),

                    "actor":
                        actor.get(
                            "login"
                        ),

                    "organization":
                        org.get(
                            "login"
                        ),

                    "public":
                        item.get(
                            "public"
                        ),

                    "action":
                        payload.get(
                            "action"
                        ),

                    "ref":
                        payload.get(
                            "ref"
                        ),

                    "before":
                        payload.get(
                            "before"
                        ),

                    "after":
                        payload.get(
                            "after"
                        ),
                },
                event={
                    "category":
                        "repository",

                    "type":
                        str(
                            item.get(
                                "type",
                                "unknown",
                            )
                        ),
                },
                payload=item,
            )

            if write_new_event(
                "github_account_event",
                event_id,
                output,
            ):
                collected += 1

        if len(events) < 100:
            break

    return collected


# ---------------------------------------------------------------------------
# Repository security alert collection
# ---------------------------------------------------------------------------


SECURITY_ENDPOINTS = {
    "dependabot":
        "dependabot/alerts",

    "code_scanning":
        "code-scanning/alerts",

    "secret_scanning":
        "secret-scanning/alerts",
}


def alert_event_timestamp(
    alert: dict[str, Any],
) -> str:
    """Choose the best available lifecycle timestamp for an alert."""

    for field in (
        "updated_at",
        "dismissed_at",
        "fixed_at",
        "resolved_at",
        "created_at",
    ):
        value = alert.get(
            field
        )

        if value:
            return str(
                value
            )

    return utc_timestamp()


def alert_lifecycle_id(
    repository_name: str,
    alert_type: str,
    alert: dict[str, Any],
) -> str | None:
    """Build an ID that changes when an alert's lifecycle state changes."""

    number = alert.get(
        "number"
    )

    if number is None:
        return None

    state = alert.get(
        "state"
    )

    timestamp = alert_event_timestamp(
        alert
    )

    return (
        f"{repository_name}:"
        f"{alert_type}:"
        f"{number}:"
        f"{state}:"
        f"{timestamp}"
    )


def collect_security_endpoint(
    repository_name: str,
    alert_type: str,
    endpoint: str,
) -> int:
    """
    Collect one security-alert type for one repository.

    No state filter is sent, allowing GitHub to return lifecycle states that
    the endpoint makes available instead of restricting collection to only
    currently-open alerts.
    """

    collected = 0

    for page in range(
        1,
        MAX_PAGES + 1,
    ):
        response = github_optional_get(
            (
                f"/repos/"
                f"{repository_name}/"
                f"{endpoint}"
            ),
            params={
                "per_page":
                    100,

                "page":
                    page,
            },
        )

        if response is None:
            logger.info(
                "Skipping unavailable security API "
                "repository=%s type=%s",
                repository_name,
                alert_type,
            )

            return collected

        alerts = response.json()

        if not isinstance(
            alerts,
            list,
        ):
            logger.warning(
                "Unexpected security API response "
                "repository=%s type=%s",
                repository_name,
                alert_type,
            )

            write_operational_event(
                "warning",
                "unexpected_security_api_response",
                "Unexpected GitHub security API response",
                repository=repository_name,
                alert_type=alert_type,
            )

            return collected

        for alert in alerts:
            if not isinstance(
                alert,
                dict,
            ):
                continue

            event_id = alert_lifecycle_id(
                repository_name,
                alert_type,
                alert,
            )

            if event_id is None:
                continue

            number = alert.get(
                "number"
            )

            state = alert.get(
                "state"
            )

            output = build_event(
                timestamp=alert_event_timestamp(
                    alert
                ),
                dataset="security_alert",
                github={
                    "event_id":
                        event_id,

                    "event":
                        alert_type,

		    "repo":
			repository_name,

                    "repository":
                        repository_name,

                    "alert_number":
                        number,

                    "state":
                        state,
                },
                event={
                    "category":
                        "security",

                    "type":
                        "alert",

                    "action":
                        str(
                            state
                            or "observed"
                        ),
                },
                payload=alert,
            )

            if write_new_event(
                "github_security_alert",
                event_id,
                output,
            ):
                collected += 1

        if len(alerts) < 100:
            break

    return collected


def collect_security_alerts(
    repository: dict[str, Any],
) -> int:
    """Collect supported GitHub security alerts for one repository."""

    if not GITHUB_SECURITY_ALERTS_ENABLED:
        return 0

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
        endpoint,
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
            raise

        except requests.RequestException as exc:
            logger.warning(
                "Security API request failed "
                "repository=%s type=%s error=%s",
                full_name,
                alert_type,
                type(exc).__name__,
            )

            write_operational_event(
                "warning",
                "security_api_request_failed",
                "GitHub security API request failed",
                repository=full_name,
                alert_type=alert_type,
                error_type=type(exc).__name__,
            )

        except Exception:
            logger.exception(
                "Security collector failed "
                "repository=%s type=%s",
                full_name,
                alert_type,
            )

            write_operational_event(
                "error",
                "security_collector_failed",
                "GitHub security collector failed",
                repository=full_name,
                alert_type=alert_type,
            )

    return collected


# ---------------------------------------------------------------------------
# GitHub Actions security telemetry
# ---------------------------------------------------------------------------


ABNORMAL_ACTION_CONCLUSIONS = {
    "failure",
    "cancelled",
    "timed_out",
    "stale",
    "action_required",
    "startup_failure",
}


def collect_abnormal_workflow_jobs(
    repository_name: str,
    run_id: int,
    run_attempt: int,
) -> int:
    """
    Collect only security/operationally interesting failed workflow details.

    Successful jobs and steps are intentionally not emitted as separate events
    because the workflow-run event already records successful execution.
    """

    if not GITHUB_ACTION_FAILURE_DETAILS_ENABLED:
        return 0

    collected = 0

    for page in range(
        1,
        MAX_PAGES + 1,
    ):
        response = github_optional_get(
            (
                f"/repos/{repository_name}"
                f"/actions/runs/{run_id}/jobs"
            ),
            params={
                "per_page":
                    100,

                "page":
                    page,
            },
        )

        if response is None:
            return collected

        body = response.json()

        if not isinstance(
            body,
            dict,
        ):
            return collected

        jobs = safe_list(
            body.get(
                "jobs"
            )
        )

        for job in jobs:
            if not isinstance(
                job,
                dict,
            ):
                continue

            job_conclusion = str(
                job.get(
                    "conclusion"
                )
                or ""
            ).strip()

            steps = safe_list(
                job.get(
                    "steps"
                )
            )

            abnormal_steps = []

            for step in steps:
                if not isinstance(
                    step,
                    dict,
                ):
                    continue

                step_conclusion = str(
                    step.get(
                        "conclusion"
                    )
                    or ""
                ).strip()

                if (
                    step_conclusion
                    not in ABNORMAL_ACTION_CONCLUSIONS
                ):
                    continue

                abnormal_steps.append(
                    {
                        "number":
                            step.get(
                                "number"
                            ),

                        "name":
                            step.get(
                                "name"
                            ),

                        "status":
                            step.get(
                                "status"
                            ),

                        "conclusion":
                            step.get(
                                "conclusion"
                            ),

                        "started_at":
                            step.get(
                                "started_at"
                            ),

                        "completed_at":
                            step.get(
                                "completed_at"
                            ),
                    }
                )

            if (
                job_conclusion
                not in ABNORMAL_ACTION_CONCLUSIONS
                and not abnormal_steps
            ):
                continue

            job_id = job.get(
                "id"
            )

            if job_id is None:
                continue

            event_id = (
                f"{repository_name}:"
                f"{run_id}:"
                f"{run_attempt}:"
                f"{job_id}:"
                f"{job_conclusion}:"
                f"{job.get('completed_at')}"
            )

            output = build_event(
                timestamp=(
                    job.get(
                        "completed_at"
                    )
                    or job.get(
                        "started_at"
                    )
                    or utc_timestamp()
                ),
                dataset="actions_job_failure",
                github={
                    "repo":
                        repository_name,

                    "repository":
                        repository_name,

                    "workflow_run_id":
                        run_id,

                    "run_attempt":
                        run_attempt,

                    "job_id":
                        job_id,

                    "job_name":
                        job.get(
                            "name"
                        ),

                    "status":
                        job.get(
                            "status"
                        ),

                    "conclusion":
                        job.get(
                            "conclusion"
                        ),

                    "runner_name":
                        job.get(
                            "runner_name"
                        ),

                    "runner_group_name":
                        job.get(
                            "runner_group_name"
                        ),

                    "abnormal_steps":
                        abnormal_steps,
                },
                event={
                    "category":
                        "ci_cd",

                    "type":
                        "workflow_job",

                    "action":
                        "abnormal_completion",

                    "outcome":
                        job.get(
                            "conclusion"
                        ),
                },
                payload=job,
            )

            if write_new_event(
                "github_actions_job_failure",
                event_id,
                output,
            ):
                collected += 1

        if len(jobs) < 100:
            break

    return collected


def collect_workflow_runs(
    repository_name: str,
) -> tuple[int, int]:
    """
    Collect workflow run changes for a repository.

    Every workflow run state/conclusion change is logged. Detailed job/step
    events are fetched only when a completed run has an abnormal conclusion.
    """

    if not GITHUB_ACTIONS_ENABLED:
        return (
            0,
            0,
        )

    runs_collected = 0
    abnormal_jobs_collected = 0

    response = github_optional_get(
        (
            f"/repos/{repository_name}"
            f"/actions/runs"
        ),
        params={
            "per_page":
                min(
                    ACTIONS_MAX_RUNS_PER_REPOSITORY,
                    100,
                ),
        },
    )

    if response is None:
        return (
            0,
            0,
        )

    body = response.json()

    if not isinstance(
        body,
        dict,
    ):
        return (
            0,
            0,
        )

    runs = safe_list(
        body.get(
            "workflow_runs"
        )
    )

    for run in runs[
        :ACTIONS_MAX_RUNS_PER_REPOSITORY
    ]:
        if not isinstance(
            run,
            dict,
        ):
            continue

        run_id = run.get(
            "id"
        )

        if run_id is None:
            continue

        try:
            run_attempt = int(
                run.get(
                    "run_attempt"
                )
                or 1
            )

        except (
            TypeError,
            ValueError,
        ):
            run_attempt = 1

        status = str(
            run.get(
                "status"
            )
            or ""
        ).strip()

        conclusion = str(
            run.get(
                "conclusion"
            )
            or ""
        ).strip()

        updated_at = (
            run.get(
                "updated_at"
            )
            or run.get(
                "run_started_at"
            )
            or run.get(
                "created_at"
            )
            or utc_timestamp()
        )

        event_id = (
            f"{repository_name}:"
            f"{run_id}:"
            f"{run_attempt}:"
            f"{status}:"
            f"{conclusion}:"
            f"{updated_at}"
        )

        actor = safe_dict(
            run.get(
                "actor"
            )
        )

        triggering_actor = safe_dict(
            run.get(
                "triggering_actor"
            )
        )

        head_repository = safe_dict(
            run.get(
                "head_repository"
            )
        )

        output = build_event(
            timestamp=str(
                updated_at
            ),
            dataset="actions_workflow_run",
            github={
                "repo":
                    repository_name,

                "repository":
                    repository_name,

                "workflow_run_id":
                    run_id,

                "workflow_id":
                    run.get(
                        "workflow_id"
                    ),

                "workflow_name":
                    run.get(
                        "name"
                    ),

                "run_number":
                    run.get(
                        "run_number"
                    ),

                "run_attempt":
                    run_attempt,

                "trigger_event":
                    run.get(
                        "event"
                    ),

                "status":
                    status,

                "conclusion":
                    conclusion
                    or None,

                "head_branch":
                    run.get(
                        "head_branch"
                    ),

                "head_sha":
                    run.get(
                        "head_sha"
                    ),

                "head_repository":
                    head_repository.get(
                        "full_name"
                    ),

                "actor":
                    actor.get(
                        "login"
                    ),

                "triggering_actor":
                    triggering_actor.get(
                        "login"
                    ),

                "html_url":
                    run.get(
                        "html_url"
                    ),
            },
            event={
                "category":
                    "ci_cd",

                "type":
                    "workflow_run",

                "action":
                    status
                    or "observed",

                "outcome":
                    conclusion
                    or None,
            },
            payload=run,
        )

        changed = write_new_event(
            "github_actions_workflow_run",
            event_id,
            output,
        )

        if not changed:
            continue

        runs_collected += 1

        if (
            status == "completed"
            and conclusion
            in ABNORMAL_ACTION_CONCLUSIONS
        ):
            try:
                abnormal_jobs_collected += (
                    collect_abnormal_workflow_jobs(
                        repository_name,
                        int(
                            run_id
                        ),
                        run_attempt,
                    )
                )

            except GitHubRateLimitError:
                raise

            except requests.RequestException as exc:
                logger.warning(
                    "Actions job-detail request failed "
                    "repository=%s run_id=%s error=%s",
                    repository_name,
                    run_id,
                    type(exc).__name__,
                )

                write_operational_event(
                    "warning",
                    "actions_job_detail_failed",
                    "GitHub Actions job-detail request failed",
                    repository=repository_name,
                    workflow_run_id=run_id,
                    error_type=type(exc).__name__,
                )

    return (
        runs_collected,
        abnormal_jobs_collected,
    )


# ---------------------------------------------------------------------------
# Repository security-state collection
# ---------------------------------------------------------------------------


def repository_security_state(
    repository: dict[str, Any],
) -> dict[str, Any]:
    """Extract only repository attributes with clear security relevance."""

    return {
        "visibility":
            repository.get(
                "visibility"
            ),

        "private":
            repository.get(
                "private"
            ),

        "archived":
            repository.get(
                "archived"
            ),

        "default_branch":
            repository.get(
                "default_branch"
            ),
    }


def collect_repository_security_state(
    repository: dict[str, Any],
) -> int:
    """
    Detect repository security-state changes.

    The first observation creates a baseline without emitting an alert. Future
    differences emit one event containing only changed fields with before/after
    values.
    """

    if not GITHUB_REPOSITORY_SECURITY_STATE_ENABLED:
        return 0

    full_name = str(
        repository.get(
            "full_name",
            "",
        )
    ).strip()

    if not full_name:
        return 0

    current = repository_security_state(
        repository
    )

    state_key = (
        "repository_security_state:"
        f"{full_name}"
    )

    previous = get_state(
        state_key
    )

    if not isinstance(
        previous,
        dict,
    ):
        set_state(
            state_key,
            current,
        )

        logger.debug(
            "Repository security baseline created repository=%s",
            full_name,
        )

        return 0

    changes: dict[str, Any] = {}

    for field in (
        "visibility",
        "private",
        "archived",
        "default_branch",
    ):
        before = previous.get(
            field
        )

        after = current.get(
            field
        )

        if before == after:
            continue

        changes[field] = {
            "before":
                before,

            "after":
                after,
        }

    if not changes:
        return 0

    output = build_event(
        timestamp=utc_timestamp(),
        dataset="repository_security_state",
        github={
            "repo":
		full_name,

	    "repository":
                full_name,

            "changes":
                changes,

            "current":
                current,
        },
        event={
            "category":
                "repository",

            "type":
                "security_state",

            "action":
                "changed",
        },
    )

    write_event(
        output
    )

    # Update the baseline only after the event has been written successfully.
    set_state(
        state_key,
        current,
    )

    logger.warning(
        "Repository security state changed repository=%s fields=%s",
        full_name,
        ",".join(
            sorted(
                changes.keys()
            )
        ),
    )

    return 1


# ---------------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------------


def poll() -> None:
    """Run one complete security-focused GitHub collection cycle."""

    logger.info(
        "Starting polling cycle"
    )

    cycle_started = time.monotonic()

    account_events = (
        collect_account_events()
    )

    repositories = (
        get_repositories()
    )

    security_events = 0
    workflow_runs = 0
    abnormal_action_jobs = 0
    repository_security_changes = 0

    for repository in repositories:
        if shutdown_requested:
            break

        full_name = str(
            repository.get(
                "full_name",
                "",
            )
        ).strip()

        if not full_name:
            continue

        try:
            repository_security_changes += (
                collect_repository_security_state(
                    repository
                )
            )

        except sqlite3.Error:
            raise

        except OSError:
            raise

        except Exception:
            logger.exception(
                "Repository security-state collection failed "
                "repository=%s",
                full_name,
            )

            write_operational_event(
                "error",
                "repository_security_state_failed",
                "Repository security-state collection failed",
                repository=full_name,
            )

        security_events += (
            collect_security_alerts(
                repository
            )
        )

        try:
            (
                run_count,
                abnormal_job_count,
            ) = collect_workflow_runs(
                full_name
            )

            workflow_runs += run_count
            abnormal_action_jobs += (
                abnormal_job_count
            )

        except GitHubRateLimitError:
            raise

        except requests.RequestException as exc:
            logger.warning(
                "Actions collection failed "
                "repository=%s error=%s",
                full_name,
                type(exc).__name__,
            )

            write_operational_event(
                "warning",
                "actions_collection_failed",
                "GitHub Actions collection failed",
                repository=full_name,
                error_type=type(exc).__name__,
            )

        except Exception:
            logger.exception(
                "Actions collector failed repository=%s",
                full_name,
            )

            write_operational_event(
                "error",
                "actions_collector_failed",
                "GitHub Actions collector failed",
                repository=full_name,
            )

    if shutdown_requested:
        return

    record_successful_poll()

    elapsed_ms = int(
        (
            time.monotonic()
            - cycle_started
        )
        * 1000
    )

    logger.info(
        "Poll complete "
        "account_events=%d "
        "repositories=%d "
        "security_events=%d "
        "workflow_runs=%d "
        "abnormal_action_jobs=%d "
        "repository_security_changes=%d "
        "duration_ms=%d",
        account_events,
        len(repositories),
        security_events,
        workflow_runs,
        abnormal_action_jobs,
        repository_security_changes,
        elapsed_ms,
    )

    write_operational_event(
        "info",
        "poll_complete",
        "Collector polling cycle completed successfully",
        account_events=account_events,
        repositories=len(
            repositories
        ),
        security_events=security_events,
        workflow_runs=workflow_runs,
        abnormal_action_jobs=abnormal_action_jobs,
        repository_security_changes=repository_security_changes,
        duration_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Main collector loop.

    Runtime API failures are logged and retried rather than terminating the
    container.
    """

    logger.info(
        "%s v%s starting",
        COLLECTOR_NAME,
        COLLECTOR_VERSION,
    )

    write_operational_event(
        "info",
        "collector_start",
        "GitHub Logs Collector starting",
    )

    # Retry authentication rather than entering a Docker restart loop for a
    # temporary GitHub/network problem.
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

            write_operational_event(
                "warning",
                "github_rate_limited",
                "GitHub rate limited during authentication",
                retry_after=exc.retry_after,
            )

            sleep_interruptible(
                exc.retry_after
            )

        except GitHubAuthenticationError as exc:
            logger.error(
                "%s; retrying in 60s",
                exc,
            )

            write_operational_event(
                "error",
                "github_authentication_failed",
                "GitHub authentication failed",
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

            write_operational_event(
                "error",
                "github_connection_failure",
                "GitHub connection failure during authentication",
                error_type=type(exc).__name__,
            )

            sleep_interruptible(
                60
            )

        except Exception:
            logger.exception(
                "GitHub identity verification failed; "
                "retrying in 60s"
            )

            write_operational_event(
                "error",
                "github_identity_verification_failed",
                "GitHub identity verification failed",
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

            write_operational_event(
                "warning",
                "github_rate_limited",
                "GitHub API rate limit reached",
                retry_after=exc.retry_after,
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

            write_operational_event(
                "error",
                "github_authentication_failed",
                "GitHub authentication failed during polling",
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

            write_operational_event(
                "warning",
                "github_api_timeout",
                "GitHub API request timed out",
            )

        except requests.RequestException as exc:
            logger.warning(
                "GitHub API communication failure "
                "error=%s; polling will continue",
                type(exc).__name__,
            )

            write_operational_event(
                "warning",
                "github_api_communication_failure",
                "GitHub API communication failure",
                error_type=type(exc).__name__,
            )

        except sqlite3.Error:
            logger.exception(
                "SQLite state operation failed; "
                "polling will continue"
            )

            write_operational_event(
                "error",
                "sqlite_operation_failed",
                "SQLite state operation failed",
            )

        except OSError:
            logger.exception(
                "Filesystem operation failed; "
                "polling will continue"
            )

            write_operational_event(
                "error",
                "filesystem_operation_failed",
                "Filesystem operation failed",
            )

        except Exception:
            logger.exception(
                "Collector polling cycle failed; "
                "polling will continue"
            )

            write_operational_event(
                "error",
                "poll_cycle_failed",
                "Collector polling cycle failed",
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
        "%s stopped",
        COLLECTOR_NAME,
    )

    write_operational_event(
        "info",
        "collector_stop",
        "GitHub Logs Collector stopped",
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
