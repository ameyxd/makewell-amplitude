"""Makewell: the web app. Each route function is one page or one form action."""
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth, db, payments, seed

APP_DIR = Path(__file__).parent

MAX_SEATS = 4  # the most seats one booking can take

# What the checkout page says for each way a booking can fail.
FAILURE_MESSAGES = {
    "invalid_details": "Invalid card details.",
    "session_full": "Sorry, this date no longer has enough seats. You have not been charged.",
    "card_declined": "Your card was declined. You have not been charged.",
}

# Runs once when the app starts: create the tables, add starter data if empty.
db.init_db()
seed.seed_if_empty()

app = FastAPI()
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

# Login memory. This keeps a signed cookie in the browser holding the user's
# id. "Signed" means the browser can read it but cannot change it unnoticed.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "dev-only-secret"),
)


# --- Small formatting helpers the templates use, e.g. {{ price|pounds }} ---

def pounds(pence):
    """6500 -> '£65', 4850 -> '£48.50'."""
    if pence % 100 == 0:
        return f"£{pence // 100}"
    return f"£{pence / 100:.2f}"


def nice_date(text):
    """'2026-11-21T10:00' -> 'Sat 21 Nov, 10:00'."""
    when = datetime.fromisoformat(text)
    return f"{when:%a} {when.day} {when:%b}, {when:%H:%M}"


def duration(minutes):
    """150 -> '2 hrs 30 min', 120 -> '2 hrs'."""
    hours, rest = divmod(minutes, 60)
    return f"{hours} hrs {rest} min" if rest else f"{hours} hrs"


templates.env.filters["pounds"] = pounds
templates.env.filters["nice_date"] = nice_date
templates.env.filters["duration"] = duration


# --- Helpers every page uses ---

