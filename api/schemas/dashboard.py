"""
AUTO-BROKER: Dashboard API Schemas
Pydantic models for Mission Control Center integration.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ==========================================
# AUTHENTICATION
# ==========================================

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str


# ==========================================
# DASHBOARD STATS
# ==========================================

class AgentStatus(BaseModel):
    status: str  # active, standby, warning, error
    calls_today: Optional[int] = 0
    pending_actions: Optional[int] = 0
    resolved_today: Optional[int] = 0
    confidence_score: Optional[float] = None
    last_action: Optional[str] = None
    current_task: Optional[str] = None


class AIAgentsStatus(BaseModel):
    sara: AgentStatus
    marco: AgentStatus
    paolo: AgentStatus
    giulia: AgentStatus


class DashboardStats(BaseModel):
    active_shipments: int
    monthly_revenue: Decimal
    current_level: int
    target_level: int
    progress_percent: float
    costs_monthly: Decimal
    margin_percent: float
    ai_agents: AIAgentsStatus
    total_shipments: int
    delivered_today: int
    alerts_count: int


# ==========================================
# SHIPMENTS
# ==========================================

class Location(BaseModel):
    lat: float
    lon: float
    address: str
    city: str
    country: str = "IT"


class CarrierInfo(BaseModel):
    id: str
    name: str
    type: str = "truck"
    rating: Optional[float] = None


class ShipmentResponse(BaseModel):
    id: str
    tracking_number: str
    origin: Location
    destination: Location
    carrier_id: str
    carrier_name: str
    status: str  # pending, confirmed, in_transit, delivered, cancelled, disputed
    margin_percent: float
    revenue: Decimal
    value: Decimal
    weight: float
    created_at: datetime
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    current_position: Optional[Location] = None
    customer_name: str
    customer_email: str
    notes: Optional[str] = None


class ShipmentListResponse(BaseModel):
    items: List[ShipmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ShipmentCreate(BaseModel):
    origin_address: str
    origin_city: str
    origin_country: str = "IT"
    dest_address: str
    dest_city: str
    dest_country: str = "IT"
    customer_name: str
    customer_email: str
    weight: float = Field(gt=0)
    value: Decimal = Field(gt=0)
    preferred_carrier_id: Optional[str] = None
    notes: Optional[str] = None


class ShipmentUpdate(BaseModel):
    origin_address: Optional[str] = None
    origin_city: Optional[str] = None
    dest_address: Optional[str] = None
    dest_city: Optional[str] = None
    status: Optional[str] = None
    carrier_id: Optional[str] = None
    notes: Optional[str] = None
    actual_delivery: Optional[datetime] = None


# ==========================================
# AGENTS
# ==========================================

class AgentActivity(BaseModel):
    id: str
    timestamp: datetime
    type: str
    description: str
    status: str  # success, warning, error
    metadata: Optional[Dict[str, Any]] = None


class AgentDetail(BaseModel):
    id: str
    name: str
    status: str
    activity_level: int  # 0-100
    last_activity: Optional[datetime] = None
    current_task: Optional[str] = None
    recent_activities: List[AgentActivity]
    suggestion: Optional[Dict[str, Any]] = None


# ==========================================
# REVENUE & ECONOMICS
# ==========================================

class RevenueMetrics(BaseModel):
    mrr: Decimal  # Monthly Recurring Revenue
    arr: Decimal  # Annual Recurring Revenue
    last_month_revenue: Decimal
    last_3_months_avg: Decimal
    growth_rate_mom: float  # Month over month
    ytd_revenue: Decimal
    projected_next_month: Decimal


class CurrentLevel(BaseModel):
    level_id: str
    level_name: str
    mrr: Decimal
    max_burn: Decimal
    cost_ratio: float
    active_components: List[str]
    disabled_components: List[str]
    next_level: Optional[Dict[str, Any]] = None


class CostBreakdown(BaseModel):
    category: str
    amount: Decimal
    percentage: float


class RevenueTimeSeries(BaseModel):
    timestamp: str
    revenue: Decimal
    costs: Decimal


class RouteMetrics(BaseModel):
    route: str
    shipments: int
    revenue: Decimal
    margin: Decimal


class HourlyMetrics(BaseModel):
    hour: int
    orders: int
    revenue: Decimal


class SimulationRequest(BaseModel):
    projected_mrr: Decimal


class SimulationResponse(BaseModel):
    current_level: str
    simulated_level: str
    triggers: List[Dict[str, Any]]
    projected_costs: Dict[str, Decimal]


# ==========================================
# COMMANDS
# ==========================================

class ChangeCarrierRequest(BaseModel):
    shipment_id: str
    new_carrier_id: str
    reason: str


class ChangeCarrierResponse(BaseModel):
    success: bool
    shipment_id: str
    old_carrier: str
    new_carrier: str
    estimated_delay: Optional[int] = None  # minutes
    message: str


class VetoPaoloRequest(BaseModel):
    suggestion_id: str
    rationale: str


class EmergencyStopRequest(BaseModel):
    reason: str
    scope: str = "all"  # all, paolo, giulia


class BlackFridayModeRequest(BaseModel):
    enabled: bool
    discount_percent: int = Field(ge=5, le=50)


class ForceLevelRequest(BaseModel):
    level: str  # auto, level_0_survival, etc.


# ==========================================
# WEBSOCKET
# ==========================================

class WebSocketMessage(BaseModel):
    type: str  # shipment_update, carrier_position, agent_activity, revenue_update, etc.
    timestamp: datetime
    data: Dict[str, Any]


class ShipmentUpdateMessage(BaseModel):
    shipment_id: str
    status: Optional[str] = None
    current_position: Optional[Location] = None
    eta: Optional[datetime] = None


class CarrierPositionMessage(BaseModel):
    carrier_id: str
    position: Location
    heading: Optional[float] = None
    speed: Optional[float] = None