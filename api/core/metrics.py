"""
Prometheus Metrics - BIG TECH 100 Standards
===========================================
Application metrics for monitoring and alerting.
"""

import time
import logging
from functools import wraps
from typing import Callable, Optional, Any
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from prometheus_client.openmetrics.exposition import (
    CONTENT_TYPE_LATEST as OPENMETRICS_CONTENT_TYPE,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Global Registry
# ═══════════════════════════════════════════════════════════════════════════════

REGISTRY = CollectorRegistry()

# ═══════════════════════════════════════════════════════════════════════════════
# Application Metrics
# ═══════════════════════════════════════════════════════════════════════════════

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0],
    registry=REGISTRY,
)

http_request_size_bytes = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000],
    registry=REGISTRY,
)

http_response_size_bytes = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000],
    registry=REGISTRY,
)

# Application info
app_info = Info(
    "app_info",
    "Application information",
    registry=REGISTRY,
)

# Active connections
active_connections = Gauge(
    "active_connections",
    "Number of active connections",
    registry=REGISTRY,
)

# Database metrics
db_connections_active = Gauge(
    "db_connections_active",
    "Active database connections",
    registry=REGISTRY,
)

db_connections_idle = Gauge(
    "db_connections_idle",
    "Idle database connections",
    registry=REGISTRY,
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=REGISTRY,
)

db_query_errors_total = Counter(
    "db_query_errors_total",
    "Total database query errors",
    ["operation", "error_type"],
    registry=REGISTRY,
)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_name"],
    registry=REGISTRY,
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_name"],
    registry=REGISTRY,
)

cache_operations_total = Counter(
    "cache_operations_total",
    "Total cache operations",
    ["operation", "cache_name"],
    registry=REGISTRY,
)

cache_operation_duration_seconds = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration in seconds",
    ["operation", "cache_name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
    registry=REGISTRY,
)

# External API metrics
external_api_requests_total = Counter(
    "external_api_requests_total",
    "Total external API requests",
    ["service", "endpoint", "status"],
    registry=REGISTRY,
)

