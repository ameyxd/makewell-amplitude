"""Simulated visitors, so the Amplitude dashboard has something to show.

A new site has no traffic, and only fake data may be used. This
script opens a real browser and walks through Makewell as about 40 made-up
people. Because it is a real browser, everything runs as it would for a
person: the tracking script, Session Replay and the guide.

Run it with the site already running on port 8000:

    python scripts/simulate_traffic.py        all visitors
    python scripts/simulate_traffic.py 3      only the first 3 (a quick trial)

Two things in here are invented, and docs/spec.md says so too:

1. The mix of visitors (how many browse, give up, pay) is made up.
2. A visitor who sees the guide's hint always types the expiry date the
   right way. So the hint "working" in the charts is an assumption written
   into this script, not a finding about real people. What the charts do
   prove is that the plumbing works from page to dashboard.
"""
import random
import sys
from datetime import datetime

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

SITE = "http://localhost:8000"
# Every simulated visitor arrives through this address. Amplitude stores the
# utm_source as a user property, which is how charts tell these visitors
# apart from accounts made by hand while testing.
LANDING_PAGE = SITE + "/?utm_source=simulation"

GOOD_CARD = "4242 4242 4242 4242"
DECLINED_CARD = "4000 0000 0000 0002"
HINT_TEXT = "Use MM/YY"                  # the text of the guide built in Amplitude
RUN = datetime.now().strftime("%H%M")    # keeps emails unique between runs

# What each kind of visitor does, and how many of each there are.
VISITORS = (
    ["browses"] * 7               # looks at workshops and leaves
    + ["stops_at_signup"] * 6     # chooses a date, meets the sign-up page, leaves
    + ["stops_at_checkout"] * 4   # signs up, sees the checkout page, leaves
    + ["pays"] * 20               # tries to pay
    + ["pays_then_cancels"] * 3   # pays, then cancels the booking
)


def pause(page, shortest=0.6, longest=1.8):
    """Wait a moment, as a person would between actions."""
    page.wait_for_timeout(random.uniform(shortest, longest) * 1000)


def type_slowly(page, selector, text):
    """Click a box, clear it, and type into it one key at a time."""
    page.click(selector)
    page.fill(selector, "")
    page.locator(selector).press_sequentially(text, delay=random.randint(60, 140))
    pause(page, 0.3, 0.9)


def look_around(page):
    """Stay on the page for about ten seconds, moving the mouse and scrolling.

    Session Replay uploads its recording in batches, and only starts a new
    batch when something happens on the page. A visitor who sat perfectly
    still and then closed the window would lose the end of their recording.
    """
    for _ in range(5):
        page.mouse.move(random.randint(200, 900), random.randint(150, 600))
        page.mouse.wheel(0, random.choice([150, -150]))
        pause(page, 1.5, 2.5)


def look_at_a_workshop(page):
    cards = page.locator("a.card")
    cards.nth(random.randrange(cards.count())).click()
    pause(page, 1.5, 4)


def choose_a_date(page):
    """Pick any date that is not sold out and press 'Book this workshop'."""
    dates = page.locator("input[name=workshop_session_id]:not([disabled])")
    dates.nth(random.randrange(dates.count())).check()
    pause(page)
    page.click("#booking-form button")


def sign_up(page, number):
    type_slowly(page, "#display_name", f"Sim Visitor {number}")
    type_slowly(page, "#email", f"sim-{RUN}-{number}@example.com")
    type_slowly(page, "#password", "workshop-demo-1")
    page.click("form[action='/signup'] button")


def hint_is_showing(page):
    """True if Amplitude's guide appeared. It is shown to half of all users."""
    try:
        page.get_by_text(HINT_TEXT).first.wait_for(state="visible", timeout=3000)
        return True
    except PlaywrightTimeout:
        return False


def pay(page, number, card_number, writes_long_year):
    """Fill in the card form and press Pay. Returns True if the booking went through."""
    type_slowly(page, "#card_name", f"Sim Visitor {number}")
    type_slowly(page, "#card_number", card_number)

    # The guide appears when the expiry box is clicked, for half of users.
    page.click("#card_expiry")
    saw_hint = hint_is_showing(page)
    if saw_hint:
        pause(page, 2.5, 4)            # reads the hint

    # THE ASSUMPTION: people who see the hint follow it. Without the hint,
    # some people type a four-digit year, which this site refuses.
    if writes_long_year and not saw_hint:
        expiry = "11/2027"
    else:
        expiry = "11/27"
    # The cursor is already in the expiry box, so just type.
    page.keyboard.type(expiry, delay=random.randint(60, 140))
    pause(page, 0.5, 1.2)

    # Having read the hint, the visitor closes it with its X button, if it
    # is still open. "Close pin" is the label Amplitude gives that button.
    close_button = page.locator("button[aria-label='Close pin']")
    if close_button.count() > 0:
        close_button.first.click()
        pause(page, 0.3, 0.9)
    type_slowly(page, "#card_cvc", "123")

    # Check the details for a moment before paying. The mouse movement also
    # gives Session Replay a reason to queue what was just typed for upload.
    pause(page, 1.5, 2.5)
    page.mouse.move(random.randint(300, 600), random.randint(300, 500))
    pause(page, 0.5, 1)

    page.click("#checkout-form button")
    page.wait_for_load_state()
    return "/confirmed" in page.url


def visit(page, number, kind):
    """One person's whole visit."""
    page.goto(LANDING_PAGE)
    pause(page, 1, 3)
    look_at_a_workshop(page)

    if kind == "browses":
        if random.random() < 0.5:      # half of them look at a second workshop
            page.click("a.back")
            pause(page)
            look_at_a_workshop(page)
        return

    choose_a_date(page)                # guests are sent to the sign-up page
    pause(page, 1, 3)
    if kind == "stops_at_signup":
        return

    sign_up(page, number)              # after signing up they land on checkout
    pause(page, 1, 3)
    if kind == "stops_at_checkout":
        return

    # Each payer gets two traits, decided by chance.
    card_declines = random.random() < 0.1       # about 1 in 10 has a card that declines
    writes_long_year = random.random() < 0.5    # about half would type 11/2027
    tries_again = random.random() < 0.6         # after a failure, 6 in 10 try again

    card = DECLINED_CARD if card_declines else GOOD_CARD
    booked = pay(page, number, card, writes_long_year)

    if not booked and tries_again:
        pause(page, 2, 5)              # reads the error message
        # On the second try they use a good card and a two-digit year.
        booked = pay(page, number, GOOD_CARD, writes_long_year=False)

    if booked and kind == "pays_then_cancels":
        pause(page, 2, 4)
        page.click("text=See my bookings")
        pause(page, 1, 3)
        page.click("text=Cancel booking")


def main():
    plan = list(VISITORS)
    random.shuffle(plan)
    if len(sys.argv) > 1:
        plan = plan[: int(sys.argv[1])]

    with sync_playwright() as playwright:
        # channel="msedge" drives the Edge already installed on this PC.
        # headless=False shows the window, so the visit can be watched.
        browser = playwright.chromium.launch(channel="msedge", headless=False)

        for number, kind in enumerate(plan, start=1):
            # A new context is a new person: no cookies, so a new device ID.
            context = browser.new_context()
            page = context.new_page()
            try:
                visit(page, number, kind)
                print(f"{number:>2} {kind}: ended on {page.url}")
            except Exception as error:   # one broken visit must not stop the rest
                print(f"{number:>2} {kind}: FAILED, {error}")
            look_around(page)    # so the end of the replay is uploaded
            context.close()

        browser.close()


if __name__ == "__main__":
    main()