def current_user(request):
    """The logged-in user's database row, or None for a guest."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get_user(user_id)


def render(request, template, context=None, status_code=200):
    """Build a page. Adds `user` so the header can show who is logged in."""
    context = context or {}
    context["user"] = current_user(request)
    context["has_pending_booking"] = "pending" in request.session
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


def pending_booking(request):
    """The session and seats this visitor chose, with the total price.

    The choice is kept in the login cookie under "pending" until they pay.
    Returns None if they have not chosen anything.
    """
    pending = request.session.get("pending")
    if pending is None:
        return None

    workshop_session = db.get_session(pending["workshop_session_id"])
    if workshop_session is None:
        return None

    return {
        "workshop_session": workshop_session,
        "seats": pending["seats"],
        "amount_pence": workshop_session["price_pence"] * pending["seats"],
    }


def after_login(request):
    """Where to send someone who has just signed up or logged in."""
    if "pending" in request.session:
        return RedirectResponse("/checkout", status_code=303)
    return RedirectResponse("/", status_code=303)


# --- Browse ---

@app.get("/")
def home(request: Request):
    """The list of all workshops."""
    return render(request, "home.html", {"workshops": db.list_workshops()})


@app.get("/workshops/{slug}")
def workshop_detail(request: Request, slug: str):
    """One workshop and its upcoming sessions."""
    workshop = db.get_workshop(slug)
    if workshop is None:
        return render(request, "not_found.html", status_code=404)

    return render(
        request,
        "workshop.html",
        {"workshop": workshop, "sessions": db.list_sessions(workshop["id"])},
    )


# --- Accounts ---

@app.get("/signup")
def signup_form(request: Request):
    return render(request, "signup.html")


@app.post("/signup")
def signup(
    request: Request,
    display_name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
):
    """Create an account and log the new user in."""
    display_name = display_name.strip()
    email = email.strip().lower()

    error = None
    if not display_name:
        error = "Enter your name."
    elif "@" not in email:
        error = "Enter a valid email address."
    elif len(password) < 8:
        error = "Use a password of at least 8 characters."
    elif db.get_user_by_email(email):
        error = "That email already has an account. Log in instead."

    if error:
        return render(
            request,
            "signup.html",
            {"error": error, "display_name": display_name, "email": email},
            status_code=400,
        )

    salt = auth.new_salt()
    user_id = db.create_user(
        email, display_name, auth.hash_password(password, salt), salt
    )
    request.session["user_id"] = user_id
    return after_login(request)


@app.get("/login")
def login_form(request: Request):
    return render(request, "login.html")


@app.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form("")):
    """Check the password and log the user in."""
    email = email.strip().lower()
    user = db.get_user_by_email(email)

    if user is None or not auth.password_matches(
        password, user["salt"], user["password_hash"]
    ):
        return render(
            request,
            "login.html",
            {"error": "Email or password is incorrect.", "email": email},
            status_code=400,
        )

    request.session["user_id"] = user["id"]
    return after_login(request)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# --- Booking ---

@app.post("/bookings/start")
def start_booking(
    request: Request,
    workshop_session_id: int = Form(0),
    seats: int = Form(1),
):
    """Remember the chosen session and seats, then go to checkout."""
    workshop_session = db.get_session(workshop_session_id)
    if workshop_session is None:
        return render(request, "not_found.html", status_code=404)

    if seats < 1 or seats > MAX_SEATS or seats > workshop_session["seats_left"]:
        workshop = db.get_workshop(workshop_session["slug"])
        return render(
            request,
            "workshop.html",
            {
                "workshop": workshop,
                "sessions": db.list_sessions(workshop["id"]),
                "error": "That date does not have enough seats left.",
            },
            status_code=400,
        )

    request.session["pending"] = {
        "workshop_session_id": workshop_session_id,
        "seats": seats,
    }
    return RedirectResponse("/checkout", status_code=303)


@app.get("/checkout")
def checkout_form(request: Request):
    """The payment page. Guests are sent to sign up first: the account wall."""
    if current_user(request) is None:
        return RedirectResponse("/signup", status_code=303)

    order = pending_booking(request)
    if order is None:
        return RedirectResponse("/", status_code=303)

    return render(request, "checkout.html", {"order": order})


@app.post("/checkout")
def checkout(
    request: Request,
    card_name: str = Form(""),
    card_number: str = Form(""),
    card_expiry: str = Form(""),
    card_cvc: str = Form(""),
):
    """Check the card, check the seats, charge, then save the booking."""
    user = current_user(request)
    if user is None:
        return RedirectResponse("/signup", status_code=303)

    order = pending_booking(request)
    if order is None:
        return RedirectResponse("/", status_code=303)

    workshop_session = order["workshop_session"]
    booking_id = None
    reason = None  # why the booking failed, if it did

    if not payments.card_details_ok(card_name, card_number, card_expiry, card_cvc):
        reason = "invalid_details"
    elif workshop_session["seats_left"] < order["seats"]:
        reason = "session_full"
    elif payments.charge(card_number, order["amount_pence"]) == "declined":
        reason = "card_declined"
    else:
        booking_id = db.create_booking(
            user["id"], workshop_session["id"], order["seats"], order["amount_pence"]
        )
        if booking_id is None:  # someone took the last seats a moment ago
            reason = "session_full"

    if reason:
        return render(
            request,
            "checkout.html",
            {"order": order, "error": FAILURE_MESSAGES[reason], "card_name": card_name},
            status_code=400,
        )

    del request.session["pending"]
    return RedirectResponse(f"/bookings/{booking_id}/confirmed", status_code=303)


@app.get("/bookings/{booking_id}/confirmed")
def booking_confirmed(request: Request, booking_id: int):
    """The confirmation page. Only the person who booked can see it."""
    user = current_user(request)
    booking = db.get_booking(booking_id)

    if user is None or booking is None or booking["user_id"] != user["id"]:
        return render(request, "not_found.html", status_code=404)

    return render(request, "confirmed.html", {"booking": booking})


# --- My bookings ---

@app.get("/my-bookings")
def my_bookings(request: Request):
    """Everything the logged-in user has booked."""
    user = current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    return render(
        request,
        "my_bookings.html",
        {"bookings": db.list_bookings(user["id"]), "now": db.now_text()},
    )


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(request: Request, booking_id: int):
    """Cancel a booking for a full refund.

    Only the person who booked can cancel, and only before the workshop starts.
    """
    user = current_user(request)
    booking = db.get_booking(booking_id)

    if user is None or booking is None or booking["user_id"] != user["id"]:
        return render(request, "not_found.html", status_code=404)

    if booking["starts_at"] > db.now_text():
        db.cancel_booking(booking)

    return RedirectResponse("/my-bookings", status_code=303)
