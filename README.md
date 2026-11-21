# Makewell

Makewell sells places on craft workshops: pottery, bread, woodwork. Visitors choose a workshop and a date, create an account and pay by card.

The client's problem: more people showed interest than booked, and support heard "I tried to pay and it didn't work". Their database only records bookings that succeeded, so nobody could see where people dropped out, or why.

This repository is the site, instrumented with Amplitude to answer that question: analytics from the browser and the server, Session Replay, and one in-app guide.

Everything in it is fake: the workshops, the people, the payments and the traffic.

## Run it

Needs Python 3 (developed and tested on 3.14). Commands are for Windows PowerShell.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Then open http://localhost:8000.

- **Amplitude:** put the project's API key in `.env`. With the key empty, the site runs with tracking switched off.
- **Blockers:** ad and tracker blockers stop the browser's events. Pause them while testing.
- **Database:** one file, `makewell.db`, created with starter data on first run. Delete it to start fresh.
- **Paying:** card `4242 4242 4242 4242` is approved and `4000 0000 0000 0002` is declined. Expiry as `MM/YY`, any three-digit security code.

Tests: `.venv\Scripts\python -m pytest`

Simulated visitors (optional, needs Microsoft Edge): `.venv\Scripts\python scripts\simulate_traffic.py`

## Read more

- [Spec](docs/spec.md): the design, including the tracking plan (section 7) and what the data showed (section 13).
- [Requirements](docs/requirements.md): what the project must do, and how each requirement is met.
