# Requirements

What the project must do, and how each requirement is met. The design is in `spec.md`.

## 1. The site

| ID | Requirement | How it is met | Done when |
|---|---|---|---|
| R1 | A small site with one core journey | Workshop booking site, 8 pages | All pages load in a browser |
| R2 | Sign-up or login, so a visitor moves from anonymous to identified | Browse as a guest; an account is required before paying | A guest can sign up in the middle of a booking and finish |
| R3 | One multi-step journey that can be measured as a funnel | View workshop, select session, start checkout, submit payment, booking confirmed | Each step sends exactly one event |
| R4 | At least one action that happens on the server | The server checks seats, runs the pretend charge, creates the booking, and handles cancel and refund | A booking exists only if the server says so |

## 2. Amplitude instrumentation

| ID | Requirement | How it is met | Done when |
|---|---|---|---|
| R5 | A tracking plan: events, event properties, user properties, and why | Section 7 of `spec.md` | Every event has an owner, a trigger and a reason |
| R6 | Browser and server tracking, each where it makes sense | Browser SDK for intent, Python SDK for outcomes | No event is sent from both sides |
| R7 | Identity: anonymous activity connects to the account | The device ID is passed to the server; the user ID is set at sign-up and login; reset at logout | One user in Amplitude shows guest and logged-in events together |
| R8 | A dashboard that answers a real product question | "Where do people drop out before a confirmed booking, and why?" | Five charts answer it |

## 3. Guide

| ID | Requirement | How it is met | Done when |
|---|---|---|---|
| R9 | One in-app guide | A hint on the checkout page | It appears in the running site |
| R10 | Aimed at a specific audience or trigger, with a reason | Shown when the expiry field is clicked, to half of users | The rule is written down with its reason |
| R11 | Measured with events already tracked | Payment success for users who saw it against users who did not | A chart on the dashboard shows it |

## 4. Session Replay

| ID | Requirement | How it is met | Done when |
|---|---|---|---|
| R12 | Replays connect to the same users and events | The replay plugin shares the SDK's device ID and session ID; server events carry the same session ID | A replay's event list shows browser and server events |
| R13 | Passwords, emails and payment details are masked or blocked, with reasons | Everything typed is masked; names shown on a page are masked | A replay shows no readable sensitive value |
| R14 | A sample rate, and how to choose one for a busy site | 100% here; a written method for sizing it against a quota | The method is in `spec.md` |
| R15 | A replay is used to investigate one drop-off | Replays of visitors whose payment failed | Section 13 of `spec.md` |

## 5. Rules

- Only fake or test data. No real personal information goes to Amplitude.
- The code stays simple and minimal: one route, one template, one job.
- Built in phases, each with a gate and its own commit.

## 6. Decisions about the build

| ID | Decision |
|---|---|
| U1 | A workshop booking site for creative crafts |
| U2 | Python, using FastAPI |
| U3 | Several pages, built in stages that each run |
| U4 | Runs locally; no hosting |
| U5 | Warm editorial light style |
| U6 | A pretend card form inside the site; no outside payment provider |
| U7 | Version 1 includes cancelling a booking with a refund |
| U8 | Discount codes, reminders and a waitlist are left out of version 1 |
| U9 | A free-plan Amplitude project |

## 7. Out of scope

- Real payments, real email sending, password reset.
- Hosting or deployment.
- Admin screens for creating workshops (data is seeded by a script).
- A mobile app.
