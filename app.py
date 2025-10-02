# app.py

import os, json, random
from datetime import datetime, date
from functools import wraps
from flask import Flask, g, session, redirect, url_for, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text, func

# -----------------------
# App setup
# -----------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_size": 20,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 1800
}

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {"db"}

db = SQLAlchemy(app)

# -----------------------
# Models
# -----------------------
#

class Salary(db.Model):
    __tablename__ = "salary"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount_per_day = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True)
    last_sent = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    receiver = db.relationship("User", backref="salaries")


class StateBudget(db.Model):
    __tablename__ = "state_budget"
    id = db.Column(db.Integer, primary_key=True)
    total_amount = db.Column(db.Integer, default=1000)   # current available funds
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class BudgetTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)  # e.g. "salary", "welfare"
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Link who created it (a minister, admin, etc.)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_by = db.relationship("User")

class SnakeScore(db.Model):
    __tablename__ = "snake_scores"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)


class FlappyScore(db.Model):
    __tablename__ = "flappy_scores"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)

class DinoScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)

class DinoReward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    distributed = db.Column(db.Boolean, default=False)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # "crime", "tvistemal", "statmal"
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref="reports")


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    coins = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Boolean, default=False)
    verification_request_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    snake_scores = db.relationship("SnakeScore", backref="user", lazy=True)
    flappy_scores = db.relationship("FlappyScore", backref="user", lazy=True)
    dino_scores = db.relationship("DinoScore", backref="user", lazy=True)

    # Foreign key for party membership
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=True)

    # Explicitly link User.party to User.party_id
    party = db.relationship("Party", foreign_keys=[party_id], backref="members")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class MarketplaceItem(db.Model):
    __tablename__ = "marketplace_items"
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Integer, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sold_at = db.Column(db.DateTime, nullable=True)

    seller = db.relationship("User", foreign_keys=[seller_id], backref="items_sold")
    buyer = db.relationship("User", foreign_keys=[buyer_id], backref="items_bought")

# -----------------------
# Before request
# -----------------------
@app.before_request
def load_logged_in_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        try:
            g.user = User.query.get(user_id)
        except Exception as e:
            print("Error loading g.user:", e)
            g.user = None

# -----------------------
# Context processor
# -----------------------
@app.context_processor
def inject_globals():
    return {
        'user': getattr(g, 'user', None),
        'now': datetime.now()
    }

# -----------------------
# Schema upgrade block
# -----------------------
with app.app_context():
    inspector = inspect(db.engine)
    # Example: Add missing columns to user table
    user_columns = [col['name'] for col in inspector.get_columns('user')]
    with db.engine.begin() as conn:
        if 'is_verified' not in user_columns:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN is_verified BOOLEAN DEFAULT FALSE'))
        if 'verification_request_at' not in user_columns:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN verification_request_at DATETIME'))

with app.app_context():
    inspector = inspect(db.engine)
    columns = [c["name"] for c in inspector.get_columns("user")]

    if "party_id" not in columns:
        with db.engine.begin() as conn:
            conn.execute(text('"ALTER TABLE "user" ADD COLUMN party_id INTEGER'))
        print("✅ Added column party_id to user table")
    else:
        print("ℹ️ Column party_id already exists")

with app.app_context():
    inspector = inspect(db.engine)
    if "snake_scores" not in inspector.get_table_names():
        SnakeScore.__table__.create(db.engine)
        print("✅ Created snake_scores table")


