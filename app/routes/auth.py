# app/routes/auth.py

from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.models import db, User

auth = Blueprint('auth', __name__)

RESET_TOKEN_MAX_AGE = 3600  # 1 hour
RESET_SALT = 'password-reset'


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def generate_reset_token(user):
    serializer = _get_serializer()
    # Include a hash of the current password so the token is invalidated
    # once it's used (or the password otherwise changes).
    payload = {'user_id': user.id, 'ph': user.password_hash[-16:]}
    return serializer.dumps(payload, salt=RESET_SALT)


def verify_reset_token(token):
    serializer = _get_serializer()
    try:
        payload = serializer.loads(token, salt=RESET_SALT, max_age=RESET_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, payload.get('user_id'))
    if not user or user.password_hash[-16:] != payload.get('ph'):
        return None
    return user

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('auth.register'))
        user = User(
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"New user registered: {email}")
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            current_app.logger.info(f"Login success: {email}")
            flash('Logged in successfully.', 'success')
            return redirect(url_for('main.index'))
        current_app.logger.warning(f"Login failure: {email}")
        flash('Invalid email or password.', 'error')
        return redirect(url_for('auth.login'))
    return render_template('login.html')

@auth.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(user)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            current_app.logger.info(f"Password reset requested for {email}: {reset_url}")
        else:
            current_app.logger.info(f"Password reset requested for unknown email: {email}")
        # Always show the same message so we don't reveal whether the email is registered.
        flash('If an account with that email exists, a password reset link has been logged.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = verify_reset_token(token)
    if not user:
        flash('That password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('auth.reset_password', token=token))
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        current_app.logger.info(f"Password reset completed for {user.email}")
        flash('Your password has been reset. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token)
