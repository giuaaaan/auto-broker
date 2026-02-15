"""
Security Middleware - BIG TECH 100 Standards
============================================
Security headers, input validation, and SQL injection protection.
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Awaitable, Optional
nimport hashlib
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware per aggiungere security headers alle risposte.
    Conforme a OWASP Secure Headers Project.
    """
    
    def __init__(
        self,
        app,
        csp_policy: Optional[str] = None,
        strict_transport_security: Optional[str] = None
    ):
        super().__init__(app)
        self.csp_policy = csp_policy or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.auto-broker.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        self.hsts = strict_transport_security or "max-age=31536000; includeSubDomains; preload"
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        
        # X-Frame-Options: Previene clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy
        
        # X-Content-Type-Options: Previene MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection: Aggiuntivo al CSP (legacy browser)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict-Transport-Security: HTTPS only
        response.headers["Strict-Transport-Security"] = self.hsts
        
        # Referrer-Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy: Limita funzionalità browser
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(self), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
        
        # X-Permitted-Cross-Domain-Policies
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        
        # Remove server identification
        response.headers.pop("Server", None)
        
        # Add request ID for tracking
        request_id = getattr(request.state, "request_id", "unknown")
        response.headers["X-Request-ID"] = request_id
        
        return response


class SQLInjectionProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware per protezione SQL injection.
    Analizza i parametri della richiesta per pattern sospetti.
    """
    
    # Pattern SQL injection comuni
    SQL_PATTERNS = [
        r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
        r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
        r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
        r"((\%27)|(\'))union",
        r"exec(\s|\+)+(s|x)p\w+",
        r"UNION\s+SELECT",
        r"INSERT\s+INTO",
        r"DELETE\s+FROM",
        r"DROP\s+TABLE",
        r"SELECT\s+.*\s+FROM",
        r";\s*INSERT\s",
        r";\s*UPDATE\s",
        r";\s*DELETE\s",
    ]
    
    # Parametri da controllare
    SENSITIVE_PARAMS = [
        "query", "search", "filter", "sort", "order", 
        "where", "select", "from", "table"
    ]
    
    def __init__(self, app, block_on_detect: bool = True, log_only: bool = False):
        super().__init__(app)
        self.block_on_detect = block_on_detect
        self.log_only = log_only
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SQL_PATTERNS]
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Analizza query parameters
        if self._detect_sql_injection(dict(request.query_params)):
            logger.warning(
                f"SQL Injection attempt detected from {request.client.host} "
                f"on {request.url.path}"
            )
            if self.block_on_detect and not self.log_only:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid input detected",
                        "code": "INVALID_INPUT"
                    }
                )
        
        # Analizza body per richieste POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode("utf-8", errors="ignore")
                    if self._detect_sql_injection_in_string(body_str):
                        logger.warning(
                            f"SQL Injection in body detected from {request.client.host}"
                        )
                        if self.block_on_detect and not self.log_only:
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "error": "Invalid input detected",
                                    "code": "INVALID_INPUT"
                                }
                            )
            except Exception:
                pass
        
        return await call_next(request)
    
    def _detect_sql_injection(self, params: dict) -> bool:
        """Controlla se i parametri contengono pattern SQL injection."""
        for key, value in params.items():
            # Controlla chiavi sensibili
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_PARAMS):
                if self._detect_sql_injection_in_string(str(value)):
                    return True
            
            # Controlla tutti i valori stringa lunghi
            if isinstance(value, str) and len(value) > 20:
                if self._detect_sql_injection_in_string(value):
                    return True
        
        return False
    
    def _detect_sql_injection_in_string(self, value: str) -> bool:
        """Controlla se una stringa contiene pattern SQL injection."""
        for pattern in self.patterns:
            if pattern.search(value):
                return True
        return False


class RateLimitSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware per rate limiting con protezione DDoS.
    Basato su sliding window algorithm.
    """
    
    def __init__(
        self,
        app,
        redis_client=None,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        super().__init__(app)
        self.redis = redis_client
        self.rpm = requests_per_minute
        self.burst = burst_size
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip per health checks
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        if self.redis:
            is_allowed = await self._check_rate_limit(client_ip)
            if not is_allowed:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "code": "RATE_LIMIT_EXCEEDED",
                        "retry_after": 60
                    },
                    headers={"Retry-After": "60"}
                )
        
        response = await call_next(request)
        
        # Aggiungi header rate limit
        if self.redis:
            remaining = await self._get_remaining_requests(client_ip)
            response.headers["X-RateLimit-Limit"] = str(self.rpm)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Estrae l'IP client dalla richiesta."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        """Controlla se la richiesta è entro il rate limit."""
        if not self.redis:
            return True
        
        key = f"ratelimit:{client_id}"
        now = datetime.utcnow().timestamp()
        window = 60  # 1 minuto
        
        # Rimuovi richieste vecchie
        await self.redis.zremrangebyscore(key, 0, now - window)
        
        # Conta richieste correnti
        current = await self.redis.zcard(key)
        
        if current >= self.rpm:
            return False
        
        # Aggiungi richiesta corrente
        await self.redis.zadd(key, {str(now): now})
        await self.redis.expire(key, window)
        
        return True
    
    async def _get_remaining_requests(self, client_id: str) -> int:
        """Restituisce il numero di richieste rimanenti."""
        if not self.redis:
            return self.rpm
        
        key = f"ratelimit:{client_id}"
        current = await self.redis.zcard(key)
        return self.rpm - current


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware per validazione aggiuntiva delle richieste.
    Controlla dimensione body, header richiesti, etc.
    """
    
    def __init__(
        self,
        app,
        max_body_size: int = 10 * 1024 * 1024,  # 10MB
        required_headers: Optional[list] = None
    ):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.required_headers = required_headers or []
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Controlla dimensione body
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > self.max_body_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Request body too large",
                        "code": "PAYLOAD_TOO_LARGE",
                        "max_size": self.max_body_size
                    }
                )
        
        # Controlla header richiesti
        for header in self.required_headers:
            if header not in request.headers:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Missing required header: {header}",
                        "code": "MISSING_HEADER"
                    }
                )
        
        # Controlla Content-Type per richieste con body
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not any(ct in content_type for ct in ["application/json", "multipart/form-data"]):
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": "Unsupported media type",
                        "code": "UNSUPPORTED_MEDIA_TYPE"
                    }
                )
        
        return await call_next(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware per audit logging delle richieste.
    Logga tutte le richieste con informazioni di sicurezza.
    """
    
    def __init__(
        self,
        app,
        sensitive_fields: Optional[list] = None
    ):
        super().__init__(app)
        self.sensitive_fields = sensitive_fields or [
            "password", "token", "api_key", "secret", "authorization",
            "credit_card", "cvv", "ssn", "tax_id"
        ]
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = datetime.utcnow()
        
        # Genera request ID
        request_id = hashlib.sha256(
            f"{request.client.host}{start_time.isoformat()}".encode()
        ).hexdigest()[:16]
        request.state.request_id = request_id
        
        # Log request
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        response = await call_next(request)
        
        # Log response
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Response {request_id}: {response.status_code} "
            f"duration={duration:.3f}s"
        )
        
        return response
    
    def _sanitize_params(self, params: dict) -> dict:
        """Rimuove campi sensibili dai parametri."""
        sanitized = {}
        for key, value in params.items():
            if any(field in key.lower() for field in self.sensitive_fields):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized


def setup_security_middleware(app, redis_client=None):
    """
    Configura tutti i middleware di sicurezza.
    
    Usage:
        from fastapi import FastAPI
        from api.middleware.security import setup_security_middleware
        
        app = FastAPI()
        setup_security_middleware(app, redis_client=redis)
    """
    # Audit logging (primo - registra tutto)
    app.add_middleware(AuditLogMiddleware)
    
    # Rate limiting (secondo - blocca early)
    if redis_client:
        app.add_middleware(
            RateLimitSecurityMiddleware,
            redis_client=redis_client
        )
    
    # SQL Injection protection
    app.add_middleware(SQLInjectionProtectionMiddleware)
    
    # Request validation
    app.add_middleware(RequestValidationMiddleware)
    
    # Security headers (ultimo - modifica risposta)
    app.add_middleware(SecurityHeadersMiddleware)
    
    logger.info("Security middleware configured")
