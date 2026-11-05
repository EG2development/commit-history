import json
from types import SimpleNamespace

import pytest

from commit_history.github import (
    GitHubError,
    GraphQL,
    error_messages,
    graphql_url,
    resolve_token,
    retry_delay,
    web_url,
)
from fakes import FakeResponse, FakeUrlopen, http_error

URL = "https://api.example.test/graphql"


@pytest.mark.parametrize("host, expected", [
    ("github.com", "https://api.github.com/graphql"),
    ("", "https://api.github.com/graphql"),
    ("https://GitHub.com/", "https://api.github.com/graphql"),
    ("acme.ghe.com", "https://api.acme.ghe.com/graphql"),
    ("api.acme.ghe.com", "https://api.acme.ghe.com/graphql"),
    ("https://ghes.example.com/", "https://ghes.example.com/api/graphql"),
])
def test_graphql_url(host, expected):
    assert graphql_url(host) == expected


def test_web_url():
    assert web_url("github.com") == "https://github.com"
    assert web_url(None) == "https://github.com"
    assert web_url("https://ghes.example.com/") == "https://ghes.example.com"


def test_resolve_token_prefers_environment_variables():
    assert resolve_token(env={"GITHUB_TOKEN": "a", "GH_TOKEN": "b"}) == ("a", "GITHUB_TOKEN")
    assert resolve_token(env={"GH_TOKEN": " b "}) == ("b", "GH_TOKEN")


def test_resolve_token_falls_back_to_the_github_cli():
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="gho_x\n", stderr="")

    assert resolve_token(host="ghes.example.com", env={}, run=run) == ("gho_x", "gh auth token")
    assert calls == [["gh", "auth", "token", "--hostname", "ghes.example.com"]]


def test_resolve_token_reports_a_missing_token():
    def run(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="not logged in\n")

    with pytest.raises(GitHubError, match="not logged in"):
        resolve_token(env={}, run=run)
    with pytest.raises(GitHubError, match="failed"):
        resolve_token(env={}, run=lambda *a, **k: (_ for _ in ()).throw(OSError("no gh")))


def test_retry_delay_policy():
    assert retry_delay(502, {}, 0, 0.0) == 1.0
    assert retry_delay(503, {}, 3, 0.0) == 8.0
    assert retry_delay(502, {}, 4, 0.0) is None
    assert retry_delay(403, {"retry-after": "7"}, 0, 0.0) == 8.0
    assert retry_delay(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1100"}, 0, 1000.0) == 101.0
    assert retry_delay(403, {}, 0, 0.0) is None
    assert retry_delay(429, {}, 1, 0.0) == 120.0
    assert retry_delay(401, {}, 0, 0.0) is None


def payload(**data) -> str:
    rate = {"cost": 1, "remaining": 4000, "resetAt": "2026-11-05T10:00:00Z"}
    return json.dumps({"data": {"rateLimit": rate, **data}})


def test_execute_retries_server_errors_then_returns_the_payload():
    urlopen = FakeUrlopen(http_error(502, "bad gateway"), FakeResponse(payload(ok=True)))
    slept = []
    client = GraphQL("https://api.example.test/graphql", "tok", urlopen=urlopen, sleep=slept.append,
                     clock=lambda: 0.0)
    result = client.execute("query X { ok }", {})
    assert result["data"]["ok"] is True
    assert slept == [1.0]
    assert client.requests == 2
    assert client.points_used == 1
    request = urlopen.requests[0]
    assert request.get_header("Authorization") == "bearer tok"
    assert json.loads(request.data)["query"] == "query X { ok }"


def test_execute_gives_up_on_a_final_error():
    urlopen = FakeUrlopen(http_error(401, '{"message":"Bad credentials"}'))
    client = GraphQL("https://api.example.test/graphql", "tok", urlopen=urlopen, sleep=lambda s: None)
    with pytest.raises(GitHubError, match="HTTP 401.*Bad credentials") as info:
        client.execute("query X { ok }", {})
    assert info.value.status == 401


def test_execute_waits_when_graphql_reports_rate_limiting():
    limited = json.dumps({"errors": [{"type": "RATE_LIMITED", "message": "slow down"}]})
    urlopen = FakeUrlopen(FakeResponse(limited, {"x-ratelimit-reset": "1030"}), FakeResponse(payload(ok=1)))
    slept = []
    client = GraphQL(URL, "tok", urlopen=urlopen, sleep=slept.append, clock=lambda: 1000.0)
    assert client.execute("query X { ok }", {})["data"]["ok"] == 1
    assert slept == [31.0]


def test_execute_pauses_when_the_budget_runs_low():
    low = json.dumps({"data": {"rateLimit": {"cost": 1, "remaining": 5, "resetAt": "2026-11-05T10:00:00Z"}}})
    urlopen = FakeUrlopen(FakeResponse(low))
    slept = []
    reset_epoch = 1_793_872_800.0  # 2026-11-05T10:00:00Z
    client = GraphQL(URL, "tok", urlopen=urlopen, sleep=slept.append, clock=lambda: reset_epoch - 120)
    client.execute("query X { ok }", {})
    assert slept == [121.0]
    assert client.remaining == 5


def test_execute_rejects_non_json():
    client = GraphQL(URL, "tok", urlopen=FakeUrlopen(FakeResponse("<html>")), sleep=lambda s: None)
    with pytest.raises(GitHubError, match="not JSON"):
        client.execute("query X { ok }", {})


def test_error_messages():
    assert error_messages({"errors": [{"type": "NOT_FOUND", "message": "gone"}, {"message": "plain"}]}) == [
        "NOT_FOUND: gone", "plain"]
    assert error_messages({}) == []
