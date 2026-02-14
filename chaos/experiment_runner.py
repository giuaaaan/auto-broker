"""
AUTO-BROKER Chaos Engineering Experiment Runner
System resilience testing
Enterprise Integration - P1

Features:
- Automated chaos experiments
- Failure injection (latency, errors, resource exhaustion)
- Hypothesis validation
- Rollback capabilities
"""

import logging
import asyncio
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Coroutine
from enum import Enum
from abc import ABC, abstractmethod

import httpx
import asyncpg

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class FailureType(Enum):
    """Types of failures that can be injected."""
    LATENCY = "latency"
    ERROR = "error"
    TIMEOUT = "timeout"
    PACKET_LOSS = "packet_loss"
    CPU_LOAD = "cpu_load"
    MEMORY_PRESSURE = "memory_pressure"
    DISK_IO = "disk_io"
    NETWORK_PARTITION = "network_partition"
    SERVICE_KILL = "service_kill"


@dataclass
class ExperimentConfig:
    """Configuration for a chaos experiment."""
    name: str
    description: str
    target_service: str
    failure_type: FailureType
    failure_params: Dict[str, Any]
    duration_seconds: int
    ramp_up_seconds: int = 30
    cooldown_seconds: int = 30
    abort_condition_failures: int = 10
    abort_condition_latency_ms: int = 5000
    rollback_on_failure: bool = True
    auto_rollback: bool = True


@dataclass
class ExperimentResult:
    """Result of a chaos experiment."""
    experiment_id: str
    config: ExperimentConfig
    status: ExperimentStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_requests: int
    failed_requests: int
    avg_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    hypothesis_validated: bool
    observations: List[Dict[str, Any]]
    errors: List[str]


class FailureInjector(ABC):
    """Abstract base class for failure injectors."""
    
    @abstractmethod
    async def inject(self, params: Dict[str, Any]) -> bool:
        """Inject the failure."""
        pass
    
    @abstractmethod
    async def rollback(self) -> bool:
        """Rollback the failure."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get injector name."""
        pass


class LatencyInjector(FailureInjector):
    """Inject latency into service calls."""
    
    def __init__(self):
        self.active = False
        self.latency_ms = 0
        self.jitter_pct = 0
    
    def get_name(self) -> str:
        return "latency"
    
    async def inject(self, params: Dict[str, Any]) -> bool:
        self.latency_ms = params.get('latency_ms', 1000)
        self.jitter_pct = params.get('jitter_pct', 10)
        self.active = True
        logger.info(f"Injecting latency: {self.latency_ms}ms ±{self.jitter_pct}%")
        return True
    
    async def rollback(self) -> bool:
        self.active = False
        self.latency_ms = 0
        logger.info("Rolled back latency injection")
        return True
    
    async def apply_latency(self):
        """Apply configured latency."""
        if not self.active:
            return
        
        jitter = random.uniform(
            -self.latency_ms * self.jitter_pct / 100,
            self.latency_ms * self.jitter_pct / 100
        )
        await asyncio.sleep((self.latency_ms + jitter) / 1000)


class ErrorInjector(FailureInjector):
    """Inject HTTP errors."""
    
    def __init__(self):
        self.active = False
        self.error_rate = 0
        self.error_codes = [500, 503, 504]
    
    def get_name(self) -> str:
        return "error"
    
    async def inject(self, params: Dict[str, Any]) -> bool:
        self.error_rate = params.get('error_rate', 0.1)
        self.error_codes = params.get('error_codes', [500, 503, 504])
        self.active = True
        logger.info(f"Injecting errors: {self.error_rate*100}% rate")
        return True
    
    async def rollback(self) -> bool:
        self.active = False
        logger.info("Rolled back error injection")
        return True
    
    def should_error(self) -> bool:
        """Check if current request should error."""
        return self.active and random.random() < self.error_rate
    
    def get_error_code(self) -> int:
        """Get random error code."""
        return random.choice(self.error_codes)


