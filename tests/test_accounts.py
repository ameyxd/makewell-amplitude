"""Phase 2 gate: sign-up, login, logout.

Each test makes its own TestClient, which acts like a separate browser with
its own cookies.
"""
from fastapi.testclient import TestClient

from app import db
from app.main import app


def sign_up(client, email, password="correct-horse", name="Robin"):
    return client.post(
        "/signup",
        data={"display_name": name, "email": email, "password": password},
    )


def test_guest_sees_log_in_and_sign_up():
    page = TestClient(app).get("/")
    assert "Log in" in page.text
    assert "Sign up" in page.text


def test_sign_up_logs_the_user_in():
    client = TestClient(app)
    page = sign_up(client, "robin@example.com")
    assert page.status_code == 200          # followed the redirect to the home page
    assert "Hi, Robin" in page.text
    assert "Log out" in page.text


def test_password_is_stored_hashed_not_in_plain_text():
    sign_up(TestClient(app), "hashed@example.com", password="correct-horse")
    user = db.get_user_by_email("hashed@example.com")
    assert "correct-horse" not in tuple(user)
    assert len(user["password_hash"]) == 64  # a SHA-256 hash in hex


def test_same_email_cannot_sign_up_twice():
    sign_up(TestClient(app), "twice@example.com")
    page = sign_up(TestClient(app), "twice@example.com")
    assert page.status_code == 400
    assert "already has an account" in page.text


def test_short_password_is_refused():
    page = sign_up(TestClient(app), "short@example.com", password="1234567")
    assert page.status_code == 400
    assert db.get_user_by_email("short@example.com") is None


def test_log_out_then_log_in_again():
    client = TestClient(app)
    sign_up(client, "return@example.com", name="Sam")

    page = client.post("/logout")
    assert "Hi, Sam" not in page.text

    page = client.post(
        "/login", data={"email": "return@example.com", "password": "correct-horse"}
    )
    assert "Hi, Sam" in page.text


def test_wrong_password_is_refused():
    sign_up(TestClient(app), "wrong@example.com")

    client = TestClient(app)
    page = client.post(
        "/login", data={"email": "wrong@example.com", "password": "not-the-password"}
    )
    assert page.status_code == 400
    assert "incorrect" in page.text
    assert "Log out" not in page.text
