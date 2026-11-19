"""Makewell: the web app. Each route function is one page or one form action."""
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth, db, seed

APP_DIR = Path(__file__).parent

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
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


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
    return RedirectResponse("/", status_code=303)


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
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
