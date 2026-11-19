"""Makewell: the web app. Each route function below is one page."""
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db, seed

APP_DIR = Path(__file__).parent

# Runs once when the app starts: create the tables, add starter data if empty.
db.init_db()
seed.seed_if_empty()

app = FastAPI()
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


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


# --- Pages ---

@app.get("/")
def home(request: Request):
    """The list of all workshops."""
    return templates.TemplateResponse(
        request, "home.html", {"workshops": db.list_workshops()}
    )


@app.get("/workshops/{slug}")
def workshop_detail(request: Request, slug: str):
    """One workshop and its upcoming sessions."""
    workshop = db.get_workshop(slug)
    if workshop is None:
        return templates.TemplateResponse(request, "not_found.html", status_code=404)

    return templates.TemplateResponse(
        request,
        "workshop.html",
        {"workshop": workshop, "sessions": db.list_sessions(workshop["id"])},
    )
