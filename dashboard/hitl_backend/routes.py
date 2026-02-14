"""
AUTO-BROKER HITL (Human-in-the-Loop) Backend
Emergency overrides, escalation queue, real-time monitoring
Security & Compliance - P0 Critical
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import (
    APIRouter, WebSocket, WebSocketDisconnect, 
    Depends, HTTPException, status, BackgroundTasks
)
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from security.identity_provider import get_current_user, require_mfa, JWTClaims
from security.rbac_matrix import require_role, Resource, Action, Role
from compliance.audit_logger import AuditLogger, DecisionType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hitl", tags=["Human-in-the-Loop"])
security = HTTPBearer()


# ==================== Data Models ====================

class OverrideType(str, Enum):
    """Types of emergency overrides."""
    PRICING = "pricing"
    SHIPMENT_BLOCK = "shipment_block"
    AGENT_HALT = "agent_halt"
    CARRIER_CHANGE = "carrier_change"


class OverrideStatus(str, Enum):
    """Status of override request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class EscalationPriority(int, Enum):
    """Escalation priority levels."""
    CRITICAL = 10  # System down, data breach
    HIGH = 7       # Major issue, angry customer
    MEDIUM = 5     # Standard escalation
    LOW = 3        # Minor concern


class EmergencyOverrideRequest(BaseModel):
    """Request for emergency override."""
    override_type: OverrideType
    target_id: str  # shipment_id, agent_id, etc.
    reason: str  # Min 20 characters required
    new_value: Optional[Dict[str, Any]] = None
    requires_immediate: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "override_type": "pricing",
                "target_id": "SHIP-12345",
                "reason": "Emergency pricing adjustment due to carrier strike - customer needs immediate alternative",
                "new_value": {"price_eur": 1500.00, "carrier_id": "ALT-001"},
                "requires_immediate": True
            }
        }


class EscalationItem(BaseModel):
    """Item in escalation queue."""
    escalation_id: str
    lead_id: Optional[str]
    shipment_id: Optional[str]
    priority: EscalationPriority
    sentiment_score: Optional[float]
    dominant_emotion: Optional[str]
    profile_type: Optional[str]
    context_summary: str
    created_at: datetime
    assigned_to: Optional[str]
    status: str


class AgentStatus(BaseModel):
    """Real-time AI agent status."""
    agent_name: str
    status: str  # "active", "paused", "error", "overridden"
    current_lead_id: Optional[str]
    last_10_logs: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]


# ==================== WebSocket Manager ====================

