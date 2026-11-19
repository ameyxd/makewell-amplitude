"""Phase 4 gate: the bookings list, and cancelling for a refund."""
from fastapi.testclient import TestClient

from app import db
from app.main import app
from helpers import book, seats_taken, sessions_for, sign_up


def test_my_bookings_needs_a_login():
    page = TestClient(app).get("/my-bookings")
    assert page.url.path == "/login"


def test_new_user_sees_an_empty_list():
    client = TestClient(app)
    sign_up(client, "empty@example.com")
    page = client.get("/my-bookings")
    assert "no bookings yet" in page.text


def test_booking_appears_in_the_list():
    session = sessions_for("natural-dye")[2]
    client = TestClient(app)
    book(client, "lister@example.com", session["id"])

    page = client.get("/my-bookings")
    assert "Natural Dyeing with Plants" in page.text
    assert "Confirmed" in page.text
    assert "£50 paid" in page.text


def test_cancelling_refunds_and_returns_the_seats():
    session = sessions_for("notebook-binding")[1]
    before = seats_taken(session["id"])
    client = TestClient(app)
    booking_id = book(client, "canceller@example.com", session["id"], seats=2)
    assert seats_taken(session["id"]) == before + 2

    page = client.post(f"/bookings/{booking_id}/cancel")
    assert "Cancelled" in page.text
    assert "£76 refunded" in page.text          # 2 seats at £38
    assert db.get_booking(booking_id)["status"] == "cancelled"
    assert seats_taken(session["id"]) == before


def test_cancelling_twice_returns_the_seats_only_once():
    session = sessions_for("notebook-binding")[2]
    before = seats_taken(session["id"])
    client = TestClient(app)
    booking_id = book(client, "twice-cancel@example.com", session["id"])

    client.post(f"/bookings/{booking_id}/cancel")
    client.post(f"/bookings/{booking_id}/cancel")
    assert seats_taken(session["id"]) == before


def test_one_user_cannot_cancel_anothers_booking():
    session = sessions_for("linocut")[2]
    owner = TestClient(app)
    booking_id = book(owner, "mine@example.com", session["id"])

    stranger = TestClient(app)
    sign_up(stranger, "not-mine@example.com")
    page = stranger.post(f"/bookings/{booking_id}/cancel")

    assert page.status_code == 404
    assert db.get_booking(booking_id)["status"] == "confirmed"
