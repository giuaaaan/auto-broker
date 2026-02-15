"""
Optimized Database Connection Pooling - BIG TECH 100 Standards
==============================================================
Connection pooling, query optimization, and async session management.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    AsyncEngine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text, event
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Configurazione database ottimizzata."""
    
    # Connection settings
    database_url: str
    echo: bool = False
    
    # Pool settings (ottimizzati per produzione)
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800  # 30 minuti
    pool_pre_ping: bool = True
    
    # Connection settings
    connect_timeout: int = 10
    command_timeout: int = 60
    
    # Query settings
    statement_timeout: int = 30000  # 30 secondi
    
    # SSL settings
    ssl_mode: str = "prefer"
    
    @property
    def engine_options(self) -> dict:
        """Opzioni per create_async_engine."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "echo": self.echo,
            "connect_args": {
                "timeout": self.connect_timeout,
                "command_timeout": self.command_timeout,
                "sslmode": self.ssl_mode,
            }
        }


class ConnectionPoolMetrics:
    """Metriche per il connection pool."""
    
    def __init__(self):
        self.connections_checked_out = 0
        self.connections_checked_in = 0
        self.connections_created = 0
        self.connections_closed = 0
        self.pool_hits = 0
        self.pool_misses = 0
        self.query_count = 0
        self.query_errors = 0
        self.slow_queries = 0
        
        # Timestamps
        self.last_reset = datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "connections": {
                "checked_out": self.connections_checked_out,
                "checked_in": self.connections_checked_in,
                "created": self.connections_created,
                "closed": self.connections_closed,
                "active": self.connections_checked_out - self.connections_checked_in,
            },
            "pool": {
                "hits": self.pool_hits,
                "misses": self.pool_misses,
                "hit_rate": self._calculate_hit_rate(),
            },
            "queries": {
                "total": self.query_count,
                "errors": self.query_errors,
                "slow": self.slow_queries,
                "error_rate": self._calculate_error_rate(),
            },
            "last_reset": self.last_reset.isoformat(),
        }
    
    def _calculate_hit_rate(self) -> float:
        total = self.pool_hits + self.pool_misses
        if total == 0:
            return 0.0
        return round(self.pool_hits / total * 100, 2)
    
    def _calculate_error_rate(self) -> float:
        if self.query_count == 0:
            return 0.0
        return round(self.query_errors / self.query_count * 100, 2)
    
    def reset(self):
        """Resetta le metriche."""
        self.__init__()


class OptimizedDatabaseManager:
    """
    Manager database ottimizzato con connection pooling.
    Supporta circuit breaker e retry logic.
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self.metrics = ConnectionPoolMetrics()
        
        # Circuit breaker
        self._failures = 0
        self._circuit_open = False
        self._last_failure: Optional[datetime] = None
        self._failure_threshold = 5
        self._recovery_timeout = 30
    
    async def initialize(self):
        """Inizializza il connection pool."""
        try:
            self.engine = create_async_engine(
                self.config.database_url,
                **self.config.engine_options
            )
            
            # Configura session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            # Setup event listeners per metriche
            self._setup_event_listeners()
            
            # Test connessione
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info(
                f"Database initialized - Pool size: {self.config.pool_size}, "
                f"Max overflow: {self.config.max_overflow}"
            )
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def _setup_event_listeners(self):
        """Setup event listeners per tracciare metriche."""
        
        @event.listens_for(self.engine.sync_engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            self.metrics.connections_checked_out += 1
        
        @event.listens_for(self.engine.sync_engine, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            self.metrics.connections_checked_in += 1
        
        @event.listens_for(self.engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            self.metrics.connections_created += 1
        
        @event.listens_for(self.engine.sync_engine, "close")
        def on_close(dbapi_conn, connection_record):
            self.metrics.connections_closed += 1
    
    def _is_circuit_open(self) -> bool:
        """Controlla se il circuit breaker è aperto."""
        if not self._circuit_open:
            return False
        
        if self._last_failure:
            elapsed = (datetime.utcnow() - self._last_failure).total_seconds()
            if elapsed > self._recovery_timeout:
                self._circuit_open = False
                self._failures = 0
                logger.info("Database circuit breaker CLOSED (recovered)")
                return False
        
        return True
    
    async def _record_failure(self):
        """Registra un fallimento."""
        self._failures += 1
        self._last_failure = datetime.utcnow()
        
        if self._failures >= self._failure_threshold:
            self._circuit_open = True
            logger.error("Database circuit breaker OPENED")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager per sessioni database.
        Gestisce automaticamente commit/rollback.
        """
        if self._is_circuit_open():
            raise Exception("Database circuit breaker is open")
        
        if not self.session_factory:
            raise Exception("Database not initialized")
        
        session = self.session_factory()
        start_time = datetime.utcnow()
        
        try:
            yield session
            await session.commit()
            self.metrics.query_count += 1
            
        except Exception as e:
            await session.rollback()
            self.metrics.query_errors += 1
            await self._record_failure()
            logger.error(f"Database error: {e}")
            raise
        
        finally:
            await session.close()
            
            # Traccia query lente
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > 1.0:  # Query lenta > 1 secondo
                self.metrics.slow_queries += 1
                logger.warning(f"Slow query detected: {elapsed:.2f}s")
    
    @asynccontextmanager
    async def read_only_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Sessione in sola lettura per query."""
        async with self.session() as session:
            # Imposta transaction read-only
            await session.execute(text("SET TRANSACTION READ ONLY"))
            yield session
    
    async def execute_with_retry(
        self,
        query: Callable,
        max_retries: int = 3,
        retry_delay: float = 0.1
    ) -> Any:
        """Esegue una query con retry automatico."""
        for attempt in range(max_retries):
            try:
                async with self.session() as session:
                    return await query(session)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                logger.warning(f"Query failed (attempt {attempt + 1}), retrying: {e}")
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
    
    async def health_check(self) -> dict:
        """Controlla lo stato del database."""
        if not self.engine:
            return {"status": "not_initialized", "healthy": False}
        
        try:
            start = datetime.utcnow()
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.fetchone()
            
            latency = (datetime.utcnow() - start).total_seconds()
            
            # Ottieni info pool
            pool_info = self._get_pool_info()
            
            return {
                "status": "connected",
                "healthy": True,
                "latency_ms": round(latency * 1000, 2),
                "circuit_open": self._circuit_open,
                "pool": pool_info,
            }
            
        except Exception as e:
            return {
                "status": "error",
                "healthy": False,
                "error": str(e),
                "circuit_open": self._circuit_open,
            }
    
    def _get_pool_info(self) -> dict:
        """Restituisce informazioni sul pool di connessioni."""
        if not self.engine:
            return {}
        
        pool = self.engine.pool
        return {
            "size": pool.size() if hasattr(pool, 'size') else 0,
            "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else 0,
            "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 0,
            "overflow": pool.overflow() if hasattr(pool, 'overflow') else 0,
        }
    
    async def get_metrics(self) -> dict:
        """Restituisce metriche dettagliate."""
        return {
            "metrics": self.metrics.to_dict(),
            "pool": self._get_pool_info(),
            "circuit": {
                "open": self._circuit_open,
                "failures": self._failures,
            }
        }
    
    async def close(self):
        """Chiude tutte le connessioni."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    async def reset_pool(self):
        """Resetta il connection pool."""
        if self.engine:
            await self.engine.dispose()
            await self.initialize()
            self.metrics.reset()
            logger.info("Database pool reset")


class QueryOptimizer:
    """Utility per ottimizzazione query."""
    
    @staticmethod
    def optimize_query(query: str) -> str:
        """Applica ottimizzazioni di base alla query."""
        # Rimuovi spazi extra
        query = " ".join(query.split())
        
        # Aggiungi LIMIT se mancante per SELECT
        if query.strip().upper().startswith("SELECT") and "LIMIT" not in query.upper():
            # Non modificare query con aggregate
            if "COUNT(" not in query.upper():
                logger.debug("Consider adding LIMIT to SELECT query")
        
        return query
    
    @staticmethod
    def add_query_hints(query: str, hints: list) -> str:
        """Aggiunge hint di ottimizzazione alla query."""
        if hints:
            hint_str = "/*+ " + " ".join(hints) + " */"
            return f"{hint_str} {query}"
        return query
    
    @staticmethod
    def build_pagination_query(
        base_query: str,
        page: int = 1,
        page_size: int = 20,
        max_page_size: int = 100
    ) -> str:
        """Aggiunge paginazione sicura alla query."""
        page_size = min(page_size, max_page_size)
        offset = (page - 1) * page_size
        
        return f"{base_query} LIMIT {page_size} OFFSET {offset}"


# Global database manager
_db_manager: Optional[OptimizedDatabaseManager] = None


async def init_database(config: DatabaseConfig) -> OptimizedDatabaseManager:
    """Inizializza il database manager globale."""
    global _db_manager
    _db_manager = OptimizedDatabaseManager(config)
    await _db_manager.initialize()
    return _db_manager


def get_database_manager() -> Optional[OptimizedDatabaseManager]:
    """Restituisce il database manager globale."""
    return _db_manager


async def close_database():
    """Chiude il database manager globale."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None


# Esporta tutto
__all__ = [
    "DatabaseConfig",
    "OptimizedDatabaseManager",
    "ConnectionPoolMetrics",
    "QueryOptimizer",
    "init_database",
    "get_database_manager",
    "close_database",
]
