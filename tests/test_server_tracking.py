"""Phase 6 gate: the server sends the right events to Amplitude.

Nothing is really sent. Each test swaps the Amplitude client for a fake one
that only remembers what it was asked to send.
"""
import pytest
from fastapi.testclient import TestClient

from app import analytics, db
from app.main import app
from helpers import GOOD_CARD, book, sessions_for, sign_up, start

DECLINED_CARD = dict(GOOD_CARD, card_number="4000 0000 0000 0002")


class FakeAmplitude:
    """Stands in for the real client and remembers what it was given."""

    def __init__(self):
        self.events = []  # every event passed to track()

    def track(self, event):
        self.events.append(event)

    def named(self, event_type):
        """The events sent with one name."""
        return [e for e in self.events if e.event_type == event_type]


@pytest.fixture
def sent(monkeypatch):
    """Switch tracking on for one test, pointed at a FakeAmplitude."""
    fake = FakeAmplitude()
    monkeypatch.setattr(analytics, "client", fake)
    return fake


def browser(device_id="device-abc123", session_id="1763700000000"):
    """A test browser that already holds the two cookies analytics.js sets."""
    client = TestClient(app)
    client.cookies.set("mw_device_id", device_id)
    client.cookies.set("mw_session_id", session_id)
    return client


def test_sign_up_sends_account_created_with_the_browsers_ids(sent):
    sign_up(browser(), "t-signup@example.com")
    user = db.get_user_by_email("t-signup@example.com")

    event = sent.named("Account Created")[0]
    assert event.user_id == user["id"]
    assert event.device_id == "device-abc123"
    assert event.session_id == 1763700000000
    assert event.event_properties == {
        "signup_source": "direct",
        # Phase 7: links the event to the Session Replay of the same visit.
        "[Amplitude] Session Replay ID": "device-abc123/1763700000000",
    }
    assert "signup_date" in event.user_properties["$setOnce"]


def test_sign_up_during_a_booking_is_marked_as_from_checkout(sent):
    client = browser()
    start(client, sessions_for("spoon-carving")[0]["id"])
    sign_up(client, "t-wall@example.com")

    event = sent.named("Account Created")[0]
    assert event.event_properties["signup_source"] == "checkout"


def test_log_in_sends_logged_in(sent):
    sign_up(TestClient(app), "t-login@example.com")
    browser().post(
        "/login", data={"email": "t-login@example.com", "password": "correct-horse"}
    )
    assert len(sent.named("Logged In")) == 1


def test_booking_sends_booking_completed_with_revenue(sent):
    session = sessions_for("spoon-carving")[1]
    client = browser()
    booking_id = book(client, "t-booker@example.com", session["id"], seats=2)
    user = db.get_user_by_email("t-booker@example.com")

    event = sent.named("Booking Completed")[0]
    assert event.event_properties["workshop_name"] == "Carve a Wooden Spoon"
    assert event.event_properties["seats"] == 2
    assert event.event_properties["order_value"] == 110.0     # 2 seats at £55
    assert event.revenue == 110.0
    assert event.insert_id == f"{user['id']}-booking-{booking_id}-completed"
    assert event.session_id == 1763700000000
    assert event.user_properties == {
        "$setOnce": {"first_workshop_category": "Woodwork"},
        "$add": {"total_bookings": 1, "total_spend": 110.0},
    }
    assert sent.named("Booking Failed") == []


def test_declined_card_sends_booking_failed_with_the_reason(sent):
    client = browser()
    sign_up(client, "t-declined@example.com")
    start(client, sessions_for("sourdough")[0]["id"])
    client.post("/checkout", data=DECLINED_CARD)

    event = sent.named("Booking Failed")[0]
    assert event.event_properties["reason"] == "card_declined"
    assert sent.named("Booking Completed") == []


def test_cancelling_twice_sends_one_refund(sent):
    client = browser()
    booking_id = book(client, "t-refund@example.com", sessions_for("sourdough")[2]["id"])

    client.post(f"/bookings/{booking_id}/cancel")
    client.post(f"/bookings/{booking_id}/cancel")

    cancelled = sent.named("Booking Cancelled")
    assert len(cancelled) == 1
    assert cancelled[0].revenue == -48.0
    assert cancelled[0].user_properties == {
        "$add": {"total_bookings": -1, "total_spend": -48.0}
    }


def test_events_are_still_sent_without_the_browser_cookies(sent):
    """For example when an ad blocker stopped the browser SDK loading."""
    sign_up(TestClient(app), "t-blocked@example.com")

    event = sent.named("Account Created")[0]
    assert event.user_id.startswith("usr_")
    assert event.device_id is None
    assert event.session_id is None
    assert event.event_properties == {"signup_source": "direct"}  # no replay link


def test_a_tampered_session_cookie_is_ignored(sent):
    page = sign_up(browser(session_id="not-a-number"), "t-tamper@example.com")

    assert page.status_code == 200
    assert sent.named("Account Created")[0].session_id is None


def test_no_event_carries_personal_or_card_data(sent):
    client = browser()
    book(client, "t-private@example.com", sessions_for("wheel-throwing")[0]["id"])

    everything = str([e.get_event_body() for e in sent.events])
    for secret in ("t-private@example.com", "Robin", "4242", "correct-horse"):
        assert secret not in everything
