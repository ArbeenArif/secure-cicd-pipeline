
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import app as app_module  # noqa: E402

app = app_module.app


@pytest.fixture()
def client(tmp_path):
    app.config["TESTING"] = True

    # Give each test its own rate-limit database
    app_module.RATE_LIMIT_DB = str(tmp_path / "rate_limit.db")
    app_module.RATE_LIMIT = 5
    app_module.RATE_WINDOW = 60

    return app.test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_index(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.get_json()["service"] == "secure-cicd-demo"


def test_dashboard(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert b"DevSecOps Security Dashboard" in res.data


def test_greet_default_and_named(client):
    assert client.get("/api/greet").get_json()["message"] == "Hello, world!"
    assert client.get("/api/greet?name=Arif").get_json()["message"] == "Hello, Arif!"


def test_limited_greet_allows_five_requests(client):
    for _ in range(5):
        res = client.get("/api/limited-greet?name=Arbeen")
        assert res.status_code == 200
        assert res.get_json()["message"] == "Hello, Arbeen!"


def test_limited_greet_blocks_sixth_request(client):
    for _ in range(5):
        client.get("/api/limited-greet?name=Arbeen")

    res = client.get("/api/limited-greet?name=Arbeen")

    assert res.status_code == 429
    assert res.get_json()["error"] == "rate limit exceeded. Try again later."


@pytest.mark.parametrize(
    "payload",
    ["<script>alert(1)</script>", "a" * 51, "'; DROP TABLE users;--", "../../etc/passwd"],
)
def test_greet_rejects_malicious_input(client, payload):
    res = client.get("/api/greet", query_string={"name": payload})
    assert res.status_code == 400


def test_echo_ok(client):
    res = client.post("/api/echo", json={"text": "hi"})
    assert res.status_code == 200
    assert res.get_json() == {"echo": "hi", "length": 2}


@pytest.mark.parametrize("body", [{"text": 5}, {"nope": "x"}, ["list"], None])
def test_echo_rejects_bad_body(client, body):
    res = client.post("/api/echo", json=body)
    assert res.status_code == 400


def test_echo_rejects_long_text(client):
    res = client.post("/api/echo", json={"text": "x" * 201})
    assert res.status_code == 400


def test_payload_too_large(client):
    res = client.post("/api/echo", data="x" * 5000, content_type="application/json")
    assert res.status_code == 413


def test_security_headers_present(client):
    res = client.get("/health")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
        "Referrer-Policy",
        "Cache-Control",
    ):
        assert header in res.headers


def test_404_and_405(client):
    assert client.get("/missing").status_code == 404
    assert client.post("/health").status_code == 405
