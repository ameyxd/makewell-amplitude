"""Steps the tests share: sign up, choose a session, pay."""
from app import db

GOOD_CARD = {
    "card_name": "Robin Example",
    "card_number": "4242 4242 4242 4242",
    "card_expiry": "11/27",
    "card_cvc": "123",
}


def sessions_for(slug):
    """The upcoming sessions of one workshop, soonest first."""
    return db.list_sessions(db.get_workshop(slug)["id"])


def seats_taken(workshop_session_id):
    return db.get_session(workshop_session_id)["seats_taken"]


def sign_up(client, email, name="Robin"):
    return client.post(
        "/signup",
        data={"display_name": name, "email": email, "password": "correct-horse"},
    )


def start(client, workshop_session_id, seats=1):
    """Choose a session and a number of seats."""
    return client.post(
        "/bookings/start",
        data={"workshop_session_id": workshop_session_id, "seats": seats},
    )


def book(client, email, workshop_session_id, seats=1):
    """Sign up, choose a session and pay. Returns the new booking's id."""
    sign_up(client, email)
    start(client, workshop_session_id, seats)
    page = client.post("/checkout", data=GOOD_CARD)
    return int(page.url.path.split("/")[2])   # /bookings/<id>/confirmed
