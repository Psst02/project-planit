import os
import random, string
import sqlite3

from argon2 import PasswordHasher
from collections import Counter
from flask import redirect, render_template, session, g, flash, current_app
from functools import wraps

# Shared instance across blueprints
ph = PasswordHasher() # Use default parameters


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def show_error(text):
    """Show error template with custom text"""

    return render_template("error.html", text=text)


# Adapted from Flask documentation:
# URL: https://flask.palletsprojects.com/en/latest/patterns/sqlite3/
# CS50 SQL → SQLite3 adaptation guidance by ChatGPT (OpenAI)
def get_db():
    """Store db connection for current request in Flask's g"""

    # Creat connection if none
    if "db" not in g:
        db_path = os.path.join(current_app.root_path, "planit.db")
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row  # Enable access via column names like CS50 SQL
    return g.db


# Adapted from Flask documentation:
# URL: https://flask.palletsprojects.com/en/latest/patterns/sqlite3/
# CS50 SQL → SQLite3 adaptation guidance by ChatGPT (OpenAI)
def close_db(error=None):
    """Close the DB connection at the end"""

    # Remove db connection from g if any
    db = g.pop("db", None)
    # Close the connection if any (to free resources)
    if db is not None:
        db.close()


# Adapted from Flask documentation:
# URL: https://flask.palletsprojects.com/en/latest/patterns/sqlite3/
# CS50 SQL → SQLite3 adaptation guidance by ChatGPT (OpenAI)
def db_teardown(app):
    """Register database teardown for the given Flask app."""

    app.teardown_appcontext(close_db)


def schedule_plan(dates, pass_limit):
    """Return an appropriate date picked"""

    # Adapted from: GeeksforGeeks
    # URL: https://www.geeksforgeeks.org/python/python-element-with-largest-frequency-in-list/
    # URL: https://www.geeksforgeeks.org/python/python-counter-objects-elements/

    # Returns a dict containing {date : count, ...}
    date_counts = Counter(dates)
    # Reject date occurrences < attendee requirement (excluding creator)
    eligible = {date: count for date, count in date_counts.items() if count >= (pass_limit - 1)}
    # Return a date, or None if none qualify
    return max(eligible, key=eligible.get) if eligible else None


def choose_activities(event_id):
    """Pick a random idea per activity/topic. Confirm choices in db"""

    db = get_db()
    cur = db.cursor()

    # Get topics from event
    cur.execute("SELECT id, topic FROM activity_topics WHERE event_id = ?", (event_id,))
    topics = cur.fetchall()

    for topic in topics:

        topic_id = topic["id"]
        topic_str = topic["topic"]

        # Get all ideas from that topic
        cur.execute("SELECT idea FROM activity_ideas WHERE topic_id = ?", (topic_id,))
        ideas = [i["idea"] for i in cur.fetchall()]

        # Adapted from: W3 school tutorials
        # URL: https://www.w3schools.com/python/ref_random_choice.asp
        # Pick a random suggestion for each topic if any
        activity_label = random.choice(ideas) if ideas else "No suggestions."

        # Insert directly into confirmed_activities
        cur.execute("INSERT INTO confirmed_activities (event_id, topic_label, activity_label) VALUES (?, ?, ?)",
                     (event_id, topic_str, activity_label))
    db.commit()


def evaluate_event(event_id):
    """Evaluate event responses against pass_limit, return status dict."""

    db = get_db()
    cur = db.cursor()
    # Query adjusted by ChatGPT (OpenAI)
    cur.execute("""SELECT
                        e.pass_limit, e.chosen_date, e.expected_total,
                        SUM(CASE WHEN r.res = 1 THEN 1 ELSE 0 END) AS confirm,
                        SUM(CASE WHEN r.res = 0 THEN 1 ELSE 0 END) AS decline
                   FROM events e
                   JOIN invites i ON e.id = i.event_id
                   LEFT JOIN responses r ON i.id = r.invite_id
                   WHERE e.id = ?""", (event_id,))
    stats = cur.fetchone()

    return {
        "confirm": stats["confirm"] or 0,
        "decline": stats["decline"] or 0,
        "expected_total": stats["expected_total"],
        "pass_limit": stats["pass_limit"],
        "chosen_date": stats["chosen_date"]
    }


def common_check(event_id, confirm, pass_limit, action="cancel"):
    """Common check before confirming and cancelling/deleting events"""

    db = get_db()
    cur = db.cursor()

    # Requirement met/Mostly confirm(s)
    if confirm >= pass_limit:
        # Find convenient date
        cur.execute("SELECT date FROM event_dates WHERE event_id = ?", (event_id,))
        dates = [row["date"] for row in cur.fetchall()]
        chosen_date = schedule_plan(dates, pass_limit)

        # Convenient date found
        if chosen_date is not None:
            # Update event and extend expiry
            cur.execute("UPDATE events SET status_id = 1, chosen_date = ? WHERE id = ?", (chosen_date, event_id))
            cur.execute("UPDATE invites SET expires_at = ? WHERE event_id = ?", (chosen_date, event_id))

        # Date not found, Cancel/Delete event
        else:
            if action == "delete":
                cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
            else:
                cur.execute("UPDATE events SET status_id = 2 WHERE id = ?", (event_id,))
    # Requirement not met, Cancel/Delete event
    else:
        if action == "delete":
            cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        else:
            cur.execute("UPDATE events SET status_id = 2 WHERE id = ?", (event_id,))
    db.commit() # Commit all changes to db


def removal_check(event_id):
    """Check if plan should be confirmed/removed at/after expiry (Scheduled Task)"""

    db = get_db()
    cur = db.cursor()

    stats = evaluate_event(event_id)
    confirm = stats["confirm"]
    pass_limit = stats["pass_limit"]

    # Event not confirmed
    if stats["chosen_date"] is None:
        common_check(event_id, confirm, pass_limit, action="delete")

    else:
        # Confirmed event expired, Delete event
        cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        db.commit() # Commit all changes to db


def responses_check(event_id):
    """Check if plan should be confirmed/cancelled (Used after response)"""

    db = get_db()
    cur = db.cursor()
    stats = evaluate_event(event_id)

    confirm = stats["confirm"]
    decline = stats["decline"]
    responded = confirm + decline

    pass_limit = stats["pass_limit"]
    expected_total = stats["expected_total"]
    pending = expected_total - responded

    # Everyone has responded
    if pending <= 0:
        common_check(event_id, confirm, pass_limit, action="cancel")

    else:
        # Too few possible confirms left, Cancel event
        if pending + confirm < pass_limit:
            cur.execute("UPDATE events SET status_id = 2 WHERE id = ?", (event_id,))
            db.commit() # Commit all changes to db


def unique_username(base_name):
    """Add random digits after username until it's unique in db"""

    db = get_db()
    cur = db.cursor()
    username = base_name

    # Keep randomizing until username is unique
    while True:
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        if not cur.fetchone():
            return username
        # 4 random digits
        username = f"{base_name}_{''.join(random.choices(string.digits, k=4))}"


def remove_photo(web_path, default_web_path):
    """Delete photo from file system if it's not default photo"""

    if web_path and web_path != default_web_path:
        # Aapted from: Python documentation - os.path
        # URL: https://docs.python.org/3/library/os.path.html
        # Adaptation guidance by ChatGPT (OpenAI)

        # Convert from web to file path
        file_path = os.path.join(current_app.root_path, web_path.lstrip("/"))
        file_path = os.path.normpath(file_path)

        # Validate path and ensure selected is a file before delete
        if os.path.exists(file_path) and os.path.isfile(file_path):
            os.remove(file_path)
