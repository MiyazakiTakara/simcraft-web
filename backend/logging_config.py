import logging
import sys
import structlog
import os


def setup_logging(log_level: str = "INFO"):
    def add_db_log(level: str, message: str, context: str = None):
        try:
            from database import add_log
            add_log(level, message, context)
        except Exception:
            pass
    
    class DBBridge:
        def __init__(self, logger, method_name):
            self._logger = logger
            self._method_name = method_name

        def __getattr__(self, name):
            return getattr(self._logger, name)

        def info(self, message, **kwargs):
            self._logger.info(message, **kwargs)
            context = str(kwargs) if kwargs else None
            add_db_log("INFO", message, context)

        def warning(self, message, **kwargs):
            self._logger.warning(message, **kwargs)
            context = str(kwargs) if kwargs else None
            add_db_log("WARNING", message, context)

        def error(self, message, **kwargs):
            self._logger.error(message, **kwargs)
            context = str(kwargs) if kwargs else None
            add_db_log("ERROR", message, context)

        def exception(self, message, **kwargs):
            self._logger.exception(message, **kwargs)
            context = str(kwargs) if kwargs else None
            add_db_log("ERROR", message, context)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    
    return structlog.get_logger()
