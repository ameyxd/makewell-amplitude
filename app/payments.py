"""A pretend card processor.

No real payment happens. Card details are checked, used once to decide
"approved" or "declined", and never stored or logged.
"""

APPROVED_CARD = "4242424242424242"
DECLINED_CARD = "4000000000000002"


def digits_only(card_number):
    """'4242 4242 4242 4242' -> '4242424242424242'."""
    return card_number.replace(" ", "")


def expiry_ok(card_expiry):
    """True only for MM/YY, e.g. '11/27'.

    PLANTED FRICTION, disclosed in the README: '11/2027' is a perfectly
    reasonable thing to type, but it fails here, and the page only says
    "Invalid card details". This gives the Session Replay investigation a
    real problem to find.
    """
    parts = card_expiry.strip().split("/")
    if len(parts) != 2:
        return False
    month, year = parts
    if len(month) != 2 or len(year) != 2:
        return False
    # THE REAL FIX, kept as a comment so the planted friction stays in place.
    # To accept '11/2027' as well as '11/27', replace the two lines above with:
    #
    #     if len(month) != 2 or len(year) not in (2, 4):
    #         return False
    #
    # The year may then be two digits or four. Nothing else changes: the
    # digit check and the month check below already work for both.
    # Two tests post '11/2027' and expect it to fail, so they must change too:
    # the one in tests/test_booking.py should expect a booking, and the one
    # in tests/test_tracking_markup.py needs another bad value, such as '13/27'.
    if not (month.isdigit() and year.isdigit()):
        return False
    return 1 <= int(month) <= 12


def card_details_ok(card_name, card_number, card_expiry, card_cvc):
    """True if all four fields are filled in the way we expect."""
    cvc = card_cvc.strip()
    return (
        card_name.strip() != ""
        and digits_only(card_number) in (APPROVED_CARD, DECLINED_CARD)
        and expiry_ok(card_expiry)
        and len(cvc) == 3
        and cvc.isdigit()
    )


def charge(card_number, amount_pence):
    """Pretend to take the money. Returns 'approved' or 'declined'."""
    if digits_only(card_number) == DECLINED_CARD:
        return "declined"
    return "approved"
