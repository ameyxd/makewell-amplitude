"""Phase 5 gate, the part that can be checked without a browser.

analytics.js reads everything it sends from data-... attributes that the
templates write. These tests check the attributes are there and correct.
Whether events actually reach Amplitude is checked by hand in the browser.
"""
from fastapi.testclient import TestClient

from app import analytics, db
from app.main import app
from helpers import GOOD_CARD, sessions_for, sign_up, start


def test_no_tracking_scripts_without_an_api_key():
    page = TestClient(app).get("/")
    assert "cdn.amplitude.com" not in page.text
    assert "analytics.js" not in page.text


def test_tracking_scripts_load_when_a_key_is_set(monkeypatch):
    monkeypatch.setattr(analytics, "API_KEY", "test-key")
    page = TestClient(app).get("/")
    assert 'data-amplitude-key="test-key"' in page.text
    # Amplitude's two scripts must come before ours, the SDK first.
    sdk = page.text.index("analytics-browser")
    replay = page.text.index("plugin-session-replay-browser")
    ours = page.text.index("/static/js/analytics.js")
    assert sdk < replay < ours
    # Our script's address carries a version, so an edited file is never
    # served from a browser's old copy.
    assert "/static/js/analytics.js?v=" in page.text


def test_the_visitors_name_is_marked_private_for_session_replay():
    """Phase 7. Replay hides the text of anything marked data-private."""
    session = sessions_for("linocut")[2]
    client = TestClient(app)
    sign_up(client, "replay@example.com", name="Zephyrine")
    start(client, session["id"])
    confirmed = client.post("/checkout", data=GOOD_CARD)

    # Header greeting plus the confirmation heading: the name is shown twice,
    # and both times it sits directly inside a tag carrying the marker.
    assert confirmed.text.count("Zephyrine") == 2
    assert "data-private>Hi, Zephyrine<" in confirmed.text
    assert "<span data-private>Zephyrine</span>" in confirmed.text


def test_guest_page_has_an_empty_user_id():
    page = TestClient(app).get("/")
    assert 'data-user-id=""' in page.text


def test_logged_in_page_carries_the_user_id_and_never_the_email():
    client = TestClient(app)
    sign_up(client, "tracked@example.com")
    user = db.get_user_by_email("tracked@example.com")

    page = client.get("/")
    assert f'data-user-id="{user["id"]}"' in page.text
    assert "tracked@example.com" not in page.text


def test_workshop_page_describes_the_workshop():
    page = TestClient(app).get("/workshops/linocut")
    assert 'data-page="workshop"' in page.text
    assert 'data-workshop-name="Linocut Printmaking"' in page.text
    assert 'data-category="Printmaking"' in page.text
    assert 'data-price="42.0"' in page.text
    assert 'data-sessions-available="3"' in page.text
    assert "data-seats-left=" in page.text
    assert "data-days-until=" in page.text


def test_checkout_page_describes_the_order():
    session = sessions_for("wheel-throwing")[1]
    client = TestClient(app)
    sign_up(client, "order@example.com")
    page = start(client, session["id"], seats=2)

    assert 'data-page="checkout"' in page.text
    assert f'data-workshop-session-id="{session["id"]}"' in page.text
    assert 'data-seats="2"' in page.text
    assert 'data-order-value="130.0"' in page.text      # 2 seats at £65
    assert 'data-currency="GBP"' in page.text


def test_failed_payment_page_is_not_counted_as_a_new_checkout():
    session = sessions_for("wheel-throwing")[1]
    client = TestClient(app)
    sign_up(client, "retry@example.com")
    start(client, session["id"])

    page = client.post("/checkout", data={**GOOD_CARD, "card_expiry": "11/2027"})
    assert 'data-page="checkout-error"' in page.text
