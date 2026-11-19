"""Starter data: six workshops, each with three dated sessions.

Everything here is invented. Dates are set relative to today so there are
always upcoming sessions.
"""
from datetime import datetime, timedelta

from app import db

# slug, name, category, blurb, description, price_pence, duration_minutes, tone
WORKSHOPS = [
    (
        "wheel-throwing",
        "Wheel Throwing for Beginners",
        "Pottery",
        "Centre the clay, pull up the walls and leave with two bowls.",
        "A patient introduction to the potter's wheel. You will learn to wedge, "
        "centre and throw, then choose a glaze. We fire your pieces and you "
        "collect them two weeks later.",
        6500,
        150,
        "clay",
    ),
    (
        "sourdough",
        "Sourdough from Scratch",
        "Baking",
        "Mix, fold, shape and bake a loaf, and take a starter home.",
        "We work through a full loaf together, from mixing to scoring. While "
        "the dough rests you will learn how to keep a starter alive and how to "
        "fit baking around a working week.",
        4800,
        180,
        "ochre",
    ),
    (
        "spoon-carving",
        "Carve a Wooden Spoon",
        "Woodwork",
        "Turn a green birch blank into a spoon using only hand tools.",
        "Using an axe, a straight knife and a hook knife, you will shape a "
        "cooking spoon from freshly cut wood. Safe grips come first, then the "
        "carving. No experience needed.",
        5500,
        180,
        "sage",
    ),
    (
        "linocut",
        "Linocut Printmaking",
        "Printmaking",
        "Design, carve and print a small edition of your own cards.",
        "Sketch a simple design, transfer it to lino and carve it out. You "
        "will ink the block and pull a set of prints on a hand press, with "
        "paper and envelopes included.",
        4200,
        120,
        "ink",
    ),
    (
        "natural-dye",
        "Natural Dyeing with Plants",
        "Textiles",
        "Dye a cotton scarf with madder, weld and onion skins.",
        "An afternoon at the dye pots. You will prepare fabric, mix three "
        "plant dyes and try simple folding and binding patterns. You take "
        "home a scarf and a swatch card.",
        5000,
        150,
        "plum",
    ),
    (
        "notebook-binding",
        "Bind Your Own Notebook",
        "Bookbinding",
        "Fold, stitch and cover a hardback notebook to keep.",
        "Learn a classic stitched binding from start to finish. You will "
        "fold the pages, sew them together, and case them in a cloth cover "
        "in a colour you choose.",
        3800,
        120,
        "rose",
    ),
]

# Each workshop gets one of these patterns, in turn.
# One row per session: (days from today, start hour, capacity, seats taken)
SESSION_PATTERNS = [
    [(3, 10, 8, 2), (10, 14, 8, 5), (17, 10, 8, 0)],
    [(4, 18, 6, 4), (11, 18, 6, 6), (18, 18, 6, 1)],    # middle one is full
    [(5, 11, 10, 8), (12, 11, 10, 3), (19, 15, 10, 0)],  # first has 2 left
]


def seed_if_empty():
    """Add the starter data, unless the database already has workshops."""
    with db.connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM workshops").fetchone()[0] > 0:
            return

        today = datetime.now().replace(minute=0, second=0, microsecond=0)

        for index, workshop in enumerate(WORKSHOPS):
            cursor = conn.execute(
                """
                INSERT INTO workshops
                    (slug, name, category, blurb, description,
                     price_pence, duration_minutes, tone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                workshop,
            )
            workshop_id = cursor.lastrowid

            pattern = SESSION_PATTERNS[index % len(SESSION_PATTERNS)]
            for days, hour, capacity, seats_taken in pattern:
                starts_at = today.replace(hour=hour) + timedelta(days=days)
                conn.execute(
                    """
                    INSERT INTO workshop_sessions
                        (workshop_id, starts_at, capacity, seats_taken)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        workshop_id,
                        starts_at.isoformat(timespec="minutes"),
                        capacity,
                        seats_taken,
                    ),
                )
