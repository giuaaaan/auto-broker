import axios from 'axios';
import type { 
  ApiResponse, 
  PaginatedResponse, 
  Shipment, 
  DashboardStats, 
  Agent, 
  CurrentLevel,
  RevenueMetrics,
  User,
  ChangeCarrierPayload,
  VetoPaoloPayload,
  EmergencyStopPayload,
} from '@/types';

// ============================================
// AXIOS INSTANCE
// ============================================

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor - Add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - Handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ============================================
// AUTH API
// ============================================

export const authApi = {
  login: async (email: string, password: string): Promise<{ token: string; user: User }> => {
    const response = await api.post<ApiResponse<{ token: string; user: User }>>('/auth/login', {
      email,
      password,
    });
    return response.data.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  me: async (): Promise<User> => {
    const response = await api.get<ApiResponse<User>>('/auth/me');
    return response.data.data;
  },

  refresh: async (): Promise<{ token: string }> => {
    const response = await api.post<ApiResponse<{ token: string }>>('/auth/refresh');
    return response.data.data;
  },
};

// ============================================
// DASHBOARD API
// ============================================

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const response = await api.get<ApiResponse<DashboardStats>>('/dashboard/stats');
    return response.data.data;
  },

  getShipments: async (params?: {
    page?: number;
    pageSize?: number;
    status?: string;
    search?: string;
  }): Promise<PaginatedResponse<Shipment>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<Shipment>>>('/shipments', {
      params,
    });
    return response.data.data;
  },

  getShipment: async (id: string): Promise<Shipment> => {
    const response = await api.get<ApiResponse<Shipment>>(`/shipments/${id}`);
    return response.data.data;
  },

  createShipment: async (data: Partial<Shipment>): Promise<Shipment> => {
    const response = await api.post<ApiResponse<Shipment>>('/shipments', data);
    return response.data.data;
  },

  updateShipment: async (id: string, data: Partial<Shipment>): Promise<Shipment> => {
    const response = await api.put<ApiResponse<Shipment>>(`/shipments/${id}`, data);
    return response.data.data;
  },

  deleteShipment: async (id: string): Promise<void> => {
    await api.delete(`/shipments/${id}`);
  },
};

// ============================================
// AGENTS API
// ============================================

export const agentsApi = {
  getStatus: async (): Promise<Agent[]> => {
    const response = await api.get<ApiResponse<Agent[]>>('/agents/status');
    return response.data.data;
  },

  getAgent: async (id: string): Promise<Agent> => {
    const response = await api.get<ApiResponse<Agent>>(`/agents/${id}`);
    return response.data.data;
  },

  getAgentLogs: async (id: string, limit: number = 50): Promise<Agent['recentActivities']> => {
    const response = await api.get<ApiResponse<Agent['recentActivities']>>(`/agents/${id}/logs`, {
      params: { limit },
    });
    return response.data.data;
  },
};

// ============================================
// REVENUE API
// ============================================

export const revenueApi = {
  getCurrent: async (): Promise<CurrentLevel> => {
    const response = await api.get<ApiResponse<CurrentLevel>>('/revenue/current');
    return response.data.data;
  },

  getMetrics: async (): Promise<RevenueMetrics> => {
    const response = await api.get<ApiResponse<RevenueMetrics>>('/revenue/metrics');
    return response.data.data;
  },

  simulate: async (projectedMrr: number): Promise<{
    currentLevel: string;
    simulatedLevel: string;
    triggers: unknown[];
    projectedCosts: unknown;
  }> => {
    const response = await api.post<ApiResponse<{
      currentLevel: string;
      simulatedLevel: string;
      triggers: unknown[];
      projectedCosts: unknown;
    }>>('/economics/simulate', { projected_mrr: projectedMrr });
    return response.data.data;
  },

  updateThresholds: async (levelId: string, config: {
    revenueMin?: number;
    revenueMax?: number;
    maxMonthlyBurn?: number;
  }): Promise<void> => {
    await api.put(`/revenue/thresholds/${levelId}`, config);
  },
};

// ============================================
// COMMAND API
// ============================================

export const commandApi = {
  changeCarrier: async (payload: ChangeCarrierPayload): Promise<void> => {
    await api.post('/command/change-carrier', payload);
  },

  vetoPaolo: async (payload: VetoPaoloPayload): Promise<void> => {
    await api.post('/command/veto-paolo', payload);
  },

  emergencyStop: async (payload: EmergencyStopPayload): Promise<void> => {
    await api.post('/command/emergency-stop', payload);
  },

  resumeOperations: async (scope: 'all' | 'paolo' | 'giulia'): Promise<void> => {
    await api.post('/command/resume', { scope });
  },

  forceLevel: async (level: string): Promise<void> => {
    await api.post('/command/force-level', { level });
  },

  toggleBlackFriday: async (enabled: boolean, discountPercent: number): Promise<void> => {
    await api.post('/command/black-friday', { enabled, discount_percent: discountPercent });
  },
};

// ============================================
// ANALYTICS API
// ============================================

export const analyticsApi = {
  getRevenueTimeSeries: async (days: number = 30): Promise<{
    revenue: { timestamp: string; value: number }[];
    costs: { timestamp: string; value: number }[];
  }> => {
    const response = await api.get<ApiResponse<{
      revenue: { timestamp: string; value: number }[];
      costs: { timestamp: string; value: number }[];
    }>>('/analytics/revenue-timeseries', {
      params: { days },
    });
    return response.data.data;
  },

  getRouteMetrics: async (): Promise<{
    route: string;
    shipments: number;
    revenue: number;
    margin: number;
  }[]> => {
    const response = await api.get<ApiResponse<{
      route: string;
      shipments: number;
      revenue: number;
      margin: number;
    }[]>>('/analytics/route-metrics');
    return response.data.data;
  },

  getHourlyMetrics: async (): Promise<{
    hour: number;
    orders: number;
    revenue: number;
  }[]> => {
    const response = await api.get<ApiResponse<{
      hour: number;
      orders: number;
      revenue: number;
    }[]>>('/analytics/hourly');
    return response.data.data;
  },
};

export default api;