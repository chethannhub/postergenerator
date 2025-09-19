import logging
import os
from logging.handlers import RotatingFileHandler

class _NoOpFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return True

def configure_logging(app_name: str = 'postergenerator', log_level: str | None = None):
    # Ensure OpenAI SDK verbose logging isn't enabled via env var
    os.environ['OPENAI_LOG'] = 'error'

    level_name = (log_level or os.getenv('LOG_LEVEL', 'INFO')).upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = '%(levelname)s %(name)s: %(message)s'
    formatter = logging.Formatter(fmt=fmt)
    req_filter = _NoOpFilter()

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    ch.addFilter(req_filter)
    logger.addHandler(ch)

    log_dir = os.getenv('LOG_DIR', 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(log_dir, f'{app_name}.log'),
            maxBytes=2_000_000, backupCount=5, encoding='utf-8'
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        fh.addFilter(req_filter)
        logger.addHandler(fh)
    except Exception:
        pass

    # Reduce noise from common third-party loggers
    for noisy in (
        'urllib3', 'google', 'PIL', 'werkzeug',
        'httpx', 'httpcore',
        # Add OpenAI SDK logger names:
        'openai', 'openai._base_client', 'openai._response'
    ):
        try:
            l = logging.getLogger(noisy)
            l.setLevel(logging.WARNING)
            # Optional: stop propagation if root is DEBUG/INFO and you want hard silencing
            # l.propagate = False
        except Exception:
            pass

    main = logging.getLogger('app.main')
    main.propagate = True
    main.setLevel(level)
    return logger
