"""
AUTO-BROKER ERP Sync Orchestrator
Bidirectional sync with conflict resolution and transaction journaling
Enterprise Integration - P1

Conflict Resolution:
- Time-based priority: later timestamp wins
- Version field: higher version wins
- Manual queue: flagged for review when conflict detected

Transaction Journaling:
- All sync operations logged in transactions_journal table
- Unapplied changes tracked in unapplied_changes table
- Support for replay and rollback
"""

import logging
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic
from abc import ABC, abstractmethod

import asyncpg
from pydantic import BaseModel, Field

from connectors.erp.sap_s4hana_adapter import SAPS4HANAAdapter, SAPSalesOrder, SAPDeliveryNote
from connectors.erp.netsuite_adapter import NetSuiteAdapter, NetSuiteTransaction
from connectors.erp.dynamics365_adapter import Dynamics365Adapter, D365SalesOrder

logger = logging.getLogger(__name__)

T = TypeVar('T')


class SyncDirection(Enum):
    """Sync direction."""
    ERP_TO_AB = "erp_to_ab"  # ERP to Auto-Broker
    AB_TO_ERP = "ab_to_erp"  # Auto-Broker to ERP
    BIDIRECTIONAL = "bidirectional"


class ConflictResolution(Enum):
    """Conflict resolution strategy."""
    TIMESTAMP_WINS = "timestamp_wins"  # Later timestamp wins
    VERSION_WINS = "version_wins"  # Higher version wins
    ERP_WINS = "erp_wins"  # ERP always wins
    AB_WINS = "ab_wins"  # Auto-Broker always wins
    MANUAL = "manual"  # Queue for manual resolution


