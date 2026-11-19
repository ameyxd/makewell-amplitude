"""Phase 1 gate: browsing workshops."""
from fastapi.testclient import TestClient

from app import seed
from app.main import app

client = TestClient(app)


def test_home_lists_every_workshop():
    page = client.get("/")
    assert page.status_code == 200
    for workshop in seed.WORKSHOPS:
        name = workshop[1]
        assert name in page.text


def test_detail_shows_dates_and_seats_left():
    page = client.get("/workshops/wheel-throwing")
    assert page.status_code == 200
    assert "Upcoming dates" in page.text
    assert "6 seats left" in page.text  # capacity 8, 2 taken


def test_full_session_reads_sold_out():
    page = client.get("/workshops/sourdough")
    assert "Sold out" in page.text


def test_nearly_full_session_shows_how_many_left():
    page = client.get("/workshops/spoon-carving")
    assert "2 left" in page.text  # capacity 10, 8 taken


def test_unknown_workshop_is_404():
    page = client.get("/workshops/does-not-exist")
    assert page.status_code == 404
