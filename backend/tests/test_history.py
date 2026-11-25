import pytest
from rest_framework.test import APIClient

from accounts.models import User
from scans.models import Scan


def make_scan(headline="h", user=None, session_key=""):
    return Scan.objects.create(
        user=user, session_key=session_key, headline=headline, label="clickbait",
        confidence=0.9, clickbait_probability=0.9, headline_probability=0.9,
        thumbnail_probability=0.0, signals=[], model_version="v1",
    )


@pytest.fixture
def staff():
    return User.objects.create_user("boss", password="x", is_staff=True)


@pytest.mark.django_db
def test_history_scoped_to_user():
    a = User.objects.create_user("a", password="x")
    b = User.objects.create_user("b", password="x")
    make_scan("a1", user=a)
    make_scan("b1", user=b)
    client = APIClient()
    client.force_login(a)
    results = client.get("/api/history").json()["results"]
    assert [r["headline"] for r in results] == ["a1"]
    assert set(results[0]) == {
        "id", "headline", "label", "clickbait_probability", "confidence", "created_at"
    }


@pytest.mark.django_db
def test_history_guest_session(fake_detector):
    one, two = APIClient(), APIClient()
    one.post("/api/predict", {"headline": "one"}, format="multipart")
    two.post("/api/predict", {"headline": "two"}, format="multipart")
    assert [r["headline"] for r in one.get("/api/history").json()["results"]] == ["one"]


@pytest.mark.django_db
def test_history_empty_for_fresh_guest():
    make_scan("orphan", session_key="")
    r = APIClient().get("/api/history")
    assert r.status_code == 200
    assert r.json()["results"] == []


@pytest.mark.django_db
def test_history_paginated():
    user = User.objects.create_user("a", password="x")
    for i in range(25):
        make_scan(f"h{i}", user=user)
    client = APIClient()
    client.force_login(user)
    body = client.get("/api/history").json()
    assert body["count"] == 25 and len(body["results"]) == 20 and body["next"] is not None
    assert body["results"][0]["headline"] == "h24"


@pytest.mark.django_db
def test_admin_endpoints_require_staff():
    user = User.objects.create_user("a", password="x")
    normal = APIClient()
    normal.force_login(user)
    for client in (normal, APIClient()):
        for url in ("/api/admin/users", "/api/admin/history"):
            r = client.get(url)
            assert r.status_code == 403
            assert isinstance(r.json()["detail"], str)


@pytest.mark.django_db
def test_admin_users_list(staff):
    client = APIClient()
    client.force_login(staff)
    body = client.get("/api/admin/users").json()
    assert body["count"] == 1
    assert body["results"][0]["role"] == "admin"
    assert "password" not in body["results"][0]


@pytest.mark.django_db
def test_admin_history_includes_username(staff):
    a = User.objects.create_user("a", password="x")
    make_scan("guest", session_key="abc")
    make_scan("mine", user=a)
    client = APIClient()
    client.force_login(staff)
    rows = {r["headline"]: r for r in client.get("/api/admin/history").json()["results"]}
    assert rows["guest"]["username"] is None
    assert rows["mine"]["username"] == "a"


@pytest.mark.django_db
def test_admin_history_query_count(staff, django_assert_max_num_queries):
    users = [User.objects.create_user(f"u{i}", password="x") for i in range(3)]
    for i in range(30):
        make_scan(f"h{i}", user=users[i % 3])
    client = APIClient()
    client.force_login(staff)
    with django_assert_max_num_queries(4):
        r = client.get("/api/admin/history")
    assert r.status_code == 200
