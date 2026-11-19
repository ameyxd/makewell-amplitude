"""Phase 3 gate: choosing a session, the account wall, paying, confirmation.

Each test uses a different workshop, so one test's bookings never change
the seat counts another test relies on.
"""
from fastapi.testclient import TestClient

from app import db
from app.main import app
from helpers import GOOD_CARD, seats_taken, sessions_for, sign_up, start


def booking_count():
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]


def test_guest_is_sent_to_sign_up_before_paying():
    session = sessions_for("linocut")[1]
    page = start(TestClient(app), session["id"])
    assert "Create your account" in page.text
    assert "finish your booking" in page.text


def test_guest_can_book_from_workshop_to_confirmation():
    session = sessions_for("linocut")[0]
    before = seats_taken(session["id"])
    client = TestClient(app)

    start(client, session["id"], seats=2)
    page = sign_up(client, "booker@example.com")
    assert "Checkout" in page.text           # sign-up led straight to checkout
    assert "Linocut Printmaking" in page.text
    assert "£84" in page.text                # 2 seats at £42

    page = client.post("/checkout", data=GOOD_CARD)
    assert "booked, Robin" in page.text
    assert seats_taken(session["id"]) == before + 2


def test_declined_card_creates_no_booking():
    session = sessions_for("natural-dye")[0]
    before_seats, before_bookings = seats_taken(session["id"]), booking_count()
    client = TestClient(app)
    sign_up(client, "declined@example.com")
    start(client, session["id"])

    page = client.post(
        "/checkout", data={**GOOD_CARD, "card_number": "4000 0000 0000 0002"}
    )
    assert page.status_code == 400
    assert "declined" in page.text
    assert seats_taken(session["id"]) == before_seats
    assert booking_count() == before_bookings


def test_four_digit_year_gets_the_vague_error():
    """The planted friction: 11/2027 is refused without saying why."""
    session = sessions_for("notebook-binding")[0]
    before_bookings = booking_count()
    client = TestClient(app)
    sign_up(client, "expiry@example.com")
    start(client, session["id"])

    page = client.post("/checkout", data={**GOOD_CARD, "card_expiry": "11/2027"})
    assert page.status_code == 400
    assert "Invalid card details." in page.text
    assert booking_count() == before_bookings


def test_sold_out_session_cannot_be_started():
    sold_out = sessions_for("sourdough")[1]
    page = start(TestClient(app), sold_out["id"])
    assert page.status_code == 400
    assert "not have enough seats" in page.text


def test_session_that_fills_during_checkout_creates_no_booking():
    session = sessions_for("wheel-throwing")[2]
    before_bookings = booking_count()
    client = TestClient(app)
    sign_up(client, "toolate@example.com")
    start(client, session["id"], seats=2)

    # Someone else takes every seat while this user is typing their card.
    with db.connect() as conn:
        conn.execute(
            "UPDATE workshop_sessions SET seats_taken = capacity WHERE id = ?",
            (session["id"],),
        )

    page = client.post("/checkout", data=GOOD_CARD)
    assert page.status_code == 400
    assert "no longer has enough seats" in page.text
    assert booking_count() == before_bookings


def test_confirmation_page_is_private():
    session = sessions_for("spoon-carving")[2]
    owner = TestClient(app)
    sign_up(owner, "owner@example.com")
    start(owner, session["id"])
    confirmation = owner.post("/checkout", data=GOOD_CARD)
    address = confirmation.url.path          # /bookings/<id>/confirmed

    stranger = TestClient(app)
    sign_up(stranger, "stranger@example.com")
    assert stranger.get(address).status_code == 404
    assert TestClient(app).get(address).status_code == 404   # a guest


def test_checkout_with_nothing_chosen_goes_home():
    client = TestClient(app)
    sign_up(client, "nothing@example.com")
    page = client.get("/checkout")
    assert page.url.path == "/"
