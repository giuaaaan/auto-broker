import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dashboardApi, agentsApi, revenueApi, commandApi, analyticsApi } from '@/api/client';
import type { Shipment, ChangeCarrierPayload, VetoPaoloPayload } from '@/types';

// ============================================
// DASHBOARD HOOKS
// ============================================

export const useDashboardStats = () => {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: dashboardApi.getStats,
    refetchInterval: 30000, // Refetch every 30 seconds
  });
};

export const useShipments = (params?: {
  page?: number;
  pageSize?: number;
  status?: string;
  search?: string;
}) => {
  return useQuery({
    queryKey: ['shipments', params],
    queryFn: () => dashboardApi.getShipments(params),
    refetchInterval: 10000,
  });
};

export const useShipment = (id: string) => {
  return useQuery({
    queryKey: ['shipment', id],
    queryFn: () => dashboardApi.getShipment(id),
    enabled: !!id,
  });
};

export const useCreateShipment = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: dashboardApi.createShipment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shipments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
    },
  });
};

export const useUpdateShipment = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Shipment> }) =>
      dashboardApi.updateShipment(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['shipments'] });
      queryClient.invalidateQueries({ queryKey: ['shipment', variables.id] });
    },
  });
};

// ============================================
// AGENTS HOOKS
// ============================================

export const useAgents = () => {
  return useQuery({
    queryKey: ['agents'],
    queryFn: agentsApi.getStatus,
    refetchInterval: 5000,
  });
};

export const useAgent = (id: string) => {
  return useQuery({
    queryKey: ['agent', id],
    queryFn: () => agentsApi.getAgent(id),
    enabled: !!id,
  });
};

export const useAgentLogs = (id: string, limit: number = 50) => {
  return useQuery({
    queryKey: ['agent', id, 'logs', limit],
    queryFn: () => agentsApi.getAgentLogs(id, limit),
    enabled: !!id,
  });
};

// ============================================
// REVENUE HOOKS
// ============================================

export const useCurrentLevel = () => {
  return useQuery({
    queryKey: ['revenue', 'current'],
    queryFn: revenueApi.getCurrent,
    refetchInterval: 60000,
  });
};

export const useRevenueMetrics = () => {
  return useQuery({
    queryKey: ['revenue', 'metrics'],
    queryFn: revenueApi.getMetrics,
    refetchInterval: 60000,
  });
};

export const useSimulateRevenue = () => {
  return useMutation({
    mutationFn: revenueApi.simulate,
  });
};

// ============================================
// COMMAND HOOKS
// ============================================

export const useChangeCarrier = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: commandApi.changeCarrier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shipments'] });
    },
  });
};

export const useVetoPaolo = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: commandApi.vetoPaolo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
};

export const useEmergencyStop = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: commandApi.emergencyStop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
    },
  });
};

export const useResumeOperations = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: commandApi.resumeOperations,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
};

export const useForceLevel = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: commandApi.forceLevel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue', 'current'] });
    },
  });
};

export const useToggleBlackFriday = () => {
  return useMutation({
    mutationFn: ({ enabled, discountPercent }: { enabled: boolean; discountPercent: number }) =>
      commandApi.toggleBlackFriday(enabled, discountPercent),
  });
};

// ============================================
// ANALYTICS HOOKS
// ============================================

export const useRevenueTimeSeries = (days: number = 30) => {
  return useQuery({
    queryKey: ['analytics', 'revenue-timeseries', days],
    queryFn: () => analyticsApi.getRevenueTimeSeries(days),
  });
};

export const useRouteMetrics = () => {
  return useQuery({
    queryKey: ['analytics', 'route-metrics'],
    queryFn: analyticsApi.getRouteMetrics,
  });
};

export const useHourlyMetrics = () => {
  return useQuery({
    queryKey: ['analytics', 'hourly'],
    queryFn: analyticsApi.getHourlyMetrics,
  });
};