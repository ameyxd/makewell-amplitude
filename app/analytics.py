"""Server-side Amplitude tracking.

main.py calls track() for facts only the server knows for certain: an
account was created, a booking succeeded, failed or was cancelled.

Sending never slows down or breaks a request. The SDK puts each event in a
queue in memory and a background thread uploads it. If Amplitude cannot be
reached, the SDK retries and then gives up; the booking is unaffected.
"""
import os

from amplitude import Amplitude, BaseEvent, Config

# The Amplitude project to send to. Empty means tracking is switched off.
# This key identifies the project; it is meant to be visible in the browser.
API_KEY = os.environ.get("AMPLITUDE_API_KEY", "")

# `client` stays None when there is no key, and track() then does nothing.
# Queued events are uploaded at most one second later (the SDK's default is
# ten), so they show up in Amplitude quickly.
client = None
if API_KEY:
    client = Amplitude(API_KEY, Config(flush_interval_millis=1000))


def browser_ids(request):
    """The device ID and session ID the browser SDK is using.

    static/js/analytics.js copies them into two cookies on every page load.
    Returns (None, None) if the cookies are missing, for example when an ad
    blocker stopped the browser SDK from loading.
    """
    device_id = request.cookies.get("mw_device_id")
    session_id = request.cookies.get("mw_session_id", "")
    # An Amplitude session ID is a whole number: the session's start time
    # in milliseconds. Anything else is ignored.
    return device_id, int(session_id) if session_id.isdigit() else None


def track(
    request,
    user_id,
    event_type,
    properties,
    revenue=None,
    insert_id=None,
    set_once=None,
    add=None,
):
    """Send one event, on the same user and session as the browser's events.

    revenue:   money in pounds; negative for a refund.
    insert_id: a name for this exact event. Amplitude keeps only the first
               event it receives with a given insert_id, so sending the same
               booking twice by mistake cannot count it twice.
    set_once:  user properties to write only if not already set,
               e.g. {"signup_date": "2026-11-21"}.
    add:       user properties to add to a running total,
               e.g. {"total_bookings": 1}. A negative number subtracts.
    """
    if client is None:
        return

    # Changes to user properties travel inside the event. Amplitude applies
    # them to this event and to everything the user does afterwards.
    user_changes = {}
    if set_once:
        user_changes["$setOnce"] = set_once
    if add:
        user_changes["$add"] = add

    device_id, session_id = browser_ids(request)
    client.track(
        BaseEvent(
            event_type=event_type,
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            event_properties=properties,
            user_properties=user_changes,
            revenue=revenue,
            insert_id=insert_id,
        )
    )
