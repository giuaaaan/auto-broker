import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Package, Truck, AlertTriangle, Filter, Search, MapPin } from 'lucide-react';
import { useShipments } from '@/hooks/useDashboard';
import { useUIStore, useDashboardStore } from '@/store';
import { formatCurrency, formatStatus, getStatusColor, formatPercent } from '@/utils/formatters';
import type { Shipment, ShipmentStatus } from '@/types';

const filters: { value: ShipmentStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Tutte' },
  { value: 'in_transit', label: 'In Transito' },
  { value: 'pending', label: 'In Attesa' },
  { value: 'delivered', label: 'Consegnate' },
  { value: 'disputed', label: 'Critiche' },
];

export const ShipmentsPanel = () => {
  const [activeFilter, setActiveFilter] = useState<ShipmentStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  const { data, isLoading } = useShipments({
    status: activeFilter === 'all' ? undefined : activeFilter,
    search: searchQuery || undefined,
  });
  
  const { openModal } = useUIStore();
  const { setSelectedShipmentId } = useDashboardStore();

  const shipments = data?.items || [];

  const handleShipmentClick = (shipment: Shipment) => {
    setSelectedShipmentId(shipment.id);
    openModal('shipmentDetails', shipment);
  };

  if (isLoading) {
    return (
      <div className="glass-panel p-4 h-[600px]">
        <div className="skeleton h-10 w-full mb-4 rounded-lg" />
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton h-24 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4 h-[600px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold flex items-center gap-2">
          <Package className="w-5 h-5 text-primary" />
          Spedizioni Attive
          <span className="badge badge-primary">{shipments.length}</span>
        </h3>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
        <input
          type="text"
          placeholder="Cerca spedizione..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="input-glass w-full pl-10"
        />
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-2 scrollbar-hide">
        {filters.map((filter) => (
          <button
            key={filter.value}
            onClick={() => setActiveFilter(filter.value)}
            className={`
              px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all
              ${
                activeFilter === filter.value
                  ? 'bg-primary/20 text-primary border border-primary/50'
                  : 'bg-surface text-text-secondary border border-border hover:text-text-primary'
              }
            `}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {/* Shipments List */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        <AnimatePresence mode="popLayout">
          {shipments.map((shipment, index) => (
            <ShipmentCard
              key={shipment.id}
              shipment={shipment}
              index={index}
              onClick={() => handleShipmentClick(shipment)}
            />
          ))}
        </AnimatePresence>
        
        {shipments.length === 0 && (
          <div className="text-center py-12 text-text-secondary">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Nessuna spedizione trovata</p>
          </div>
        )}
      </div>
    </div>
  );
};

interface ShipmentCardProps {
  shipment: Shipment;
  index: number;
  onClick: () => void;
}

const ShipmentCard = ({ shipment, index, onClick }: ShipmentCardProps) => {
  const statusColor = getStatusColor(shipment.status);
  const isCritical = shipment.status === 'disputed' || shipment.marginPercent < 10;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ delay: index * 0.05 }}
      onClick={onClick}
      className={`
        p-4 rounded-xl border cursor-pointer card-hover
        ${isCritical ? 'bg-danger/5 border-danger/30' : 'bg-surface border-border'}
      `}
    >
      <div className="flex items-start justify-between">
        {/* Left: Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm text-text-secondary">
              #{shipment.trackingNumber}
            </span>
            {isCritical && (
              <AlertTriangle className="w-4 h-4 text-danger" />
            )}
          </div>
          
          <div className="flex items-center gap-2 text-sm mb-2">
            <span className="text-text-primary font-medium truncate">
              {shipment.origin.city}
            </span>
            <span className="text-text-secondary">→</span>
            <span className="text-text-primary font-medium truncate">
              {shipment.destination.city}
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1 text-text-secondary">
              <Truck className="w-3 h-3" />
              {shipment.carrier.name}
            </div>
            <div
              className="px-2 py-0.5 rounded-full font-medium"
              style={{
                background: `${statusColor}20`,
                color: statusColor,
              }}
            >
              {formatStatus(shipment.status)}
            </div>
          </div>
        </div>

        {/* Right: Margin & Value */}
        <div className="text-right ml-4">
          <p className="font-mono font-semibold text-text-primary">
            {formatCurrency(shipment.value)}
          </p>
          <p
            className={`text-xs font-medium ${
              shipment.marginPercent >= 25
                ? 'text-success'
                : shipment.marginPercent >= 15
                ? 'text-warning'
                : 'text-danger'
            }`}
          >
            Margine: {formatPercent(shipment.marginPercent)}
          </p>
        </div>
      </div>

      {/* Action Buttons (visible on hover) */}
      <div className="mt-3 pt-3 border-t border-border flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button className="btn-primary text-xs py-1.5">
          Cambia Carrier
        </button>
        <button className="text-xs px-3 py-1.5 text-text-secondary hover:text-text-primary transition-colors">
          Modifica
        </button>
        <button className="text-xs px-3 py-1.5 text-text-secondary hover:text-primary transition-colors flex items-center gap-1">
          <MapPin className="w-3 h-3" />
          Traccia
        </button>
      </div>
    </motion.div>
  );
};