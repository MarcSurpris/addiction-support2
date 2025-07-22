from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from dotenv import load_dotenv
import os
from urllib.parse import urlparse, urljoin
from models import db, User, Entry
from sqlalchemy import Column, String, Integer, Text, DateTime
import datetime

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
database_url = os.getenv('DATABASE_URL', 'sqlite:///site.db')  # Fallback to SQLite if env var is missing
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Create database tables with error handling
with app.app_context():
    try:
        # Test the connection and create tables
        db.engine.connect()  # Test connection before creating tables
        db.create_all()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Fallback to SQLite if PostgreSQL fails (optional)
        if "does not exist" in str(e) or "connection" in str(e).lower():
            print("Falling back to SQLite or check DATABASE_URL.")
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
            db.create_all()
            print("SQLite database initialized as fallback.", {str(e)})
        else:
            raise

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Safe URL check
def is_safe_url(target):
    """Check if the target URL is safe for redirection."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

# Routes
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Please provide both username and password.", "error")
            return redirect(url_for("register"))
        if len(username) > 120:
            flash("Username too long (max 120 characters).", "error")
            return redirect(url_for("register"))
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists.", "error")
            return redirect(url_for("register"))
        try:
            user = User(username=username, password_hash=generate_password_hash(password, method='scrypt'))
            db.session.add(user)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            if "string data right truncation" in str(e).lower() or "unique constraint" in str(e).lower():
                flash("Registration failed due to invalid data or duplicate username.", "error")
            else:
                flash(f"Registration failed: {str(e)}", "error")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful!", "success")
            next_page = request.args.get("next")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        addiction_type = request.form.get("addiction_type")
        description = request.form.get("description")
        if not addiction_type or not description:
            flash("Please provide both addiction type and description.", "error")
            return redirect(url_for("index"))
        if len(addiction_type) > 100:
            flash("Addiction type too long (max 100 characters).", "error")
            return redirect(url_for("index"))
        if len(description) > 1000:
            flash("Description too long (max 1000 characters).", "error")
            return redirect(url_for("index"))
        response = get_xai_response(f"Addiction type: {addiction_type}\nDescription: {description}")
        entry = Entry(
            user_id=current_user.id,
            addiction_type=addiction_type,
            description=description,
            response=response
        )
        try:
            db.session.add(entry)
            db.session.commit()
            flash("Entry saved successfully.", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Entry save error: {str(e)}")
            flash("Failed to save entry. Please try again.", "error")
        return redirect(url_for("index"))
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.created_at.desc()).all()
    return render_template("index.html", entries=entries)

def get_xai_response(user_input):
    messages = [
        {"role": "system", "content": (
            "You are a compassionate addiction support assistant. "
            "Respond in a calm, supportive, and empathetic tone. "
            "Avoid giving medical advice. Always suggest professional help if needed."
        )},
        {"role": "user", "content": user_input}
    ]
    headers = {
        "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "grok-3",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 150
    }
    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        print("xAI API Error:", e)
        return "I'm sorry, I'm having trouble responding right now. Please reach out to a professional."

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))