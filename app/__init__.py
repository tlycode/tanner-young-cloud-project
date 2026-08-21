# app/__init__.py

import click
from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from .logger import configure as configure_logging, get_logger
from .models import db, User

login_manager = LoginManager()
csrf = CSRFProtect()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'

    # This package is named 'app', so Flask's own app.logger is the very
    # same logger configure() sets up — framework messages land in the
    # terminal with the shared format and level.
    configure_logging(app.config.get('LOG_LEVEL'))
    log = get_logger(__name__)

    from .routes.auth import auth
    from .routes.products import products
    from .routes.main import main
    from .routes.admin import admin
    from .routes.cart import cart, get_cart_count
    from .routes.reviews import reviews
    from .routes.orders import orders

    app.register_blueprint(auth)
    app.register_blueprint(products)
    app.register_blueprint(main)
    app.register_blueprint(admin)
    app.register_blueprint(cart)
    app.register_blueprint(reviews)
    app.register_blueprint(orders)

    @app.context_processor
    def inject_cart_count():
        return {'cart_count': get_cart_count()}

    @app.errorhandler(403)
    def forbidden(e):
        log.notice('Forbidden', path=request.path, method=request.method)
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        log.info('Not found', path=request.path, method=request.method)
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        # Whatever reached here broke a user's request outright.
        log.exception('Unhandled server error', path=request.path,
                      method=request.method)
        return render_template('500.html'), 500

    @app.cli.command('create-admin')
    @click.argument('email')
    @click.password_option()
    def create_admin(email, password):
        """Bootstrap an admin user. Creates the user if they don't exist, promotes if they do."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_admin = True
                db.session.commit()
                click.echo(f'Promoted {email} to admin.')
            else:
                user = User(email=email,
                            password_hash=generate_password_hash(password),
                            is_admin=True)
                db.session.add(user)
                db.session.commit()
                click.echo(f'Created admin user {email}.')

    with app.app_context():
        db.create_all()

    log.notice('Application started', log_level=app.config.get('LOG_LEVEL'))

    return app
