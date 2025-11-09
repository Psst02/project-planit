import os
import sqlite3
import uuid

from argon2 import exceptions as argon2_exceptions
from flask import Blueprint, render_template, request, redirect, session, flash, current_app
from helpers import login_required, show_error, get_db, ph, remove_photo
from werkzeug.utils import secure_filename

# Adapted from: Real Python
# URL: https://realpython.com/flask-blueprint/
# Define blueprint for all setting routes
acc_bp = Blueprint("acc", __name__)


@acc_bp.route("/account-details", methods=["GET", "POST"])
@login_required
def account_details():
    """Let user change photo, edit username and link email"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    # Get user details
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    # User already linked or logged in via google
    has_google = user["email"]
    d_web_path = "/static/uploads/default.png" # Default photo

    if request.method == "POST":
        # Remove photo (to default)
        if request.form.get("remove") == "1":
            # Store photo to be removed before changing to default
            r_web_path = user["photo"]
            cur.execute("UPDATE users SET photo = ? WHERE id = ?", (d_web_path, user_id))
            db.commit()

            remove_photo(r_web_path, d_web_path)
            session["user_photo"] = d_web_path

            flash("Profile photo removed!", "success")
            return redirect("/account-details")

        # Change photo (to upload)
        upload_file = request.files.get("upload")
        # Adapted from: Uploading Files - Flask Documentation
        # URL: https://flask.palletsprojects.com/en/stable/patterns/fileuploads/
        # Ensure file is chosen and named
        if upload_file and upload_file.filename:
            # Aapted from: Python documentation - os.path
            # URL: https://docs.python.org/3/library/os.path.html
            # Adaptation guidance by ChatGPT (OpenAI)

            # Ensure safe naming and get file path to save (hex in case of similar names)
            file_name = f"{uuid.uuid4().hex}_{secure_filename(upload_file.filename)}"
            file_path = os.path.join(current_app.root_path, "static", "uploads", file_name)
            upload_file.save(file_path)

            # Create web path from file path
            u_web_path = "/" + os.path.relpath(file_path, current_app.root_path).replace(os.sep, "/")

            # Store photo to be removed before changing to default
            r_web_path = user["photo"]
            cur.execute("UPDATE users SET photo = ? WHERE id = ?", (u_web_path, user_id))
            db.commit()

            remove_photo(r_web_path, d_web_path)
            session["user_photo"] = u_web_path

            flash("Profile photo updated!", "success")
            return redirect("/account-details")

        # Ensure username is not empty
        username = (request.form.get("username") or user["username"]).strip()
        if not username:
            return render_template("account_details.html", user=user, has_google=has_google, username_fb="required field")

        # Ensure username is unique and update user data
        try:
            cur.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
            db.commit()
        except sqlite3.IntegrityError:
            return render_template("account_details.html", user=user, has_google=has_google, username_fb="username taken")

        flash("Changes saved!", "success")
        return redirect("/account-details")

    # Render template for GET method
    return render_template("account_details.html", user=user, has_google=has_google)


@acc_bp.route("/reset-password", methods=["GET", "POST"])
@login_required
def reset_password():
    """Let user change password"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    cur.execute("SELECT hash FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    has_password = bool(user["hash"])

    if request.method == "POST":
        old_psw_fb = new_psw_fb = ""
        password = (request.form.get("old-password") or "").strip()
        new_password = (request.form.get("new-password") or "").strip()
        confirmation = (request.form.get("confirmation") or "").strip()

        # Required fields check
        if has_password and not password:
            old_psw_fb = "required field"
        if not new_password or not confirmation:
            new_psw_fb = "required field(s)"
        elif new_password != confirmation:
            new_psw_fb = "confirm password"

        # Validate old password if any
        if has_password and old_psw_fb == "":
            try:
                ph.verify(user["hash"], password)
            except argon2_exceptions.VerifyMismatchError:
                old_psw_fb = "incorrect password"
            else:
                # Valiate new password
                try:
                    if ph.verify(user["hash"], new_password):
                        new_psw_fb = "same as old password"
                except argon2_exceptions.VerifyMismatchError:
                    pass  # New password is different
    
        # Return feedbck if any
        if old_psw_fb or new_psw_fb:
            return render_template("reset_psw.html",
                has_password=has_password,
                old_psw_fb=old_psw_fb,
                new_psw_fb=new_psw_fb
            )

        # Hash and update password
        hashed = ph.hash(new_password)
        cur.execute("UPDATE users SET hash = ? WHERE id = ?", (hashed, user_id))
        db.commit()

        flash("Password updated successfully!", "success")
        return redirect("/reset-password")

    # Render template for GET method
    return render_template("reset_psw.html", has_password=has_password)


@acc_bp.route("/delete-account", methods=["GET", "POST"])
@login_required
def delete_account():
    """Let user delete account"""

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    cur.execute("SELECT hash FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    has_password = bool(user["hash"])

    if request.method == "POST":
        password_fb = ""
        if has_password:
            # Ensure password was submitted
            password = (request.form.get("password") or "").strip()
            if not password:
                password_fb = "required field"
            else:
                # Validate password
                stored_hash = user["hash"]
                try:
                    ph.verify(stored_hash, password)
                except argon2_exceptions.VerifyMismatchError:
                    password_fb = "incorrect password"

        # Return feedbck if any
        if password_fb:
            return render_template("delete_account.html", has_password=has_password, password_fb=password_fb)

        # Proceed to delete (No errors)
        session.clear()
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()

        flash("Account deleted!", "success")
        return redirect("/")

    # Render template for GET method
    return render_template("delete_account.html", has_password=has_password)

