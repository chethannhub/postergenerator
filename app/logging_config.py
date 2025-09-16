import logging
import os
from logging.handlers import RotatingFileHandler


class _NoOpFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return True


def configure_logging(app_name: str = 'postergenerator', log_level: str | None = None):
    level_name = (log_level or os.getenv('LOG_LEVEL', 'INFO')).upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)

    # Avoid duplicate handlers if called twice (e.g., in debug reloads)
    if logger.handlers:
        return logger

    # Minimal, clean format: no time, no request id
    fmt = '%(levelname)s %(name)s: %(message)s'
    formatter = logging.Formatter(fmt=fmt)
    req_filter = _NoOpFilter()

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    ch.addFilter(req_filter)
    logger.addHandler(ch)

    # File handler (rotating)
    log_dir = os.getenv('LOG_DIR', 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(os.path.join(log_dir, f'{app_name}.log'), maxBytes=2_000_000, backupCount=5, encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        fh.addFilter(req_filter)
        logger.addHandler(fh)
    except Exception:
        # Fallback to console-only if file handler fails
        pass

    # Reduce noise from common third-party loggers
    for noisy in ('urllib3', 'google', 'PIL', 'werkzeug', 'httpx', 'httpcore', 'google_genai'):
        try:
            logging.getLogger(noisy).setLevel(logging.WARNING)
        except Exception:
            pass

    # Provide a simple main logger for high-level steps
    main = logging.getLogger('app.main')
    main.propagate = True
    main.setLevel(level)
    return logger
