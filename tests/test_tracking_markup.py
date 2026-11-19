"""Phase 5 gate, the part that can be checked without a browser.

analytics.js reads everything it sends from data-... attributes that the
templates write. These tests check the attributes are there and correct.
Whether events actually reach Amplitude is checked by hand in the browser.
"""
from fastapi.testclient import TestClient

from app import db, main
from app.main import app
from helpers import GOOD_CARD, sessions_for, sign_up, start


def test_no_tracking_scripts_without_an_api_key():
    page = TestClient(app).get("/")
    assert "cdn.amplitude.com" not in page.text
    assert "analytics.js" not in page.text


def test_tracking_scripts_load_when_a_key_is_set(monkeypatch):
    monkeypatch.setattr(main, "AMPLITUDE_API_KEY", "test-key")
    page = TestClient(app).get("/")
    assert 'data-amplitude-key="test-key"' in page.text
    # Amplitude's script must come before ours.
    assert page.text.index("cdn.amplitude.com") < page.text.index("analytics.js")


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
