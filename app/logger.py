# app/logger.py

"""Shared application logging.

Wraps the stdlib :mod:`logging` module so the rest of the app has one
consistent way to record important actions. Supports five levels:

    ERROR   (40)  something failed and needs attention
    WARN    (30)  something suspicious but recoverable
    NOTICE  (25)  a normal but significant event (orders, admin changes)
    INFO    (20)  routine activity
    DEBUG   (10)  developer detail, off by default

NOTICE isn't part of the stdlib, so it's registered here at level 25 —
the syslog convention of sitting between WARNING and INFO.
"""

import logging
import os
import sys

# --- NOTICE level registration -------------------------------------------

NOTICE = 25
logging.addLevelName(NOTICE, 'NOTICE')
# Render WARNING as WARN so every level name fits the same column width.
logging.addLevelName(logging.WARNING, 'WARN')

# Level names accepted by LOG_LEVEL, mapped to their numeric value. 'WARN' is
# spelled out here so config can use either it or the stdlib's 'WARNING'.
LEVELS = {
    'ERROR': logging.ERROR,
    'WARN': logging.WARNING,
    'WARNING': logging.WARNING,
    'NOTICE': NOTICE,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}

DEFAULT_LEVEL = 'INFO'
LOG_FORMAT = '[%(asctime)s] %(levelname)-6s %(name)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def resolve_level(level):
    """Turn a level name or number into a numeric logging level."""
    if isinstance(level, int):
        return level
    return LEVELS.get(str(level).upper(), logging.INFO)


class AppLogger:
    """A named logger with one method per supported level.

    Usage::

        from app.logger import get_logger

        log = get_logger(__name__)
        log.notice('Order placed', order_id=12, total=41.50)

    Keyword arguments are appended to the message as ``key=value`` pairs so
    log lines stay greppable in the terminal.
    """

    def __init__(self, name, level=None):
        self._logger = logging.getLogger(name)
        if level is not None:
            self._logger.setLevel(resolve_level(level))

    @property
    def name(self):
        return self._logger.name

    @property
    def stdlib_logger(self):
        """The underlying stdlib logger, for handler/level wiring."""
        return self._logger

    # --- level methods ----------------------------------------------------

    def error(self, message, exc_info=False, **context):
        """Something failed and needs attention."""
        self._log(logging.ERROR, message, exc_info, context)

    def warn(self, message, exc_info=False, **context):
        """Something suspicious but recoverable."""
        self._log(logging.WARNING, message, exc_info, context)

    # Alias so callers used to the stdlib spelling aren't surprised.
    warning = warn

    def notice(self, message, exc_info=False, **context):
        """A normal but significant event worth surfacing by default."""
        self._log(NOTICE, message, exc_info, context)

    def info(self, message, exc_info=False, **context):
        """Routine activity."""
        self._log(logging.INFO, message, exc_info, context)

    def debug(self, message, exc_info=False, **context):
        """Developer detail, off unless LOG_LEVEL=DEBUG."""
        self._log(logging.DEBUG, message, exc_info, context)

    def exception(self, message, **context):
        """Log at ERROR with the current traceback attached."""
        self._log(logging.ERROR, message, True, context)

    # --- internals --------------------------------------------------------

    def _log(self, level, message, exc_info, context):
        # Bail before formatting if the level is filtered out anyway.
        if not self._logger.isEnabledFor(level):
            return
        self._logger.log(level, self._format(message, context),
                         exc_info=exc_info, stacklevel=3)

    @staticmethod
    def _format(message, context):
        if not context:
            return str(message)
        pairs = ' '.join(f'{key}={value}' for key, value in context.items())
        return f'{message} {pairs}'


def configure(level=None, stream=None):
    """Attach a single stream handler to the root 'app' logger.

    Called once from :func:`app.create_app`. Safe to call repeatedly — the
    handler is replaced rather than stacked, so log lines never duplicate.
    """
    level = resolve_level(level or os.environ.get('LOG_LEVEL', DEFAULT_LEVEL))

    root = logging.getLogger('app')
    root.setLevel(level)
    # Propagation stays on so test harnesses (pytest's caplog) and any
    # future root handler still see these records. Nothing in this app
    # installs a root handler, so records aren't printed twice.
    root.propagate = True

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)

    return root


def get_logger(name=None):
    """Return an :class:`AppLogger` namespaced under the 'app' logger."""
    if not name or name == 'app':
        return AppLogger('app')
    # Module names already start with 'app.'; anything else gets prefixed so
    # every logger inherits the handler configure() installed.
    if not name.startswith('app.'):
        name = f'app.{name}'
    return AppLogger(name)
