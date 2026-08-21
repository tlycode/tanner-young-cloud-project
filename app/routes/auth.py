# app/routes/auth.py

from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.logger import get_logger
from app.models import db, User

auth = Blueprint('auth', __name__)

log = get_logger(__name__)

RESET_TOKEN_MAX_AGE = 3600  # 1 hour
RESET_SALT = 'password-reset'

# Consecutive failed logins for one email before we escalate INFO -> NOTICE -> WARN.
FAILED_LOGIN_WARN_THRESHOLD = 3
FAILED_LOGIN_KEY = 'failed_logins'


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _record_failed_login(email):
    """Count consecutive failures per email so repeated attempts escalate.

    Session-scoped, so this reflects one browser rather than a global count —
    enough to surface a user fighting with their own password, which is the
    frustrating case we want visibility into.
    """
    failures = session.get(FAILED_LOGIN_KEY, {})
    failures[email] = failures.get(email, 0) + 1
    session[FAILED_LOGIN_KEY] = failures
    session.modified = True
    return failures[email]


def _clear_failed_logins(email):
    failures = session.get(FAILED_LOGIN_KEY, {})
    if failures.pop(email, None) is not None:
        session[FAILED_LOGIN_KEY] = failures
        session.modified = True


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
    except SignatureExpired:
        log.notice('Password reset token expired')
        return None
    except BadSignature:
        log.warn('Password reset token failed signature check')
        return None
    user = db.session.get(User, payload.get('user_id'))
    if not user:
        log.warn('Password reset token references a missing user',
                 user_id=payload.get('user_id'))
        return None
    if user.password_hash[-16:] != payload.get('ph'):
        # Expected when a link is reused after the password already changed.
        log.notice('Password reset token already used', user_id=user.id)
        return None
    return user

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if len(password) < 8:
            log.info('Registration rejected: password too short', email=email)
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            log.notice('Registration rejected: email already registered', email=email)
            flash('Email already registered.', 'error')
            return redirect(url_for('auth.register'))
        user = User(
            email=email,
            password_hash=generate_password_hash(password)
        )
        try:
            db.session.add(user)
            db.session.commit()
        except Exception:
            # A failed signup is a dead end for the user - always an ERROR.
            db.session.rollback()
            log.exception('Registration failed: could not save user', email=email)
            flash('Something went wrong creating your account. Please try again.', 'error')
            return redirect(url_for('auth.register'))
        log.info('New user registered', email=email, user_id=user.id)
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
            _clear_failed_logins(email)
            log.info('Login success', email=email, user_id=user.id)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('main.index'))

        attempts = _record_failed_login(email)
        # One slip is routine; a run of them means the user is stuck.
        reason = 'unknown_email' if user is None else 'bad_password'
        if attempts >= FAILED_LOGIN_WARN_THRESHOLD:
            log.warn('Repeated login failures', email=email,
                     attempts=attempts, reason=reason)
        else:
            log.notice('Login failure', email=email,
                       attempts=attempts, reason=reason)
        flash('Invalid email or password.', 'error')
        return redirect(url_for('auth.login'))
    return render_template('login.html')

@auth.route('/logout')
def logout():
    user_id = current_user.id if current_user.is_authenticated else None
    logout_user()
    log.info('Logout', user_id=user_id)
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
            log.info(f"Password reset requested for {email}: {reset_url}")
        else:
            # Worth surfacing: someone is trying to recover an account that
            # doesn't exist, which usually means a forgotten/mistyped email.
            log.notice('Password reset requested for unknown email', email=email)
        # Always show the same message so we don't reveal whether the email is registered.
        flash('If an account with that email exists, a password reset link has been logged.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = verify_reset_token(token)
    if not user:
        # verify_reset_token has already logged why.
        flash('That password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password')
        if len(password) < 8:
            log.info('Password reset rejected: password too short', user_id=user.id)
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('auth.reset_password', token=token))
        try:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
        except Exception:
            # User holds a valid token but can't get back in - always an ERROR.
            db.session.rollback()
            log.exception('Password reset failed: could not save new password',
                          user_id=user.id)
            flash('Something went wrong resetting your password. Please try again.', 'error')
            return redirect(url_for('auth.reset_password', token=token))
        _clear_failed_logins(user.email)
        log.info('Password reset completed', email=user.email, user_id=user.id)
        flash('Your password has been reset. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token)
