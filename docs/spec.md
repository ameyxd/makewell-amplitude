# Spec: Makewell

A small site where people book a seat in a craft workshop. Build progress is tracked in section 16.

Status key: **Decided** = settled. **Proposed** = suggested, not yet settled. **Open** = unanswered.

## 1. Summary

A guest browses workshops, picks a dated session and a number of seats, creates an account, pays with a fake card and gets a confirmation. They can later cancel for a refund. The server owns seat counts, payment results and bookings.

The app exists to carry the instrumentation. Every page is one route and one template, so any change is small.

The app is called **Makewell**. The name appears only in the base template, so changing it is a one-line edit.

## 2. Decisions so far

| Decision | Choice | Status |
|---|---|---|
| App | Workshop booking, creative crafts | Decided |
| Server | Python with FastAPI, pages rendered on the server | Decided |
| Payment | Our own fake card form; server approves or declines by test rules | Decided |
| Version 1 extra | Cancel a booking with refund | Decided |
| Visual style | Warm editorial light | Decided |
| Hosting | Local only | Decided |
| Amplitude account | A free-plan project | Decided |
| Account wall | Sign-up is required after choosing a session, before paying | Decided |
| Database | SQLite through Python's built-in `sqlite3`, no ORM | Decided |
| Login | Email and password | Decided |
| Planted friction for the replay investigation | See section 13 | Decided |
| Automatic capture | Page views and sessions on; clicks and forms off | Decided |
| Code style | Simple and minimal; see the rules below | Decided |
| Delivery | Phases with exit gates and one commit each; see section 16 | Decided |
| App name | Makewell | Decided |
| Guide | A hint on the checkout page; see section 11 | Decided |

### Simplicity rules

- One route, one template, one job. No layers that only pass values along.
- Standard library first. A package is added only when it removes more code than it adds.
- No classes where a function will do. No clever one-liners.
- Each file is short enough to read in one sitting, and each phase adds only what that phase needs.
- If a line cannot be explained in a sentence, it is rewritten.

## 3. Stack

| Part | Choice | Why |
|---|---|---|
| Web framework | FastAPI + Uvicorn | Small and well documented; pages and forms need little code |
| Pages | Jinja2 templates | Plain HTML; no front-end build step |
| Forms | Standard HTML forms (`python-multipart`) | Each action is a normal page request |
| Database | SQLite, `sqlite3` module | No extra concepts to explain |
| Login session | Signed cookie (Starlette `SessionMiddleware`, which needs the `itsdangerous` package) | A few lines; no session table |
| Passwords | `hashlib.pbkdf2_hmac` with a per-user salt | Standard library only |
| Server tracking | `amplitude-analytics` (Python SDK) | Official SDK |
| Browser tracking | Amplitude Browser SDK 2 by script tag | No bundler in this project |
| Session Replay | Amplitude Session Replay plugin by script tag | Shares identity with the SDK |
| Guides | Amplitude Guides & Surveys by script tag | Same |
| Test traffic | Playwright for Python | Real browser sessions produce real replays |
| Settings | `.env` file read with `python-dotenv` | Keeps the API key out of the code |

All browser tracking code lives in one file, `app/static/js/analytics.js`.

## 4. Pages and routes

| Route | Method | Page or action | Login needed |
|---|---|---|---|
| `/` | GET | Workshop list | No |
| `/workshops/{slug}` | GET | Workshop detail with its sessions and seats left | No |
| `/bookings/start` | POST | Remember the chosen session and seats, go to checkout | No |
| `/signup` | GET, POST | Create account | No |
| `/login` | GET, POST | Log in | No |
| `/logout` | POST | Log out | Yes |
| `/checkout` | GET | Booking summary and card form | Yes (guests are sent to sign-up first) |
| `/checkout` | POST | Check seats, charge, create booking | Yes |
| `/bookings/{id}/confirmed` | GET | Confirmation | Yes |
| `/my-bookings` | GET | List of the user's bookings | Yes |
| `/bookings/{id}/cancel` | POST | Cancel and refund | Yes |

## 5. Data model

