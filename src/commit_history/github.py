"""GitHub GraphQL transport with the standard library only.

Resolves a token, posts queries, retries transient failures, honours
``Retry-After`` and the primary and secondary rate limits, and pauses when the
remaining GraphQL budget runs low.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

USER_AGENT = "github-commit-history/0.1"
TOKEN_VARIABLES = ("GITHUB_TOKEN", "GH_TOKEN")
MAX_ATTEMPTS = 5


class GitHubError(RuntimeError):
    """A request that could not be completed after retries."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def graphql_url(host: str | None) -> str:
    """Return the GraphQL endpoint for github.com, GHE.com or GitHub Enterprise Server."""
    cleaned = (host or "").strip().lower()
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    cleaned = cleaned.strip("/")
    if cleaned in ("", "github.com", "api.github.com"):
        return "https://api.github.com/graphql"
    if cleaned.endswith(".ghe.com"):
        api_host = cleaned if cleaned.startswith("api.") else f"api.{cleaned}"
        return f"https://{api_host}/graphql"
    return f"https://{cleaned}/api/graphql"


def web_url(host: str | None) -> str:
    """Return the browser host that repository links should use."""
    cleaned = (host or "github.com").strip().lower()
    for prefix in ("https://", "http://"):
        cleaned = cleaned.removeprefix(prefix)
    cleaned = cleaned.strip("/")
    if cleaned in ("", "api.github.com"):
        cleaned = "github.com"
    return f"https://{cleaned}"


def resolve_token(
    host: str = "github.com",
    env: Mapping[str, str] = os.environ,
    run: Callable = subprocess.run,
) -> tuple[str, str]:
    """Return ``(token, source)`` from the environment or the GitHub CLI."""
    for name in TOKEN_VARIABLES:
        value = env.get(name, "").strip()
        if value:
            return value, name
    command = ["gh", "auth", "token"]
    if host and host != "github.com":
        command += ["--hostname", host]
    hint = f"set {' or '.join(TOKEN_VARIABLES)}, or run `gh auth login`"
    try:
        result = run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubError(f"no token found: `gh auth token` failed ({exc}); {hint}") from exc
    token = (result.stdout or "").strip()
    if result.returncode != 0 or not token:
        detail = (result.stderr or "").strip().splitlines()
        reason = detail[-1] if detail else "no output"
        raise GitHubError(f"no token found: `gh auth token` returned {result.returncode} ({reason}); {hint}")
    return token, "gh auth token"


def retry_delay(status: int, headers: Mapping[str, str], attempt: int, now: float) -> float | None:
    """Seconds to wait before retrying an HTTP failure, or ``None`` when it is final."""
    if attempt >= MAX_ATTEMPTS - 1:
        return None
    if status in (403, 429):
        retry_after = (headers.get("retry-after") or "").strip()
        if retry_after.isdigit():
            return float(retry_after) + 1
        if (headers.get("x-ratelimit-remaining") or "").strip() == "0":
            reset = (headers.get("x-ratelimit-reset") or "").strip()
            if reset.isdigit():
                return max(float(reset) - now, 1.0) + 1
        if status == 429:
            return min(60.0 * (attempt + 1), 300.0)
        return None
    if status in (500, 502, 503, 504):
        return min(2.0 ** attempt, 30.0)
    return None


def seconds_until(iso_timestamp: str, now: float) -> float:
    """Seconds from ``now`` until an ISO 8601 timestamp such as ``2026-11-05T10:00:00Z``."""
    reset = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    if reset.tzinfo is None:
        reset = reset.replace(tzinfo=UTC)
    return max(reset.timestamp() - now, 0.0)


class GraphQL:
    """A small GraphQL client bound to one endpoint and one token."""

    def __init__(
        self,
        url: str,
        token: str,
        *,
        urlopen: Callable = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        budget_floor: int = 50,
        log: Callable[[str], None] | None = None,
    ):
        self.url = url
        self._token = token
        self._urlopen = urlopen
        self._sleep = sleep
        self._clock = clock
        self._budget_floor = budget_floor
        self._log = log or (lambda message: None)
        self.requests = 0
        self.points_used = 0
        self.remaining: int | None = None

    def execute(self, query: str, variables: dict) -> dict:
        """Post one query and return the decoded JSON body (``data`` and ``errors``)."""
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        headers = {
            "Authorization": f"bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        attempt = 0
        while True:
            request = urllib.request.Request(self.url, data=body, method="POST", headers=headers)
            try:
                with self._urlopen(request, timeout=90) as response:
                    status = response.status
                    response_headers = response.headers
                    text = response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                status = exc.code
                response_headers = exc.headers
                text = exc.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt >= MAX_ATTEMPTS - 1:
                    raise GitHubError(f"network error talking to {self.url}: {exc}") from exc
                self._pause(min(2.0 ** attempt, 30.0), f"network error ({exc})")
                attempt += 1
                continue

            self.requests += 1
            if status == 200:
                payload = self._decode(text)
                wait = self._rate_limited_wait(payload, response_headers)
                if wait is not None and attempt < MAX_ATTEMPTS - 1:
                    self._pause(wait, "GraphQL rate limit reached")
                    attempt += 1
                    continue
                self._account(payload)
                return payload

            delay = retry_delay(status, response_headers, attempt, self._clock())
            if delay is None:
                snippet = text.strip().replace("\n", " ")[:300]
                raise GitHubError(f"HTTP {status} from {self.url}: {snippet}", status)
            self._pause(delay, f"HTTP {status}")
            attempt += 1

    def _decode(self, text: str) -> dict:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GitHubError(f"GraphQL response was not JSON: {text[:200]}") from exc
        if not isinstance(payload, dict):
            raise GitHubError("GraphQL response was not a JSON object")
        return payload

    def _rate_limited_wait(self, payload: dict, headers: Mapping[str, str]) -> float | None:
        errors = payload.get("errors") or []
        if not any((error or {}).get("type") == "RATE_LIMITED" for error in errors):
            return None
        reset = (headers.get("x-ratelimit-reset") or "").strip()
        if reset.isdigit():
            return max(float(reset) - self._clock(), 1.0) + 1
        return 60.0

    def _account(self, payload: dict) -> None:
        rate = ((payload.get("data") or {}).get("rateLimit")) or None
        if not rate:
            return
        self.points_used += int(rate.get("cost") or 0)
        remaining = rate.get("remaining")
        if remaining is None:
            return
        self.remaining = int(remaining)
        if self.remaining < self._budget_floor and rate.get("resetAt"):
            wait = seconds_until(str(rate["resetAt"]), self._clock()) + 1
            self._pause(wait, f"{self.remaining} GraphQL points left")

    def _pause(self, seconds: float, reason: str) -> None:
        self._log(f"waiting {seconds:.0f}s: {reason}")
        self._sleep(seconds)


def error_messages(payload: dict) -> list[str]:
    """Human-readable messages from a GraphQL ``errors`` array."""
    messages = []
    for error in payload.get("errors") or []:
        if not isinstance(error, dict):
            continue
        kind = error.get("type")
        text = error.get("message") or "unknown error"
        messages.append(f"{kind}: {text}" if kind else text)
    return messages
