# create_db_with_hashed_users.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from datetime import datetime, date

# --- Flask & DB setup ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"  # local file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    coins = db.Column(db.Integer, default=500)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SnakeScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)

class SnakeReward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    distributed = db.Column(db.Boolean, default=False)

# --- Dataset with plain passwords ---
users_plain = [
    {"username": "Axel", "password": "Axel", "coins": 1952},
    {"username": "viggo3", "password": "viggo3", "coins": 1234},
    {"username": "William", "password": "wo123", "coins": 742},
]

# --- Create DB and insert users ---
with app.app_context():
    db.create_all()
    print("Empty database.db created with tables.")

    for u in users_plain:
        hashed_pw = generate_password_hash(u["password"])
        user = User(
            username=u["username"],
            password_hash=hashed_pw,
            coins=u["coins"]
        )
        db.session.add(user)
    db.session.commit()
    print(f"{len(users_plain)} users added with hashed passwords.")

    print("database.db is ready. You can upload it to your app.")