| Table | Columns |
|---|---|
| `users` | `id` (text, e.g. `usr_3f9a…`), `email`, `password_hash`, `salt`, `display_name`, `created_at` |
| `workshops` | `id`, `slug`, `name`, `category`, `blurb`, `description`, `price_pence`, `duration_minutes`, `tone` (the card's colour) |
| `workshop_sessions` | `id`, `workshop_id`, `starts_at`, `capacity`, `seats_taken` |
| `bookings` | `id`, `user_id`, `workshop_session_id`, `seats`, `amount_pence`, `status` (`confirmed` or `cancelled`), `created_at`, `cancelled_at` |

Notes:

- A dated class is called a **workshop session** everywhere, so it is never confused with an Amplitude session.
- User IDs are long text values. Amplitude rejects IDs shorter than 5 characters by default.
- Card details are never stored.

## 6. Core journey and funnel

1. View a workshop.
2. Select a session and seats.
3. Sign up or log in (only if not already logged in).
4. Reach checkout.
5. Submit payment.
6. Booking confirmed, or failed with a reason.

Fake card rules: `4242 4242 4242 4242` approves; `4000 0000 0000 0002` declines; anything else fails validation. The security code must be three digits and the expiry must be `MM/YY`.

How a booking is decided, in order: card details are checked, then the seats, then the card is "charged", then the seats are taken and the booking saved in one database step. Each failure has a reason code (`invalid_details`, `session_full`, `card_declined`) that the tracking reuses.

The chosen session and seat count are kept in the login cookie until payment, so they survive the trip through sign-up. One booking takes at most four seats.

Cancelling: the person who booked can cancel any time before the workshop starts, for a full refund. The booking is marked cancelled, not deleted, and its seats go back on sale.

## 7. Tracking plan

### Rules

- Event names: Title Case, object then past-tense verb.
- Property names: `snake_case`.
- One owner per event: browser or server, never both.
- No personal data in any event: no email, name or card value.
- Money is sent as a number in pounds, with `currency`.

### Events

| Event | Sent by | Fires when | Properties | Why we track it |
|---|---|---|---|---|
| `Workshop Viewed` | Browser | Detail page loads | `workshop_id`, `workshop_name`, `category`, `price`, `sessions_available` | Top of the funnel; shows which workshops attract interest |
| `Session Selected` | Browser | Booking form is submitted | `workshop_id`, `workshop_session_id`, `seats`, `seats_left`, `days_until_session` | First sign of intent; shows whether scarcity or date affects choice |
| `Checkout Started` | Browser | Checkout page loads | `workshop_id`, `workshop_session_id`, `seats`, `order_value`, `currency` | Marks who got past the account wall |
| `Payment Submitted` | Browser | The payment form is submitted | `workshop_session_id`, `order_value`, `currency` | Attempts, to compare with outcomes |
| `Account Created` | Server | User row is saved | `signup_source` (`checkout` or `direct`) | Fact of record; first event carrying both device ID and user ID |
| `Logged In` | Server | Password check passes | `login_source` | Returning-user activity |
| `Booking Completed` | Server | Booking row is saved | `booking_id`, `workshop_id`, `workshop_name`, `workshop_session_id`, `category`, `seats`, `order_value`, `currency`, plus revenue | The outcome that matters; must not depend on the browser |
| `Booking Failed` | Server | Server rejects the booking | `reason` (`session_full`, `card_declined`, `invalid_details`), `workshop_session_id`, `seats`, `order_value` | Tells us why people fail at the last step |
| `Booking Cancelled` | Server | Booking is cancelled | `booking_id`, `workshop_id`, `workshop_name`, `refund_amount`, `currency`, `hours_before_session`, plus negative revenue | Refunds reduce revenue; shows late-cancel patterns |

Server event details (built in phase 6, all in `app/analytics.py`):

- **Revenue.** `Booking Completed` carries `revenue` in pounds; `Booking Cancelled` carries the same amount as a negative number, so Amplitude's revenue totals are net of refunds.
- **No double counting.** The two money events carry an `insert_id` built from the user ID and booking ID. Amplitude keeps only the first event with a given `insert_id`. A second cancel is also stopped earlier, by the database.
- **If Amplitude is unreachable.** The SDK queues events in memory and uploads on a background thread, so a request never waits for Amplitude and never fails because of it. Events still queued when the server is killed are lost; a production system would use a durable queue.

That is nine events: four from the browser and five from the server. A tenth, `Checkout Validation Failed`, was dropped on 2026-11-18 because card details are checked only on the server, where the same failure is `Booking Failed` with reason `invalid_details`.

Automatic capture:

| Feature | Setting | Why |
|---|---|---|
| Page views, sessions | On | Free context for every visit |
| Attribution (where the visitor came from) | On | Costs nothing; useful for a real customer |
| Form interactions, file downloads, element clicks | Off | Generic events; the named steps above are clearer |

The SDK also adds page details (address, title, previous page) to every browser event. That is its default and contains no personal data here. Amplitude's project settings can override these choices remotely.

Counting rules built into the pages:

- `Workshop Viewed` and `Checkout Started` fire on page load. When the same page is shown again after a failed choice or payment, it is labelled as an error page and the event does not fire a second time.
- `Session Selected` and `Payment Submitted` fire on form submission. Anything still unsent when the page changes is sent as the page closes.

### User properties

| Property | Operation | Set when | Why |
|---|---|---|---|
| `signup_date` | Set once | Account created | Group users by when they joined |
| `first_workshop_category` | Set once | First booking | Does the first craft predict repeat booking? |
| `total_bookings` | Add 1 / subtract 1 | Booking completed / cancelled | Split first-time from repeat customers |
| `total_spend` | Add / subtract | Booking completed / cancelled | Find high-value customers |

These changes travel inside the server event that causes them (`$setOnce` and `$add` in the event's `user_properties`), so the event itself already shows the new values. A separate Identify call was tried first and dropped: on 2026-11-21 it sometimes reached Amplitude after the event it belonged to, leaving that event with the old values.

## 8. Identity design

| Moment | What happens |
|---|---|
| First visit | Browser SDK creates a device ID. Events carry the device ID only. |
| Sign-up or login | The next page carries the user ID in `data-user-id`; `analytics.js` passes it to the SDK when it starts. The first event with both IDs links them in Amplitude, and earlier guest events join that user. |
| Logout | Submitting the logout form calls `reset()`: the user ID is cleared and a new device ID is made, so the next person on that browser is a new anonymous user. |
| Every page load | `analytics.js` copies the SDK's device ID and session ID into two cookies, `mw_device_id` and `mw_session_id`, so the server can read them. |
| Server events | Carry user ID, device ID and session ID, so they sit in the same user and session as browser events. `Account Created` is the first event with both IDs. |
| Cookies missing (for example an ad blocker stopped the browser SDK) | Every server event belongs to a logged-in user, so it is still sent, with the user ID alone. Outcomes are never lost to a blocker; only the browser steps are. |

## 9. Browser versus server

| Sent from the browser | Sent from the server |
|---|---|
| What the user tried to do: views, selections, submissions, form errors | What actually happened: account created, booking completed, failed or cancelled |
| Can be lost to ad blockers and closed tabs | Cannot be blocked or faked by the user |
| Knows the page and session | Knows the truth about seats, payment and money |

## 10. Session Replay

| Topic | Choice | Reason |
|---|---|---|
| Linking | Replay plugin added to the same SDK instance | It then uses the same device ID and session ID as every event |
| Sample rate here | 100% | Low traffic; every test session should be watchable |
| Sample rate for a high-traffic customer | Monthly replay quota divided by monthly sessions, then adjusted | Example: 500,000 replays for 5 million sessions is 10% |
| Form inputs | All masked (mask level `medium`) | Passwords, emails and card numbers are never recorded |
| Email and names shown on the page | Masked with a `data-private` marker | They appear in the header and on the confirmation page |
| Card form | Masked, not blocked | Blocking hides the whole area, so we could not see which field caused trouble |
| Prices, workshop names | Left visible | Not personal; needed to understand a replay |
| Attributes | No personal data in `placeholder`, `title` or `aria-label` | Those are recorded as plain text |

Replay settings can also be changed in Amplitude's interface, and those remote settings override the code.

As built (phase 7):

- `base.html` loads the replay plugin script between Amplitude's SDK and our file. `analytics.js` adds the plugin before `init()`, and skips it if a blocker stopped the plugin script, so the rest of the tracking still runs.
- The browser SDK stamps each of its events with `[Amplitude] Session Replay ID` (`<device ID>/<session ID>`). `app/analytics.py` adds the same property to server events when it has both IDs, so `Booking Failed` and `Booking Completed` also link to the replay.
- That server-side link assumes the visit was recorded. At a sample rate below 100% it would sometimes point at a replay that does not exist; the fix is a third cookie saying whether this session is being recorded.
- Masking was checked on 2026-11-21 by downloading the stored recording of a test visit and searching it: the typed name, email, password, card name, card number, expiry and security code were all absent; the greeting in the header was stored as `*** *****`; workshop names, prices and the "Invalid card details." message were present.
- A masked field keeps its length (a seven-letter name was stored as seven asterisks). The planted friction should therefore still be visible as seven asterisks in the expiry field, then five. The first automated test visit recorded page loads but not typing, because its browser window had no focus and it moved between pages within a second. **Confirmed by hand 2026-11-21:** a visit made in a normal browser gave a replay that covers the whole visit and shows typing as asterisks. It showed five asterisks on the good try but not seven on the failed try.
- **Defect found and fixed 2026-11-21: the end of each page's typing was missing from the recording.** The stored recording of that visit was downloaded and its input events counted. Across five "Pay" clicks, three lost the last 6 to 7 seconds before the click. On the `11/2027` try only the first four characters of the expiry and none of the security code were stored. The recording's own settings show why this can happen: the plugin (1.37.1) was keeping events in memory (`storeType: "memory"`) and uploading them in batches up to 10 seconds apart, so whatever had not been uploaded when "Pay" loaded the next page was lost. Our pages reload on every form submit, so this hits exactly the moment the investigation needs.
- The fix is `storeType: 'idb'` in `analytics.js`, which keeps unsent recording in the browser's own storage (IndexedDB) so the next page can upload it. **Verified 2026-11-21** on a second visit made by hand: the stored recording of the `11/2027` try has all seven expiry characters and all three of the security code (the last typed two seconds before "Pay"), and the good try has five and three. Nothing was missing before either click. It cannot be checked in a hidden browser window, because the plugin does not upload while the page is hidden.
- Cost of the fix: recording waits in the browser's storage until a later page of this site uploads it. If "Pay" were the visitor's last page ever, its last seconds would stay on their computer and never arrive.
- Browsers were running a stale copy of `analytics.js` (found 2026-11-21: a test visit sent no cookies and recorded no replay). Script and stylesheet addresses now carry `?v=<time last changed>` through `static_url` in `main.py`.

## 11. Guide

**Decided 2026-11-21: Candidate C, a hint on the checkout page.** It is built in Amplitude, not in code.

| | Candidate C |
|---|---|
| What | A short hint on the checkout page: "Use MM/YY for the expiry date, for example 11/27" |
| Why this one | It answers the problem the dashboard and the replay find (most failed bookings are `invalid_details`, caused by the expiry format), and it ships without a code deploy |
| Shape | A pin on the expiry date box (`#card_expiry`), open by default |
| Audience | Page: address contains `/checkout`. Who: All Users at a 50% rollout, bucketed by ID. The other half is the comparison group |
| Trigger | When element clicked: `#card_expiry` (changed on 2026-11-21 from Immediately, which showed the hint before the visitor had reached the field; the first three real testers dismissed it within 1 to 9 seconds, before typing anything). The "Got it!" button was removed at the same time |
| Known gap | A visitor who reaches the box with the Tab key does not click it, so does not get the hint. Covering Tab needs a browser event on focus to trigger on, which means a code release; that was turned down because the point of the guide is that it ships without one |
| Not used | Showing it only after a failure would need a trigger on `Booking Failed`, which the server sends; guides can only be triggered by events the browser sends |
| Measured by | Share of `Payment Submitted` that reach `Booking Completed`, and the count of `Booking Failed` with reason `invalid_details`, for people who saw the hint and people who did not |
| Easy to miss | "Disable auto-advance on target click" must be on. By default, clicking a pin's target completes the guide, and our target is the box people click to type in |

As built (phase 8):

- `base.html` loads `https://cdn.amplitude.com/script/<API key>.engagement.js` after the replay plugin. `analytics.js` adds `window.engagement.plugin()`, and skips it if a blocker stopped the script. It was first added before `init()`; since phase 9 it is added after the SDK has started (section 13 says why).
- Checked in the browser on 2026-11-21: the script loads, `window.engagement` exists, and it calls `gs.amplitude.com` for its configuration and decisions. No errors.
- The guide itself is built in Amplitude. It is not in the repository.
- Published on 2026-11-21 as "Checkout Expiry Hint": one pin step titled "Expiry Date Format", at first with a "Got it!" button, which was removed when the trigger changed.
- Gate check, 2026-11-21. Nine test accounts were made by hand and each was taken to checkout. Each account's events were then read from Amplitude:

  | Accounts | Result | Counts toward the gate? |
  |---|---|---|
  | Test A, B, C, D | Saw the hint, but every guide event carries `Is From Debug Mode: true`. The preview bar was still active in that browser, and preview shows the guide to everyone | No |
  | Test F, G, J | Saw the hint. `Guide Viewed` on `/checkout` only, within a second of the page loading, then `Guide Completed` through the button (`Was Completed Via CTA: true`) | Yes |
  | Test H, I | Reached checkout, no guide event of any kind | Yes |

  So of five real accounts, three saw it and two did not, and no account has a guide event on any page other than `/checkout`. Both halves of the gate are met.
- The hint reached brand-new users: `Guide Viewed` came one second after `Account Created`.
- Second check, after the trigger changed to a click (2026-11-21, accounts Test K to N). Read from events and from the stored replay recordings:
  - Test L and Test N: the hint was drawn 0.2 seconds after a click on the expiry box, on `/checkout`, with `Is From Debug Mode: false`. Both then closed it (`Guide Dismissed`). Test N clicked the box again afterwards and the hint did not return, so "Stop showing when dismissed" works.
  - Test K and Test M: reached checkout with no guide event. Their recordings do not show a click on the expiry box, so from the data alone they do not prove the holdout under the new trigger. The no-hint case was seen by hand, and the 50% split itself was proven above (Test H and I) and has not been changed.
  - Not seen in any recording: someone typing in the box while the hint is open. It was then confirmed by hand with account Test Q: the hint stays open while typing in the box.
  - The replay recording contains the hint's text, so a replay shows the guide appearing.
- Consequences for phase 9: charts that count who saw the hint must exclude `Is From Debug Mode = true`. And once a user closes the hint, "Stop showing when dismissed" keeps it from returning, including on the page shown after a failed payment.
- Free plan, read from the account on 2026-11-21: one published guide ("Published Guides 0 / 1"). Amplitude's docs say standard triggers, event triggers and cohort targeting are on every plan.

The earlier candidates, kept for the record:

| | Candidate A | Candidate B |
|---|---|---|
| What | Banner for people who chose a session but never booked | Tooltip on the sign-up page explaining why an account is needed |
| Audience | Behaviour: did `Session Selected`, not `Booking Completed` | Page: guests arriving at sign-up from a booking |
| Needs | Targeting by behaviour or cohort | Targeting by page only |
| Measured by | Conversion from `Session Selected` to `Booking Completed`, seen versus not seen | Conversion from `Session Selected` to `Account Created`, seen versus not seen |

A and B were set aside because neither follows from what the replay investigation finds.

## 12. Dashboard

Question: **where do people drop off before a confirmed booking, and why?**

| Chart | Type | Shows |
|---|---|---|
| Booking funnel | Funnel | `Workshop Viewed` → `Session Selected` → `Account Created` → `Checkout Started` → `Payment Submitted` → `Booking Completed` |
| Why bookings fail | Bar | `Booking Failed` split by `reason` |
| Booking rate by category | Funnel, grouped | `Workshop Viewed` → `Booking Completed` by `category`: whether some crafts convert worse |
| Booked and refunded by workshop | Bar | Sum of `order_value` on `Booking Completed` and of `refund_amount` on `Booking Cancelled`, by `workshop_name` |
| Payment success: hint against no hint | Funnel, segmented | `Payment Submitted` → `Booking Completed` for users who saw the guide and those who did not |

As built: the dashboard is "Makewell: Where Bookings are Lost". Every chart is filtered to the simulated visitors (`initial_utm_source = simulation`).

## 13. Test data and the replay investigation

- A Playwright script drives a real browser through the site as about 30 fake people with different behaviour: browsers, abandoners at the account wall, declined cards, successful bookers, cancellers.
- All names and emails are invented (`@example.com`).
- **Planted friction:** the card expiry field accepts only `MM/YY` and shows a vague "Invalid card details" message for `MM/YYYY`. Some fake users hit it, retry and leave. The replay investigation then finds a real, visible cause.
- The traffic is simulated and the friction was planted. Both are stated here and in the code.

As built (phase 9), `scripts/simulate_traffic.py`:

- Drives the Microsoft Edge already installed on the PC (Playwright 1.65.2, `channel="msedge"`, window visible). Each visitor is a new browser context, so a new device ID.
- 40 visitors: 7 browse and leave, 6 stop at the sign-up page, 4 stop at checkout, 20 try to pay, 3 pay and then cancel. Each payer has three traits decided by chance: a card that declines (1 in 10), a habit of typing a four-digit year (1 in 2), and whether they try again after a failure (6 in 10).
- **The assumption built in:** a visitor who sees the guide's hint types `MM/YY`. So the hint "working" in the charts is written into the script; it is not a finding about people. The charts prove the pipeline from page to dashboard.
- Every simulated visitor lands on `/?utm_source=simulation`. Charts filter on the user property `initial_utm_source = simulation`, which keeps out the accounts made by hand on 2026-11-21.
- The local database was backed up to `makewell-backup-2026-11-21.db` and recreated before the run.

Three defects the trial visits exposed, all fixed before the full run:

| Found | Cause | Fix |
|---|---|---|
| `utm_source` was wiped on the second page | On a real domain the SDK ignores its own pages as a referrer. On `localhost` it cannot tell, so each click looked like a new traffic source | `attribution: { excludeReferrers: [location.host] }` in `analytics.js` |
| The replay still lost the typing just before "Pay", and the last page | `storeType: 'idb'` alone was not enough. The recording is cut into batches, a batch is only closed when something happens on the page, and the gap between batches grows to 10 seconds. The open batch is lost on a page change. The hand check on 2026-11-21 passed by luck of timing | `flushIntervalConfig` of one second in `analytics.js`, so at most about the last second of a page is lost. The script's visitors also pause and move the mouse before paying and before leaving |
| Amplitude logged `Guide Rage Closed` | The scripted visitor closed the hint under two seconds after it appeared | The visitor now reads the hint for a few seconds first |

Also seen: with Position on Auto, the hint was drawn over the "Pay" button, so a visitor had to close it before paying. The script closes it, and the pin was moved to "Top of target" on 2026-11-21.

First full run (2026-11-21, 15:40 to 16:03): 40 visitors, no failed visits. 16 booked, 3 booked and then cancelled, 4 failed to pay and left, 4 stopped at checkout, 6 stopped at sign-up, 7 only browsed. Checked in Amplitude for the 31 who signed up (27 from this run and 4 from the trials): one session each, a replay for each, 8 `Booking Failed` with `invalid_details` and 1 with `card_declined`. Of 13 payers who saw the hint, none failed on card details. Of 14 who did not, 8 failed on the first try, 4 of those tried again and booked, and 4 left.

A fourth defect, found by that run:

| Found | Cause | Fix |
|---|---|---|
| 10 of the 31 had no `initial_utm_source`, and no events at all from their landing page | The SDK holds every event in memory until all its plugins have started. The Guides and Surveys plugin makes four network calls first, so on a visitor's first page the SDK was not ready until 1.4 seconds in (0.25 seconds on later pages). Anyone who clicked on sooner lost the first page's events, including where they came from | The plugin is now added after the SDK has started, inside `started.promise.then(...)`, which Amplitude's docs allow. The SDK is ready at 0.4 seconds. In a test of eight visitors leaving after 0.15 to 1.5 seconds, those who stayed 0.8 seconds or more kept their events; before the fix only the 1.5-second visitor did |

Two things were tried first and did not help, so they were taken out again: sending every event as a beacon, and switching off the SDK's own remote settings (`fetchRemoteConfig: false`).

What remains: a visitor who leaves their first page within about 0.6 seconds of it loading still loses that page's events. The cost of the fix: a guide cannot be triggered by an event that fired before the plugin was added. Ours is triggered by a click.

A second full run of 40 ran from 16:12 to 16:36 with all four fixes in place. No failed visits: 14 booked, 2 booked and then cancelled, 7 failed to pay and left, 4 stopped at checkout, 6 stopped at sign-up, 7 only browsed. Checked in Amplitude for the 29 who signed up (27 from the run and 2 from its trial): all 29 carry `initial_utm_source = simulation`, all have their landing-page events, one session and one replay each, and there were no rage closes. There were 10 `Booking Failed`, all `invalid_details`. Of 10 payers who saw the hint, none failed and all booked. Of 15 who did not, 10 failed on the first try, 3 of those tried again and booked, and 7 left.

The stored recordings of all 10 failed payments were read: each has seven characters in the expiry box followed by a page showing "Invalid card details.", the three retries have five, and no typed card character was stored unmasked. The replays were also watched from the chart, and show the seven asterisks (2026-11-21).

Charts count the tagged visitors of both runs. Twenty-four diagnostic visits, made while tracing the fourth defect, are left out through a cohort.

The replays behind a chart's bar are reached by clicking the bar and choosing "Watch Session Replays".

## 14. Visual design

| Element | Choice |
|---|---|
| Background | Warm cream |
| Text | Dark brown-black |
| Accent | Terracotta, used for buttons and links only |
| Second colour | Muted sage for tags and seat counts |
| Headings | Serif (Fraunces, with system serif fallback) |
| Body | Sans-serif (Inter, with system fallback) |
| Workshop cards | Large cards with a coloured illustrated panel; no stock photos |
| Layout | One centred column, generous spacing, works at phone width |

## 15. Project layout

```
app/
  __init__.py        reads the .env file before anything else runs
  main.py            routes
  db.py              database connection and queries
  auth.py            password hashing
  payments.py        fake card rules
  analytics.py       Amplitude server client and the one track() function
  seed.py            creates workshops and sessions
  templates/         one HTML file per page, plus base.html
  static/css/site.css
  static/js/analytics.js   all browser tracking code
scripts/
  simulate_traffic.py  simulated visitors, driven through a real browser
tests/               a few checks per phase, run with pytest
conftest.py          points the tests at a throwaway database, with tracking off
docs/
  requirements.md
  spec.md
.env.example
requirements.txt
README.md
```

## 16. Phases and exit gates

A phase is finished only when its gate is met. Every gate includes these four checks, plus the phase's own:

1. `pytest` passes.
2. The phase's behaviour works by hand in a Windows browser.
3. Every new file has been read through line by line.
4. The docs match the code, and the work is one commit named `Phase N: …`.

| Phase | Builds | Exit gate | Status |
|---|---|---|---|
| 0 Plan | Requirements, spec, repo | The spec's choices are agreed | Done 2026-11-18 |
| 1 Browse | App skeleton, visual design, workshop list and detail from seeded data | Six workshops listed from the database; detail page shows sessions and seats left; a full session reads "Sold out"; an unknown address returns 404; the look is approved | Done 2026-11-18 |
| 2 Accounts | Sign-up, login, logout | Sign up, log out and log in all work; a wrong password is refused; passwords are stored hashed; the header shows who is logged in | Done 2026-11-18 |
| 3 Booking | Session choice, account wall, checkout, fake payment, confirmation | A guest can go from workshop to confirmation; seats go down by the number booked; a declined card and a full session each show a clear message and create no booking; the expiry friction is present | Done 2026-11-18 |
| 4 My bookings | Booking list, cancel with refund | Cancelling marks the booking cancelled and returns the seats; one user cannot cancel another's booking | Done 2026-11-18 |
| 5 Browser tracking | Browser SDK, the four browser events, identity | Each browser event appears in Amplitude with the right properties; a guest who signs up is one user, not two; logout gives a new device ID | Done 2026-11-21 (events confirmed in Amplitude) |
| 6 Server tracking | Python SDK, the five server events, revenue | Server events land on the same user and session as browser events; revenue appears; no event arrives twice; the app still works when Amplitude is unreachable | Done 2026-11-21. Checked in Amplitude |
| 7 Session Replay | Replay plugin, masking | A replay exists for a test visit, linked to its user and events; no password, email, name or card value is readable in it | Done 2026-11-21. Masking checked in the stored recording. A hand-made visit confirmed a replay exists and typing shows as asterisks (2026-11-21). The last seconds of typing before each "Pay" click were missing; fixed with `storeType: 'idb'` and verified in the stored recording of a second hand-made visit (section 10). |
| 8 Guide | One guide, targeted | It shows only to its audience; its own events arrive in Amplitude | Done 2026-11-21. The guide was built and published in Amplitude; of five real test accounts three saw it and two did not, only on `/checkout`, and its events arrived (section 11). |
| 9 Evidence | Simulated traffic, dashboard, replay investigation | At least 30 simulated users; five charts on the dashboard; one replay finding written up | Done 2026-11-21. Two runs of 40 simulated visitors; five charts and the dashboard built in Amplitude; replay finding in section 13. Four tracking defects found and fixed on the way (section 13). |
| 10 Handover | README and links | A fresh copy runs from the README alone; the dashboard, guide and replay links open | Done 2026-11-21 |

## 17. Risks and open questions

| # | Item | Needs |
|---|---|---|
| 1 | Ad and tracker blocking. A DNS-level blocker and a VPN on the development machine blocked every Amplitude address until they were switched off. | Keep such tools off, or allow `amplitude.com`, while testing tracking |
| 2 | Free plan: can a guide be targeted by behaviour or cohort? | Checked in phase 8: the free plan allows one published guide, with page rules, triggers and a rollout percentage |
| 6 | Session Replay lost the last seconds of typing before a page change (section 10). Fixed in two steps (sections 10 and 13) and verified on the recordings of the simulated visits. About the last second before a page change can still be lost. | Accepted |
| 4 | Developed on Python 3.14. A package without 3.14 support would have forced a switch to 3.11. | None did |
| 5 | Guides & Surveys and Session Replay are both available on the free plan (confirmed 2026-11-18). It allows one published guide. | None |

## 18. SDK facts, and how each was checked

Checked on 2026-11-18 against Amplitude's docs (through search) and the Python SDK source on GitHub:

- Python: `Amplitude(api_key, configuration)`, `client.track(BaseEvent(...))`, `client.identify(Identify, EventOptions)`, `client.revenue(Revenue, EventOptions)`, `flush()`, `shutdown()`. `BaseEvent` accepts `user_id`, `device_id`, `session_id` (integer, session start in milliseconds), `insert_id`, `event_properties`, `user_properties` and revenue fields.
- Browser: the replay plugin is added with `amplitude.add(...)` before `amplitude.init(...)`. Replay sample rate defaults to 0, which records nothing.
- Replay privacy: `privacyConfig` takes `defaultMaskLevel` (`light`, `medium`, `conservative`), `maskSelector`, `blockSelector`, `unmaskSelector`. Text inputs are masked by default.
- Guides & Surveys: its script goes below the analytics script; Amplitude's docs add the plugin before `init`, and allow adding it once the SDK has started; the analytics script must not load asynchronously. Event-based triggers need event forwarding switched on.

Checked on 2026-11-18 against the Browser SDK 2 reference, and confirmed by running it:

- Script: `https://cdn.amplitude.com/libs/analytics-browser-2.49.3-min.js.gz`, loaded with a plain script tag. It creates the global `amplitude`.
- `amplitude.init(apiKey, userId, options)`; `track(name, properties)`; `getDeviceId()`, `getSessionId()`, `getUserId()`, `setUserId()`; `flush()`; `setTransport('beacon')`.
- `reset()` clears the user ID and makes a new device ID. It does not start a new session.
- Identity is kept in a first-party cookie named `AMP_` plus the first ten characters of the API key. Unsent events wait in the browser's local storage.
- Events upload about once a second (`flushIntervalMillis` 1000). Sessions end after 30 minutes of inactivity.
- User IDs and device IDs must be at least five characters.
- The separate Session Replay script is `https://cdn.amplitude.com/libs/plugin-session-replay-browser-1.37.1-min.js.gz` (the version in Amplitude's guide on 2026-11-21). It defines `window.sessionReplay.plugin`.
- Free plan replay quota: 10,000 sessions a month, shared across the organisation's projects.

Checked on 2026-11-21 by running the Python SDK (`amplitude-analytics` 1.3.0) against the project:

- The browser's `amplitude.init(...)` returns an object whose `promise` finishes when the SDK is ready. `getDeviceId()` and `getSessionId()` are only reliable after that.
- `revenue` must be a decimal number (`65.0`, not `65`). The SDK logs an error and drops a field of the wrong type.
- A missing `insert_id` is filled with a random one. The SDK also registers its own flush for when the server exits.
- User property operations (`$setOnce`, `$add`) are accepted inside an event's `user_properties` and are applied to that same event.
- A server event sent with the browser's session ID appears inside that browser session in the user's activity view.

Checked on 2026-11-21 against Amplitude's Guides and Surveys docs (Web SDK page updated 2026-11-18), and the first two by running it:

- Script: `https://cdn.amplitude.com/script/<API key>.engagement.js`, placed below the analytics script. It defines `window.engagement`.
- Amplitude's docs put `amplitude.add(window.engagement.plugin())` before `amplitude.init()`, and allow adding it after the SDK has started. This site does the second (section 13). In plugin mode there is no separate `init` or `boot` call, and it must use the same API key as analytics.
- Its events are prefixed `[Guides-Surveys]`: `Guide Viewed`, `Guide Dismissed`, `Guide Completed`, `Guide Step Completed`, `Guide Rage Closed` and others. They do not count toward the event quota. Events from preview mode carry `Is From Debug Mode: true`.
- Triggers: None, Immediately, When element appears, When element clicked, After time on page, On event tracked (browser events only), and others. Page rules match on the address or on a CSS selector being present.
- Targeting: All Users or Targeted Users (segments by property or cohort), each with a rollout percentage. Bucketing unit defaults to User ID.
- A pin completes when its target element is clicked unless "Disable auto-advance on target click" is on.
- Limits "Stop showing when completed" and "Stop showing when dismissed" are on by default.

Found while building the guide (2026-11-21):

- A rollout percentage cannot be set on a segment with no filter: publishing fails with "Fill in the empty segment or filter". It is not needed: **All Users** has its own percentage box. The guide uses All Users at 50%, bucketed by ID, with Even distribution off.
- The hint staying open during typing was confirmed by hand, not from a recording.
