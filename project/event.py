import uuid

from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from helpers import login_required, show_error, get_db, choose_activities, removal_check, responses_check

# Adapted from: Real Python
# URL: https://realpython.com/flask-blueprint/
# Define blueprint for all event routes
event_bp = Blueprint("event", __name__)


@event_bp.route("/")
@login_required
def dashboard():
    """Show events and their statuses"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    # All events associated with user
    # Query adjusted by ChatGPT (OpenAI)
    cur.execute("""
                   SELECT DISTINCT e.*, s.status_label
                   FROM events e
                   JOIN event_statuses s ON e.status_id = s.id
                   LEFT JOIN invites i ON e.id = i.event_id
                   LEFT JOIN responses r ON i.id = r.invite_id
                   WHERE e.creator_id = ? OR r.user_id = ?
                   ORDER BY e.created_at DESC""", (user_id, user_id))
    events = cur.fetchall()

    plans = []
    for event in events:
        # Get invite id
        cur.execute("SELECT id, token, expires_at FROM invites WHERE event_id = ?", (event["id"],))
        invite = cur.fetchone()

        response_count = 0
        expected_total = event["expected_total"]
        expires_at = date.fromisoformat(invite["expires_at"])

        # Call system check if expired
        if expires_at <= date.today():
            removal_check(event["id"])

        # Get details from valid event
        else:
            # Get responses via invite id
            cur.execute("SELECT res, user_id FROM responses WHERE invite_id = ?", (invite["id"],))
            responses = cur.fetchall()

            # Responses count and user specific response
            response_count = sum(1 for r in responses if r["res"] is not None)              # Add 1 for every response that is not pending
            user_res = next((r["res"] for r in responses if r["user_id"] == user_id), None) # Get res from responses where user id matches

            chosen_date = None
            countdown = 0
            # Adapted from: GeeksforGeeks
            # URL: https://www.geeksforgeeks.org/python/python-program-to-find-number-of-days-between-two-given-dates/
            # Countdown until expiry (event is ongoing)
            if event["status_id"] == 0:
                countdown = (expires_at - date.today()).days
            # Countdown until chosen date (event is confirmed)
            elif event["status_id"] == 1:
                chosen_date = date.fromisoformat(event["chosen_date"])
                countdown = (chosen_date - date.today()).days

            plans.append ({
                "id": event["id"],
                "creator_id": event["creator_id"],
                "token": invite["token"],
                "status": event["status_label"],
                "invitees": expected_total,
                "responses": response_count,
                "user_res": user_res,
                "chosen_date": chosen_date,
                "countdown": countdown
            })

    return render_template("dashboard.html", plans=plans)


@event_bp.route("/create-event", methods=["GET", "POST"])
@login_required
def create_event():
    """Let user configure and create event"""

    db = get_db()
    cur = db.cursor()
    creator_id = session["user_id"]

    # Get options
    cur.execute("SELECT focus_label FROM event_focuses")
    focuses = [row["focus_label"] for row in cur.fetchall()]

    cur.execute("SELECT setting_label FROM event_settings")
    settings = [row["setting_label"] for row in cur.fetchall()]

    if request.method == "POST":
        # ---------------- Section 1 -------------------
        focus = request.form.get("focus")
        setting = request.form.get("setting")

        # Ensure selected options exist
        if focus not in focuses:
            return render_template("create_event.html", focuses=focuses, settings=settings, focus_fb="invalid option")
        elif setting not in settings:
            return render_template("create_event.html", focuses=focuses, settings=settings, setting_fb="invalid option")

        # ---------------- Section 2 -------------------
        date1 = request.form.get("start-date")
        date2 = request.form.get("end-date")

        # Validate date format
        try:
            start_date = date.fromisoformat(date1)
            end_date = date.fromisoformat(date2)
        except ValueError:
            return render_template("create_event.html", focuses=focuses, settings=settings, date_fb="invalid date")

        # Validate date range
        today = date.today()
        if start_date < today or end_date <= today or end_date <= start_date:
            return render_template("create_event.html", focuses=focuses, settings=settings, date_fb="invalid range")

        # ---------------- Section 3 -------------------
        topics = [t.strip() for t in request.form.getlist("topic") if t.strip()] # Add only non-empty to list

        # Ensure at least 1 but no more than 5 topics
        if not topics:
            return render_template("create_event.html", focuses=focuses, settings=settings, table_fb="min 1 activity")
        elif len(topics) > 5:
            return render_template("create_event.html", focuses=focuses, settings=settings, table_fb="max 5 activities")

        topic_ideas = {}
        for i, topic in enumerate(topics):
            # Formatting decision: Reddit
            # URL: https://www.reddit.com/r/learnpython/comments/1gzhfno/whats_better_to_use_fstring_or_format/
            # Answered by MiniMages
            idea_list = request.form.getlist(f"ideas[{i}][]")
            filtered = [idea.strip() for idea in idea_list if idea.strip()][:2] # Accept only 2 per topic, Discard empty if any

            # Ensure 1 idea per topic before adding
            if len(filtered) == 0:
                return render_template("create_event.html", focuses=focuses, settings=settings, table_fb="min 1 option per activity")
            topic_ideas[i] = filtered

        # ---------------- Section 4 -------------------
        # Ensure it is positive integer
        try:
            pass_limit = int(request.form.get("min-participants"))
            if pass_limit < 1:
                raise ValueError
        except ValueError:
            return render_template("create_event.html", focuses=focuses, settings=settings, limit_fb="invalid number")

        # Ensure it is positive integer >= pass limit
        try:
            expected_total = int(request.form.get("max-participants"))
            if expected_total < pass_limit:
                raise ValueError
        except ValueError:
            return render_template("create_event.html", focuses=focuses, settings=settings, max_fb="invalid number")

        # ---------------- DB queries -------------------
        # Insert event and get id
        cur.execute("""
                       INSERT INTO events (creator_id, focus_id, setting_id, start_date, end_date, pass_limit, expected_total)
                       VALUES (
                           ?,
                           (SELECT id FROM event_focuses WHERE focus_label = ?),
                           (SELECT id FROM event_settings WHERE setting_label = ?),
                           ?, ?, ?, ?)""", (creator_id, focus, setting, start_date, end_date, pass_limit, expected_total))
        event_id = cur.lastrowid

        # Insert topics, topic_ideas from Section 3
        for i, topic in enumerate(topics):
            cur.execute("INSERT INTO activity_topics (event_id, topic) VALUES (?, ?)", (event_id, topic))
            topic_id = cur.lastrowid
            for idea in topic_ideas[i]:
                cur.execute("INSERT INTO activity_ideas (topic_id, user_id, idea) VALUES (?, ?, ?)", (topic_id, creator_id, idea))

        # Generate invite token (expires after a week)
        invite_token = uuid.uuid4().hex
        expires_at = date.today() + timedelta(days=7) # Testing 1 - Change to 7 for production

        # insert invite and get id
        cur.execute("""INSERT INTO invites (event_id, creator_id, token, expires_at)
                       VALUES (?, ?, ?, ?)""", (event_id, creator_id, invite_token, expires_at))
        invite_id = cur.lastrowid

        # Creator auto-confirm
        cur.execute("INSERT INTO responses (invite_id, user_id, res) VALUES (?, ?, ?)", (invite_id, creator_id, 1))
        db.commit() # Commit all changes

        # Return invite link
        invite_link = url_for("event.respond_event", token=invite_token, _external=True)
        return render_template("create_event.html", focuses=focuses, settings=settings, invite_link=invite_link)

    # Render template for GET method
    return render_template("create_event.html", focuses=focuses, settings=settings)


@event_bp.route("/rsvp/<token>", methods=["GET", "POST"])
@login_required
def respond_event(token):
    """Let user respond to valid rsvp form via invite link"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    cur.execute("SELECT * FROM invites WHERE token = ?", (token,))
    invite = cur.fetchone()
    # Validate invite
    if not invite:
        return show_error("Invalid/Expired invite.")

    invite_id = invite["id"]
    event_id = invite["event_id"]
    creator_id = invite["creator_id"]

    # Event and related labels
    cur.execute("""
                   SELECT e.*, f.focus_label, s.setting_label, u.username
                   FROM events e
                   JOIN event_focuses f ON e.focus_id = f.id
                   JOIN event_settings s ON e.setting_id = s.id
                   JOIN users u ON e.creator_id = u.id
                   WHERE e.id = ?""", (event_id,))
    event = cur.fetchone()
    # Ensure event exists
    if not event:
        return show_error("Event/Creator not found.")

    status = event["status_id"]
    # Handle confirmed/cancelled events
    if status == 1:
        return redirect(url_for("event.schedule_event", token=token))
    elif status == 2:
        return show_error("Event cancelled.")

    # Set up ongoing event
    cur.execute("SELECT * FROM activity_topics WHERE event_id = ?", (event_id,))
    topics = cur.fetchall()
    cur.execute("SELECT res FROM responses WHERE invite_id = ? AND user_id = ?", (invite_id, user_id))
    user = cur.fetchone()

    # Register response if not yet there
    if not user:
        cur.execute("""INSERT INTO responses (invite_id, user_id) VALUES (?, ?)""", (invite_id, user_id))
        db.commit()

    # Show response if already responded
    elif user["res"] is not None and user_id != creator_id:
        return redirect(url_for("event.show_response", token=token))

    if request.method == "POST":
        # Creator can't submit
        if user_id == creator_id:
            return show_error("Creator may not respond.")

        # Decline invite
        if "decline" in request.form or "not-coming" in request.form:
            # Update user response and call system check
            cur.execute("UPDATE responses SET res = 0 WHERE invite_id = ? AND user_id = ?", (invite_id, user_id))
            db.commit()
            responses_check(event_id)

            flash("Invite Declined!", "success")
            return redirect("/")

        # Confirm invite
        elif "confirm" in request.form:
            # Get responses and discard blanks in the list
            dates = [d.strip() for d in request.form.getlist("date") if d.strip()]

            # Ensure min 1 date
            if not dates:
                return render_template("rsvp_form.html", event=event, topics=topics, token=token, date_fb="pick at least 1 date")

            start_date = date.fromisoformat(event["start_date"])
            end_date = date.fromisoformat(event["end_date"])

            # Validate each input date
            for input_date in dates:
                try:
                    input_date = date.fromisoformat(input_date)
                except ValueError:
                    return render_template("rsvp_form.html", event=event, topics=topics, token=token, date_fb="invalid date(s)")

                # Ensure date is within appropriate range
                if not start_date <= input_date <= end_date:
                    return render_template("rsvp_form.html", event=event, topics=topics, token=token, date_fb="out of range")

                elif input_date == date.today():
                    return render_template("rsvp_form.html", event=event, topics=topics, token=token, date_fb="date too soon")

                # Only add non-duplicate dates
                cur.execute("""INSERT INTO event_dates (event_id, user_id, date) SELECT ?, ?, ? WHERE NOT EXISTS (
                                   SELECT * FROM event_dates
                                   WHERE event_id = ? AND user_id = ? AND date = ?
                               )""", (event_id, user_id, input_date, event_id, user_id, input_date))

            # Insert non-empty ideas
            for topic in topics:
                idea = request.form.get(f"idea_{topic['id']}", "").strip()
                if idea:
                    cur.execute("INSERT INTO activity_ideas (topic_id, user_id, idea) VALUES (?, ?, ?)", (topic['id'], user_id, idea))

            # Update user response and call system check
            cur.execute("UPDATE responses SET res = 1 WHERE invite_id = ? AND user_id = ?", (invite_id, user_id))
            db.commit()
            responses_check(event_id)

            flash("Invite Confirmed!", "success")
            return redirect("/")

    # Render template for GET method
    return render_template("rsvp_form.html", event=event, topics=topics, token=token)


