 # app.py
import os
from datetime import datetime, date
from functools import wraps
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func

# Flask app
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
        selected_date=selected_date,  # <-- Pass date to template
        ADMIN_USERNAME=ADMIN_USERNAME
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
    return render_template('stats.html')


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

    # relations
    seller = db.relationship("User", foreign_keys=[seller_id], backref="items_sold")
    buyer = db.relationship("User", foreign_keys=[buyer_id], backref="items_bought")


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

@app.route("/download-db-secret")
def download_db():
    return send_file("database.db", as_attachment=True)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# --- Admin Routes (temporary for Render) ---
ADMIN_USERNAME = "YOUR_ADMIN_USERNAME"  # change this

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

@app.route('/marketplace/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    item = MarketplaceItem.query.get_or_404(item_id)

    if item.seller_id != g.user.id:
        flash('Du kan bara ta bort dina egna objekt.', 'danger')
        return redirect(url_for('marketplace'))

    if item.buyer_id is not None:
        flash('Du kan inte ta bort ett objekt som redan är sålt.', 'warning')
        return redirect(url_for('marketplace'))

    # Ta bort från DB
    db.session.delete(item)
    db.session.commit()
    flash(f'Objektet "{item.title}" har tagits bort.', 'success')
    return redirect(url_for('marketplace'))

from datetime import timedelta

from flask import abort, g
from datetime import date, timedelta
import random
from sqlalchemy import func

from flask import abort, g
from datetime import date, timedelta
from sqlalchemy import func

@app.route('/admin/close-day', methods=['POST'])
@login_required
def close_day():
    if g.user.username != ADMIN_USERNAME:
        abort(403)

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






# --- Run app ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=True)
