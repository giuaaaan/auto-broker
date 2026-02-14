// ============================================
// AUTO-BROKER MISSION CONTROL CENTER TYPES
// ============================================

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'operator' | 'viewer';
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// ============================================
// SHIPMENTS
// ============================================

export type ShipmentStatus = 
  | 'pending' 
  | 'confirmed' 
  | 'in_transit' 
  | 'delivered' 
  | 'cancelled'
  | 'disputed';

export type CarrierType = 
  | 'truck' 
  | 'van' 
  | 'express' 
  | 'rail' 
  | 'air';

export interface Location {
  lat: number;
  lng: number;
  address: string;
  city: string;
  country: string;
}

export interface Carrier {
  id: string;
  name: string;
  type: CarrierType;
  rating: number;
  pricePerKm: number;
  available: boolean;
  currentLocation?: Location;
}

export interface Shipment {
  id: string;
  trackingNumber: string;
  origin: Location;
  destination: Location;
  carrier: Carrier;
  status: ShipmentStatus;
  weight: number;
  volume: number;
  value: number;
  margin: number;
  marginPercent: number;
  createdAt: string;
  estimatedDelivery: string;
  actualDelivery?: string;
  distanceKm: number;
  currentPosition?: {
    lat: number;
    lng: number;
    updatedAt: string;
  };
  route?: {
    coordinates: [number, number][];
    distance: number;
    duration: number;
  };
  customerName: string;
  customerEmail: string;
  notes?: string;
}

// ============================================
// REVENUE & ECONOMICS
// ============================================

export type EconomicLevel = 
  | 'level_0_survival'
  | 'level_1_bootstrap' 
  | 'level_2_growth'
  | 'level_3_scale'
  | 'level_4_enterprise';

export interface RevenueMetrics {
  mrr: number;
  arr: number;
  lastMonthRevenue: number;
  last3MonthsAvg: number;
  growthRateMoM: number;
  growthRateQoQ: number;
  ytdRevenue: number;
  projectedNextMonth: number;
}

export interface EconomicLevelConfig {
  id: EconomicLevel;
  name: string;
  revenueMin: number;
  revenueMax: number | null;
  maxMonthlyBurn: number;
  activeComponents: string[];
  disabledComponents: string[];
  requiredConsecutiveMonths: number;
}

export interface CurrentLevel {
  levelId: EconomicLevel;
  levelName: string;
  mrr: number;
  maxBurn: number;
  costRatio: number;
  activeComponents: string[];
  disabledComponents: string[];
  nextLevel: {
    id: EconomicLevel;
    threshold: number;
    progress: number;
  } | null;
}

// ============================================
// AI AGENTS
// ============================================

export type AgentType = 'SARA' | 'MARCO' | 'PAOLO' | 'GIULIA';

export type AgentStatus = 
  | 'active' 
  | 'standby' 
  | 'processing' 
  | 'warning' 
  | 'error';

export interface AgentActivity {
  id: string;
  timestamp: string;
  type: string;
  description: string;
  status: 'success' | 'warning' | 'error';
  metadata?: Record<string, unknown>;
}

export interface Agent {
  id: AgentType;
  name: string;
  status: AgentStatus;
  activityLevel: number; // 0-100
  lastActivity?: string;
  currentTask?: string;
  recentActivities: AgentActivity[];
  suggestion?: {
    id: string;
    title: string;
    description: string;
    priority: 'low' | 'medium' | 'high' | 'urgent';
    shipmentId?: string;
    actions: {
      label: string;
      action: string;
    }[];
  };
}

export interface PaoloSuggestion {
  id: string;
  shipmentId: string;
  currentCarrier: Carrier;
  suggestedCarrier: Carrier;
  reason: string;
  savings: number;
  confidence: number;
  vetoWindowSeconds: number;
}

// ============================================
// DASHBOARD STATS
// ============================================

export interface DashboardStats {
  totalShipments: number;
  activeShipments: number;
  deliveredToday: number;
  revenueToday: number;
  marginToday: number;
  avgDeliveryTime: number;
  onTimeRate: number;
  activeCarriers: number;
  alertsCount: number;
}

export interface TimeSeriesData {
  timestamp: string;
  value: number;
}

export interface RevenueTimeSeries {
  revenue: TimeSeriesData[];
  costs: TimeSeriesData[];
  profit: TimeSeriesData[];
}

export interface RouteMetrics {
  route: string;
  shipments: number;
  revenue: number;
  margin: number;
  marginPercent: number;
}

export interface HourlyMetrics {
  hour: number;
  orders: number;
  revenue: number;
}

// ============================================
// WEBSOCKET
// ============================================

export type WebSocketStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

export interface WebSocketMessage {
  type: 'shipment_update' | 'carrier_position' | 'agent_activity' | 'revenue_update' | 'paolo_suggestion' | 'system_alert';
  timestamp: string;
  data: unknown;
}

export interface ShipmentUpdateMessage {
  shipmentId: string;
  status: ShipmentStatus;
  currentPosition?: {
    lat: number;
    lng: number;
  };
  eta?: string;
}

export interface CarrierPositionMessage {
  carrierId: string;
  position: {
    lat: number;
    lng: number;
  };
  heading?: number;
  speed?: number;
}

// ============================================
// MAP
// ============================================

export interface MapMarker {
  id: string;
  type: 'origin' | 'destination' | 'carrier';
  position: [number, number];
  label: string;
  status?: ShipmentStatus;
  shipmentId?: string;
  carrierId?: string;
}

export interface MapRoute {
  id: string;
  coordinates: [number, number][];
  color: string;
  animated?: boolean;
  shipmentId?: string;
}

// ============================================
// UI STATE
// ============================================

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

export interface ModalState {
  isOpen: boolean;
  type: string | null;
  data?: unknown;
}

export interface FilterState {
  status: ShipmentStatus[];
  carrier: string[];
  dateRange: {
    from: string | null;
    to: string | null;
  };
  minMargin: number | null;
  search: string;
}

// ============================================
// API RESPONSES
// ============================================

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ============================================
// COMMAND CENTER
// ============================================

export interface EmergencyStopPayload {
  reason: string;
  operatorId: string;
  scope: 'all' | 'paolo' | 'giulia';
}

export interface ChangeCarrierPayload {
  shipmentId: string;
  newCarrierId: string;
  reason: string;
}

export interface VetoPaoloPayload {
  suggestionId: string;
  operatorId: string;
  rationale: string;
}

export interface BlackFridayMode {
  enabled: boolean;
  discountPercent: number;
  startDate: string;
  endDate: string;
}