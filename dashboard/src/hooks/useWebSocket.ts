import { useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { useWebSocketStore, useDashboardStore, useUIStore, useMapStore } from '@/store';
import type { 
  WebSocketMessage, 
  ShipmentUpdateMessage, 
  CarrierPositionMessage,
  Agent,
} from '@/types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export const useWebSocket = () => {
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const { 
    status, 
    setStatus, 
    setLatency, 
    setLastMessage, 
    incrementReconnectAttempts, 
    resetReconnectAttempts 
  } = useWebSocketStore();
  
  const { 
    updateShipmentPosition, 
    updateShipmentStatus, 
    updateAgent,
    setRevenueMetrics,
  } = useDashboardStore();
  
  const { addToast } = useUIStore();
  const { updateMarker } = useMapStore();

  const connect = useCallback(() => {
    if (socketRef.current?.connected) return;
    
    setStatus('connecting');
    
    const token = localStorage.getItem('token');
    
    socketRef.current = io(`${WS_URL}/ws/command-center`, {
      transports: ['websocket'],
      auth: { token },
      reconnection: false, // We handle reconnection manually
    });

    const socket = socketRef.current;

    socket.on('connect', () => {
      console.log('[WebSocket] Connected');
      setStatus('connected');
      resetReconnectAttempts();
      addToast({
        type: 'success',
        title: 'Connessione stabilita',
        message: 'Dashboard in tempo reale attiva',
        duration: 3000,
      });
    });

    socket.on('disconnect', (reason) => {
      console.log('[WebSocket] Disconnected:', reason);
      setStatus('disconnected');
      
      if (reason === 'io server disconnect') {
        // Server forced disconnect, don't reconnect
        return;
      }
      
      // Attempt reconnection with exponential backoff
      incrementReconnectAttempts();
      const attempts = useWebSocketStore.getState().reconnectAttempts;
      const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
      
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    });

    socket.on('connect_error', (error) => {
      console.error('[WebSocket] Connection error:', error);
      setStatus('error');
    });

    // Handle incoming messages
    socket.on('shipment_update', (data: ShipmentUpdateMessage) => {
      console.log('[WebSocket] Shipment update:', data);
      setLastMessage(new Date());
      
      if (data.status) {
        updateShipmentStatus(data.shipmentId, data.status);
      }
      
      if (data.currentPosition) {
        updateShipmentPosition(
          data.shipmentId, 
          data.currentPosition.lat, 
          data.currentPosition.lng
        );
        
        // Update map marker
        updateMarker(`carrier-${data.shipmentId}`, {
          position: [data.currentPosition.lng, data.currentPosition.lat],
        });
      }
      
      // Show toast for important status changes
      if (['delivered', 'cancelled', 'disputed'].includes(data.status)) {
        addToast({
          type: data.status === 'delivered' ? 'success' : 'warning',
          title: `Spedizione ${data.status === 'delivered' ? 'consegnata' : 'aggiornata'}`,
          message: `ID: ${data.shipmentId}`,
          duration: 5000,
        });
      }
    });

    socket.on('carrier_position', (data: CarrierPositionMessage) => {
      setLastMessage(new Date());
      
      updateMarker(`carrier-${data.carrierId}`, {
        position: [data.position.lng, data.position.lat],
      });
    });

    socket.on('agent_activity', (data: { agentId: string; activity: Agent }) => {
      console.log('[WebSocket] Agent activity:', data);
      setLastMessage(new Date());
      updateAgent(data.activity);
      
      // Show toast for PAOLO suggestions
      if (data.agentId === 'PAOLO' && data.activity.suggestion) {
        addToast({
          type: 'warning',
          title: 'PAOLO suggerisce un\'azione',
          message: data.activity.suggestion.title,
          duration: 10000,
        });
      }
    });

    socket.on('revenue_update', (data: { mrr: number; growth: number }) => {
      console.log('[WebSocket] Revenue update:', data);
      setLastMessage(new Date());
      
      setRevenueMetrics({
        mrr: data.mrr,
        arr: data.mrr * 12,
        lastMonthRevenue: 0,
        last3MonthsAvg: 0,
        growthRateMoM: data.growth,
        growthRateQoQ: 0,
        ytdRevenue: 0,
        projectedNextMonth: data.mrr * (1 + data.growth),
      });
    });

    socket.on('system_alert', (data: { type: string; message: string; severity: string }) => {
      console.log('[WebSocket] System alert:', data);
      setLastMessage(new Date());
      
      addToast({
        type: data.severity as 'info' | 'warning' | 'error' | 'success',
        title: 'Alert di Sistema',
        message: data.message,
        duration: 10000,
      });
    });

    // Latency measurement
    socket.on('pong', () => {
      const start = (socket as any).pingStart;
      if (start) {
        setLatency(Date.now() - start);
      }
    });

  }, [setStatus, setLatency, setLastMessage, incrementReconnectAttempts, resetReconnectAttempts, 
      updateShipmentPosition, updateShipmentStatus, updateAgent, setRevenueMetrics, addToast, updateMarker]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (socketRef.current) {
      socketRef.current.removeAllListeners();
      socketRef.current.close();
      socketRef.current = null;
    }
    
    setStatus('disconnected');
  }, [setStatus]);

  const sendPing = useCallback(() => {
    if (socketRef.current?.connected) {
      (socketRef.current as any).pingStart = Date.now();
      socketRef.current.emit('ping');
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();
    
    // Ping every 30 seconds to measure latency
    const pingInterval = setInterval(sendPing, 30000);
    
    return () => {
      clearInterval(pingInterval);
      disconnect();
    };
  }, [connect, disconnect, sendPing]);

  return {
    status,
    connect,
    disconnect,
    sendPing,
  };
};

export default useWebSocket;