@event_bp.route("/rsvp/<token>/thank-you")
@login_required
def show_response(token):
    """Display user responses"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]
    # Get user's response to this event
    cur.execute("""
                   SELECT r.res FROM responses r
                   JOIN invites i ON r.invite_id = i.id
                   WHERE i.token = ? AND r.user_id = ?""", (token, user_id))
    response = cur.fetchone()
    # Ensure response exists
    if not response:
        return show_error("Response not found for this user.")

    # Find event id
    cur.execute("""
                   SELECT e.id, e.start_date, e.end_date
                   FROM invites i
                   JOIN events e ON i.event_id = e.id
                   WHERE i.token = ?""", (token,))
    event = cur.fetchone()
    # Ensure event exists
    if not event:
        return show_error("Event not found.")

    # Find dates selected by user
    cur.execute("SELECT date FROM event_dates WHERE event_id = ? AND user_id = ?", (event["id"], user_id))
    date_list = [row["date"] for row in cur.fetchall()]

    # Adapted from: Stack Overflow
    # URL: https://stackoverflow.com/questions/18934487/convert-null-to-default-value
    # Answered by Vulcronos
    activities = []
    # Query adjusted by ChatGPT (OpenAI)
    cur.execute("""
                   SELECT at.topic, COALESCE(ai.idea, '-') AS idea
                   FROM activity_topics at
                   LEFT JOIN activity_ideas ai ON at.id = ai.topic_id AND ai.user_id = ?
                   WHERE at.event_id = ?
                   ORDER BY at.id""", (user_id, event["id"]))

    rows = cur.fetchall()
    activities = [{"topic": r["topic"], "idea": r["idea"]} for r in rows]

    return render_template("thank_you.html", event=event, dates=date_list, activities=activities, res=response["res"])


@event_bp.route("/scheduled/<token>")
@login_required
def schedule_event(token):
    """Choose activities and display confirmed plan"""

    db = get_db()
    cur = db.cursor()
    # Find event details
    cur.execute("""
                   SELECT e.*, f.focus_label, s.setting_label
                   FROM invites i
                   JOIN events e ON i.event_id = e.id
                   JOIN event_focuses f ON e.focus_id = f.id
                   JOIN event_settings s ON e.setting_id = s.id
                   WHERE i.token = ?""", (token,))
    event = cur.fetchone()
    # Ensure event exists
    if not event:
        return show_error("Event not found.")
    event_id = event["id"]

    # Choose activities if not yet decided
    cur.execute("SELECT topic_label, activity_label FROM confirmed_activities WHERE event_id = ?", (event_id,))
    activities = cur.fetchall()

    if not activities:
        choose_activities(event_id)
        # Get latest insert
        cur.execute("SELECT topic_label, activity_label FROM confirmed_activities WHERE event_id = ?", (event_id,))
        activities = cur.fetchall()

    # Get attendee details
    cur.execute("""
                   SELECT u.id, u.username, u.photo
                   FROM responses r
                   JOIN invites i ON r.invite_id = i.id
                   JOIN users u ON r.user_id = u.id
                   WHERE i.event_id = ? AND r.res = 1""", (event_id,))
    attendees = cur.fetchall()

    return render_template("scheduled.html", event=event, activities=activities, attendees=attendees)

