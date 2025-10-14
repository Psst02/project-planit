import os
import sqlite3

# Google Cloud Console OAuth Credentials set up
# URL: https://youtu.be/TjMhPr59qn4?si=hL71d10sQR_ew-bE
# Tutorial by Appwrite

from authlib.integrations.flask_client import OAuth
from argon2 import exceptions as argon2_exceptions
from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from helpers import login_required, get_db, ph, unique_username

# Adapted from: Real Python
# URL: https://realpython.com/flask-blueprint/
# Define blueprint for all user auth routes
auth_bp = Blueprint("auth", __name__)

oauth = OAuth()

# Adapted from: GeeksforGeeks
# URL: https://www.geeksforgeeks.org/python/oauth-authentication-with-flask-connect-to-google-twitter-and-facebook/
# Create OAuth for Google
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Auto-fetch all the URLs (authorize, token, userinfo) using OpenID metadata
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url=CONF_URL,
    client_kwargs={'scope': 'openid email profile'}
)


@auth_bp.route('/login/google')
def login_google():
    """Redirect user to google for authentication"""

    # Ensure token isn't cleared during cleanup if any
    invite_token = session.pop("invite_token", None)
    session.clear()
    if invite_token:
        session["invite_token"] = invite_token
        
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/login/google/callback')
def google_callback():
    """Handle callback and log user in"""

    # Adapted from: Authlib Flask OAuth documentation
    # URL: https://docs.authlib.org/en/latest/client/flask.html#authorization-code-grant
    # Flask OpenID Connect Client
    # Exchange auth code for token
    token = oauth.google.authorize_access_token()

    # Get user info from Google
    user_info = token.get("userinfo")
    username = user_info.get("name")
    email = user_info.get("email")
    photo = user_info.get("picture")

    db = get_db()
    cur = db.cursor()
    # Store in db if new user
    cur.execute("SELECT id, photo FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    if not user:
        try:
            cur.execute("INSERT INTO users (username, email, photo) VALUES (?, ?, ?)", (username, email, photo))
        except sqlite3.IntegrityError:
            nickname = unique_username(username) # Make username unique
            cur.execute("INSERT INTO users (username, email, photo) VALUES (?, ?, ?)", (nickname, email, photo))
        db.commit()

        # Get latest info
        cur.execute("SELECT id, photo FROM users WHERE email = ?", (email,))
        user = cur.fetchone()

    # Remember user id, photo
    session["user_id"] = user["id"]
    session["user_photo"] = user["photo"]

    # Handle redirects
    invite_token = session.pop("invite_token", None)
    if invite_token:
        return redirect(url_for("event.respond_event", token=invite_token))
        
    flash("You're logged in!", "success")
    return redirect("/")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Register user via username"""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        # # Ensure inputs are filled
        if not username:
            return render_template("signup.html", username_fb="required field")
        elif not password:
            return render_template("signup.html", password_fb="required field")

        hashed = ph.hash(password)

        db = get_db()
        cur = db.cursor()

        # Only update db if username is unique
        try:
            cur.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hashed))
            db.commit()
        except sqlite3.IntegrityError:
            return render_template("signup.html", username_fb="username taken")

        # Get latest info
        cur.execute("SELECT id, photo FROM users WHERE username = ?", (username,))
        user = cur.fetchone()

        # Remember user id, photo
        session["user_id"] = user["id"]
        session["user_photo"] = user["photo"]

        # Handle redirects
        invite_token = session.pop("invite_token", None)
        if invite_token:
            return redirect(url_for("event.respond_event", token=invite_token))
        
        flash("Sign up successful!", "success")
        return redirect("/")

    # Render template for GET method
    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Log user in via username"""

    if request.method == "POST":
        # Ensure token isn't cleared if any
        invite_token = session.pop("invite_token", None)
        session.clear()
        
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        # Ensure inputs are filled
        if not username:
            return render_template("login.html", username_fb="required field")
        elif not password:
            return render_template("login.html", password_fb="required field")

        db = get_db()
        cur = db.cursor()

        # Ensure username exists
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        if not user:
            return render_template("login.html", username_fb="invalid username")

        # Ensure password is correct
        stored_hash = user["hash"]
        try:
            ph.verify(stored_hash, password)
        except argon2_exceptions.VerifyMismatchError:
            return render_template("login.html", password_fb="incorrect password")

        # Rehash if parameters changed (future developments)
        if ph.check_needs_rehash(stored_hash):
            new_hash = ph.hash(password)
            cur.execute("UPDATE users SET hash = ? WHERE username = ?", (new_hash, username))
            db.commit()

        # Remember user id, photo
        session["user_id"] = user["id"]
        session["user_photo"] = user["photo"]

        # Handle redirects
        if invite_token:
            return redirect(url_for("event.respond_event", token=invite_token))
            
        flash("You're logged in!", "success")
        return redirect("/")

    # Render template for GET method
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Log user out"""

    # Forget user info and show dashboard
    session.clear()
    return redirect("/")


@auth_bp.route('/link/google')
@login_required
def link_google():
    """Route to google linking process for logged in users"""

    redirect_uri = url_for('auth.google_link_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/link/google/callback')
@login_required
def google_link_callback():
    """Handle callback to link gmail"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    # Get user details
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    # Adapted from: Authlib Flask OAuth documentation
    # URL: https://docs.authlib.org/en/latest/client/flask.html#authorization-code-grant
    # Flask OpenID Connect Client
    # Exchange auth code for token
    token = oauth.google.authorize_access_token()

    # Get user info from Google
    user_info = token.get("userinfo")
    email = user_info.get("email")

    # Ensure email isn't already in use
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing = cur.fetchone()
    if existing:
        return render_template("account_details.html", user=user, has_google=False, email_fb="already linked to another user")

    # Link account to Google
    cur.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
    db.commit()

    flash("Account linked successfully!", "success")
    return redirect("/account-details")

