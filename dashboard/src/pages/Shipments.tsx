import { useState } from 'react';
import { motion } from 'framer-motion';
import { Plus, Search, Filter, Package } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useShipments } from '@/hooks/useDashboard';
import { useUIStore } from '@/store';
import { formatCurrency, formatStatus, getStatusColor } from '@/utils/formatters';
import type { Shipment, ShipmentStatus } from '@/types';

const statusFilters: { value: ShipmentStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Tutte' },
  { value: 'pending', label: 'In Attesa' },
  { value: 'confirmed', label: 'Confermate' },
  { value: 'in_transit', label: 'In Transito' },
  { value: 'delivered', label: 'Consegnate' },
  { value: 'cancelled', label: 'Annullate' },
];

const ShipmentsPage = () => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ShipmentStatus | 'all'>('all');
  const { openModal } = useUIStore();
  
  const { data, isLoading } = useShipments({
    search: search || undefined,
    status: statusFilter === 'all' ? undefined : statusFilter,
  });

  const shipments = data?.items || [];

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h1 className="text-2xl font-bold">Spedizioni</h1>
            <p className="text-text-secondary text-sm">
              Gestisci tutte le spedizioni del sistema
            </p>
          </div>
          
          <button
            onClick={() => openModal('createShipment')}
            className="btn-success flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Nuova Spedizione
          </button>
        </header>

        {/* Filters */}
        <div className="px-6 py-4 border-b border-border flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Cerca spedizione..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-glass w-full pl-10"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-text-secondary" />
            {statusFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => setStatusFilter(filter.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === filter.value
                    ? 'bg-primary/20 text-primary border border-primary/50'
                    : 'bg-surface text-text-secondary border border-border hover:text-text-primary'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        {/* Shipments Table */}
        <div className="flex-1 overflow-auto p-6">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="skeleton h-16 rounded-lg" />
              ))}
            </div>
          ) : shipments.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-16 h-16 mx-auto mb-4 text-text-secondary opacity-30" />
              <p className="text-text-secondary">Nessuna spedizione trovata</p>
            </div>
          ) : (
            <div className="glass-panel overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left p-4 text-sm font-medium text-text-secondary">Tracking</th>
                    <th className="text-left p-4 text-sm font-medium text-text-secondary">Rotta</th>
                    <th className="text-left p-4 text-sm font-medium text-text-secondary">Carrier</th>
                    <th className="text-left p-4 text-sm font-medium text-text-secondary">Stato</th>
                    <th className="text-right p-4 text-sm font-medium text-text-secondary">Valore</th>
                    <th className="text-right p-4 text-sm font-medium text-text-secondary">Margine</th>
                    <th className="text-left p-4 text-sm font-medium text-text-secondary">Azioni</th>
                  </tr>
                </thead>
                <tbody>
                  {shipments.map((shipment) => (
                    <tr
                      key={shipment.id}
                      className="border-b border-border hover:bg-surface/50 transition-colors"
                    >
                      <td className="p-4">
                        <span className="font-mono text-sm">#{shipment.trackingNumber}</span>
                      </td>
                      <td className="p-4">
                        <span className="text-sm">
                          {shipment.origin.city} → {shipment.destination.city}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className="text-sm">{shipment.carrier.name}</span>
                      </td>
                      <td className="p-4">
                        <span
                          className="px-2 py-1 rounded-full text-xs font-medium"
                          style={{
                            background: `${getStatusColor(shipment.status)}20`,
                            color: getStatusColor(shipment.status),
                          }}
                        >
                          {formatStatus(shipment.status)}
                        </span>
                      </td>
                      <td className="p-4 text-right font-mono">
                        {formatCurrency(shipment.value)}
                      </td>
                      <td className="p-4 text-right">
                        <span
                          className={`font-mono ${
                            shipment.marginPercent >= 25
                              ? 'text-success'
                              : shipment.marginPercent >= 15
                              ? 'text-warning'
                              : 'text-danger'
                          }`}
                        >
                          {shipment.marginPercent.toFixed(1)}%
                        </span>
                      </td>
                      <td className="p-4">
                        <button
                          onClick={() => openModal('shipmentDetails', shipment)}
                          className="text-primary hover:underline text-sm"
                        >
                          Dettagli
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ShipmentsPage;