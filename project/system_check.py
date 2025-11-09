from datetime import datetime, date
from app import app
from helpers import get_db, close_db, removal_check

def remove_events():

    db = get_db()
    cur = db.cursor()
    # Get all events and their expiry dates
    cur.execute("""
        SELECT e.id AS event_id, i.expires_at
        FROM events e
        JOIN invites i ON e.id = i.event_id
    """)
    rows = cur.fetchall()

    # Loop through events and check expiry
    for row in rows:
        expires_at = date.fromisoformat(row["expires_at"])
        if expires_at <= date.today():
            removal_check(row["event_id"])

    close_db()

if __name__ == "__main__":
    with app.app_context():
        remove_events()
