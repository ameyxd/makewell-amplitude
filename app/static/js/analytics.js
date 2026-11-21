// Makewell browser tracking.
//
// All Amplitude code that runs in the browser is in this file. It runs on
// every page, after Amplitude's own script has loaded and created the
// global `amplitude` object.
//
// The page tells this file what it needs through data-... attributes on
// the <body> tag, written by the Python templates. For example
// <body data-page="workshop" data-price="42"> is read here as
// body.dataset.page and body.dataset.price.

const body = document.body;
const page = body.dataset.page;                    // which page this is
const userId = body.dataset.userId || undefined;   // empty for guests


// 1. Start Amplitude.
//
//    First, Session Replay. It is a plugin: adding it to `amplitude` before
//    init() makes it record with the same device ID and session ID as every
//    event, which is what links a replay to a user and their events.
//
//    sampleRate: the share of sessions to record. 1 means all of them, which
//                suits a demo. A busy site would use a small fraction.
//    Privacy:    'medium' replaces everything typed into any form field with
//                asterisks before it leaves the browser. On top of that, any
//                element marked data-private in the HTML has its text hidden
//                (we mark the visitor's name wherever a page shows it).
//    storeType:  where the recording waits before it is uploaded. 'idb' is
//                IndexedDB, a small database inside the browser. Every form
//                on this site loads a new page, and with the plugin's
//                in-memory default the last seconds before that were lost.
//                Stored in the browser, the next page can upload them.
//    flushIntervalConfig: how often a batch of recording is closed and
//                queued for upload. By default the gap grows to 10 seconds,
//                and the batch still open when a page changes is lost. One
//                second keeps that loss to about the last second of a page,
//                at the cost of more, smaller uploads.

if (window.sessionReplay) {
  amplitude.add(window.sessionReplay.plugin({
    sampleRate: 1,
    storeType: 'idb',
    flushIntervalConfig: { minIntervalMs: 1000, maxIntervalMs: 1000 },
    privacyConfig: {
      defaultMaskLevel: 'medium',
      maskSelector: ['[data-private]'],
    },
  }));
}

//    Second, Guides and Surveys, also a plugin. It fetches the guides built
//    in Amplitude's website and shows them on our pages, so a message can
//    be added or changed without touching this code. Adding it before
//    init() means it starts knowing who the visitor is, and it sends its
//    own events (such as "Guide Viewed") through the same SDK.

if (window.engagement) {
  amplitude.add(window.engagement.plugin());
}

//    Then the SDK itself.
//    Guests get a random device ID. Logged-in users also get their user ID,
//    which is how Amplitude joins a guest's earlier activity to the account.

const started = amplitude.init(body.dataset.amplitudeKey, userId, {
  autocapture: {
    attribution: {              // where the visitor came from (utm_source, referrer)
      // Our own pages are not a traffic source. On a real domain the SDK
      // works that out by itself. On localhost it cannot, and every click
      // to another page wiped the utm_source the visitor arrived with.
      excludeReferrers: [location.host],
    },
    pageViews: true,
    sessions: true,
    formInteractions: false,    // off: we name the steps that matter ourselves
    fileDownloads: false,
    elementInteractions: false,
  },
});

//    Tell the server who this browser is. Once Amplitude has finished
//    starting, copy its device ID and session ID into two cookies. The
//    browser sends cookies with every request, so the Python code can read
//    them and put its own events on the same user and session.

started.promise.then(() => {
  document.cookie = 'mw_device_id=' + amplitude.getDeviceId() + '; path=/; SameSite=Lax';
  document.cookie = 'mw_session_id=' + amplitude.getSessionId() + '; path=/; SameSite=Lax';
});


// 2. Send anything still waiting when the visitor leaves the page.
//    Events are normally sent in batches about once a second. "beacon" is a
//    way of sending that the browser completes even while the page closes.

window.addEventListener('pagehide', () => {
  amplitude.setTransport('beacon');
  amplitude.flush();
});


// 3. Events that fire when a page loads.

if (page === 'workshop') {
  amplitude.track('Workshop Viewed', {
    workshop_id: Number(body.dataset.workshopId),
    workshop_name: body.dataset.workshopName,
    category: body.dataset.category,
    price: Number(body.dataset.price),
    sessions_available: Number(body.dataset.sessionsAvailable),
  });
}

if (page === 'checkout') {
  amplitude.track('Checkout Started', {
    workshop_id: Number(body.dataset.workshopId),
    workshop_session_id: Number(body.dataset.workshopSessionId),
    seats: Number(body.dataset.seats),
    order_value: Number(body.dataset.orderValue),
    currency: body.dataset.currency,
  });
}


// 4. Events that fire when a form is submitted.

const bookingForm = document.querySelector('#booking-form');
if (bookingForm) {
  bookingForm.addEventListener('submit', () => {
    const chosen = bookingForm.querySelector('input[name="workshop_session_id"]:checked');
    amplitude.track('Session Selected', {
      workshop_id: Number(body.dataset.workshopId),
      workshop_session_id: Number(chosen.value),
      seats: Number(bookingForm.querySelector('#seats').value),
      seats_left: Number(chosen.dataset.seatsLeft),
      days_until_session: Number(chosen.dataset.daysUntil),
    });
  });
}

const checkoutForm = document.querySelector('#checkout-form');
if (checkoutForm) {
  checkoutForm.addEventListener('submit', () => {
    // Only what was chosen and what it costs. Never the card fields.
    amplitude.track('Payment Submitted', {
      workshop_session_id: Number(body.dataset.workshopSessionId),
      order_value: Number(body.dataset.orderValue),
      currency: body.dataset.currency,
    });
  });
}


// 5. Logging out.
//    reset() forgets the user ID and makes a new device ID, so the next
//    person to use this browser is not mistaken for the last one.

const logoutForm = document.querySelector('#logout-form');
if (logoutForm) {
  logoutForm.addEventListener('submit', () => {
    amplitude.reset();
  });
}
