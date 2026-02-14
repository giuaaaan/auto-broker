import { format, formatDistanceToNow } from 'date-fns';
import { it } from 'date-fns/locale';

// ============================================
// CURRENCY FORMATTERS
// ============================================

export const formatCurrency = (
  value: number,
  currency: string = 'EUR',
  locale: string = 'it-IT'
): string => {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

export const formatCurrencyCompact = (value: number): string => {
  if (value >= 1_000_000) {
    return `€${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `€${(value / 1_000).toFixed(1)}K`;
  }
  return `€${value.toFixed(0)}`;
};

// ============================================
// NUMBER FORMATTERS
// ============================================

export const formatNumber = (value: number, decimals: number = 0): string => {
  return new Intl.NumberFormat('it-IT', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
};

export const formatPercent = (value: number, decimals: number = 1): string => {
  return `${value.toFixed(decimals)}%`;
};

export const formatCompact = (value: number): string => {
  return new Intl.NumberFormat('it-IT', {
    notation: 'compact',
  }).format(value);
};

// ============================================
// DATE FORMATTERS
// ============================================

export const formatDate = (date: string | Date, pattern: string = 'dd/MM/yyyy'): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return format(d, pattern, { locale: it });
};

export const formatDateTime = (date: string | Date): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return format(d, 'dd/MM/yyyy HH:mm', { locale: it });
};

export const formatRelative = (date: string | Date): string => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return formatDistanceToNow(d, { addSuffix: true, locale: it });
};

export const formatDuration = (minutes: number): string => {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  
  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
};

// ============================================
// SHIPMENT STATUS FORMATTERS
// ============================================

export const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'In Attesa', color: '#A0A0A0' },
  confirmed: { label: 'Confermata', color: '#00D9FF' },
  in_transit: { label: 'In Transito', color: '#FF6B00' },
  delivered: { label: 'Consegnata', color: '#00FF88' },
  cancelled: { label: 'Annullata', color: '#FF2D55' },
  disputed: { label: 'In Contestazione', color: '#FF2D55' },
};

export const formatStatus = (status: string): string => {
  return statusLabels[status]?.label || status;
};

export const getStatusColor = (status: string): string => {
  return statusLabels[status]?.color || '#A0A0A0';
};

// ============================================
// AGENT STATUS FORMATTERS
// ============================================

export const agentStatusLabels: Record<string, { label: string; color: string }> = {
  active: { label: 'Attivo', color: '#00FF88' },
  standby: { label: 'Standby', color: '#00D9FF' },
  processing: { label: 'Elaborazione', color: '#FF6B00' },
  warning: { label: 'Attenzione', color: '#FF6B00' },
  error: { label: 'Errore', color: '#FF2D55' },
};

export const formatAgentStatus = (status: string): string => {
  return agentStatusLabels[status]?.label || status;
};

export const getAgentStatusColor = (status: string): string => {
  return agentStatusLabels[status]?.color || '#A0A0A0';
};

// ============================================
// ECONOMIC LEVEL FORMATTERS
// ============================================

export const levelLabels: Record<string, string> = {
  level_0_survival: 'Sopravvivenza',
  level_1_bootstrap: 'Bootstrap',
  level_2_growth: 'Crescita',
  level_3_scale: 'Scala',
  level_4_enterprise: 'Enterprise',
};

export const formatLevel = (levelId: string): string => {
  return levelLabels[levelId] || levelId;
};

export const getLevelColor = (levelId: string): string => {
  const colors: Record<string, string> = {
    level_0_survival: '#A0A0A0',
    level_1_bootstrap: '#00D9FF',
    level_2_growth: '#00FF88',
    level_3_scale: '#FF6B00',
    level_4_enterprise: '#FFD700',
  };
  return colors[levelId] || '#A0A0A0';
};

// ============================================
// WEBSOCKET STATUS FORMATTERS
// ============================================

export const wsStatusLabels: Record<string, { label: string; color: string }> = {
  connected: { label: 'LIVE', color: '#00FF88' },
  connecting: { label: 'CONN...', color: '#FF6B00' },
  disconnected: { label: 'OFFLINE', color: '#A0A0A0' },
  error: { label: 'ERROR', color: '#FF2D55' },
};

// ============================================
// VALIDATORS
// ============================================

export const isValidEmail = (email: string): boolean => {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
};

export const isValidTrackingNumber = (tracking: string): boolean => {
  return tracking.length >= 5 && /^[A-Z0-9-]+$/i.test(tracking);
};

// ============================================
// HELPERS
// ============================================

export const truncate = (str: string, maxLength: number): string => {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength) + '...';
};

export const generateTrackingNumber = (): string => {
  const prefix = 'AB';
  const timestamp = Date.now().toString(36).toUpperCase();
  const random = Math.random().toString(36).substring(2, 5).toUpperCase();
  return `${prefix}-${timestamp}-${random}`;
};

export const calculateProgress = (current: number, target: number): number => {
  if (target === 0) return 0;
  return Math.min((current / target) * 100, 100);
};

export const debounce = <T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

export const throttle = <T extends (...args: unknown[]) => unknown>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle = false;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
};