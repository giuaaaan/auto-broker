"""
Structured Logging - BIG TECH 100 Standards
===========================================
JSON structured logging with correlation IDs and contextual information.
"""

import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Optional, Dict
from contextvars import ContextVar
import uuid

# Context variables for correlation
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
request_id: ContextVar[str] = ContextVar('request_id', default='')
user_id: ContextVar[str] = ContextVar('user_id', default='')


class StructuredLogFormatter(logging.Formatter):
    """
    Formatter per log in formato JSON strutturato.
    Compatibile con log aggregation systems (ELK, Datadog, etc).
    """
    
    def __init__(
        self,
        service_name: str = "auto-broker",
        environment: str = "production",
        include_extra_fields: bool = True
    ):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.include_extra_fields = include_extra_fields
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            # Timestamp ISO 8601
            "timestamp": datetime.utcnow().isoformat() + "Z",
            
            # Log level
            "level": record.levelname,
            
            # Message
            "message": record.getMessage(),
            
            # Logger name
            "logger": record.name,
            
            # Service info
            "service": self.service_name,
            "environment": self.environment,
            
            # Source location
            "source": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
        }
        
        # Correlation context
        corr_id = correlation_id.get()
        req_id = request_id.get()
        usr_id = user_id.get()
        
        if corr_id:
            log_data["correlation_id"] = corr_id
        if req_id:
            log_data["request_id"] = req_id
        if usr_id:
            log_data["user_id"] = usr_id
        
        # Exception info
        if record.exc_info:
            log_data["exception"] = self._format_exception(record.exc_info)
        
        # Stack trace for errors
        if record.stack_info:
            log_data["stack_trace"] = record.stack_info
        
        # Extra fields
        if self.include_extra_fields:
            extra_fields = self._extract_extra_fields(record)
            if extra_fields:
                log_data["extra"] = extra_fields
        
        return json.dumps(log_data, default=str)
    
    def _format_exception(self, exc_info) -> Dict[str, Any]:
        """Format exception information."""
        exc_type, exc_value, exc_tb = exc_info
        return {
            "type": exc_type.__name__ if exc_type else "Unknown",
            "message": str(exc_value) if exc_value else "",
            "stack_trace": traceback.format_exception(*exc_info),
        }
    
    def _extract_extra_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Extract custom fields from log record."""
        standard_fields = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
            'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
            'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
            'thread', 'threadName', 'processName', 'process', 'getMessage',
            'message', 'asctime'
        }
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_fields and not key.startswith('_'):
                extra[key] = value
        
        return extra


class ColoredConsoleFormatter(logging.Formatter):
    """
    Formatter per console con colori (utile per development).
    """
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors."""
        levelname = record.levelname
        
        if self.use_colors and levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        # Add correlation ID to message
        corr_id = correlation_id.get()
        if corr_id:
            record.msg = f"[{corr_id[:8]}] {record.msg}"
        
        return super().format(record)


class ContextFilter(logging.Filter):
    """Filter per aggiungere context alle log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to record."""
        record.correlation_id = correlation_id.get()
        record.request_id = request_id.get()
        record.user_id = user_id.get()
        return True


def setup_logging(
    level: int = logging.INFO,
    service_name: str = "auto-broker",
    environment: str = "production",
    json_format: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Log level (default: INFO)
        service_name: Name of the service
        environment: Environment name
        json_format: Use JSON format (production) or colored text (development)
        log_file: Optional file path for logging
    """
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if json_format:
        formatter = StructuredLogFormatter(
            service_name=service_name,
            environment=environment
        )
    else:
        formatter = ColoredConsoleFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ContextFilter())
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(StructuredLogFormatter(
            service_name=service_name,
            environment=environment
        ))
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info(f"Logging initialized for {service_name} in {environment}")


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """
    Set correlation ID for the current context.
    
    Returns:
        The correlation ID
    """
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return correlation_id.get()


def set_request_id(req_id: Optional[str] = None) -> str:
    """Set request ID for the current context."""
    if req_id is None:
        req_id = str(uuid.uuid4())
    request_id.set(req_id)
    return req_id


def get_request_id() -> str:
    """Get current request ID."""
    return request_id.get()


def set_user_id(usr_id: str) -> None:
    """Set user ID for the current context."""
    user_id.set(usr_id)


def get_user_id() -> str:
    """Get current user ID."""
    return user_id.get()


def clear_context() -> None:
    """Clear all context variables."""
    correlation_id.set('')
    request_id.set('')
    user_id.set('')


class LogContext:
    """
    Context manager per logging con context.
    
    Usage:
        with LogContext(correlation_id="abc123", user_id="user456"):
            logger.info("Processing request")
    """
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        self.corr_id = correlation_id
        self.req_id = request_id
        self.usr_id = user_id
        self.tokens = {}
    
    def __enter__(self):
        if self.corr_id:
            self.tokens['correlation'] = correlation_id.set(self.corr_id)
        if self.req_id:
            self.tokens['request'] = request_id.set(self.req_id)
        if self.usr_id:
            self.tokens['user'] = user_id.set(self.usr_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous values
        if 'correlation' in self.tokens:
            correlation_id.reset(self.tokens['correlation'])
        if 'request' in self.tokens:
            request_id.reset(self.tokens['request'])
        if 'user' in self.tokens:
            user_id.reset(self.tokens['user'])


# FastAPI Integration
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware per logging automatico delle richieste HTTP.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(app)
        self.logger = logger or logging.getLogger("api.access")
    
    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        req_id = set_request_id()
        
        # Try to get correlation ID from header
        corr_id = request.headers.get("X-Correlation-ID")
        set_correlation_id(corr_id or req_id)
        
        # Log request
        self.logger.info(
            f"Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else None,
            }
        )
        
        start_time = datetime.utcnow()
        
        try:
            response = await call_next(request)
            
            # Log response
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(
                f"Request completed",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            )
            
            # Add headers to response
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Correlation-ID"] = get_correlation_id()
            
            return response
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(
                f"Request failed",
                extra={
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True
            )
            raise
        
        finally:
            clear_context()


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


# Esporta tutto
__all__ = [
    # Setup
    "setup_logging",
    "get_logger",
    
    # Formatters
    "StructuredLogFormatter",
    "ColoredConsoleFormatter",
    
    # Context
    "set_correlation_id",
    "get_correlation_id",
    "set_request_id",
    "get_request_id",
    "set_user_id",
    "get_user_id",
    "clear_context",
    "LogContext",
    
    # Middleware
    "LoggingMiddleware",
    
    # Context variables
    "correlation_id",
    "request_id",
    "user_id",
]