external_api_duration_seconds = Histogram(
    "external_api_duration_seconds",
    "External API request duration in seconds",
    ["service", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)

external_api_errors_total = Counter(
    "external_api_errors_total",
    "Total external API errors",
    ["service", "error_type"],
    registry=REGISTRY,
)

# Business metrics
vehicles_scraped_total = Counter(
    "vehicles_scraped_total",
    "Total vehicles scraped",
    ["source", "status"],
    registry=REGISTRY,
)

pricing_calculations_total = Counter(
    "pricing_calculations_total",
    "Total pricing calculations",
    ["method"],
    registry=REGISTRY,
)

orders_created_total = Counter(
    "orders_created_total",
    "Total orders created",
    ["status"],
    registry=REGISTRY,
)

payments_processed_total = Counter(
    "payments_processed_total",
    "Total payments processed",
    ["status", "payment_method"],
    registry=REGISTRY,
)

# Error metrics
errors_total = Counter(
    "errors_total",
    "Total errors",
    ["type", "component"],
    registry=REGISTRY,
)

exceptions_total = Counter(
    "exceptions_total",
    "Total exceptions",
    ["exception_type", "module"],
    registry=REGISTRY,
)

# Worker metrics
worker_tasks_total = Counter(
    "worker_tasks_total",
    "Total worker tasks processed",
    ["queue", "status"],
    registry=REGISTRY,
)

worker_task_duration_seconds = Histogram(
    "worker_task_duration_seconds",
    "Worker task duration in seconds",
    ["queue"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
    registry=REGISTRY,
)

queue_size = Gauge(
    "queue_size",
    "Current queue size",
    ["queue"],
    registry=REGISTRY,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Decorators
# ═══════════════════════════════════════════════════════════════════════════════

def measure_duration(
    histogram: Histogram,
    labels: Optional[dict] = None
) -> Callable:
    """
    Decorator per misurare la durata di una funzione.
    
    Usage:
        @measure_duration(http_request_duration_seconds, labels={"method": "GET"})
        async def my_endpoint():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                label_values = labels or {}
                histogram.observe(duration, **label_values)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                label_values = labels or {}
                histogram.observe(duration, **label_values)
        
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    
    return decorator


def count_calls(
    counter: Counter,
    labels: Optional[dict] = None
) -> Callable:
    """
    Decorator per contare le chiamate a una funzione.
    
    Usage:
        @count_calls(http_requests_total, labels={"method": "GET", "status": "200"})
        async def my_endpoint():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                label_values = labels or {}
                counter.inc(**label_values)
                return result
            except Exception as e:
                label_values = labels or {}
                label_values["status"] = "error"
                counter.inc(**label_values)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                label_values = labels or {}
                counter.inc(**label_values)
                return result
            except Exception as e:
                label_values = labels or {}
                label_values["status"] = "error"
                counter.inc(**label_values)
                raise
        
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    
    return decorator


def track_exceptions(
    counter: Counter = exceptions_total,
    module: Optional[str] = None
) -> Callable:
    """
    Decorator per tracciare le eccezioni.
    
    Usage:
        @track_exceptions(module="api.services")
        async def my_service():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                counter.inc(
                    exception_type=type(e).__name__,
                    module=module or func.__module__
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                counter.inc(
                    exception_type=type(e).__name__,
                    module=module or func.__module__
                )
                raise
        
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Context Managers
# ═══════════════════════════════════════════════════════════════════════════════

@contextmanager
def measure_time(
    histogram: Histogram,
    labels: Optional[dict] = None
):
    """
    Context manager per misurare il tempo di esecuzione.
    
    Usage:
        with measure_time(db_query_duration_seconds, {"operation": "SELECT"}):
            result = await db.execute(query)
    """
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        histogram.observe(duration, **(labels or {}))


@contextmanager
def track_error(
    counter: Counter,
    error_type: str,
    component: str
):
    """
    Context manager per tracciare errori.
    
    Usage:
        with track_error(errors_total, "ValidationError", "api"):
            validate_data(data)
    """
    try:
        yield
    except Exception as e:
        counter.inc(type=error_type, component=component)
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def get_metrics() -> bytes:
    """Genera output metrics in formato Prometheus."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Restituisce il content type per i metrics."""
    return CONTENT_TYPE_LATEST


def set_app_info(
    version: str,
    environment: str,
    **kwargs
):
    """Imposta informazioni applicazione."""
    app_info.info({
        "version": version,
        "environment": environment,
        **kwargs
    })


def record_cache_hit(cache_name: str = "default"):
    """Registra un cache hit."""
    cache_hits_total.inc(cache_name=cache_name)
    cache_operations_total.inc(operation="get", cache_name=cache_name)


def record_cache_miss(cache_name: str = "default"):
    """Registra un cache miss."""
    cache_misses_total.inc(cache_name=cache_name)
    cache_operations_total.inc(operation="get", cache_name=cache_name)


def record_cache_operation(
    operation: str,
    duration: float,
    cache_name: str = "default"
):
    """Registra un'operazione cache."""
    cache_operations_total.inc(operation=operation, cache_name=cache_name)
    cache_operation_duration_seconds.observe(duration, operation=operation, cache_name=cache_name)


def record_db_query(
    operation: str,
    table: str,
    duration: float,
    success: bool = True
):
    """Registra una query database."""
    db_query_duration_seconds.observe(duration, operation=operation, table=table)
    if not success:
        db_query_errors_total.inc(operation=operation, error_type="query_failed")


def record_external_api_call(
    service: str,
    endpoint: str,
    status: str,
    duration: float
):
    """Registra una chiamata API esterna."""
    external_api_requests_total.inc(service=service, endpoint=endpoint, status=status)
    external_api_duration_seconds.observe(duration, service=service, endpoint=endpoint)


def record_vehicle_scraped(source: str, success: bool = True):
    """Registra uno scraping di veicolo."""
    status = "success" if success else "failed"
    vehicles_scraped_total.inc(source=source, status=status)


def record_pricing_calculation(method: str = "standard"):
    """Registra un calcolo di pricing."""
    pricing_calculations_total.inc(method=method)


def record_order_created(status: str = "pending"):
    """Registra la creazione di un ordine."""
    orders_created_total.inc(status=status)


def record_payment_processed(status: str, payment_method: str = "card"):
    """Registra un pagamento processato."""
    payments_processed_total.inc(status=status, payment_method=payment_method)


def record_error(error_type: str, component: str):
    """Registra un errore."""
    errors_total.inc(type=error_type, component=component)


def record_worker_task(queue: str, duration: float, success: bool = True):
    """Registra un task worker."""
    status = "success" if success else "failed"
    worker_tasks_total.inc(queue=queue, status=status)
    worker_task_duration_seconds.observe(duration, queue=queue)


def update_queue_size(queue: str, size: int):
    """Aggiorna la dimensione della coda."""
    queue_size.set(size, queue=queue)


def update_active_connections(count: int):
    """Aggiorna il numero di connessioni attive."""
    active_connections.set(count)


def update_db_connections(active: int, idle: int):
    """Aggiorna le metriche delle connessioni database."""
    db_connections_active.set(active)
    db_connections_idle.set(idle)


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI Integration
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware per raccogliere automaticamente metriche HTTP.
    """
    
    def __init__(self, app: ASGIApp, app_name: str = "auto-broker"):
        super().__init__(app)
        self.app_name = app_name
    
    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        
        # Skip metrics endpoint
        if path == "/metrics":
            return await call_next(request)
        
        # Record request size
        content_length = request.headers.get("content-length", 0)
        if content_length:
            http_request_size_bytes.observe(int(content_length), method=method, endpoint=path)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            
            # Record metrics
            http_requests_total.inc(method=method, endpoint=path, status=status_code)
            http_request_duration_seconds.observe(time.time() - start_time, method=method, endpoint=path)
            
            # Record response size
            response_length = response.headers.get("content-length", 0)
            if response_length:
                http_response_size_bytes.observe(int(response_length), method=method, endpoint=path)
            
            return response
            
        except Exception as e:
            http_requests_total.inc(method=method, endpoint=path, status="500")
            http_request_duration_seconds.observe(time.time() - start_time, method=method, endpoint=path)
            exceptions_total.inc(exception_type=type(e).__name__, module="api")
            raise


def setup_metrics(app: Any, app_name: str = "auto-broker", app_version: str = "1.0.0"):
    """
    Configura le metriche per l'applicazione FastAPI.
    
    Usage:
        from fastapi import FastAPI
        from api.core.metrics import setup_metrics
        
        app = FastAPI()
        setup_metrics(app, app_name="auto-broker", app_version="1.0.0")
    """
    from fastapi import Response
    
    # Setup app info
    set_app_info(version=app_version, environment="production")
    
    # Add middleware
    app.add_middleware(PrometheusMiddleware, app_name=app_name)
    
    # Add metrics endpoint
    @app.get("/metrics", tags=["monitoring"])
    async def metrics():
        return Response(
            content=get_metrics(),
            media_type=get_metrics_content_type()
        )
    
    logger.info(f"Metrics initialized for {app_name} v{app_version}")


# Esporta tutto
__all__ = [
    # Registry
    "REGISTRY",
    "get_metrics",
    "get_metrics_content_type",
    
    # Decorators
    "measure_duration",
    "count_calls",
    "track_exceptions",
    
    # Context managers
    "measure_time",
    "track_error",
    
    # Helper functions
    "set_app_info",
    "record_cache_hit",
    "record_cache_miss",
    "record_cache_operation",
    "record_db_query",
    "record_external_api_call",
    "record_vehicle_scraped",
    "record_pricing_calculation",
    "record_order_created",
    "record_payment_processed",
    "record_error",
    "record_worker_task",
    "update_queue_size",
    "update_active_connections",
    "update_db_connections",
    
    # FastAPI integration
    "PrometheusMiddleware",
    "setup_metrics",
    
    # Metrics objects
    "http_requests_total",
    "http_request_duration_seconds",
    "db_query_duration_seconds",
    "cache_hits_total",
    "cache_misses_total",
]
