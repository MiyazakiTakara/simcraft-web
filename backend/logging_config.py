import logging
import sys
import structlog
import os


def setup_logging(log_level: str = "INFO"):
    from database import add_log
    
    _log = structlog.get_logger()
    
    class DBLoggingLogger:
        def info(self, message, **kwargs):
            _log.info(message, **kwargs)
            add_log("INFO", message, str(kwargs) if kwargs else None)
            
        def warning(self, message, **kwargs):
            _log.warning(message, **kwargs)
            add_log("WARNING", message, str(kwargs) if kwargs else None)
            
        def error(self, message, **kwargs):
            _log.error(message, **kwargs)
            add_log("ERROR", message, str(kwargs) if kwargs else None)
            
        def exception(self, message, **kwargs):
            _log.exception(message, **kwargs)
            add_log("ERROR", message, str(kwargs) if kwargs else None)
    
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
    
    return DBLoggingLogger()