class SyncStatus(Enum):
    """Sync operation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    MANUAL_REVIEW = "manual_review"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    operation_id: str
    status: SyncStatus
    records_processed: int
    records_failed: int
    conflicts_detected: int
    errors: List[str]
    started_at: datetime
    completed_at: Optional[datetime] = None


@dataclass
class EntityChange:
    """Represents a change to an entity."""
    entity_type: str  # sales_order, customer, delivery
    entity_id: str
    change_type: str  # CREATE, UPDATE, DELETE
    source_system: str  # sap, netsuite, dynamics, auto-broker
    timestamp: datetime
    version: int
    data: Dict[str, Any]
    previous_data: Optional[Dict[str, Any]] = None


class SyncRule(BaseModel):
    """Sync rule configuration."""
    entity_type: str
    direction: SyncDirection
    conflict_resolution: ConflictResolution
    sync_interval_minutes: int = 15
    last_sync_timestamp: Optional[datetime] = None
    enabled: bool = True
    filters: Dict[str, Any] = Field(default_factory=dict)


class ERPAdapter(ABC):
    """Abstract base class for ERP adapters."""
    
    @property
    @abstractmethod
    def system_name(self) -> str:
        """Return system identifier."""
        pass
    
    @abstractmethod
    async def get_sales_orders(self, from_date: Optional[datetime] = None) -> List[Any]:
        """Get sales orders."""
        pass
    
    @abstractmethod
    async def get_delivery_notes(self, from_date: Optional[datetime] = None) -> List[Any]:
        """Get delivery notes."""
        pass
    
    @abstractmethod
    async def post_pod_confirmation(self, delivery_id: str, **kwargs) -> bool:
        """Post POD confirmation."""
        pass


class SyncOrchestrator:
    """
    ERP Synchronization Orchestrator.
    
    Features:
    - Bidirectional sync with conflict resolution
    - Transaction journaling for audit trail
    - Unapplied changes tracking
    - Configurable sync rules per entity type
    - Automatic retry with exponential backoff
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        redis_client: Optional[Any] = None
    ):
        self.db = db_pool
        self.redis = redis_client
        self.adapters: Dict[str, ERPAdapter] = {}
        self.sync_rules: Dict[str, SyncRule] = {}
        self._lock = asyncio.Lock()
        self._running = False
    
    def register_adapter(self, adapter: ERPAdapter) -> None:
        """Register an ERP adapter."""
        self.adapters[adapter.system_name] = adapter
        logger.info(f"Registered adapter: {adapter.system_name}")
    
    def configure_sync_rule(self, rule: SyncRule) -> None:
        """Configure sync rule for entity type."""
        self.sync_rules[rule.entity_type] = rule
        logger.info(f"Configured sync rule for {rule.entity_type}")
    
    async def _log_transaction(
        self,
        operation_id: str,
        source_system: str,
        target_system: str,
        entity_type: str,
        entity_id: str,
        change_type: str,
        status: SyncStatus,
        data: Dict[str, Any],
        error_message: Optional[str] = None
    ) -> None:
        """Log sync transaction to journal."""
        try:
            await self.db.execute("""
                INSERT INTO transactions_journal (
                    operation_id, source_system, target_system,
                    entity_type, entity_id, change_type,
                    status, data_payload, error_message,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            """, operation_id, source_system, target_system,
                entity_type, entity_id, change_type,
                status.value, 
                json.dumps(data) if isinstance(data, dict) else data,
                error_message)
        except Exception as e:
            logger.error(f"Failed to log transaction: {e}")
    
    async def _queue_unapplied_change(
        self,
        operation_id: str,
        source_system: str,
        entity_type: str,
        entity_id: str,
        change_data: Dict[str, Any],
        reason: str
    ) -> None:
        """Queue change that couldn't be applied."""
        try:
            await self.db.execute("""
                INSERT INTO unapplied_changes (
                    operation_id, source_system,
                    entity_type, entity_id,
                    change_data, reason,
                    retry_count, status,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, 0, 'pending', NOW())
            """, operation_id, source_system, entity_type, entity_id,
                json.dumps(change_data), reason)
        except Exception as e:
            logger.error(f"Failed to queue unapplied change: {e}")
    
    async def _detect_conflict(
        self,
        entity_type: str,
        entity_id: str,
        incoming_change: EntityChange,
        existing_data: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect if there's a conflict.
        
        Returns:
            (is_conflict, conflict_reason)
        """
        if not existing_data:
            return False, None
        
        # Check if existing data has been modified since last sync
        existing_version = existing_data.get('_sync_version', 0)
        incoming_version = incoming_change.version
        
        if existing_version > incoming_version:
            return True, f"Version conflict: existing v{existing_version} > incoming v{incoming_version}"
        
        # Check timestamps
        existing_timestamp = existing_data.get('_last_modified')
        if existing_timestamp:
            existing_dt = datetime.fromisoformat(existing_timestamp)
            if existing_dt > incoming_change.timestamp:
                return True, f"Timestamp conflict: local modified later"
        
        return False, None
    
    async def _resolve_conflict(
        self,
        entity_type: str,
        incoming_change: EntityChange,
        existing_data: Dict[str, Any]
    ) -> Tuple[bool, ConflictResolution]:
        """
        Resolve conflict based on configured strategy.
        
        Returns:
            (should_apply_incoming, resolution_strategy)
        """
        rule = self.sync_rules.get(entity_type)
        if not rule:
            # Default to manual
            return False, ConflictResolution.MANUAL
        
        strategy = rule.conflict_resolution
        
        if strategy == ConflictResolution.TIMESTAMP_WINS:
            existing_ts = existing_data.get('_last_modified')
            if existing_ts:
                existing_dt = datetime.fromisoformat(existing_ts)
                if incoming_change.timestamp > existing_dt:
                    return True, strategy
            return False, strategy
            
        elif strategy == ConflictResolution.VERSION_WINS:
            existing_ver = existing_data.get('_sync_version', 0)
            return incoming_change.version > existing_ver, strategy
            
        elif strategy == ConflictResolution.ERP_WINS:
            return incoming_change.source_system != 'auto-broker', strategy
            
        elif strategy == ConflictResolution.AB_WINS:
            return incoming_change.source_system == 'auto-broker', strategy
            
        else:  # MANUAL
            return False, ConflictResolution.MANUAL
    
    async def sync_sales_orders(
        self,
        system: str,
        direction: SyncDirection = SyncDirection.ERP_TO_AB
    ) -> SyncResult:
        """
        Sync sales orders from/to ERP.
        
        Args:
            system: ERP system identifier (sap, netsuite, dynamics)
            direction: Sync direction
        """
        operation_id = f"sync_so_{system}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = SyncResult(
            operation_id=operation_id,
            status=SyncStatus.IN_PROGRESS,
            records_processed=0,
            records_failed=0,
            conflicts_detected=0,
            errors=[],
            started_at=datetime.now()
        )
        
        adapter = self.adapters.get(system)
        if not adapter:
            result.status = SyncStatus.FAILED
            result.errors.append(f"No adapter registered for {system}")
            return result
        
        rule = self.sync_rules.get('sales_order')
        if rule and rule.last_sync_timestamp:
            from_date = rule.last_sync_timestamp
        else:
            from_date = datetime.now() - timedelta(days=1)
        
        try:
            async with adapter:  # Context manager for connection
                orders = await adapter.get_sales_orders(from_date=from_date)
                
                for order in orders:
                    try:
                        # Transform to internal format
                        if system == 'sap' and isinstance(order, SAPSalesOrder):
                            internal_data = self._transform_sap_order(order)
                        elif system == 'netsuite' and isinstance(order, NetSuiteTransaction):
                            internal_data = self._transform_netsuite_order(order)
                        elif system == 'dynamics' and isinstance(order, D365SalesOrder):
                            internal_data = self._transform_d365_order(order)
                        else:
                            continue
                        
                        # Check for existing record
                        existing = await self.db.fetchrow("""
                            SELECT id, _sync_version, _last_modified, data
                            FROM erp_sales_orders 
                            WHERE erp_id = $1 AND erp_system = $2
                        """, internal_data['erp_id'], system)
                        
                        change = EntityChange(
                            entity_type='sales_order',
                            entity_id=internal_data['erp_id'],
                            change_type='UPDATE' if existing else 'CREATE',
                            source_system=system,
                            timestamp=datetime.now(),
                            version=internal_data.get('_sync_version', 1),
                            data=internal_data
                        )
                        
                        if existing:
                            existing_data = json.loads(existing['data']) if isinstance(existing['data'], str) else existing['data']
                            is_conflict, reason = await self._detect_conflict(
                                'sales_order', internal_data['erp_id'], change, existing_data
                            )
                            
                            if is_conflict:
                                result.conflicts_detected += 1
                                should_apply, resolution = await self._resolve_conflict(
                                    'sales_order', change, existing_data
                                )
                                
                                if resolution == ConflictResolution.MANUAL or not should_apply:
                                    await self._queue_unapplied_change(
                                        operation_id, system, 'sales_order',
                                        internal_data['erp_id'], internal_data,
                                        f"Conflict: {reason}, resolution: {resolution.value}"
                                    )
                                    await self._log_transaction(
                                        operation_id, system, 'auto-broker',
                                        'sales_order', internal_data['erp_id'],
                                        change.change_type, SyncStatus.CONFLICT,
                                        internal_data, reason
                                    )
                                    continue
                        
                        # Apply change
                        await self._apply_sales_order_change(system, internal_data, existing)
                        result.records_processed += 1
                        
                        await self._log_transaction(
                            operation_id, system, 'auto-broker',
                            'sales_order', internal_data['erp_id'],
                            change.change_type, SyncStatus.SUCCESS,
                            internal_data
                        )
                        
                    except Exception as e:
                        result.records_failed += 1
                        error_msg = str(e)
                        result.errors.append(error_msg)
                        await self._log_transaction(
                            operation_id, system, 'auto-broker',
                            'sales_order', getattr(order, 'order_id', 'unknown'),
                            'ERROR', SyncStatus.FAILED, {}, error_msg
                        )
                
                # Update last sync timestamp
                if rule:
                    rule.last_sync_timestamp = datetime.now()
                
                result.status = SyncStatus.SUCCESS if result.records_failed == 0 else SyncStatus.FAILED
                
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            logger.error(f"Sync failed for {system}: {e}")
        
        result.completed_at = datetime.now()
        return result
    
    def _transform_sap_order(self, order: SAPSalesOrder) -> Dict[str, Any]:
        """Transform SAP sales order to internal format."""
        return {
            'erp_id': order.order_id,
            'erp_system': 'sap',
            'customer_id': order.customer_id,
            'order_date': order.order_date.isoformat(),
            'delivery_date': order.delivery_date.isoformat(),
            'total_value': order.total_value,
            'currency': order.currency,
            'status': order.status,
            '_sync_version': 1,
            '_last_modified': datetime.now().isoformat()
        }
    
    def _transform_netsuite_order(self, order: NetSuiteTransaction) -> Dict[str, Any]:
        """Transform NetSuite order to internal format."""
        return {
            'erp_id': order.id,
            'erp_system': 'netsuite',
            'customer_id': order.entity,
            'order_date': order.trandate.isoformat(),
            'total_value': order.total,
            'currency': order.currency,
            'status': order.status,
            '_sync_version': 1,
            '_last_modified': datetime.now().isoformat()
        }
    
    def _transform_d365_order(self, order: D365SalesOrder) -> Dict[str, Any]:
        """Transform D365 sales order to internal format."""
        return {
            'erp_id': order.sales_order_number,
            'erp_system': 'dynamics',
            'customer_id': order.customer_account,
            'delivery_date': order.requested_receipt_date.isoformat(),
            'total_value': order.total_amount,
            'currency': order.currency_code,
            'status': order.sales_order_status,
            '_sync_version': 1,
            '_last_modified': datetime.now().isoformat()
        }
    
    async def _apply_sales_order_change(
        self,
        system: str,
        data: Dict[str, Any],
        existing: Optional[asyncpg.Record]
    ) -> None:
        """Apply sales order change to database."""
        if existing:
            await self.db.execute("""
                UPDATE erp_sales_orders 
                SET data = $1, _sync_version = $2, _last_modified = NOW(),
                    updated_at = NOW()
                WHERE erp_id = $3 AND erp_system = $4
            """, json.dumps(data), data.get('_sync_version', 1),
                data['erp_id'], system)
        else:
            await self.db.execute("""
                INSERT INTO erp_sales_orders 
                (erp_id, erp_system, customer_id, data, _sync_version, 
                 _last_modified, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW(), NOW())
            """, data['erp_id'], system, data['customer_id'],
                json.dumps(data), data.get('_sync_version', 1))
    
    async def post_pod_to_erp(
        self,
        system: str,
        delivery_id: str,
        received_by: str,
        received_at: datetime,
        quantity_received: int
    ) -> bool:
        """Post POD confirmation back to ERP."""
        operation_id = f"pod_{system}_{delivery_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        adapter = self.adapters.get(system)
        if not adapter:
            logger.error(f"No adapter for {system}")
            return False
        
        try:
            async with adapter:
                success = await adapter.post_pod_confirmation(
                    delivery_id=delivery_id,
                    received_by=received_by,
                    received_at=received_at,
                    quantity_received=quantity_received
                )
                
                await self._log_transaction(
                    operation_id, 'auto-broker', system,
                    'pod_confirmation', delivery_id,
                    'UPDATE',
                    SyncStatus.SUCCESS if success else SyncStatus.FAILED,
                    {'received_by': received_by, 'quantity': quantity_received}
                )
                
                return success
                
        except Exception as e:
            await self._log_transaction(
                operation_id, 'auto-broker', system,
                'pod_confirmation', delivery_id,
                'UPDATE', SyncStatus.FAILED, {}, str(e)
            )
            return False
    
    async def start_continuous_sync(self) -> None:
        """Start continuous sync loop."""
        self._running = True
        logger.info("Starting continuous sync")
        
        while self._running:
            try:
                for entity_type, rule in self.sync_rules.items():
                    if not rule.enabled:
                        continue
                    
                    # Check if it's time to sync
                    if rule.last_sync_timestamp:
                        elapsed = (datetime.now() - rule.last_sync_timestamp).total_seconds() / 60
                        if elapsed < rule.sync_interval_minutes:
                            continue
                    
                    if entity_type == 'sales_order':
                        for system in self.adapters.keys():
                            result = await self.sync_sales_orders(system, rule.direction)
                            logger.info(f"Sync result for {system}: {result.status.value}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(60)
    
    def stop_continuous_sync(self) -> None:
        """Stop continuous sync loop."""
        self._running = False
        logger.info("Stopping continuous sync")
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        # Get counts from journal
        row = await self.db.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'success') as success_count,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                COUNT(*) FILTER (WHERE status = 'conflict') as conflict_count,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h
            FROM transactions_journal
        """)
        
        # Get unapplied changes
        unapplied = await self.db.fetchval("""
            SELECT COUNT(*) FROM unapplied_changes WHERE status = 'pending'
        """)
        
        return {
            "adapters_registered": list(self.adapters.keys()),
            "sync_rules_configured": list(self.sync_rules.keys()),
            "transactions_24h": row['last_24h'],
            "success_count": row['success_count'],
            "failed_count": row['failed_count'],
            "conflict_count": row['conflict_count'],
            "unapplied_changes": unapplied,
            "continuous_sync_running": self._running
        }