class DatabaseLatencyInjector(FailureInjector):
    """Inject latency into database queries."""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.active = False
        self.latency_ms = 0
    
    def get_name(self) -> str:
        return "database_latency"
    
    async def inject(self, params: Dict[str, Any]) -> bool:
        self.latency_ms = params.get('latency_ms', 500)
        self.active = True
        
        # Install pg_sleep wrapper via advisory lock
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE OR REPLACE FUNCTION chaos_sleep()
                RETURNS void AS $$
                BEGIN
                    PERFORM pg_sleep($1 / 1000.0);
                END;
                $$ LANGUAGE plpgsql;
            """, self.latency_ms / 1000.0)
        
        logger.info(f"Injecting DB latency: {self.latency_ms}ms")
        return True
    
    async def rollback(self) -> bool:
        self.active = False
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("DROP FUNCTION IF EXISTS chaos_sleep()")
        
        logger.info("Rolled back DB latency")
        return True


class NetworkPartitionInjector(FailureInjector):
    """Simulate network partition (via iptables)."""
    
    def __init__(self):
        self.active = False
        self.target_hosts: List[str] = []
    
    def get_name(self) -> str:
        return "network_partition"
    
    async def inject(self, params: Dict[str, Any]) -> bool:
        self.target_hosts = params.get('target_hosts', [])
        duration = params.get('duration_seconds', 60)
        
        # This would require elevated privileges in production
        # Using iptables to drop packets
        import subprocess
        
        for host in self.target_hosts:
            try:
                subprocess.run([
                    'iptables', '-A', 'OUTPUT', '-d', host,
                    '-j', 'DROP'
                ], check=True)
            except Exception as e:
                logger.error(f"Failed to inject network partition: {e}")
                return False
        
        self.active = True
        
        # Schedule automatic rollback
        asyncio.create_task(self._auto_rollback(duration))
        
        logger.info(f"Network partition injected for {self.target_hosts}")
        return True
    
    async def rollback(self) -> bool:
        import subprocess
        
        for host in self.target_hosts:
            try:
                subprocess.run([
                    'iptables', '-D', 'OUTPUT', '-d', host,
                    '-j', 'DROP'
                ], check=True)
            except Exception as e:
                logger.error(f"Failed to rollback network partition: {e}")
                return False
        
        self.active = False
        logger.info("Network partition rolled back")
        return True
    
    async def _auto_rollback(self, delay_seconds: int):
        """Auto rollback after delay."""
        await asyncio.sleep(delay_seconds)
        if self.active:
            await self.rollback()


class ExperimentRunner:
    """
    Chaos Engineering Experiment Runner.
    
    Manages chaos experiments with:
    - Hypothesis-based testing
    - Safe failure injection
    - Automatic rollback
    - Metrics collection
    
    Principles:
    1. Build Hypothesis around steady-state behavior
    2. Vary real-world events
    3. Run experiments in production
    4. Automate experiments
    5. Minimize blast radius
    """
    
    def __init__(
        self,
        db_pool: Optional[asyncpg.Pool] = None,
        redis_client = None
    ):
        self.db_pool = db_pool
        self.redis = redis_client
        self.experiments: Dict[str, ExperimentResult] = {}
        self.injectors: Dict[FailureType, FailureInjector] = {}
        self._running = False
        
        # Register injectors
        self._register_injectors()
    
    def _register_injectors(self):
        """Register default failure injectors."""
        self.injectors[FailureType.LATENCY] = LatencyInjector()
        self.injectors[FailureType.ERROR] = ErrorInjector()
        
        if self.db_pool:
            self.injectors[FailureType.DATABASE_LATENCY] = DatabaseLatencyInjector(self.db_pool)
    
    def register_injector(
        self,
        failure_type: FailureType,
        injector: FailureInjector
    ):
        """Register a custom failure injector."""
        self.injectors[failure_type] = injector
    
    async def run_experiment(
        self,
        config: ExperimentConfig,
        steady_state_check: Callable[[], Coroutine[Any, Any, bool]],
        load_generator: Optional[Callable[[], Coroutine[Any, Any, Dict]]] = None
    ) -> ExperimentResult:
        """
        Run a chaos experiment.
        
        Args:
            config: Experiment configuration
            steady_state_check: Function to verify system health
            load_generator: Function to generate synthetic load
            
        Returns:
            ExperimentResult with metrics and observations
        """
        experiment_id = f"{config.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        result = ExperimentResult(
            experiment_id=experiment_id,
            config=config,
            status=ExperimentStatus.PENDING,
            started_at=None,
            completed_at=None,
            total_requests=0,
            failed_requests=0,
            avg_latency_ms=0,
            p99_latency_ms=0,
            min_latency_ms=0,
            max_latency_ms=0,
            hypothesis_validated=False,
            observations=[],
            errors=[]
        )
        
        self.experiments[experiment_id] = result
        
        logger.info(f"Starting experiment: {experiment_id}")
        
        try:
            # Phase 1: Verify steady state
            result.status = ExperimentStatus.RUNNING
            result.started_at = datetime.now()
            
            logger.info("Phase 1: Verifying steady state...")
            if not await steady_state_check():
                result.errors.append("Steady state check failed before experiment")
                result.status = ExperimentStatus.FAILED
                return result
            
            # Phase 2: Ramp up load (if load generator provided)
            if load_generator and config.ramp_up_seconds > 0:
                logger.info(f"Phase 2: Ramping up for {config.ramp_up_seconds}s...")
                await self._run_load_phase(
                    load_generator,
                    config.ramp_up_seconds,
                    result,
                    inject_failure=False
                )
            
            # Phase 3: Inject failure
            logger.info(f"Phase 3: Injecting {config.failure_type.value}...")
            injector = self.injectors.get(config.failure_type)
            if not injector:
                result.errors.append(f"No injector for {config.failure_type}")
                result.status = ExperimentStatus.FAILED
                return result
            
            success = await injector.inject(config.failure_params)
            if not success:
                result.errors.append("Failed to inject failure")
                result.status = ExperimentStatus.FAILED
                return result
            
            # Phase 4: Run experiment with failure
            logger.info(f"Phase 4: Running experiment for {config.duration_seconds}s...")
            await self._run_load_phase(
                load_generator or self._default_load_generator(config.target_service),
                config.duration_seconds,
                result,
                inject_failure=True,
                injector=injector
            )
            
            # Phase 5: Check if still healthy
            logger.info("Phase 5: Verifying steady state post-failure...")
            is_healthy = await steady_state_check()
            
            # Phase 6: Rollback
            result.status = ExperimentStatus.ROLLING_BACK
            logger.info("Phase 6: Rolling back failure...")
            await injector.rollback()
            
            # Phase 7: Cooldown
            if config.cooldown_seconds > 0:
                logger.info(f"Phase 7: Cooldown for {config.cooldown_seconds}s...")
                await asyncio.sleep(config.cooldown_seconds)
            
            # Phase 8: Final verification
            logger.info("Phase 8: Final steady state verification...")
            is_healthy_final = await steady_state_check()
            
            # Validate hypothesis
            # Hypothesis: System maintains steady state despite failure
            result.hypothesis_validated = is_healthy and is_healthy_final
            result.status = ExperimentStatus.COMPLETED if result.hypothesis_validated else ExperimentStatus.FAILED
            result.completed_at = datetime.now()
            
            # Check abort conditions
            if result.failed_requests > config.abort_condition_failures:
                result.errors.append(f"Too many failures: {result.failed_requests}")
                result.hypothesis_validated = False
            
            if result.p99_latency_ms > config.abort_condition_latency_ms:
                result.errors.append(f"P99 latency exceeded: {result.p99_latency_ms}ms")
                result.hypothesis_validated = False
            
            logger.info(f"Experiment {experiment_id} completed: hypothesis_validated={result.hypothesis_validated}")
            
        except Exception as e:
            logger.error(f"Experiment {experiment_id} failed: {e}")
            result.status = ExperimentStatus.FAILED
            result.errors.append(str(e))
            
            # Emergency rollback
            if config.rollback_on_failure:
                await self._emergency_rollback(config.failure_type)
        
        return result
    
    async def _run_load_phase(
        self,
        load_generator: Callable[[], Coroutine[Any, Any, Dict]],
        duration_seconds: int,
        result: ExperimentResult,
        inject_failure: bool = False,
        injector: Optional[FailureInjector] = None
    ):
        """Run load generation phase."""
        start_time = time.time()
        latencies: List[float] = []
        
        while time.time() - start_time < duration_seconds:
            try:
                request_start = time.time()
                
                # Apply latency injection if active
                if inject_failure and isinstance(injector, LatencyInjector):
                    await injector.apply_latency()
                
                # Generate load
                response = await load_generator()
                
                # Check for injected errors
                if inject_failure and isinstance(injector, ErrorInjector):
                    if injector.should_error():
                        result.failed_requests += 1
                        result.observations.append({
                            'timestamp': datetime.now().isoformat(),
                            'type': 'injected_error',
                            'code': injector.get_error_code()
                        })
                        continue
                
                request_latency = (time.time() - request_start) * 1000
                latencies.append(request_latency)
                result.total_requests += 1
                
                # Check for actual errors
                if response.get('status') >= 400:
                    result.failed_requests += 1
                
            except Exception as e:
                result.failed_requests += 1
                result.observations.append({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'error',
                    'message': str(e)
                })
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        # Calculate latency stats
        if latencies:
            result.avg_latency_ms = sum(latencies) / len(latencies)
            result.min_latency_ms = min(latencies)
            result.max_latency_ms = max(latencies)
            latencies.sort()
            result.p99_latency_ms = latencies[int(len(latencies) * 0.99)]
    
    async def _default_load_generator(self, target_service: str) -> Dict:
        """Default load generator - health check."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{target_service}/health",
                    timeout=5.0
                )
                return {
                    'status': response.status_code,
                    'latency_ms': response.elapsed.total_seconds() * 1000
                }
        except Exception as e:
            return {'status': 0, 'error': str(e)}
    
    async def _emergency_rollback(self, failure_type: FailureType):
        """Emergency rollback of failure injection."""
        logger.warning(f"Emergency rollback for {failure_type.value}")
        injector = self.injectors.get(failure_type)
        if injector:
            await injector.rollback()
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentResult]:
        """Get experiment result."""
        return self.experiments.get(experiment_id)
    
    def get_all_experiments(self) -> List[ExperimentResult]:
        """Get all experiment results."""
        return list(self.experiments.values())
    
    def generate_report(self, experiment_id: str) -> Dict[str, Any]:
        """Generate detailed experiment report."""
        result = self.experiments.get(experiment_id)
        if not result:
            return {'error': 'Experiment not found'}
        
        duration = (result.completed_at - result.started_at).total_seconds() if result.completed_at else 0
        
        return {
            'experiment_id': result.experiment_id,
            'name': result.config.name,
            'description': result.config.description,
            'status': result.status.value,
            'duration_seconds': duration,
            'hypothesis': f"System maintains steady state despite {result.config.failure_type.value}",
            'hypothesis_validated': result.hypothesis_validated,
            'metrics': {
                'total_requests': result.total_requests,
                'failed_requests': result.failed_requests,
                'failure_rate': result.failed_requests / result.total_requests if result.total_requests > 0 else 0,
                'avg_latency_ms': round(result.avg_latency_ms, 2),
                'p99_latency_ms': round(result.p99_latency_ms, 2),
                'min_latency_ms': round(result.min_latency_ms, 2),
                'max_latency_ms': round(result.max_latency_ms, 2)
            },
            'failure_injected': {
                'type': result.config.failure_type.value,
                'params': result.config.failure_params
            },
            'observations': result.observations,
            'errors': result.errors,
            'recommendations': self._generate_recommendations(result)
        }
    
    def _generate_recommendations(self, result: ExperimentResult) -> List[str]:
        """Generate recommendations based on experiment results."""
        recommendations = []
        
        if not result.hypothesis_validated:
            recommendations.append(
                f"System failed to maintain steady state under {result.config.failure_type.value}. "
                "Consider improving resilience."
            )
        
        failure_rate = result.failed_requests / result.total_requests if result.total_requests > 0 else 0
        if failure_rate > 0.05:
            recommendations.append(
                f"Failure rate of {failure_rate*100:.1f}% exceeds 5% threshold. "
                "Review error handling and circuit breaker configuration."
            )
        
        if result.p99_latency_ms > 1000:
            recommendations.append(
                f"P99 latency of {result.p99_latency_ms:.0f}ms is high. "
                "Consider caching or query optimization."
            )
        
        if result.hypothesis_validated and failure_rate < 0.01:
            recommendations.append(
                "System shows good resilience. Consider increasing failure intensity in future experiments."
            )
        
        return recommendations
    
    async def run_scheduled_experiments(self, configs: List[ExperimentConfig]):
        """Run experiments on a schedule."""
        self._running = True
        
        while self._running:
            for config in configs:
                if not self._running:
                    break
                
                # Skip if outside allowed time window (e.g., business hours only)
                if not self._is_allowed_time():
                    continue
                
                logger.info(f"Running scheduled experiment: {config.name}")
                
                await self.run_experiment(
                    config=config,
                    steady_state_check=self._default_steady_state_check
                )
                
                # Wait between experiments
                await asyncio.sleep(300)  # 5 minutes
            
            # Wait before next cycle
            await asyncio.sleep(3600)  # 1 hour
    
    def _is_allowed_time(self) -> bool:
        """Check if experiments are allowed at current time."""
        now = datetime.now()
        # Only run during business hours (9-17) on weekdays
        if now.weekday() >= 5:  # Weekend
            return False
        if now.hour < 9 or now.hour >= 17:
            return False
        return True
    
    async def _default_steady_state_check(self) -> bool:
        """Default steady state check."""
        # Check database connectivity
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
            except Exception:
                return False
        
        # Check Redis connectivity
        if self.redis:
            try:
                await self.redis.ping()
            except Exception:
                return False
        
        return True
    
    def stop(self):
        """Stop scheduled experiments."""
        self._running = False
        logger.info("Stopping scheduled experiments")


