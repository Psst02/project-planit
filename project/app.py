import os

from dotenv import load_dotenv
from flask import Flask
from flask_session import Session
from helpers import db_teardown

# blueprints
from auth import auth_bp, oauth
from acc import acc_bp
from event import event_bp

app = Flask(__name__)
load_dotenv()
print("SECRET_KEY =", os.environ.get("SECRET_KEY"))

# Running locally
if os.environ.get("PYTHONANYWHERE_DOMAIN") is None:
    # Ensures invite links work when locally tested
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

app.secret_key = os.environ.get("SECRET_KEY")

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

oauth.init_app(app)  # Sets up Authlib OAuth with Flask
db_teardown(app)     # Register db teardown

# Adapted from: Real Python
# URL: https://realpython.com/flask-blueprint/
# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(acc_bp)
app.register_blueprint(event_bp)


# Disable data cache (Ensures fresh content)
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response
