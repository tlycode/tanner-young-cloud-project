# tests/test_logger.py

import io
import logging

import pytest

from app.logger import NOTICE, AppLogger, configure, get_logger, resolve_level


@pytest.fixture
def stream():
    """Configure the shared logger to write into a buffer we can read back."""
    buffer = io.StringIO()
    configure('DEBUG', stream=buffer)
    yield buffer
    configure('INFO')


def test_notice_level_is_registered_between_warning_and_info():
    assert logging.WARNING > NOTICE > logging.INFO
    assert logging.getLevelName(NOTICE) == 'NOTICE'


@pytest.mark.parametrize('method,label', [
    ('error', 'ERROR'),
    ('warn', 'WARN'),
    ('notice', 'NOTICE'),
    ('info', 'INFO'),
    ('debug', 'DEBUG'),
])
def test_each_level_writes_its_label(stream, method, label):
    log = get_logger('test')
    getattr(log, method)('a message')
    output = stream.getvalue()
    assert label in output
    assert 'a message' in output


def test_warning_is_an_alias_for_warn(stream):
    get_logger('test').warning('via alias')
    assert 'WARN' in stream.getvalue()


def test_context_is_appended_as_key_value_pairs(stream):
    get_logger('test').notice('Order placed', order_id=42, total='41.50')
    assert 'Order placed order_id=42 total=41.50' in stream.getvalue()


def test_message_without_context_is_unchanged(stream):
    get_logger('test').info('plain message')
    assert 'plain message' in stream.getvalue()


def test_level_filtering_suppresses_lower_levels():
    buffer = io.StringIO()
    configure('WARN', stream=buffer)
    log = get_logger('test')
    log.debug('hidden debug')
    log.info('hidden info')
    log.notice('hidden notice')
    log.warn('shown warn')
    log.error('shown error')
    output = buffer.getvalue()
    assert 'hidden' not in output
    assert 'shown warn' in output
    assert 'shown error' in output
    configure('INFO')


def test_exception_includes_traceback(stream):
    log = get_logger('test')
    try:
        raise ValueError('boom')
    except ValueError:
        log.exception('Something failed', order_id=7)
    output = stream.getvalue()
    assert 'Something failed order_id=7' in output
    assert 'ValueError: boom' in output
    assert 'Traceback' in output


def test_logger_names_are_namespaced_under_app():
    assert get_logger('cart').name == 'app.cart'
    assert get_logger('app.routes.cart').name == 'app.routes.cart'
    assert get_logger('app').name == 'app'
    assert get_logger(None).name == 'app'


def test_configure_replaces_handlers_instead_of_stacking():
    configure('INFO')
    configure('INFO')
    first = io.StringIO()
    configure('INFO', stream=first)
    get_logger('test').info('only once')
    assert first.getvalue().count('only once') == 1
    configure('INFO')


def test_resolve_level_accepts_names_and_numbers():
    assert resolve_level('error') == logging.ERROR
    assert resolve_level('WARN') == logging.WARNING
    assert resolve_level('WARNING') == logging.WARNING
    assert resolve_level('NOTICE') == NOTICE
    assert resolve_level(logging.DEBUG) == logging.DEBUG
    # Unknown names fall back to INFO rather than blowing up at startup.
    assert resolve_level('nonsense') == logging.INFO


def test_app_factory_logs_startup_at_notice(caplog):
    from app import create_app
    with caplog.at_level(NOTICE):
        create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    assert any('Application started' in r.message for r in caplog.records)


def test_flask_app_logger_shares_the_shared_configuration():
    from app import create_app
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    # The package is named 'app', so existing current_app.logger calls resolve
    # to the same logger the shared class configures.
    assert app.logger is AppLogger('app').stdlib_logger