# Predefined experiment templates

EXPERIMENT_TEMPLATES = {
    'api_latency': ExperimentConfig(
        name="api_latency",
        description="Test API resilience under high latency",
        target_service="api:8000",
        failure_type=FailureType.LATENCY,
        failure_params={'latency_ms': 2000, 'jitter_pct': 20},
        duration_seconds=300,
        ramp_up_seconds=30,
        abort_condition_latency_ms=10000
    ),
    'api_errors': ExperimentConfig(
        name="api_errors",
        description="Test API resilience under error conditions",
        target_service="api:8000",
        failure_type=FailureType.ERROR,
        failure_params={'error_rate': 0.2, 'error_codes': [500, 503]},
        duration_seconds=300,
        abort_condition_failures=50
    ),
    'database_slowdown': ExperimentConfig(
        name="database_slowdown",
        description="Test system resilience under database latency",
        target_service="postgres:5432",
        failure_type=FailureType.DATABASE_LATENCY,
        failure_params={'latency_ms': 1000},
        duration_seconds=300,
        abort_condition_latency_ms=5000
    ),
    'network_partition': ExperimentConfig(
        name="network_partition",
        description="Test resilience during network partition",
        target_service="redis:6379",
        failure_type=FailureType.NETWORK_PARTITION,
        failure_params={
            'target_hosts': ['redis:6379'],
            'duration_seconds': 60
        },
        duration_seconds=60,
        auto_rollback=True
    )
}
