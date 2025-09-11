import os
import random
import shutil
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, g,
    jsonify, send_file, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {"db"}

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    coins = db.Column(db.Integer, default=500)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_transactions = db.relationship('Transaction', foreign_keys='Transaction.sender_id', backref='sender', lazy=True)
    received_transactions = db.relationship('Transaction', foreign_keys='Transaction.receiver_id', backref='receiver', lazy=True)
    messages = db.relationship('Message', backref='user', lazy=True)
    snake_scores = db.relationship('SnakeScore', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class SnakeScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)


class SnakeReward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    distributed = db.Column(db.Boolean, default=False)


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Du måste vara inloggad för att se den sidan.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id else None


# CLI command to create DB
@app.cli.command('init-db')
def init_db():
    db.create_all()
    print("Databasen är skapad!")


# --- Utility ---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Routes ---
@app.route('/')
def index():
    return redirect(url_for('dashboard') if g.user else url_for('login'))


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


# --- Snake leaderboard page ---
@app.route('/snake', methods=['GET'])
@login_required
def snake():
    today = date.today()

    today_total = (
        db.session.query(User.username, func.sum(SnakeScore.score).label('total'))
        .join(SnakeScore)
        .filter(SnakeScore.date == today)
        .group_by(User.id)
        .order_by(func.sum(SnakeScore.score).desc())
        .all()
    )

    today_highscore = (
        db.session.query(User.username, func.max(SnakeScore.score).label('highscore'))
        .join(SnakeScore)
        .filter(SnakeScore.date == today)
        .group_by(User.id)
        .order_by(func.max(SnakeScore.score).desc())
        .all()
    )

    alltime_total = (
        db.session.query(User.username, func.sum(SnakeScore.score).label('total'))
        .join(SnakeScore)
        .group_by(User.id)
        .order_by(func.sum(SnakeScore.score).desc())
        .all()
    )

    alltime_highscore = (
        db.session.query(User.username, func.max(SnakeScore.score).label('highscore'))
        .join(SnakeScore)
        .group_by(User.id)
        .order_by(func.max(SnakeScore.score).desc())
        .all()
    )

    return render_template('snake.html',
                           today_total=today_total,
                           today_highscore=today_highscore,
                           alltime_total=alltime_total,
                           alltime_highscore=alltime_highscore,
                           user=g.user)


# --- Admin-only decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Replace this with your actual admin check logic
        if not g.user or g.user.username != 'admin':
            flash('Endast administratörer har tillgång.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- Admin: simulate day ---
@app.route('/admin/simulate-day', methods=['GET', 'POST'])
@admin_required
def simulate_day():
    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        try:
            simulated_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Ogiltigt datumformat. Använd ÅÅÅÅ-MM-DD.', 'danger')
            return redirect(url_for('simulate_day'))

        # Check if rewards have already been distributed for this date
        reward_record = SnakeReward.query.filter_by(date=simulated_date).first()
        if reward_record and reward_record.distributed:
            flash(f"Belöningar för {simulated_date} har redan distribuerats.", "warning")
            return redirect(url_for('simulate_day'))

        users = User.query.all()
        if not users:
            flash("Inga användare finns för att simulera.", "danger")
            return redirect(url_for('simulate_day'))

        # Add random scores only for users who do NOT already have a score for this date
        added_scores = 0
        for user in users:
            existing_score = SnakeScore.query.filter_by(user_id=user.id, date=simulated_date).first()
            if existing_score:
                continue  # Skip if score already exists
            random_score = random.randint(10, 100)
            new_score = SnakeScore(user_id=user.id, score=random_score, date=simulated_date)
            db.session.add(new_score)
            added_scores += 1

        db.session.commit()

        # Calculate leaderboard for the simulated date
        leaderboard = (
            db.session.query(SnakeScore.user_id, func.sum(SnakeScore.score).label('total_score'))
            .filter(SnakeScore.date == simulated_date)
            .group_by(SnakeScore.user_id)
            .order_by(func.sum(SnakeScore.score).desc())
            .limit(5)
            .all()
        )

        if not leaderboard:
            flash(f"Inga poäng finns för datumet {simulated_date}.", "warning")
            return redirect(url_for('simulate_day'))

        # Distribute rewards to top 5 players
        for rank, (user_id, total_score) in enumerate(leaderboard, start=1):
            reward_amount = 150 - (rank - 1) * 20  # 1st:150, 2nd:130, ..., 5th:70
            user = User.query.get(user_id)
            if user:
                user.coins += reward_amount
                # Optional: add a message for the reward
                msg_content = f"Belöning för Snake Leaderboard på {simulated_date}: {reward_amount} coins för plats {rank}."
                msg = Message(user_id=user.id, content=msg_content)
                db.session.add(msg)

        # Mark rewards as distributed for that date
        if not reward_record:
            reward_record = SnakeReward(date=simulated_date, distributed=True)
        else:
            reward_record.distributed = True
        db.session.add(reward_record)

        db.session.commit()

        flash(f"Simulering för {simulated_date} klar. {added_scores} poäng lades till och belöningar distribuerades.", "success")
        return redirect(url_for('simulate_day'))

    return render_template('simulate_day.html')


# --- Admin: Upload database file ---
@app.route('/admin/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Ingen fil vald.', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Ingen fil vald.', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Replace current database file with uploaded one
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            if os.path.exists(db_path):
                os.remove(db_path)
            shutil.move(filepath, db_path)

            flash('Databasfil uppladdad och ersatt.', 'success')
            return redirect(url_for('upload'))
        else:
            flash('Endast .db filer är tillåtna.', 'danger')
            return redirect(request.url)
    return render_template('upload.html')


# --- Error handlers ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True)