# -----------------------
# Utility / decorators
# -----------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not getattr(g, 'user', None):
            flash('Du måste vara inloggad för att se den sidan.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

# -----------------------
# Routes
# -----------------------
@app.route('/')
def index():
    if getattr(g, 'user', None):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        password2 = request.form['password2']
        if not username or not password or not password2:
            flash('Fyll i alla fält.', 'danger')
            return render_template('register.html')
        if password != password2:
            flash('Lösenorden matchar inte.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Användarnamnet finns redan.', 'danger')
            return render_template('register.html')
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registrering lyckades. Logga in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('Felaktigt användarnamn eller lösenord.', 'danger')
            return render_template('login.html')
        session.clear()
        session['user_id'] = user.id
        flash(f'Välkommen, {user.username}!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Du är utloggad.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        receiver_username = request.form['receiver'].strip()
        amount_str = request.form['amount'].strip()
        if not amount_str.isdigit():
            flash('Ange ett giltigt antal coins.', 'danger')
            return redirect(url_for('dashboard'))
        amount = int(amount_str)
        if amount < 1:
            flash('Antalet coins måste vara minst 1.', 'danger')
            return redirect(url_for('dashboard'))
        if receiver_username == g.user.username:
            flash('Du kan inte skicka coins till dig själv.', 'danger')
            return redirect(url_for('dashboard'))
        receiver = User.query.filter_by(username=receiver_username).first()
        if not receiver:
            flash('Mottagaren finns inte.', 'danger')
            return redirect(url_for('dashboard'))
        if g.user.coins < amount:
            flash('Du har inte tillräckligt med coins.', 'danger')
            return redirect(url_for('dashboard'))
        g.user.coins -= amount
        receiver.coins += amount
        transaction = Transaction(sender_id=g.user.id, receiver_id=receiver.id, amount=amount)
        db.session.add(transaction)
        db.session.commit()
        flash(f'Skickade {amount} coins till {receiver_username}.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('dashboard.html', user=g.user)

@app.route('/transactions')
@login_required
def transactions():
    sent = Transaction.query.filter_by(sender_id=g.user.id).order_by(Transaction.timestamp.desc()).all()
    received = Transaction.query.filter_by(receiver_id=g.user.id).order_by(Transaction.timestamp.desc()).all()
    return render_template('transactions.html', sent=sent, received=received, user=g.user)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        new_password2 = request.form['new_password2']
        if not g.user.check_password(current_password):
            flash('Felaktigt nuvarande lösenord.', 'danger')
            return redirect(url_for('change_password'))
        if new_password != new_password2:
            flash('De nya lösenorden matchar inte.', 'danger')
            return redirect(url_for('change_password'))
        if len(new_password) < 6:
            flash('Lösenordet måste vara minst 6 tecken.', 'danger')
            return redirect(url_for('change_password'))
        g.user.set_password(new_password)
        db.session.commit()
        flash('Lösenordet ändrades.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('change_password.html')

@app.route('/dice', methods=['GET', 'POST'])
@login_required
def dice():
    result = None
    rolled_number = None
    guess = None
    bet = None
    if request.method == 'POST':
        guess_str = request.form.get('guess', '').strip()
        bet_str = request.form.get('bet', '').strip()
        if not guess_str.isdigit() or not bet_str.isdigit():
            flash('Vänligen mata in giltigt nummer och insats.', 'danger')
            return redirect(url_for('dice'))
        guess = int(guess_str)
        bet = int(bet_str)
        if guess < 1 or guess > 6 or bet < 1 or bet > g.user.coins:
            flash('Felaktig gissning eller insats.', 'danger')
            return redirect(url_for('dice'))
        rolled_number = random.randint(1, 6)
        if guess == rolled_number:
            winnings = bet * 6
            g.user.coins += winnings
            result = f'Grattis! Du gissade rätt och vann {winnings} coins!'
        else:
            g.user.coins -= bet
            result = f'Tyvärr, tärningen visade {rolled_number}. Du förlorade {bet} coins.'
        db.session.commit()
    return render_template('dice.html', result=result, rolled_number=rolled_number, guess=guess, bet=bet, user=g.user)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        content = request.form.get('message', '').strip()
        if content:
            msg = Message(user_id=g.user.id, content=content)
            db.session.add(msg)
            db.session.commit()
            flash('Meddelande skickat.', 'success')
        else:
            flash('Meddelandet kan inte vara tomt.', 'danger')
        return redirect(url_for('chat'))
    messages = Message.query.order_by(Message.timestamp.asc()).limit(50).all()
    return render_template('chat.html', messages=messages, user=g.user)

from sqlalchemy import func
from datetime import date

# --- Snake leaderboard page ---
@app.route('/snake', methods=['GET'])
@login_required
def snake():
    # Allow ?day=YYYY-MM-DD in the URL
    day_str = request.args.get("day")
    if day_str:
        try:
            selected_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    # Daily Total
    today_total = (
        db.session.query(User.username, func.sum(SnakeScore.score).label('total'))
        .join(SnakeScore)
        .filter(SnakeScore.date == selected_date)
        .group_by(User.id)
        .order_by(func.sum(SnakeScore.score).desc())
        .all()
    )

    # Daily Highscore
    today_highscore = (
        db.session.query(User.username, func.max(SnakeScore.score).label('highscore'))
        .join(SnakeScore)
        .filter(SnakeScore.date == selected_date)
        .group_by(User.id)
        .order_by(func.max(SnakeScore.score).desc())
        .all()
    )

    # All-time total
    alltime_total = (
        db.session.query(User.username, func.sum(SnakeScore.score).label('total'))
        .join(SnakeScore)
        .group_by(User.id)
        .order_by(func.sum(SnakeScore.score).desc())
        .all()
    )

    # All-time highscore
    alltime_highscore = (
        db.session.query(User.username, func.max(SnakeScore.score).label('highscore'))
        .join(SnakeScore)
        .group_by(User.id)
        .order_by(func.max(SnakeScore.score).desc())
        .all()
    )

    user_highscore = (
        db.session.query(func.max(SnakeScore.score))
        .filter(SnakeScore.user_id == g.user.id)
        .scalar()
        or 0
    )

    return render_template(
        "snake.html",
        today_total=today_total,
        today_highscore=today_highscore,
        alltime_total=alltime_total,
        alltime_highscore=alltime_highscore,
        user=g.user,
        user_highscore=user_highscore,
        selected_date=selected_date,
        ADMIN_USERNAME=ADMIN_USERNAME,
        #ui_mode = g.user.ui_mode
    )


# --- Submit snake score ---
@app.route('/snake/submit', methods=['POST'])
@login_required
def snake_submit():
    data = request.get_json()
    score = data.get('score')
    if not isinstance(score, int) or score < 0:
        return jsonify({'error': 'Invalid score'}), 400

    today = date.today()

    # Save the new score
    new_score = SnakeScore(user_id=g.user.id, score=score, date=today)
    db.session.add(new_score)
    db.session.commit()

    return jsonify({'message': 'Score saved', 'score': score})


@app.route('/stats')
@login_required
def stats():
    user = g.user

    # Snake highscore
    snake_highscore = db.session.query(func.max(SnakeScore.score)).filter(
        SnakeScore.user_id == user.id
    ).scalar() or 0

    # FlappyBird highscore
    flappy_highscore = db.session.query(func.max(FlappyScore.score)).filter(
        FlappyScore.user_id == user.id
    ).scalar() or 0

    # Dino highscore
    dino_highscore = db.session.query(func.max(DinoScore.score)).filter(
        DinoScore.user_id == user.id
    ).scalar() or 0

    return render_template(
        "stats.html",
        user=user,
        snake_highscore=snake_highscore,
        flappy_highscore=flappy_highscore,
        dino_highscore=dino_highscore
    )


@app.route('/marketplace')
@login_required
def marketplace():
    items = MarketplaceItem.query.filter_by(buyer_id=None).order_by(MarketplaceItem.created_at.desc()).all()
    return render_template('marketplace.html', items=items, user=g.user)

@app.route('/marketplace/add', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        price = request.form['price'].strip()

        if not title or not price.isdigit() or int(price) <= 0:
            flash('Titel och pris krävs (pris måste vara ett positivt heltal).', 'danger')
            return redirect(url_for('add_item'))

        price = int(price)
        image = request.files.get('image')
        image_filename = None

        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image_filename = f"{datetime.utcnow().timestamp()}_{filename}"
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        item = MarketplaceItem(
            seller_id=g.user.id,
            title=title,
            description=description,
            price=price,
            image_filename=image_filename
        )
        db.session.add(item)
        db.session.commit()
        flash('Objekt tillagt i marknaden.', 'success')
        return redirect(url_for('marketplace'))

    return render_template('add_item.html', user=g.user)

@app.route('/marketplace/buy/<int:item_id>', methods=['POST'])
@login_required
def buy_item(item_id):
    item = MarketplaceItem.query.get_or_404(item_id)

    if item.buyer_id is not None:
        flash('Denna produkt är redan såld.', 'warning')
        return redirect(url_for('marketplace'))

    if item.seller_id == g.user.id:
        flash('Du kan inte köpa dina egna objekt.', 'danger')
        return redirect(url_for('marketplace'))

    if g.user.coins < item.price:
        flash('Du har inte tillräckligt med coins.', 'danger')
        return redirect(url_for('marketplace'))

    # Transfer coins
    buyer = g.user
    seller = User.query.get(item.seller_id)

    buyer.coins -= item.price
    seller.coins += item.price
    item.buyer_id = buyer.id
    item.sold_at = datetime.utcnow()

    db.session.commit()
    flash(f'Du har köpt "{item.title}" för {item.price} coins.', 'success')
    return redirect(url_for('marketplace'))

@app.route('/marketplace/my-bought')
@login_required
def my_bought_items():
    items = MarketplaceItem.query.filter_by(buyer_id=g.user.id).order_by(MarketplaceItem.sold_at.desc()).all()
    return render_template('my_bought_items.html', items=items, user=g.user)


@app.route('/marketplace/my-sold')
@login_required
def my_sold_items():
    items = MarketplaceItem.query.filter_by(seller_id=g.user.id).filter(MarketplaceItem.buyer_id.isnot(None)).order_by(MarketplaceItem.sold_at.desc()).all()
    return render_template('my_sold_items.html', items=items, user=g.user)


@app.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = MarketplaceItem.query.get_or_404(item_id)

    if g.user.username != "admin" and g.user.id != item.seller_id:
        flash("Du har inte behörighet att ta bort detta objekt.", "danger")
        return redirect(url_for("marketplace"))

    db.session.delete(item)
    db.session.commit()
    flash("Objektet togs bort.", "success")
    return redirect(url_for("marketplace"))


@app.route("/download-db-secret")
def download_db():
    return send_file("database.db", as_attachment=True)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# --- Admin Routes (temporary for Render) ---
ADMIN_USERNAME: str = "YOUR_ADMIN_USERNAME"  # change this

# Add this to your app.py
import os
import shutil
from flask import Flask, request, redirect, url_for, flash, render_template, g
from functools import wraps

# --- Ensure this path matches your SQLALCHEMY_DATABASE_URI ---
ACTIVE_DB_PATH = "/opt/render/project/src/database.db"  # cloud DB path

# --- Admin decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user or g.user.username != "admin":  # replace "admin" with your admin username
            flash("Admin access required", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

# --- Upload route ---
@app.route('/admin/upload-db', methods=['GET', 'POST'])
@admin_required
def admin_upload_db():
    if request.method == "POST":
        if "db_file" not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)

        file = request.files["db_file"]
        if file.filename == "":
            flash("No selected file", "danger")
            return redirect(request.url)

        if file and file.filename.endswith(".db"):
            # Save temporarily
            uploads_folder = os.path.join(os.path.dirname(ACTIVE_DB_PATH), "uploads")
            os.makedirs(uploads_folder, exist_ok=True)
            temp_path = os.path.join(uploads_folder, file.filename)
            file.save(temp_path)

            # Backup current DB just in case
            backup_path = os.path.join(uploads_folder, f"database_backup_{file.filename}")
            if os.path.exists(ACTIVE_DB_PATH):
                shutil.copy(ACTIVE_DB_PATH, backup_path)

            # Overwrite active cloud DB
            shutil.copy(temp_path, ACTIVE_DB_PATH)

            flash("Database successfully uploaded and active!", "success")
            return redirect(url_for("admin_upload_db"))
        else:
            flash("Invalid file type. Only .db files are allowed.", "danger")
            return redirect(request.url)

    return render_template("admin_upload_db.html")


@app.route('/admin/reset-coins')
@login_required
def reset_coins():
    if g.user.username != ADMIN_USERNAME:
        abort(403)
    for u in User.query.all():
        u.coins = 500
    db.session.commit()
    return "Coins reset to 500 for all users!"

@app.route('/admin/view-leaderboard')
@login_required
def view_leaderboard():
    if g.user.username != ADMIN_USERNAME:
        abort(403)
    today = date.today()
    leaderboard = (
        db.session.query(User.username, func.sum(SnakeScore.score).label('total'))
        .join(SnakeScore)
        .filter(SnakeScore.date == today)
        .group_by(User.id)
        .order_by(func.sum(SnakeScore.score).desc())
        .all()
    )
    output = "<h2>Today's Snake Leaderboard</h2><ul>"
    for s in leaderboard:
        output += f"<li>{s.username}: {s.total}</li>"
    output += "</ul>"
    return output
@app.route("/admin/create-marketplace-table")
def create_marketplace_table():
    db.create_all()
    return "Marketplace table created!"

from datetime import timedelta

from flask import abort, g
from datetime import date, timedelta
import random
from sqlalchemy import func

from flask import abort, g
from datetime import date, timedelta
from sqlalchemy import func


# --- Flappy leaderboard page ---
@app.route('/flappy', methods=['GET'])
@login_required
def flappy():
    today = date.today()

    today_highscore = (
        db.session.query(User.username, func.max(FlappyScore.score).label('highscore'))
        .join(FlappyScore)
        .filter(FlappyScore.date == today)
        .group_by(User.id)
        .order_by(func.max(FlappyScore.score).desc())
        .all()
    )

    alltime_highscore = (
        db.session.query(User.username, func.max(FlappyScore.score).label('highscore'))
        .join(FlappyScore)
        .group_by(User.id)
        .order_by(func.max(FlappyScore.score).desc())
        .all()
    )

    user_highscore = db.session.query(func.max(FlappyScore.score)).filter(
        FlappyScore.user_id == g.user.id
    ).scalar() or 0

    return render_template(
        'flappy.html',
        today_highscore=today_highscore,
        alltime_highscore=alltime_highscore,
        user=g.user,
        user_highscore=user_highscore
    )


# --- Submit flappy score ---
@app.route('/flappy/submit', methods=['POST'])
@login_required
def flappy_submit():
    data = request.get_json()
    score = data.get('score')

    if not isinstance(score, int) or score < 0:
        return jsonify({'error': 'Invalid score'}), 400

    today = date.today()

    # Save the new score (do not overwrite so highscores track properly)
    new_score = FlappyScore(user_id=g.user.id, score=score, date=today)
    db.session.add(new_score)

    # Reward 1 coin per score
    g.user.coins += score

    db.session.commit()

    return jsonify({'message': 'Score saved', 'score': score, 'coins': g.user.coins})


from datetime import datetime, timedelta, date
from flask import g, request, redirect, url_for, flash, render_template

# ---------------------------
# BankAccount Model
# ---------------------------
class BankAccount(db.Model):
    __tablename__ = "bank_account"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0)
    loan = db.Column(db.Integer, default=0)
    credit_score = db.Column(db.Integer, default=500)
    last_interest_date = db.Column(db.Date, default=date.today)
    loan_taken_at = db.Column(db.DateTime, nullable=True)

    loans_taken = db.Column(db.Integer, default=0)
    loans_repaid_on_time = db.Column(db.Integer, default=0)
    loans_missed = db.Column(db.Integer, default=0)

    user = db.relationship("User", backref=db.backref("bank_account", uselist=False))
    transactions = db.relationship("BankTransaction", backref="account", lazy=True)

    def calculate_credit_score(self):
        score = 500
        # Savings effect
        score += min(self.balance // 100, 200)
        # Outstanding loan effect
        score -= min(self.loan // 100, 200)
        # Repayment history
        if self.loans_taken > 0:
            on_time_ratio = self.loans_repaid_on_time / self.loans_taken
            missed_ratio = self.loans_missed / self.loans_taken
            score += int(on_time_ratio * 100)
            score -= int(missed_ratio * 150)
        # Account age effect
        try:
            age_days = (date.today() - self.user.created_at.date()).days
            score += min(age_days // 30, 50)
        except Exception:
            pass
        self.credit_score = max(300, min(850, score))

# ---------------------------
# BankTransaction Model
# ---------------------------
class BankTransaction(db.Model):
    __tablename__ = "bank_transaction"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("bank_account.id"), nullable=False)
    type = db.Column(db.String(20))  # "deposit", "withdraw", "loan", "repay", "interest"
    amount = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)

# ---------------------------
# Apply interest based on credit score
# ---------------------------
def apply_interest(account):
    today = date.today()
    days_passed = (today - account.last_interest_date).days
    if days_passed <= 0:
        return

    # Base interest rates
    deposit_rate = 0.05  # 5% daily
    loan_rate = 0.10     # 10% daily

    # Credit score modifier
    modifier = (account.credit_score - 500) // 100 * 0.01  # +/-1% per 100 points
    deposit_rate += modifier
    loan_rate -= modifier  # higher credit score = cheaper loans

    # Penalize very low credit score
    if account.credit_score < 400:
        loan_rate += 0.02
    if account.credit_score < 300:
        loan_rate += 0.03

    # Apply interest for each missed day
    if account.balance > 0:
        gained = int(account.balance * deposit_rate * days_passed)
        account.balance += gained
        db.session.add(BankTransaction(account_id=account.id, type="interest", amount=gained, note="Deposit interest"))

    if account.loan > 0:
        added = int(account.loan * loan_rate * days_passed)
        account.loan += added
        db.session.add(BankTransaction(account_id=account.id, type="interest", amount=added, note="Loan interest"))

    account.last_interest_date = today
    account.calculate_credit_score()
    db.session.commit()

# ---------------------------
# Bank Route
# ---------------------------
@app.route('/bank', methods=['GET', 'POST'])
@login_required
def bank():
    account = g.user.bank_account
    if not account:
        account = BankAccount(user_id=g.user.id)
        db.session.add(account)
        db.session.commit()

    # Apply interest for missed days
    apply_interest(account)

    if request.method == 'POST':
        action = request.form.get("action")
        amount = int(request.form.get("amount", 0))

        # Deposit
        if action == "deposit" and g.user.coins >= amount:
            g.user.coins -= amount
            account.balance += amount
            db.session.add(BankTransaction(account_id=account.id, type="deposit", amount=amount))

        # Withdraw
        elif action == "withdraw" and account.balance >= amount:
            account.balance -= amount
            g.user.coins += amount
            db.session.add(BankTransaction(account_id=account.id, type="withdraw", amount=amount))

        # Loan
        elif action == "loan":
            max_loan = account.credit_score * 2
            if amount <= max_loan and account.loan == 0:
                account.loan += amount
                account.loan_taken_at = datetime.utcnow()
                account.loans_taken += 1
                g.user.coins += amount
                db.session.add(BankTransaction(account_id=account.id, type="loan", amount=amount))

        # Repay (only after 24h)
        elif action == "repay" and account.loan > 0 and g.user.coins >= amount:
            if account.loan_taken_at and datetime.utcnow() - account.loan_taken_at < timedelta(hours=24):
                flash("You must hold the loan for at least 24 hours before repayment.", "danger")
            else:
                repay_amount = min(amount, account.loan)
                account.loan -= repay_amount
                g.user.coins -= repay_amount
                account.loans_repaid_on_time += 1
                db.session.add(BankTransaction(account_id=account.id, type="repay", amount=repay_amount))

        account.calculate_credit_score()
        db.session.commit()
        return redirect(url_for("bank"))

    # ---- This is outside POST block ----
    transactions = BankTransaction.query.filter_by(account_id=account.id).order_by(
        BankTransaction.timestamp.desc()
    ).limit(50).all()

    # Prepare chart data: daily balance and loan snapshots
    history = BankTransaction.query.filter_by(account_id=account.id).order_by(BankTransaction.timestamp.asc()).all()
    chart_data = []
    balance = 0
    loan = 0
    for t in history:
        if t.type == "deposit":
            balance += t.amount
        elif t.type == "withdraw":
            balance -= t.amount
        elif t.type == "loan":
            loan += t.amount
        elif t.type == "repay":
            loan -= t.amount
        chart_data.append({
            "timestamp": t.timestamp.strftime("%Y-%m-%d"),
            "balance": balance,
            "loan": loan
        })

    return render_template(
        "bank.html",
        user=g.user,
        account=account,
        transactions=transactions,
        chart_data=json.dumps(chart_data)  # pass as JSON
    )


@app.route('/admin/close-day', methods=['POST', 'GET'])
@login_required
def close_day():

    today = date.today()

    # Always recalculate rewards fresh
    today_totals = (
        db.session.query(User.id, func.sum(SnakeScore.score).label('total_score'))
        .join(SnakeScore)
        .filter(SnakeScore.date == today)
        .group_by(User.id)
        .all()
    )

    if today_totals:
        total_points = sum([t.total_score for t in today_totals])

        # 1. Proportionally distribute 1000 coins
        if total_points > 0:
            for user_id, total_score in today_totals:
                user = User.query.get(user_id)
                reward = int(1000 * total_score / total_points)
                user.coins += reward

        # 2. Highscore winner gets total_points extra
        highscore_winner = (
            db.session.query(User)
            .join(SnakeScore)
            .filter(SnakeScore.date == today)
            .order_by(SnakeScore.score.desc())
            .first()
        )
        if highscore_winner:
            highscore_winner.coins += total_points

    # Reset today’s scores (clear leaderboard)
    SnakeScore.query.filter(SnakeScore.date == today).delete()

    # Always reset reward entry so button can be pressed again
    reward_entry = SnakeReward.query.filter_by(date=today).first()
    if not reward_entry:
        reward_entry = SnakeReward(date=today)
        db.session.add(reward_entry)
    reward_entry.distributed = True

    db.session.commit()

    flash(f"Day {today} closed, rewards distributed and leaderboard reset!", "success")
    return redirect(url_for("snake"))

@app.route("/toggle-ui")
@login_required
def toggle_ui():
    g.user.ui_mode = "modern" if g.user.ui_mode == "legacy" else "legacy"
    db.session.commit()
    flash(f"Switched to {g.user.ui_mode} mode!", "success")
    return redirect(url_for("snake"))

from datetime import date

from sqlalchemy import inspect
from flask import jsonify

from flask import jsonify

from flask import Flask, g, redirect, url_for, flash
from sqlalchemy import text

@app.route("/admin/create-dino-table")
@login_required
def create_dino_table():
    if g.user.username != ADMIN_USERNAME:
        abort(403)
    db.create_all()
    return "✅ DinoScore table created (and any other missing tables)."




@app.route('/admin/download-db-backup', methods=['GET'])
@login_required
def download_db_backup():
    # Only admin can access
    if g.user.username != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    # Backup file path
    backup_file = os.path.join("backups", "viggo_db_backup.dump")

    # Ensure backup folder exists
    os.makedirs("backups", exist_ok=True)

    # PostgreSQL credentials from your config
    host = "dpg-d2su8c3e5dus73d9md0g-a.frankfurt-postgres.render.com"
    user = "viggo_db_user"
    db_name = "viggo_db"
    password = "LaL1YWC59icz3L8ZRAifMTXNnBonZ4YM"

    # Set PGPASSWORD env variable so pg_dump doesn't prompt
    os.environ["PGPASSWORD"] = password

    # Run pg_dump
    try:
        subprocess.run([
            "pg_dump",
            "-h", host,
            "-U", user,
            "-d", db_name,
            "-F", "c",
            "-b",
            "-v",
            "-f", backup_file
        ], check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Backup failed: {str(e)}"}), 500

    # Return file for download
    return send_file(backup_file, as_attachment=True, download_name="viggo_db_backup.dump")


@app.route('/dino')
@login_required
def dino():
    today = date.today()

    # --- Daily leaderboard (top highscores today) ---
    today_highscore = (
        db.session.query(User.username, func.max(DinoScore.score).label('high'))
        .join(DinoScore)
        .filter(DinoScore.date == today)
        .group_by(User.id)
        .order_by(func.max(DinoScore.score).desc())
        .limit(10)
        .all()
    )

    # --- All-time leaderboard (top highscores ever) ---
    alltime_highscore = (
        db.session.query(User.username, func.max(DinoScore.score).label('high'))
        .join(DinoScore)
        .group_by(User.id)
        .order_by(func.max(DinoScore.score).desc())
        .limit(10)
        .all()
    )

    # user’s personal highscore
    user_highscore = db.session.query(func.max(DinoScore.score)).filter(
        DinoScore.user_id == g.user.id
    ).scalar() or 0

    return render_template(
        'dino.html',
        today_highscore=today_highscore,
        alltime_highscore=alltime_highscore,
        user=g.user,
        user_highscore=user_highscore
    )


@app.route('/dino/submit', methods=['POST'])
@login_required
def dino_submit():
    data = request.get_json()
    score = data.get('score')
    if not isinstance(score, int) or score < 0:
        return jsonify({'error': 'Invalid score'}), 400

    today = date.today()

    # Save the score
    new_score = DinoScore(user_id=g.user.id, score=score, date=today)
    db.session.add(new_score)
    db.session.commit()

    # --- Check if daily reward is already distributed ---
    reward_entry = DinoReward.query.filter_by(date=today).first()
    if not reward_entry:
        reward_entry = DinoReward(date=today, distributed=False)
        db.session.add(reward_entry)
        db.session.commit()

    if not reward_entry.distributed:
        # Find today’s top score
        top_player = (
            db.session.query(User, func.max(DinoScore.score).label('high'))
            .join(DinoScore)
            .filter(DinoScore.date == today)
            .group_by(User.id)
            .order_by(func.max(DinoScore.score).desc())
            .first()
        )

        if top_player:
            winner, highscore = top_player
            winner.coins += 1000
            reward_entry.distributed = True
            db.session.commit()

    # Return updated personal highscore
    highscore = db.session.query(func.max(DinoScore.score)).filter(
        DinoScore.user_id == g.user.id
    ).scalar()

    return jsonify({'message': 'Score saved', 'highscore': highscore})

@app.route('/profile/<username>')
def profile(username):
    profile_user = User.query.filter_by(username=username).first_or_404()

    # Compute max scores for this user
    snake_highscore = max((s.score for s in profile_user.snake_scores), default=0)
    flappy_highscore = max((f.score for f in profile_user.flappy_scores), default=0)
    dino_highscore = max((d.score for d in profile_user.dino_scores), default=0)

    # Compute record scores across all users
    snake_record = db.session.query(func.max(SnakeScore.score)).scalar() or 1
    flappy_record = db.session.query(func.max(FlappyScore.score)).scalar() or 1
    dino_record = db.session.query(func.max(DinoScore.score)).scalar() or 1

    # Compute percentages
    snake_percent = min(int(snake_highscore / snake_record * 100), 100)
    flappy_percent = min(int(flappy_highscore / flappy_record * 100), 100)
    dino_percent = min(int(dino_highscore / dino_record * 100), 100)

    return render_template(
        'profile.html',
        profile_user=profile_user,
        snake_highscore=snake_highscore,
        flappy_highscore=flappy_highscore,
        dino_highscore=dino_highscore,
        snake_percent=snake_percent,
        flappy_percent=flappy_percent,
        dino_percent=dino_percent
    )



@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if not g.user:
        return redirect(url_for('login'))

    selected_avatar = request.form.get('avatar')
    if selected_avatar:
        # Save the new avatar in the database
        user = g.user
        # If you store just the filename
        user.avatar = os.path.basename(selected_avatar)
        db.session.commit()

    return redirect(url_for('profile', username=g.user.username))

class Party(db.Model):
    __tablename__ = "party"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    founder_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    founder = db.relationship("User", foreign_keys=[founder_id], backref="founded_parties")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_in_government = db.Column(db.Boolean, default=False)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

from datetime import datetime, timedelta

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    proposer_party_id = db.Column(db.Integer, db.ForeignKey('party.id'))
    passed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    vote_deadline = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=12))
    proposer_party = db.relationship("Party", foreign_keys=[proposer_party_id])


class CoalitionProposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proposer_party_id = db.Column(db.Integer, db.ForeignKey('party.id'))
    invited_party_id = db.Column(db.Integer, db.ForeignKey('party.id'))
    status = db.Column(db.String(20), default="pending")  # "pending", "accepted", "rejected"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BillVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'), nullable=False)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=False)
    vote_choice = db.Column(db.String(10), nullable=False)  # "yes", "no", "abstain"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    party = db.relationship("Party")

class ConstitutionVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    constitution_id = db.Column(db.Integer, db.ForeignKey('constitution.id'), nullable=False)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=False)
    vote_choice = db.Column(db.String(10), nullable=False)
    phase = db.Column(db.String(10), nullable=False)  # "first" or "final"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


PARTY_COLORS = {
    "red": "e74c3c",
    "green": "27ae60",
    "blue": "3498db",
    "yellow": "f1c40f",
    "brown": "8e44ad",
    # fallback color
    "default": "7f8c8d"
}


@app.route('/coalition', methods=['GET', 'POST'])
@login_required
def coalition_page():
    user_party = Party.query.filter_by(founder_id=g.user.id).first()
    proposals = CoalitionProposal.query.all()
    parties = Party.query.all()

    if request.method == 'POST':
        invited_id = request.form.get('invited_party_id')
        if not user_party:
            flash("Only party founders can propose coalitions!", "danger")
            return redirect(url_for('coalition_page'))

        proposal = CoalitionProposal(
            proposer_party_id=user_party.id,
            invited_party_id=invited_id
        )
        db.session.add(proposal)
        db.session.commit()
        flash("Coalition proposal sent!", "success")
        return redirect(url_for('coalition_page'))

    return render_template("coalition.html",
                           proposals=proposals,
                           parties=parties,
                           user_party=user_party)


@app.route('/coalition/respond/<int:proposal_id>/<action>', methods=['POST'])
@login_required
def coalition_respond(proposal_id, action):
    proposal = CoalitionProposal.query.get_or_404(proposal_id)
    invited_party = Party.query.get(proposal.invited_party_id)

    if not invited_party or invited_party.founder_id != g.user.id:
        abort(403)

    if action == "accept":
        proposal.status = "accepted"
    elif action == "reject":
        proposal.status = "rejected"

    db.session.commit()
    flash(f"Proposal {action}ed!", "info")
    return redirect(url_for('coalition_page'))


@app.route('/bill/propose', methods=['GET', 'POST'])
@login_required
def propose_bill():
    party = Party.query.filter_by(founder_id=g.user.id, is_in_government=True).first()
    if not party:
        flash("Only government party leaders can propose bills!", "danger")
        return redirect(url_for('riksdag'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        bill = Bill(title=title, content=content, proposer_party_id=party.id)
        db.session.add(bill)
        db.session.commit()
        flash("Bill proposed!", "success")
        return redirect(url_for('bill_view', bill_id=bill.id))

    return render_template("bill_propose.html")

@app.route("/bill/<int:bill_id>", methods=["GET", "POST"])
@login_required
def bill_view(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    now = datetime.utcnow()
    expired = now > bill.vote_deadline if bill.vote_deadline else False

    riksdag_results = calculate_riksdag_seats()
    total_seats = sum(p["seats"] for p in riksdag_results)

    # Handle POST vote only if bill is not expired
    if request.method == "POST" and g.user and not expired:
        vote_choice = request.form.get("vote")
        if vote_choice in ["yes", "no", "abstain"]:
            existing_vote = BillVote.query.filter_by(
                bill_id=bill.id, party_id=g.user.party_id
            ).first()

            if existing_vote:
                existing_vote.vote_choice = vote_choice
            else:
                new_vote = BillVote(
                    bill_id=bill.id,
                    party_id=g.user.party_id,
                    vote_choice=vote_choice
                )
                db.session.add(new_vote)
            db.session.commit()
            flash("Din röst har sparats!", "success")
            return redirect(url_for("bill_view", bill_id=bill.id))

    # --- Compute votes ---
    votes = BillVote.query.filter_by(bill_id=bill.id).all()

    def get_party_seats(party_id):
        return next((p["seats"] for p in riksdag_results if p["id"] == party_id), 0)

    yes_seats = sum(get_party_seats(v.party_id) for v in votes if v.vote_choice == "yes")
    no_seats = sum(get_party_seats(v.party_id) for v in votes if v.vote_choice == "no")
    abstain_seats = sum(get_party_seats(v.party_id) for v in votes if v.vote_choice == "abstain")

    # Determine bill status
    if expired or yes_seats > total_seats / 2 or no_seats >= total_seats / 2:
        if yes_seats > no_seats:
            bill_status = "passed"
        else:
            bill_status = "failed"
    else:
        bill_status = "not voted"

    # Prepare votes for display in template
    vote_display = [
        {
            "party_name": next((p["party"] for p in riksdag_results if p["id"] == v.party_id), f"Party {v.party_id}"),
            "vote_choice": v.vote_choice
        }
        for v in votes
    ]

    return render_template(
        "bill_view.html",
        bill=bill,
        votes=vote_display,
        bill_status=bill_status,
        yes_seats=yes_seats,
        no_seats=no_seats,
        abstain_seats=abstain_seats,
        total_seats=total_seats,
        expired=expired,
        now=now
    )




@app.route('/bills')
@login_required
def bills_list():
    bills = Bill.query.all()
    results = []

    riksdag_results = calculate_riksdag_seats()
    total_seats = sum(p["seats"] for p in riksdag_results)

    for bill in bills:
        votes = BillVote.query.filter_by(bill_id=bill.id).all()

        yes_seats = sum(next((p["seats"] for p in riksdag_results if p["id"] == v.party_id), 0)
                        for v in votes if v.vote_choice == "yes")
        no_seats = sum(next((p["seats"] for p in riksdag_results if p["id"] == v.party_id), 0)
                       for v in votes if v.vote_choice == "no")

        # Determine bill status
        now = datetime.utcnow()
        if now > bill.vote_deadline or yes_seats > total_seats / 2 or no_seats >= total_seats / 2:
            if yes_seats > no_seats:
                status = "passed"
            else:
                status = "failed"
        else:
            status = "not voted"

        # Prepare votes for display
        vote_display = []
        for v in votes:
            party_name = next((p["party"] for p in riksdag_results if p["id"] == v.party_id), f"Party {v.party_id}")
            vote_display.append({
                "party_name": party_name,
                "vote_choice": v.vote_choice
            })

        results.append({
            "bill": bill,
            "status": status,
            "votes": vote_display
        })

    return render_template("bills_list.html", results=results, ADMIN_USERNAME=ADMIN_USERNAME)


@app.route('/constitutions')
@login_required
def constitution_list():
    constitutions = Constitution.query.all()
    return render_template("constitution_list.html", constitutions=constitutions, ADMIN_USERNAME=ADMIN_USERNAME)

@app.route('/constitution/propose', methods=['GET', 'POST'])
@login_required
def propose_constitution():
    party = Party.query.filter_by(founder_id=g.user.id, is_in_government=True).first()
    if not party:
        flash("Only government parties can propose amendments!", "danger")
        return redirect(url_for('riksdag'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        new_const = Constitution(
            title=title,
            content=content,
            proposed_by_party_id=party.id,
            first_vote_date=datetime.utcnow(),
            final_vote_deadline=datetime.utcnow()
        )
        db.session.add(new_const)
        db.session.commit()
        flash("Amendment proposed!", "success")
        return redirect(url_for('constitution_list', const_id=new_const.id))

    return render_template("constitution_propose.html")

@app.route("/constitution/<int:constitution_id>", methods=["GET", "POST"])
@login_required
def constitution_detail(constitution_id):
    constitution = Constitution.query.get_or_404(constitution_id)
    riksdag_results = calculate_riksdag_seats()
    total_seats = sum(p["seats"] for p in riksdag_results)
    majority_needed = total_seats // 2 + 1

    # Compute vote counts
    votes = ConstitutionVote.query.filter_by(constitution_id=constitution.id).all()
    yes_seats = sum(p["seats"] for p in riksdag_results if any(v.party_id == p["id"] and v.vote_choice == "yes" for v in votes))
    no_seats = sum(p["seats"] for p in riksdag_results if any(v.party_id == p["id"] and v.vote_choice == "no" for v in votes))
    abstain_seats = sum(p["seats"] for p in riksdag_results if any(v.party_id == p["id"] and v.vote_choice == "abstain" for v in votes))

    now = datetime.utcnow()

    if constitution.final_vote_passed:
        status = "passed"
    elif constitution.first_vote_passed:
        # first vote passed but final vote not done yet
        status = "in_final_vote"
    else:
        # first vote not yet passed, so voting is open
        status = "not_voted_yet"

    return render_template(
        "constitution_detail.html",
        constitution=constitution,
        votes=votes,
        total_seats=total_seats,
        majority_needed=majority_needed,
        yes_seats=yes_seats,
        no_seats=no_seats,
        abstain_seats=abstain_seats,
        status=status
    )





def calculate_riksdag_seats():
    total_votes = db.session.query(func.count(Vote.id)).scalar() or 0
    if total_votes == 0:
        return []

    party_votes = (
        db.session.query(Party.id, Party.name, func.count(Vote.id).label("votes"))
        .outerjoin(Vote)
        .group_by(Party.id)
        .all()
    )

    results = []
    for party_id, party_name, votes in party_votes:
        seats = round((votes / total_votes) * 349)  # Swedish Riksdag has 349 seats
        results.append({
            "id": party_id,
            "party": party_name,
            "votes": votes,
            "seats": seats
        })
    return results


    results = []
    for party_id, party_name, votes in party_votes:
        seats = round((votes / total_votes) * 349)  # total seats = 49
        color_key = party_name.lower()
        color = PARTY_COLORS.get(color_key, PARTY_COLORS["default"])
        results.append({
            "id": party_id,       # ✅ now defined correctly
            "party": party_name,
            "votes": votes,
            "seats": seats,
            "color": color
        })
    return results



@app.route('/party/create', methods=['GET', 'POST'])
@login_required
def create_party():
    if request.method == 'POST':
        name = request.form.get('name')  # <--- works with HTML forms

        if not name:
            flash("Party name required", "danger")
            return redirect(url_for('create_party'))

        if g.user.coins < 1000:
            flash("Not enough coins (1000 required)", "danger")
            return redirect(url_for('create_party'))

        if Party.query.filter_by(name=name).first():
            flash("Party already exists", "danger")
            return redirect(url_for('create_party'))

        new_party = Party(name=name, founder_id=g.user.id)
        g.user.party_id = new_party.id
        db.session.add(new_party)
        g.user.coins -= 1000
        db.session.commit()

        flash(f"Party '{name}' created!", "success")
        return redirect(url_for('vote'))

    return render_template("create_party.html")


# vote.py route
@app.route('/vote', methods=['GET', 'POST'])
@login_required
def vote():
    today = date.today()
    # Thursday = 3, Friday = 4
    if today.weekday() not in [0, 3]:
        flash("Röstning bara öppen Onsdag och Torsdag!", "danger")
        return redirect(url_for("dashboard"))

    # Check if user is verified
    if not g.user.is_verified:
        # If user has never requested verification, set timestamp
        if not g.user.verification_request_at:
            g.user.verification_request_at = datetime.utcnow()
            db.session.commit()
            flash("You must verify your real name before voting! Verification request submitted.", "warning")
        else:
            flash("You must verify your real name before voting! Verification pending.", "warning")
        return redirect(url_for('verify'))

    # Determine start of current week (Thursday)
    # Assuming week_start for voting is Thursday
    # If today is Thursday or Friday, week_start = Thursday of this week
    weekday_offset = (today.weekday() - 3) % 7  # 3 = Thursday
    week_start = today - timedelta(days=weekday_offset)

    if request.method == 'POST':
        party_id = request.form.get('party_id')
        if not party_id:
            flash("Please select a party", "danger")
            return redirect(url_for('vote'))

        # Check if user already voted this week
        existing_vote = Vote.query.filter_by(user_id=g.user.id, week_start=week_start).first()
        if existing_vote:
            flash("You already voted this week!", "warning")
            return redirect(url_for('vote'))

        # Record new vote
        new_vote = Vote(user_id=g.user.id, party_id=party_id, week_start=week_start)
        db.session.add(new_vote)
        db.session.commit()
        flash("Vote submitted!", "success")
        return redirect(url_for('vote'))

    # GET request: show all parties
    parties = Party.query.all()
    return render_template("vote.html", parties=parties)

@app.route('/admin/verify-requests')
@login_required
def admin_verify_requests():
    pending_users = User.query.filter(
        User.is_verified == False,
        User.verification_request_at.isnot(None)
    ).all()

    return render_template("admin_verify.html", pending_users=pending_users)


@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
def admin_approve(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = True
    db.session.commit()
    flash(f"{user.username} has been verified.", "success")
    return redirect(url_for('admin_verify_requests'))


@app.route('/admin/end_vote', methods=['POST'])
@login_required
def end_vote():
    if g.user.username != ADMIN_USERNAME:
        flash("Admins only!", "danger")
        return redirect(url_for('riksdag'))

    # Calculate results and clear votes for next week
    results = calculate_riksdag_seats()

    # Clear votes after calculation
    db.session.query(Vote).delete()
    db.session.commit()

    flash("Voting ended. Results have been calculated!", "info")
    return render_template("riksdag.html", results=results)

@app.route("/admin/backfill_party_ids")
@login_required
def backfill_party_ids():
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    users = User.query.all()
    for user in users:
        if not user.party_id:
            party = Party.query.filter_by(founder_id=user.id).first()
            if party:
                user.party_id = party.id
    db.session.commit()
    return "Backfill complete ✅"

@app.route("/admin/assign_user_party", methods=["POST"])
@login_required
def assign_user_party():
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    username = request.form.get("username")
    partyname = request.form.get("partyname")

    if not username or not partyname:
        flash("Username and Party Name are required!", "danger")
        return redirect(url_for("assign_user_form"))

    user = User.query.filter_by(username=username).first()
    party = Party.query.filter_by(name=partyname).first()

    if not user:
        flash(f"No user found with username '{username}'", "danger")
        return redirect(url_for("assign_user_form"))

    if not party:
        flash(f"No party found with name '{partyname}'", "danger")
        return redirect(url_for("assign_user_form"))

    user.party_id = party.id
    db.session.commit()

    flash(f"User '{username}' has been assigned to party '{partyname}' ✅", "success")
    return redirect(url_for("assign_user_form"))


@app.route("/admin/assign_user_form")
@login_required
def assign_user_form():
    if g.user.username != ADMIN_USERNAME:
        abort(403)
    return render_template("admin_assign_user.html")


@app.route('/verify', methods=['GET', 'POST'])
@login_required
def verify():
    if request.method == 'POST':
        g.user.real_name = request.form.get('real_name')
        g.user.verification_request_at = datetime.utcnow()
        db.session.commit()
        flash("Verification request submitted!", "success")
        return redirect(url_for('dashboard'))

    return render_template("verify.html")


@app.route('/riksdag')
def riksdag():
    results = calculate_riksdag_seats()
    return render_template("riksdag.html", results=results, ADMIN_USERNAME=ADMIN_USERNAME)



@app.route('/admin/delete_party/<int:party_id>', methods=['POST'])
@login_required
def admin_delete_party(party_id):
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    party = Party.query.get_or_404(party_id)

    # Delete all votes for that party first (to avoid FK constraint errors)
    Vote.query.filter_by(party_id=party.id).delete()

    db.session.delete(party)
    db.session.commit()

    flash(f"Party '{party.name}' has been deleted.", "info")
    return redirect(url_for('riksdag'))

@app.route('/riksdag/coalition', methods=['GET', 'POST'])
@login_required
def riksdag_coalition():
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    results = calculate_riksdag_seats()
    total_seats = 349
    majority = (total_seats // 2) + 1

    if request.method == 'POST':
        selected_party_ids = request.form.getlist('party_ids')  # list of party IDs
        coalition = [p for p in results if str(p["id"]) in selected_party_ids]
        seats_sum = sum(p["seats"] for p in coalition)
        status = "majority" if seats_sum >= majority else "no_majority"
        return render_template(
            "riksdag_coalition.html",
            results=results,
            coalition=coalition,
            seats_sum=seats_sum,
            majority=majority,
            status=status
        )

    return render_template(
        "riksdag_coalition.html",
        results=results,
        coalition=[],
        seats_sum=0,
        majority=majority,
        status=None
    )



def form_government(selected_parties_ids):
    results = calculate_riksdag_seats()
    total_seats = sum([p["seats"] for p in results])
    selected_seats = sum([p["seats"] for p in results if p["id"] in selected_parties_ids])

    if selected_seats / total_seats < 0.5:
        return False, "Not enough seats for a majority. Coalition required!"

    # Mark parties as in government
    for party_id in selected_parties_ids:
        party = Party.query.get(party_id)
        party.is_in_government = True
    db.session.commit()
    return True, "Government formed successfully!"

def vote_on_bill(bill_id, votes_dict):
    bill = Bill.query.get(bill_id)
    now = datetime.utcnow()
    if now > bill.vote_deadline:
        return bill.passed  # ignore late votes

    results = calculate_riksdag_seats()
    total_seats = sum(p["seats"] for p in results)
    yes_seats = sum(
        p["seats"] for p in results
        if votes_dict.get(p["id"]) == "yes"
    )

    bill.passed = yes_seats > total_seats / 2
    db.session.commit()
    return bill.passed


class Constitution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    proposed_by_party_id = db.Column(db.Integer, db.ForeignKey('party.id'))
    first_vote_passed = db.Column(db.Boolean, default=False)
    final_vote_passed = db.Column(db.Boolean, default=False)
    first_vote_date = db.Column(db.DateTime)
    final_vote_date = db.Column(db.DateTime)
    first_vote_deadline = db.Column(db.DateTime)
    final_vote_deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


from datetime import datetime, timedelta

def propose_constitution_change(title, content, proposer_party_id):
    new_const = Constitution(
        title=title,
        content=content,
        proposed_by_party_id=proposer_party_id,
        first_vote_date=datetime.utcnow()
    )
    db.session.add(new_const)
    db.session.commit()
    return new_const

def vote_constitution_first(const_id, votes_dict):
    const = Constitution.query.get(const_id)
    results = calculate_riksdag_seats()
    total_seats = sum([p["seats"] for p in results])
    yes_seats = sum([p["seats"] for p in results if votes_dict.get(p["id"]) == "yes"])

    if yes_seats > total_seats / 2:
        const.first_vote_passed = True
        const.final_vote_date = const.first_vote_date + timedelta(days=7)  # waiting period
    db.session.commit()
    return const.first_vote_passed

def vote_constitution_final(const_id, votes_dict):
    const = Constitution.query.get(const_id)
    if datetime.utcnow() < const.final_vote_date:
        return False, "Final vote not yet open. Waiting period active."

    results = calculate_riksdag_seats()
    total_seats = sum([p["seats"] for p in results])
    yes_seats = sum([p["seats"] for p in results if votes_dict.get(p["id"]) == "yes"])

    if yes_seats > total_seats / 2:
        const.final_vote_passed = True
        db.session.commit()
        return True, "Constitutional amendment passed!"
    
    const.final_vote_passed = False
    db.session.commit()
    return False, "Amendment failed in final vote."

    db.create_all()
    return "Database initialized ✅"

from sqlalchemy import inspect, text

@app.route("/admin/migrate_tables", methods=['GET', 'POST'])
@login_required
def migrate_tablese():
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    inspector = inspect(db.engine)

    # --- Constitution table ---
    const_columns = [col["name"] for col in inspector.get_columns("constitution")]
    with db.engine.begin() as conn:
        if "created_at" not in const_columns:
            conn.execute(text(
                'ALTER TABLE constitution ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            ))
            print("✅ Added column created_at to Constitution")

        if "first_vote_deadline" not in const_columns:
            conn.execute(text(
                'ALTER TABLE constitution ADD COLUMN first_vote_deadline TIMESTAMP'
            ))
            print("✅ Added column first_vote_deadline to Constitution")

        if "final_vote_deadline" not in const_columns:
            conn.execute(text(
                'ALTER TABLE constitution ADD COLUMN final_vote_deadline TIMESTAMP'
            ))
            print("✅ Added column final_vote_deadline to Constitution")

        if "first_vote_passed" not in const_columns:
            conn.execute(text(
                'ALTER TABLE constitution ADD COLUMN first_vote_passed BOOLEAN DEFAULT FALSE'
            ))
            print("✅ Added column first_vote_passed to Constitution")

    # --- StateBudget table ---
    budget_columns = [col["name"] for col in inspector.get_columns("state_budget")]
    with db.engine.begin() as conn:
        if "total_funds" not in budget_columns:
            conn.execute(text(
                'ALTER TABLE state_budget ADD COLUMN total_funds INTEGER DEFAULT 0'
            ))
            print("✅ Added column total_funds to StateBudget")

        if "updated_at" not in budget_columns:
            conn.execute(text(
                'ALTER TABLE state_budget ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            ))
            print("✅ Added column updated_at to StateBudget")

    return "✅ Migration complete for Constitution and StateBudget tables!"

@app.route("/admin/migrate_state_budget")
@login_required
def migrate_state_budget():
    if not g.user or g.user.username != ADMIN_USERNAME:
        abort(403)

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("state_budget")]

    with db.engine.begin() as conn:
        if "total_amount" not in columns:
            # Add column total_amount with default 0
            conn.execute(text(
                "ALTER TABLE state_budget ADD COLUMN total_amount INTEGER DEFAULT 100"
            ))
            print("✅ Added column total_amount to StateBudget")

    return "✅ StateBudget table migrated successfully!"

@app.route("/admin/delete_constitution/<int:constitution_id>", methods=["POST"])
@login_required
def admin_delete_constitution(constitution_id):
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    constitution = Constitution.query.get_or_404(constitution_id)
    db.session.delete(constitution)
    db.session.commit()
    flash("Constitution deleted ✅", "success")
    return redirect(url_for("constitutions_list"))



@app.route("/admin/migrate_tables", methods=['GET'])
@login_required
def migrate_tables():
    if not g.user or g.user.username != "YOUR_ADMIN_USERNAME":
        return "Forbidden", 403

    with db.engine.connect() as conn:

        # Bill table
        try:
            conn.execute(text('ALTER TABLE bill ADD COLUMN created_at TIMESTAMP DEFAULT NOW()'))
        except Exception as e:
            print("bill.created_at exists:", e)

        try:
            conn.execute(text('ALTER TABLE bill ADD COLUMN vote_deadline TIMESTAMP'))
        except Exception as e:
            print("bill.vote_deadline exists:", e)

        # Constitution table
        try:
            conn.execute(text('ALTER TABLE constitution ADD COLUMN first_vote_deadline TIMESTAMP'))
        except Exception as e:
            print("constitution.first_vote_deadline exists:", e)

        try:
            conn.execute(text('ALTER TABLE constitution ADD COLUMN final_vote_deadline TIMESTAMP'))
        except Exception as e:
            print("constitution.final_vote_deadline exists:", e)
        try:
            conn.execute(text('ALTER TABLE constitution ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'))
            print("✅ Added column created_at to Constitution")
        except Exception as e:
            print("constitution.final_vote_deadline exists:", e)
        try:
            conn.execute(text('ALTER TABLE bill ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'))
        except Exception as e:
            print("bill.created_at exists or error:", e)

            # Create Report table if not exists
        try:
            conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS report (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category VARCHAR(50) NOT NULL,
                            description TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by_id INTEGER,
                            FOREIGN KEY(created_by_id) REFERENCES user (id)
                        )
                    """))
        except Exception as e:
            print("report table exists or error:", e)
        try:
            conn.execute(text("""
                        CREATE TABLE state_budget (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            total_amount FLOAT DEFAULT 0.0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
            conn.execute(text("INSERT INTO state_budget (total_amount) VALUES (1000000)"))  # seed 1M kr
            print("✅ state_budget table created")
        except Exception as e:
            print("ℹ️ state_budget already exists:", e)

            # --- BudgetTransaction table ---
        try:
            conn.execute(text("""
                        CREATE TABLE budget_transaction (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category VARCHAR(100) NOT NULL,
                            amount FLOAT NOT NULL,
                            description TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by_id INTEGER,
                            FOREIGN KEY(created_by_id) REFERENCES user(id)
                        )
                    """))
            print("✅ budget_transaction table created")
        except Exception as e:
            print("ℹ️ budget_transaction already exists:", e)

    return "✅ Migration complete for Bill and Constitution tables"

@app.route("/migrate_user_to_users", methods=["GET"])
def migrate_user_to_users():
    with db.engine.begin() as conn:
        # Drop empty table
        conn.execute(text('DROP TABLE IF EXISTS "users";'))
        # Rename old table
        conn.execute(text('ALTER TABLE "user" RENAME TO "users";'))

    return "Migration complete ✅"

@app.route('/admin/end_weekly_vote', methods=['POST', 'GET'])
@login_required
def end_weekly_vote():
    if g.user.username != ADMIN_USERNAME:
        flash("Admins only!", "danger")
        return redirect(url_for('riksdag'))

    results = calculate_riksdag_seats()

    # Clear all votes for next week
    Vote.query.delete()
    db.session.commit()

    flash("Weekly Riksdag vote ended early. Results have been calculated!", "info")
    return render_template("riksdag.html", results=results)
@app.route('/admin/end_const_vote/<int:const_id>/<phase>', methods=['POST', 'GET'])
@login_required
def end_const_vote(const_id, phase):
    if g.user.username != ADMIN_USERNAME:
        flash("Admins only!", "danger")
        return redirect(url_for('constitution_list'))

    const = Constitution.query.get_or_404(const_id)

    if phase == "first" and not const.first_vote_passed:
        vote_constitution_first(const.id, {})  # empty dict counts all as NO? Or just tally current votes
        flash(f"First vote on '{const.title}' ended early.", "info")

    elif phase == "final" and const.first_vote_passed and not const.final_vote_passed:
        vote_constitution_final(const.id, {})  # tally current votes
        flash(f"Final vote on '{const.title}' ended early.", "info")

    else:
        flash("Cannot end vote: either phase already completed or invalid.", "warning")

    return redirect(url_for('constitution_detail', const_id=const.id))

@app.route('/government/form_self', methods=['POST'])
@login_required
def form_government_self():
    party = Party.query.filter_by(founder_id=g.user.id).first()
    if not party:
        flash("Only party founders can form a government!", "danger")
        return redirect(url_for('riksdag'))

    results = calculate_riksdag_seats()
    party_seats = next((p["seats"] for p in results if p["id"] == party.id), 0)
    total_seats = sum(p["seats"] for p in results)
    majority = (total_seats // 2) + 1

    if party_seats >= majority:
        # Mark this party as in government
        party.is_in_government = True
        db.session.commit()
        flash(f"{party.name} now forms a government alone ✅", "success")
    else:
        flash("You do not have a majority. Coalition required.", "warning")

    return redirect(url_for('riksdag'))


@app.route('/admin/delete_bill/<int:bill_id>', methods=['POST'])
@login_required
def admin_delete_bill(bill_id):
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    bill = Bill.query.get_or_404(bill_id)

    # Delete associated votes first to avoid foreign key issues
    BillVote.query.filter_by(bill_id=bill.id).delete()

    db.session.delete(bill)
    db.session.commit()

    flash(f"Bill '{bill.title}' has been deleted.", "info")
    return redirect(url_for('bills_list'))


@app.route('/admin/force_government/<int:party_id>', methods=['POST'])
@login_required
def admin_force_government(party_id):
    if g.user.username != ADMIN_USERNAME:
        flash("Admins only!", "danger")
        return redirect(url_for('riksdag'))

    party = Party.query.get_or_404(party_id)
    party.is_in_government = True
    db.session.commit()

    flash(f"Admin has forced {party.name} to form government ✅", "success")
    return redirect(url_for('riksdag'))

@app.route('/admin/delete_const/<int:constitution_id>', methods=['POST'])
@login_required
def admin_delete_const(constitution_id):
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    constitution = Constitution.query.get_or_404(constitution_id)
    db.session.delete(constitution)
    db.session.commit()
    flash(f"Constitution '{constitution.title}' has been deleted.", "info")
    return redirect(url_for('constitution_list'))


@app.route("/admin/pass_constitution/<int:constitution_id>", methods=["POST"])
@login_required
def admin_pass_const(constitution_id):
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    const = Constitution.query.get_or_404(constitution_id)
    const.first_vote_passed = True
    const.final_vote_deadline = datetime.utcnow() + timedelta(hours=24)
    db.session.commit()

    flash("Constitution has been force-passed by admin!", "info")
    return redirect(url_for("constitution_detail", constitution_id=const.id))

import subprocess
import tempfile
from flask import send_file

@app.route("/admin/download-db")
@login_required
def admin_download_db():
    if g.user.username != ADMIN_USERNAME:
        flash("You are not authorized to download the database.", "danger")
        return redirect(url_for("index"))

    db_path = os.path.join(os.getcwd(), "app.db")  # adjust if using SQLite
    return send_file(db_path, as_attachment=True, download_name="database.sqlite")

@app.route("/admin/add/<username>", methods=["POST", "GET"])
@login_required
def admin_add_money(username):
    if g.user.username != ADMIN_USERNAME:
        abort(403)

    user = User.query.filter_by(username=username).first_or_404()

    if request.method == "POST":
        try:
            amount = int(request.form.get("amount", 0))
        except ValueError:
            flash("Invalid amount.", "danger")
            return redirect(url_for("admin_add_money", username=username))

        if amount <= 0:
            flash("Amount must be greater than 0.", "danger")
            return redirect(url_for("admin_add_money", username=username))

        # Add money to user
        user.coins = (user.coins or 0) + amount
        db.session.commit()

        flash(f"✅ Added {amount} coins to {user.username}.", "success")
        return redirect(url_for("dashboard"))

    return render_template("admin_add_money.html", user=user)

@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    if request.method == "POST":
        category = request.form.get("category")
        description = request.form.get("description")

        if not category or not description:
            flash("❌ All fields are required.", "danger")
        else:
            new_report = Report(
                category=category,
                description=description,
                user_id=g.user.id
            )
            db.session.add(new_report)
            db.session.commit()
            flash("✅ Your report has been submitted.", "success")
            return redirect(url_for("report"))

    return render_template("report.html")

@app.route("/admin/reports")
@login_required
def admin_reports():
    # Only allow specific users
    if g.user.username not in ["YOUR_ADMIN_USERNAME", ""]:
        abort(403)

    reports = Report.query.order_by(Report.created_at.desc()).all()
    return render_template("admin_reports.html", reports=reports)

@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget_dashboard():
    budget = StateBudget.query.first()
    if not budget:
        budget = StateBudget(total_amount=10000)  # default: 10000 kr
        db.session.add(budget)
        db.session.commit()

    if request.method == "POST":
        if g.user.username != "YOUR_ADMIN_USERNAME":  # only regering can spend
            flash("❌ Only the Regering can manage the budget!", "danger")
            return redirect(url_for("budget_dashboard"))

        category = request.form["category"]
        amount = float(request.form["amount"])
        description = request.form["description"]

        if budget.total_amount - int(amount) < 0:
            flash("❌ Not enough funds!", "danger")
        else:
            budget.total_amount -= amount
            tx = BudgetTransaction(
                category=category,
                amount=-amount,
                description=description,
                created_by_id=g.user.id,
            )
            db.session.add(tx)
            db.session.commit()
            flash(f"✅ Spent {amount} kr on {category}", "success")

    transactions = BudgetTransaction.query.order_by(BudgetTransaction.created_at.desc()).all()
    return render_template("budget.html", budget=budget, transactions=transactions, total=budget.total_amount)

@app.route("/admin/budget", methods=["GET", "POST"])
@login_required
def admin_budget():
    if not g.user or g.user.username not in ["YOUR_ADMIN_USERNAME", "ombudsman"]:
        abort(403)

    pay_daily_salaries()
    # Fetch state budget
    budget = StateBudget.query.first()
    if not budget:
        # Create budget row if not exists
        budget = StateBudget(total_funds=0)
        db.session.add(budget)
        db.session.commit()

    # Handle spending
    if request.method == "POST":
        category = request.form.get("category")
        amount_str = request.form.get("amount", "0").strip()
        description = request.form.get("description", "").strip()

        if not amount_str.isdigit() or int(amount_str) <= 0:
            flash("Ange ett giltigt belopp.", "danger")
            return redirect(url_for("admin_budget"))

        amount = int(amount_str)
        if amount > budget.total_funds:
            flash("Otillräckliga statliga medel.", "danger")
            return redirect(url_for("admin_budget"))

        # Deduct from budget
        budget.total_funds -= amount

        # Special handling for salaries
        if category == "salary":
            username = request.form.get("username", "").strip()
            user = User.query.filter_by(username=username).first()
            if not user:
                flash("Användaren finns inte.", "danger")
                return redirect(url_for("admin_budget"))

            salary = Salary(
                user_id=user.id,
                amount_per_day=amount,
                active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(salary)
            flash(f"{amount} VGC per dag tilldelad {username}.", "success")
        else:
            # Create a transaction record for other categories
            transaction = Transaction(
                amount=amount,
                category=category,
                description=description,
                created_by_id=g.user.id
            )
            db.session.add(transaction)
            flash(f"{amount} VGC spenderat på {category}.", "success")

        db.session.commit()
        return redirect(url_for("admin_budget"))

    # Show all transactions
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    total = StateBudget.total_amount  # <- define total here
    return render_template("budget.html", budget=budget, transactions=transactions)

@app.route("/admin/salaries", methods=["GET", "POST"])
@login_required
def admin_salaries():
    if not g.user or g.user.username not in ["YOUR_ADMIN_USERNAME", "ombudsman"]:
        abort(403)
    pay_daily_salaries()

    # Handle cancel salary
    if request.method == "POST":
        salary_id = request.form.get("salary_id")
        salary = Salary.query.get(salary_id)
        if salary:
            salary.active = False
            db.session.commit()
            flash(f"Salary for {salary.receiver.username} has been canceled.", "success")
        return redirect(url_for("admin_salaries"))

    # Fetch all active salaries
    salaries = Salary.query.order_by(Salary.created_at.desc()).all()
    return render_template("admin_salaries.html", salaries=salaries)

def pay_daily_salaries():
    today = datetime.utcnow().date()
    salaries = Salary.query.filter_by(active=True).all()

    for s in salaries:
        # Only pay if never paid today
        if not s.last_sent or s.last_sent.date() < today:
            # Ensure the user exists
            if not s.receiver:
                continue

            # Pay the user
            s.receiver.coins += s.amount_per_day
            s.last_sent = datetime.utcnow()

            # Optional: create a transaction for logging
            transaction = Transaction(
                sender_id=None,  # Paid by state
                receiver_id=s.receiver.id,
                amount=s.amount_per_day,
                category="salary",
                description="Daily salary payout"
            )
            db.session.add(transaction)

    db.session.commit()


from sqlalchemy import inspect, text
from flask import abort
from datetime import datetime

from sqlalchemy import inspect, text

@app.route("/admin/migrate_salary")
@login_required
def migrate_salary():
    inspector = inspect(db.engine)
    if "salary" not in inspector.get_table_names():
        with db.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE salary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount_per_day INTEGER NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    last_sent DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
            """))
        return "✅ Salary table created!"
    return "Salary table already exists."

@app.route("/admin/migrate_salary")
@login_required
def migrate_salary():
    if g.user.username != "YOUR_ADMIN_USERNAME":
        abort(403)

    inspector = inspect(db.engine)
    if "salary" not in inspector.get_table_names():
        with db.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE salary (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES "user"(id),
                    amount_per_day INTEGER NOT NULL,
                    active BOOLEAN DEFAULT TRUE,
                    last_sent TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        return "✅ Salary table created!"
    return "Salary table already exists."


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
