import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  AuthState,
  User,
  Shipment,
  Agent,
  DashboardStats,
  CurrentLevel,
  RevenueMetrics,
  Toast,
  ModalState,
  FilterState,
  WebSocketStatus,
  MapMarker,
  MapRoute,
  EconomicLevel,
} from '@/types';

// ============================================
// AUTH STORE
// ============================================

interface AuthStore extends AuthState {
  login: (user: User, token: string) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      login: (user, token) => set({ user, token, isAuthenticated: true, isLoading: false }),
      logout: () => set({ user: null, token: null, isAuthenticated: false, isLoading: false }),
      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

// ============================================
// DASHBOARD STORE
// ============================================

interface DashboardStore {
  stats: DashboardStats | null;
  shipments: Shipment[];
  agents: Agent[];
  currentLevel: CurrentLevel | null;
  revenueMetrics: RevenueMetrics | null;
  isLoading: boolean;
  selectedShipmentId: string | null;
  
  // Actions
  setStats: (stats: DashboardStats) => void;
  setShipments: (shipments: Shipment[]) => void;
  updateShipment: (shipment: Shipment) => void;
  addShipment: (shipment: Shipment) => void;
  setAgents: (agents: Agent[]) => void;
  updateAgent: (agent: Agent) => void;
  setCurrentLevel: (level: CurrentLevel) => void;
  setRevenueMetrics: (metrics: RevenueMetrics) => void;
  setLoading: (loading: boolean) => void;
  setSelectedShipmentId: (id: string | null) => void;
  updateShipmentPosition: (shipmentId: string, lat: number, lng: number) => void;
  updateShipmentStatus: (shipmentId: string, status: string) => void;
}

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  stats: null,
  shipments: [],
  agents: [],
  currentLevel: null,
  revenueMetrics: null,
  isLoading: false,
  selectedShipmentId: null,

  setStats: (stats) => set({ stats }),
  setShipments: (shipments) => set({ shipments }),
  updateShipment: (shipment) => set((state) => ({
    shipments: state.shipments.map((s) => s.id === shipment.id ? shipment : s),
  })),
  addShipment: (shipment) => set((state) => ({
    shipments: [shipment, ...state.shipments],
  })),
  setAgents: (agents) => set({ agents }),
  updateAgent: (agent) => set((state) => ({
    agents: state.agents.map((a) => a.id === agent.id ? agent : a),
  })),
  setCurrentLevel: (level) => set({ currentLevel: level }),
  setRevenueMetrics: (metrics) => set({ revenueMetrics: metrics }),
  setLoading: (loading) => set({ isLoading: loading }),
  setSelectedShipmentId: (id) => set({ selectedShipmentId: id }),
  
  updateShipmentPosition: (shipmentId, lat, lng) => set((state) => ({
    shipments: state.shipments.map((s) =>
      s.id === shipmentId
        ? { ...s, currentPosition: { lat, lng, updatedAt: new Date().toISOString() } }
        : s
    ),
  })),
  
  updateShipmentStatus: (shipmentId, status) => set((state) => ({
    shipments: state.shipments.map((s) =>
      s.id === shipmentId ? { ...s, status: status as Shipment['status'] } : s
    ),
  })),
}));

// ============================================
// WEBSOCKET STORE
// ============================================

interface WebSocketStore {
  status: WebSocketStatus;
  latency: number;
  lastMessage: Date | null;
  reconnectAttempts: number;
  
  // Actions
  setStatus: (status: WebSocketStatus) => void;
  setLatency: (latency: number) => void;
  setLastMessage: (date: Date) => void;
  incrementReconnectAttempts: () => void;
  resetReconnectAttempts: () => void;
}

export const useWebSocketStore = create<WebSocketStore>((set) => ({
  status: 'disconnected',
  latency: 0,
  lastMessage: null,
  reconnectAttempts: 0,
  
  setStatus: (status) => set({ status }),
  setLatency: (latency) => set({ latency }),
  setLastMessage: (date) => set({ lastMessage: date }),
  incrementReconnectAttempts: () => set((state) => ({ reconnectAttempts: state.reconnectAttempts + 1 })),
  resetReconnectAttempts: () => set({ reconnectAttempts: 0 }),
}));

// ============================================
// MAP STORE
// ============================================

