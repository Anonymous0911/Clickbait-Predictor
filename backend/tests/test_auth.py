import pytest
from rest_framework.test import APIClient

from accounts.models import User
from accounts.throttles import AuthThrottle
from scans.models import Scan

PW = "correct-horse-battery-42"
DUPLICATE = "That username is already in use."
BAD_LOGIN = "Invalid username or password."
BAD_CURRENT = "Current password is incorrect."


@pytest.fixture
def client():
    return APIClient()


def register(client, username="alice", password=PW):
    return client.post("/api/auth/register", {"username": username, "password": password}, format="json")


def login(client, username="alice", password=PW):
    return client.post("/api/auth/login", {"username": username, "password": password}, format="json")


@pytest.mark.django_db
def test_register_logs_in(client):
    r = register(client)
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["username"] == "alice" and user["role"] == "user"
    assert client.get("/api/auth/me").json()["user"]["username"] == "alice"


@pytest.mark.django_db
def test_register_duplicate_case_insensitive(client):
    register(client)
    r = register(APIClient(), "Alice")
    assert r.status_code == 400
    assert r.json()["detail"] == DUPLICATE


@pytest.mark.django_db
def test_register_weak_password(client):
    r = register(client, password="1234")
    assert r.status_code == 400
    assert r.json()["detail"]


@pytest.mark.django_db
def test_login_bad_credentials(client):
    User.objects.create_user("alice", password=PW)
    for username, password in [("alice", "wrong"), ("nobody", PW)]:
        r = login(client, username, password)
        assert r.status_code == 400
        assert r.json()["detail"] == BAD_LOGIN


@pytest.mark.django_db
def test_me_guest(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json() == {"user": None}


@pytest.mark.django_db
def test_logout(client):
    register(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").json() == {"user": None}


@pytest.mark.django_db
def test_change_password(client):
    register(client)
    url = "/api/auth/change-password"
    r = client.post(url, {"current_password": "nope", "new_password": "another-long-pass-77"}, format="json")
    assert r.status_code == 400
    assert r.json()["detail"] == BAD_CURRENT

    r = client.post(url, {"current_password": PW, "new_password": "another-long-pass-77"}, format="json")
    assert r.status_code == 200
    assert r.json() == {"message": "Password changed successfully."}
    assert client.get("/api/auth/me").json()["user"]["username"] == "alice"
    client.post("/api/auth/logout")
    assert login(client, password="another-long-pass-77").status_code == 200


@pytest.mark.django_db
def test_change_password_rejects_weak_new_password(client):
    register(client)
    r = client.post(
        "/api/auth/change-password", {"current_password": PW, "new_password": "1234"}, format="json"
    )
    assert r.status_code == 400
    assert r.json()["detail"]


@pytest.mark.django_db
def test_csrf_enforced_on_session_writes():
    user = User.objects.create_user("alice", password=PW)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    body = {"current_password": PW, "new_password": "another-long-pass-77"}
    assert client.post("/api/auth/change-password", body, format="json").status_code == 403

    client.get("/api/auth/csrf")
    token = client.cookies["csrftoken"].value
    r = client.post("/api/auth/change-password", body, format="json", HTTP_X_CSRFTOKEN=token)
    assert r.status_code != 403


@pytest.mark.django_db
def test_csrf_cookie_endpoint():
    client = APIClient()
    r = client.get("/api/auth/csrf")
    assert r.status_code == 204
    assert "csrftoken" in r.cookies


@pytest.mark.django_db
def test_login_case_insensitive(client):
    register(client, "Alice")
    assert login(APIClient(), "alice").status_code == 200


@pytest.mark.django_db
def test_login_requires_csrf():
    User.objects.create_user("alice", password=PW)
    client = APIClient(enforce_csrf_checks=True)
    assert login(client).status_code == 403


@pytest.mark.django_db
def test_register_requires_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert register(client).status_code == 403
    assert not User.objects.exists()


def guest_scan(client, headline):
    r = client.post("/api/predict", {"headline": headline}, format="multipart")
    assert r.status_code == 200


@pytest.mark.django_db
def test_guest_scans_move_on_register(client, fake_detector):
    guest_scan(client, "mine")
    guest_scan(APIClient(), "someone else")
    register(client)
    user = User.objects.get(username="alice")
    assert Scan.objects.get(headline="mine").user == user
    assert Scan.objects.get(headline="mine").session_key == ""
    assert Scan.objects.get(headline="someone else").user is None


@pytest.mark.django_db
def test_guest_scans_move_on_login(client, fake_detector):
    user = User.objects.create_user("alice", password=PW)
    guest_scan(client, "mine")
    guest_scan(APIClient(), "someone else")
    assert login(client).status_code == 200
    assert Scan.objects.get(headline="mine").user == user
    assert Scan.objects.get(headline="someone else").user is None


@pytest.mark.django_db
def test_auth_throttle(client, monkeypatch):
    monkeypatch.setattr(AuthThrottle, "THROTTLE_RATES", {"auth": "2/min"})
    codes = [login(client, "x", "y").status_code for _ in range(3)]
    assert codes == [400, 400, 429]


@pytest.mark.django_db
def test_auth_throttle_applies_when_signed_in(monkeypatch):
    monkeypatch.setattr(AuthThrottle, "THROTTLE_RATES", {"auth": "2/min"})
    client = APIClient()
    client.force_login(User.objects.create_user("alice", password=PW))
    codes = [login(client, "alice", "wrong").status_code for _ in range(3)]
    assert codes == [400, 400, 429]


@pytest.mark.django_db
def test_register_fullwidth_duplicate_rejected(client):
    register(client)
    r = register(APIClient(), "\uff21\uff2c\uff29\uff23\uff25")
    assert r.status_code == 400
    assert r.json()["detail"] == DUPLICATE


@pytest.mark.django_db
def test_register_username_with_space_rejected(client):
    r = register(client, "bad name")
    assert r.status_code == 400
    assert r.json()["detail"]


@pytest.mark.django_db
def test_username_unique_in_database():
    from django.db import IntegrityError, transaction

    User.objects.create_user("alice", password=PW)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("Alice", password=PW)


@pytest.mark.django_db
def test_password_change_throttle(client, monkeypatch):
    from accounts.throttles import PasswordChangeThrottle

    monkeypatch.setattr(PasswordChangeThrottle, "THROTTLE_RATES", {"password": "2/min"})
    register(client)
    body = {"current_password": "nope", "new_password": "another-long-pass-77"}
    codes = [client.post("/api/auth/change-password", body, format="json").status_code for _ in range(3)]
    assert codes == [400, 400, 429]


@pytest.mark.django_db
def test_logout_starts_empty_guest_history(client, fake_detector):
    guest_scan(client, "before")
    register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/history").json()["count"] == 0
    guest_scan(client, "after")
    body = client.get("/api/history").json()
    assert [r["headline"] for r in body["results"]] == ["after"]