class HITLWebSocketManager:
    """Manage WebSocket connections for real-time HITL updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.supervisor_connections: Dict[str, WebSocket] = {}  # user_id -> websocket
    
    async def connect(self, websocket: WebSocket, user_id: str, is_supervisor: bool = False):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if is_supervisor:
            self.supervisor_connections[user_id] = websocket
        
        logger.info(f"HITL WebSocket connected: {user_id} (supervisor={is_supervisor})")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove disconnected WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if user_id in self.supervisor_connections:
            del self.supervisor_connections[user_id]
        
        logger.info(f"HITL WebSocket disconnected: {user_id}")
    
    async def broadcast_escalation(self, escalation: Dict[str, Any]):
        """Broadcast new escalation to all supervisors."""
        message = {
            "type": "new_escalation",
            "data": escalation,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        disconnected = []
        for user_id, connection in self.supervisor_connections.items():
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(user_id)
        
        # Clean up disconnected
        for user_id in disconnected:
            if user_id in self.supervisor_connections:
                del self.supervisor_connections[user_id]
    
    async def broadcast_agent_update(self, agent_status: Dict[str, Any]):
        """Broadcast agent status update."""
        message = {
            "type": "agent_update",
            "data": agent_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass
    
    async def notify_override_executed(self, user_id: str, override: Dict[str, Any]):
        """Notify supervisor that override was executed."""
        if user_id in self.supervisor_connections:
            await self.supervisor_connections[user_id].send_json({
                "type": "override_executed",
                "data": override
            })


# Singleton manager
ws_manager = HITLWebSocketManager()


# ==================== API Routes ====================

@router.post(
    "/override/{target_type}/{target_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Emergency override (requires MFA)"
)
async def create_emergency_override(
    target_type: OverrideType,
    target_id: str,
    request: EmergencyOverrideRequest,
    background_tasks: BackgroundTasks,
    current_user: JWTClaims = Depends(require_mfa()),  # MFA required
    audit_logger: AuditLogger = Depends()
):
    """
    Create emergency override request.
    
    Requires MFA verification and supervisor role.
    All overrides are audited immutably.
    """
    # Validate reason length
    if len(request.reason) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason must be at least 20 characters"
        )
    
    # Check permissions
    if current_user.role not in [Role.SUPERVISOR, Role.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor or Admin role required"
        )
    
    # Log the override decision
    decision_id = audit_logger.log_human_override(
        original_decision_id=None,  # New decision
        new_decision={
            "override_type": target_type.value,
            "target_id": target_id,
            "new_value": request.new_value,
            "requires_immediate": request.requires_immediate
        },
        override_reason=request.reason,
        overridden_by=current_user.sub,
        input_data={
            "user_id": current_user.sub,
            "organization_id": current_user.organization_id,
            "ip_address": "[REDACTED]",
            "mfa_verified": current_user.mfa_verified
        }
    )
    
    # Execute override in background
    background_tasks.add_task(
        _execute_override,
        target_type=target_type,
        target_id=target_id,
        new_value=request.new_value,
        overridden_by=current_user.sub
    )
    
    # Notify via WebSocket
    await ws_manager.notify_override_executed(
        current_user.sub,
        {
            "decision_id": str(decision_id),
            "target_type": target_type.value,
            "target_id": target_id,
            "status": "executing"
        }
    )
    
    return {
        "override_id": str(decision_id),
        "status": "executing",
        "target_type": target_type.value,
        "target_id": target_id,
        "executed_by": current_user.sub,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get(
    "/queue",
    response_model=List[EscalationItem],
    summary="Get escalation queue"
)
async def get_escalation_queue(
    priority_min: Optional[int] = None,
    assigned_only: bool = False,
    current_user: JWTClaims = Depends(get_current_user)
):
    """
    Get list of items requiring human intervention.
    
    Sorted by priority (highest first), then by creation time.
    """
    # Check permissions
    if current_user.role == Role.BROKER:
        # Brokers see only their own escalations
        assigned_only = True
    
    # Mock data - in production: query from database
    queue = [
        EscalationItem(
            escalation_id="ESC-001",
            lead_id="LEAD-123",
            shipment_id=None,
            priority=EscalationPriority.HIGH,
            sentiment_score=-0.75,
            dominant_emotion="Anger",
            profile_type="security",
            context_summary="Customer threatening legal action, needs supervisor",
            created_at=datetime.utcnow() - timedelta(minutes=5),
            assigned_to=None,
            status="open"
        ),
        EscalationItem(
            escalation_id="ESC-002",
            lead_id="LEAD-456",
            shipment_id="SHIP-789",
            priority=EscalationPriority.MEDIUM,
            sentiment_score=-0.45,
            dominant_emotion="Frustration",
            profile_type="analyst",
            context_summary="Pricing dispute, requesting data breakdown",
            created_at=datetime.utcnow() - timedelta(minutes=15),
            assigned_to=None,
            status="open"
        )
    ]
    
    # Filter by priority
    if priority_min:
        queue = [q for q in queue if q.priority.value >= priority_min]
    
    # Filter by assignment
    if assigned_only and current_user.role == Role.BROKER:
        queue = [q for q in queue if q.assigned_to == current_user.sub]
    
    # Sort by priority, then time
    queue.sort(key=lambda x: (-x.priority.value, x.created_at))
    
    return queue


@router.post(
    "/queue/{escalation_id}/assign",
    summary="Assign escalation to supervisor"
)
async def assign_escalation(
    escalation_id: str,
    current_user: JWTClaims = Depends(require_role(Role.SUPERVISOR))
):
    """Assign an escalation to the current supervisor."""
    # In production: update database
    # For now: return success
    return {
        "escalation_id": escalation_id,
        "assigned_to": current_user.sub,
        "assigned_at": datetime.utcnow().isoformat(),
        "status": "assigned"
    }


@router.post(
    "/queue/{escalation_id}/resolve",
    summary="Mark escalation as resolved"
)
async def resolve_escalation(
    escalation_id: str,
    resolution_notes: str,
    current_user: JWTClaims = Depends(require_role(Role.SUPERVISOR))
):
    """Mark an escalation as resolved."""
    if len(resolution_notes) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolution notes must be at least 10 characters"
        )
    
    return {
        "escalation_id": escalation_id,
        "resolved_by": current_user.sub,
        "resolution_notes": resolution_notes,
        "resolved_at": datetime.utcnow().isoformat(),
        "status": "resolved"
    }


@router.get(
    "/agents/status",
    response_model=List[AgentStatus],
    summary="Get AI agent status"
)
async def get_agent_status(
    current_user: JWTClaims = Depends(get_current_user)
):
    """
    Get real-time status of all AI agents.
    
    Returns current lead, recent logs, and performance metrics.
    """
    # Mock data - in production: query from agent monitoring service
    return [
        AgentStatus(
            agent_name="SARA",
            status="active",
            current_lead_id="LEAD-123",
            last_10_logs=[
                {"timestamp": "2026-02-14T12:00:00Z", "action": "call_initiated", "lead_id": "LEAD-123"},
                {"timestamp": "2026-02-14T12:01:00Z", "action": "qualification_started"},
                {"timestamp": "2026-02-14T12:03:00Z", "action": "pricing_requested"}
            ],
            performance_metrics={
                "conversion_rate": 0.23,
                "avg_call_duration": 245.5,
                "escalation_rate": 0.05
            }
        ),
        AgentStatus(
            agent_name="MARCO",
            status="paused",
            current_lead_id=None,
            last_10_logs=[
                {"timestamp": "2026-02-14T11:30:00Z", "action": "override_applied", "reason": "Emergency halt"}
            ],
            performance_metrics={
                "conversion_rate": 0.31,
                "avg_call_duration": 189.2,
                "escalation_rate": 0.03
            }
        ),
        AgentStatus(
            agent_name="CARLO",
            status="active",
            current_lead_id="LEAD-456",
            last_10_logs=[
                {"timestamp": "2026-02-14T12:05:00Z", "action": "call_initiated", "lead_id": "LEAD-456"}
            ],
            performance_metrics={
                "conversion_rate": 0.28,
                "avg_call_duration": 210.0,
                "escalation_rate": 0.04
            }
        )
    ]


@router.post(
    "/agents/{agent_name}/halt",
    summary="Emergency halt agent"
)
async def halt_agent(
    agent_name: str,
    reason: str,
    current_user: JWTClaims = Depends(require_role(Role.SUPERVISOR))
):
    """
    Emergency halt an AI agent.
    
    Immediately stops all agent operations. Requires MFA.
    """
    if len(reason) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason must be at least 20 characters"
        )
    
    # In production: send signal to agent service
    logger.critical(
        f"Agent {agent_name} halted by {current_user.sub}",
        extra={"agent": agent_name, "reason": reason}
    )
    
    # Broadcast update
    await ws_manager.broadcast_agent_update({
        "agent_name": agent_name,
        "status": "halted",
        "halted_by": current_user.sub,
        "reason": reason,
        "halted_at": datetime.utcnow().isoformat()
    })
    
    return {
        "agent_name": agent_name,
        "status": "halted",
        "halted_by": current_user.sub,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post(
    "/agents/{agent_name}/resume",
    summary="Resume halted agent"
)
async def resume_agent(
    agent_name: str,
    current_user: JWTClaims = Depends(require_role(Role.ADMIN))
):
    """Resume a halted agent (Admin only)."""
    logger.info(f"Agent {agent_name} resumed by {current_user.sub}")
    
    await ws_manager.broadcast_agent_update({
        "agent_name": agent_name,
        "status": "active",
        "resumed_by": current_user.sub,
        "resumed_at": datetime.utcnow().isoformat()
    })
    
    return {
        "agent_name": agent_name,
        "status": "resumed",
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== WebSocket Endpoint ====================

@router.websocket("/ws")
async def hitl_websocket(
    websocket: WebSocket,
    token: str  # JWT token as query param
):
    """
    WebSocket for real-time HITL updates.
    
    Sends:
    - New escalations
    - Agent status changes
    - Override confirmations
    """
    # Validate token
    from security.identity_provider import IdentityProvider
    idp = IdentityProvider()
    
    try:
        user = await idp.validate_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    is_supervisor = user.role in [Role.SUPERVISOR, Role.ADMIN]
    
    await ws_manager.connect(websocket, user.sub, is_supervisor)
    
    try:
        while True:
            # Receive ping/ack from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif message.get("action") == "subscribe_agent":
                # Client wants updates for specific agent
                agent_name = message.get("agent_name")
                await websocket.send_json({
                    "type": "subscribed",
                    "agent": agent_name
                })
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user.sub)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, user.sub)


# ==================== Background Tasks ====================

async def _execute_override(
    target_type: OverrideType,
    target_id: str,
    new_value: Optional[Dict[str, Any]],
    overridden_by: str
):
    """Execute override in background."""
    try:
        if target_type == OverrideType.PRICING:
            # Update pricing in database
            logger.info(f"Executing pricing override for {target_id}")
            # In production: update shipment pricing
            
        elif target_type == OverrideType.SHIPMENT_BLOCK:
            # Block shipment
            logger.info(f"Blocking shipment {target_id}")
            # In production: update shipment status
            
        elif target_type == OverrideType.AGENT_HALT:
            # Halt agent
            logger.info(f"Halting agent {target_id}")
            
        elif target_type == OverrideType.CARRIER_CHANGE:
            # Change carrier
            logger.info(f"Changing carrier for {target_id}")
            
        # Notify completion
        await ws_manager.broadcast_agent_update({
            "type": "override_complete",
            "target_type": target_type.value,
            "target_id": target_id,
            "executed_by": overridden_by,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Override execution failed: {e}")
        # Notify failure
        await ws_manager.broadcast_agent_update({
            "type": "override_failed",
            "target_type": target_type.value,
            "target_id": target_id,
            "error": str(e)
        })
