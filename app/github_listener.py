#!/usr/bin/env python3

"""
GitHub Logs Collector

Receives GitHub webhook events, validates their HMAC-SHA256 signature,
normalises useful metadata, and writes newline-delimited JSON (JSONL)
for ingestion by SIEM and log-management platforms.

Security design:
- Rejects unsigned/incorrectly signed webhook requests.
- Uses constant-time HMAC comparison.
- Requires application/json.
- Limits inbound request size.
- Does not log secrets or arbitrary HTTP headers.
- Sanitises selected metadata before writing.
- Writes one JSON object per line.
- Uses UTC timestamps.
- Avoids Flask debug mode.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, request


# ---------------------------------------------------------------------------
# Application configuration
# ---------------------------------------------------------------------------

app = Flask(__name__)


# Security:
# Limit the maximum HTTP request body that Flask will accept.
# This reduces memory/resource abuse from oversized requests.
#
# GitHub webhook payloads are normally far smaller than this.
MAX_CONTENT_LENGTH = int(
    os.getenv(
        "MAX_CONTENT_LENGTH",
        str(5 * 1024 * 1024),
    )
)

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# Security:
# The webhook secret must not be stored in source code.
# Supply it through a Docker secret, environment variable, or secret manager.
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

if not WEBHOOK_SECRET:
    raise RuntimeError(
        "GITHUB_WEBHOOK_SECRET is not configured"
    )


# Security / portability:
# The output location can be configured by the container runtime.
LOG_FILE = Path(
    os.getenv(
        "GITHUB_WEBHOOK_LOG",
        "/var/log/github/events.jsonl",
    )
)


# Security:
# Reject excessively long metadata values before storing them.
MAX_METADATA_LENGTH = int(
    os.getenv(
        "MAX_METADATA_LENGTH",
        "512",
    )
)


# Optional security control:
# Restrict GitHub event names to sane characters and lengths.
EVENT_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]{1,100}$"
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper(),
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
# Utility functions
# ---------------------------------------------------------------------------

def utc_timestamp() -> str:
    """
    Return an ISO-8601 UTC timestamp.

    Security / logging:
    Using UTC avoids timezone ambiguity during incident investigation.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def sanitise_string(
    value: Any,
    max_length: int = MAX_METADATA_LENGTH,
) -> str | None:
    """
    Safely convert selected metadata to a bounded string.

    Security:
    Prevents extremely large metadata fields and strips CR/LF characters
    that could make textual log output misleading.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    value = value.replace(
        "\r",
        "",
    ).replace(
        "\n",
        "",
    )

    return value[:max_length]


def verify_signature(
    payload_body: bytes,
    signature_header: str | None,
) -> bool:
    """
    Validate GitHub's X-Hub-Signature-256 HMAC.

    Security:
    - Requires SHA-256 webhook signatures.
    - Uses hmac.compare_digest() to reduce timing leakage.
    - Operates against the original raw HTTP request body.
    """

    if not signature_header:
        return False

    expected_prefix = "sha256="

    if not signature_header.startswith(
        expected_prefix
    ):
        return False

    expected_signature = (
        expected_prefix
        + hmac.new(
            WEBHOOK_SECRET.encode(
                "utf-8"
            ),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        expected_signature,
        signature_header,
    )


def extract_repository(
    payload: dict[str, Any],
) -> str | None:
    repository = payload.get(
        "repository"
    )

    if not isinstance(
        repository,
        dict,
    ):
        return None

    return sanitise_string(
        repository.get(
            "full_name"
        )
    )


def extract_organization(
    payload: dict[str, Any],
) -> str | None:
    organization = payload.get(
        "organization"
    )

    if not isinstance(
        organization,
        dict,
    ):
        return None

    return sanitise_string(
        organization.get(
            "login"
        )
    )


def extract_sender(
    payload: dict[str, Any],
) -> str | None:
    sender = payload.get(
        "sender"
    )

    if not isinstance(
        sender,
        dict,
    ):
        return None

    return sanitise_string(
        sender.get(
            "login"
        )
    )


def write_event(
    event: dict[str, Any],
) -> None:
    """
    Append one JSON object to the JSONL event log.

    Security:
    - Uses compact JSON to keep each event on exactly one physical line.
    - UTF-8 output is explicitly selected.
    - Does not use shell commands or external processes.
    """

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialized = json.dumps(
        event,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as log_handle:
        log_handle.write(
            serialized
        )
        log_handle.write(
            "\n"
        )


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(_error):
    return jsonify(
        {
            "error": "bad_request"
        }
    ), 400


@app.errorhandler(401)
def unauthorized(_error):
    return jsonify(
        {
            "error": "unauthorized"
        }
    ), 401


@app.errorhandler(413)
def payload_too_large(_error):
    return jsonify(
        {
            "error": "payload_too_large"
        }
    ), 413


@app.errorhandler(415)
def unsupported_media_type(_error):
    return jsonify(
        {
            "error": "unsupported_media_type"
        }
    ), 415


@app.errorhandler(500)
def internal_server_error(_error):
    return jsonify(
        {
            "error": "internal_server_error"
        }
    ), 500


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.route(
    "/health",
    methods=["GET"],
)
def health():
    """
    Minimal health endpoint.

    Security:
    Deliberately does not expose:
    - secrets
    - filesystem paths
    - package versions
    - Python version
    - configuration
    """

    return jsonify(
        {
            "status": "healthy"
        }
    ), 200


# ---------------------------------------------------------------------------
# GitHub webhook endpoint
# ---------------------------------------------------------------------------

@app.route(
    "/github-webhook",
    methods=["POST"],
)
def github_webhook():

    # Security:
    # Accept only JSON webhook requests.
    #
    # The signature is still checked against the raw body before parsing.
    if not request.is_json:
        abort(415)

    # Security:
    # Read the exact body supplied by GitHub.
    # HMAC validation must use the original bytes.
    raw_payload = request.get_data(
        cache=True,
        as_text=False,
    )

    signature = request.headers.get(
        "X-Hub-Signature-256"
    )

    # Security:
    # Never process or store an event before authentication succeeds.
    if not verify_signature(
        raw_payload,
        signature,
    ):
        logger.warning(
            "Rejected webhook with invalid signature"
        )

        abort(401)

    github_event = request.headers.get(
        "X-GitHub-Event"
    )

    delivery_id = request.headers.get(
        "X-GitHub-Delivery"
    )

    hook_id = request.headers.get(
        "X-GitHub-Hook-ID"
    )

    # Security:
    # Require GitHub event identification.
    if not github_event:
        abort(400)

    github_event = sanitise_string(
        github_event,
        max_length=100,
    )

    # Security:
    # Event names should contain only simple expected characters.
    if (
        not github_event
        or not EVENT_NAME_PATTERN.fullmatch(
            github_event
        )
    ):
        abort(400)

    delivery_id = sanitise_string(
        delivery_id,
        max_length=128,
    )

    hook_id = sanitise_string(
        hook_id,
        max_length=128,
    )

    try:
        payload = request.get_json(
            force=False,
            silent=False,
        )
    except Exception:
        abort(400)

    # Security:
    # GitHub webhook payloads should be JSON objects.
    # Reject arrays, strings, integers, etc.
    if not isinstance(
        payload,
        dict,
    ):
        abort(400)

    event = {
        "@timestamp": utc_timestamp(),

        "source": {
            "type": "github",
            "transport": "webhook",
        },

        "github": {
            "event": github_event,

            "delivery_id": delivery_id,

            "hook_id": hook_id,

            "repository": extract_repository(
                payload
            ),

            "organization": extract_organization(
                payload
            ),

            "sender": extract_sender(
                payload
            ),

            "action": sanitise_string(
                payload.get(
                    "action"
                )
            ),
        },

        # Preserve the original GitHub body so SIEM platforms can
        # inspect event-specific fields without the collector needing
        # to understand every GitHub webhook type.
        "payload": payload,
    }

    try:
        write_event(
            event
        )

    except OSError:
        # Security:
        # Do not return filesystem paths or Python exception details
        # to an external client.
        logger.exception(
            "Unable to write webhook event"
        )

        abort(500)

    logger.info(
        "Accepted GitHub webhook event=%s delivery_id=%s repository=%s",
        github_event,
        delivery_id or "-",
        extract_repository(
            payload
        ) or "-",
    )

    return jsonify(
        {
            "status": "accepted",
            "delivery_id": delivery_id,
        }
    ), 200


# ---------------------------------------------------------------------------
# Development entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # Security:
    # This entrypoint is for development/testing only.
    #
    # Production containers should run the application through Gunicorn.
    #
    # Debug mode must remain disabled because Flask's debugger can expose
    # sensitive information and should never be internet-facing.
    app.run(
        host="127.0.0.1",
        port=8080,
        debug=False,
    )
