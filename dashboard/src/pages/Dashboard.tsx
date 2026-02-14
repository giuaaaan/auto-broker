import { useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Sidebar } from '@/components/layout/Sidebar';
import { RevenueHUD } from '@/components/panels/RevenueHUD';
import { AgentsPanel } from '@/components/panels/AgentsPanel';
import { ShipmentsPanel } from '@/components/panels/ShipmentsPanel';
import { CommandCenter } from '@/components/panels/CommandCenter';
import { Map2D } from '@/components/map/Map2D';
import { Globe3D } from '@/components/map/Globe3D';
import { useMapStore } from '@/store';
import { useShipments, useAgents, useDashboardStats } from '@/hooks/useDashboard';
import { Wifi, WifiOff, AlertCircle } from 'lucide-react';
import { useWebSocketStore, useUIStore } from '@/store';
import type { Shipment } from '@/types';

// WebSocket Status Indicator
const WebSocketStatus = () => {
  const { status, latency, lastMessage } = useWebSocketStore();

  const getIcon = () => {
    switch (status) {
      case 'connected':
        return <Wifi className="w-4 h-4 text-success" />;
      case 'connecting':
        return <Wifi className="w-4 h-4 text-warning animate-pulse" />;
      case 'error':
      case 'disconnected':
        return <WifiOff className="w-4 h-4 text-danger" />;
    }
  };

  const getLabel = () => {
    switch (status) {
      case 'connected':
        return `LIVE ${latency > 0 ? `${latency}ms` : ''}`;
      case 'connecting':
        return 'CONN...';
      case 'error':
        return 'ERROR';
      case 'disconnected':
        return 'OFFLINE';
    }
  };

  const getColor = () => {
    switch (status) {
      case 'connected':
        return 'text-success';
      case 'connecting':
        return 'text-warning';
      case 'error':
      case 'disconnected':
        return 'text-danger';
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-border">
      {getIcon()}
      <span className={`text-xs font-mono font-medium ${getColor()}`}>
        {getLabel()}
      </span>
      {lastMessage && (
        <span className="text-xs text-text-secondary">
          Last: {new Date(lastMessage).toLocaleTimeString('it-IT', { hour12: false })}
        </span>
      )}
    </div>
  );
};

// Main Dashboard Page
const DashboardPage = () => {
  const { viewMode, setMarkers, setRoutes } = useMapStore();
  const { openModal } = useUIStore();
  const { data: shipments } = useShipments();
  const { data: agents } = useAgents();
  const { data: stats } = useDashboardStats();

  // Update map markers when shipments change
  useEffect(() => {
    if (!shipments?.items) return;

    const markers = shipments.items.flatMap((shipment: Shipment) => [
      {
        id: `${shipment.id}-origin`,
        type: 'origin' as const,
        position: [shipment.origin.lng, shipment.origin.lat] as [number, number],
        label: shipment.origin.city,
        shipmentId: shipment.id,
      },
      {
        id: `${shipment.id}-dest`,
        type: 'destination' as const,
        position: [shipment.destination.lng, shipment.destination.lat] as [number, number],
        label: shipment.destination.city,
        shipmentId: shipment.id,
      },
      ...(shipment.currentPosition
        ? [
            {
              id: `${shipment.id}-carrier`,
              type: 'carrier' as const,
              position: [shipment.currentPosition.lng, shipment.currentPosition.lat] as [number, number],
              label: `${shipment.carrier.name} - ${shipment.trackingNumber}`,
              shipmentId: shipment.id,
              carrierId: shipment.carrier.id,
            },
          ]
        : []),
    ]);

    const routes = shipments.items
      .filter((s: Shipment) => s.route?.coordinates)
      .map((shipment: Shipment) => ({
        id: shipment.id,
        coordinates: shipment.route!.coordinates,
        color: '#00D9FF',
        animated: shipment.status === 'in_transit',
        shipmentId: shipment.id,
      }));

    setMarkers(markers);
    setRoutes(routes);
  }, [shipments, setMarkers, setRoutes]);

  const handleMarkerClick = useCallback((shipment: Shipment) => {
    openModal('shipmentDetails', shipment);
  }, [openModal]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h1 className="text-2xl font-bold">Mission Control Center</h1>
            <p className="text-text-secondary text-sm">
              Panoramica operativa in tempo reale
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <WebSocketStatus />
            
            {/* Quick Stats */}
            <div className="flex items-center gap-6 px-4 py-2 rounded-xl bg-surface border border-border">
              <div className="text-center">
                <p className="text-2xl font-bold number-mono text-success">
                  {stats?.activeShipments || 0}
                </p>
                <p className="text-xs text-text-secondary">Attive</p>
              </div>
              <div className="w-px h-8 bg-border" />
              <div className="text-center">
                <p className="text-2xl font-bold number-mono text-warning">
                  {stats?.alertsCount || 0}
                </p>
                <p className="text-xs text-text-secondary">Alert</p>
              </div>
              <div className="w-px h-8 bg-border" />
              <div className="text-center">
                <p className="text-2xl font-bold number-mono text-primary">
                  {agents?.filter((a) => a.status === 'active').length || 0}
                </p>
                <p className="text-xs text-text-secondary">Agenti</p>
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Grid */}
        <div className="flex-1 p-6 overflow-hidden">
          <div className="h-full grid grid-cols-12 gap-6">
            {/* Left Column - Agents */}
            <div className="col-span-3 flex flex-col gap-6 h-full overflow-hidden">
              <RevenueHUD />
              <div className="flex-1 overflow-hidden">
                <AgentsPanel />
              </div>
            </div>

            {/* Center Column - Map */}
            <div className="col-span-6 flex flex-col gap-6 h-full">
              <div className="flex-1 glass-panel p-1 rounded-xl overflow-hidden">
                {viewMode === '2d' ? (
                  <Map2D onMarkerClick={handleMarkerClick} />
                ) : (
                  <Globe3D onMarkerClick={handleMarkerClick} />
                )}
              </div>
              <CommandCenter />
            </div>

            {/* Right Column - Shipments */}
            <div className="col-span-3 h-full overflow-hidden">
              <ShipmentsPanel />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;