interface MapStore {
  markers: MapMarker[];
  routes: MapRoute[];
  selectedMarker: string | null;
  viewMode: '2d' | '3d';
  showHeatmap: boolean;
  showClusters: boolean;
  
  // Actions
  setMarkers: (markers: MapMarker[]) => void;
  addMarker: (marker: MapMarker) => void;
  updateMarker: (id: string, updates: Partial<MapMarker>) => void;
  removeMarker: (id: string) => void;
  setRoutes: (routes: MapRoute[]) => void;
  addRoute: (route: MapRoute) => void;
  setSelectedMarker: (id: string | null) => void;
  setViewMode: (mode: '2d' | '3d') => void;
  toggleHeatmap: () => void;
  toggleClusters: () => void;
}

export const useMapStore = create<MapStore>((set) => ({
  markers: [],
  routes: [],
  selectedMarker: null,
  viewMode: '2d',
  showHeatmap: false,
  showClusters: true,
  
  setMarkers: (markers) => set({ markers }),
  addMarker: (marker) => set((state) => ({ markers: [...state.markers, marker] })),
  updateMarker: (id, updates) => set((state) => ({
    markers: state.markers.map((m) => m.id === id ? { ...m, ...updates } : m),
  })),
  removeMarker: (id) => set((state) => ({
    markers: state.markers.filter((m) => m.id !== id),
  })),
  setRoutes: (routes) => set({ routes }),
  addRoute: (route) => set((state) => ({ routes: [...state.routes, route] })),
  setSelectedMarker: (id) => set({ selectedMarker: id }),
  setViewMode: (mode) => set({ viewMode: mode }),
  toggleHeatmap: () => set((state) => ({ showHeatmap: !state.showHeatmap })),
  toggleClusters: () => set((state) => ({ showClusters: !state.showClusters })),
}));

// ============================================
// UI STORE
// ============================================

interface UIStore {
  toasts: Toast[];
  modal: ModalState;
  sidebarOpen: boolean;
  filterPanelOpen: boolean;
  filter: FilterState;
  
  // Actions
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  openModal: (type: string, data?: unknown) => void;
  closeModal: () => void;
  toggleSidebar: () => void;
  toggleFilterPanel: () => void;
  setFilter: (filter: Partial<FilterState>) => void;
  resetFilters: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  toasts: [],
  modal: { isOpen: false, type: null },
  sidebarOpen: true,
  filterPanelOpen: false,
  filter: {
    status: [],
    carrier: [],
    dateRange: { from: null, to: null },
    minMargin: null,
    search: '',
  },
  
  addToast: (toast) => set((state) => ({
    toasts: [...state.toasts, { ...toast, id: Math.random().toString(36).substr(2, 9) }],
  })),
  
  removeToast: (id) => set((state) => ({
    toasts: state.toasts.filter((t) => t.id !== id),
  })),
  
  openModal: (type, data) => set({ modal: { isOpen: true, type, data } }),
  closeModal: () => set({ modal: { isOpen: false, type: null } }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  toggleFilterPanel: () => set((state) => ({ filterPanelOpen: !state.filterPanelOpen })),
  setFilter: (filter) => set((state) => ({ filter: { ...state.filter, ...filter } })),
  resetFilters: () => set({
    filter: {
      status: [],
      carrier: [],
      dateRange: { from: null, to: null },
      minMargin: null,
      search: '',
    },
  }),
}));

// ============================================
// COMMAND STORE (Emergency Controls)
// ============================================

interface CommandStore {
  emergencyStopActive: boolean;
  blackFridayMode: {
    enabled: boolean;
    discountPercent: number;
  };
  forcedLevel: EconomicLevel | 'auto';
  
  // Actions
  setEmergencyStop: (active: boolean) => void;
  setBlackFridayMode: (enabled: boolean, discountPercent?: number) => void;
  setForcedLevel: (level: EconomicLevel | 'auto') => void;
}

export const useCommandStore = create<CommandStore>((set) => ({
  emergencyStopActive: false,
  blackFridayMode: {
    enabled: false,
    discountPercent: 10,
  },
  forcedLevel: 'auto',
  
  setEmergencyStop: (active) => set({ emergencyStopActive: active }),
  setBlackFridayMode: (enabled, discountPercent = 10) => set({
    blackFridayMode: { enabled, discountPercent },
  }),
  setForcedLevel: (level) => set({ forcedLevel: level }),
}));