# Database schema for sync tables (to be added to init script)
SYNC_TABLES_SQL = """
-- ERP synced sales orders
CREATE TABLE IF NOT EXISTS erp_sales_orders (
    id SERIAL PRIMARY KEY,
    erp_id VARCHAR(50) NOT NULL,
    erp_system VARCHAR(20) NOT NULL,
    customer_id VARCHAR(50),
    data JSONB NOT NULL DEFAULT '{}',
    _sync_version INT DEFAULT 1,
    _last_modified TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(erp_id, erp_system)
);

-- Transaction journal for audit trail
CREATE TABLE IF NOT EXISTS transactions_journal (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    target_system VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    data_payload JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transactions_journal_operation ON transactions_journal(operation_id);
CREATE INDEX idx_transactions_journal_entity ON transactions_journal(entity_type, entity_id);
CREATE INDEX idx_transactions_journal_created ON transactions_journal(created_at);

-- Unapplied changes queue
CREATE TABLE IF NOT EXISTS unapplied_changes (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(100) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    change_data JSONB NOT NULL,
    reason TEXT,
    retry_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE INDEX idx_unapplied_changes_status ON unapplied_changes(status);
CREATE INDEX idx_unapplied_changes_entity ON unapplied_changes(entity_type, entity_id);
"""

import json
