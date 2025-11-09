from datetime import datetime, date
from helpers import get_db, removal_check

def remove_events():

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    # Get all events
    cur.execute("""SELECT * FROM events WHERE 
                   SELECT DISTINCT e.*, s.status_label
                   FROM events e
                   JOIN event_statuses s ON e.status_id = s.id
                   LEFT JOIN invites i ON e.id = i.event_id
                   LEFT JOIN responses r ON i.id = r.invite_id
                   WHERE e.creator_id = ? OR r.user_id = ?
                   ORDER BY e.created_at DESC""", (user_id, user_id))
    events = cur.fetchall()

    for event in events:
        # Get invite id
        cur.execute("SELECT id, token, expires_at FROM invites WHERE event_id = ?", (event["id"],))
        invite = cur.fetchone()
        expires_at = date.fromisoformat(invite["expires_at"])

        # Call system check if expired
        if expires_at <= date.today():
            removal_check(event["id"])

if this = "__main__":
    remove_events()
