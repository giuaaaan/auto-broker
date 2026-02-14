import { X, MapPin, Truck, Package, Clock, DollarSign, User, FileText } from 'lucide-react';
import { motion } from 'framer-motion';
import { useShipment, useUpdateShipment } from '@/hooks/useDashboard';
import { useMapStore, useUIStore } from '@/store';
import { formatCurrency, formatDateTime, formatStatus, getStatusColor } from '@/utils/formatters';
import { ModalHeader } from '../ui/ModalContainer';
import type { Shipment } from '@/types';

interface ShipmentDetailsModalProps {
  data: Shipment;
  onClose: () => void;
}

export const ShipmentDetailsModal = ({ data, onClose }: ShipmentDetailsModalProps) => {
  const { data: shipment, isLoading } = useShipment(data.id);
  const updateMutation = useUpdateShipment();
  const { setSelectedMarker } = useMapStore();
  const { addToast } = useUIStore();

  const s = shipment || data;

  const handleTrackOnMap = () => {
    setSelectedMarker(`${s.id}-carrier`);
    onClose();
  };

  const handleStatusChange = async (newStatus: string) => {
    try {
      await updateMutation.mutateAsync({ id: s.id, data: { status: newStatus } });
      addToast({
        type: 'success',
        title: 'Stato aggiornato',
        message: `Spedizione ${s.trackingNumber} aggiornata`,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile aggiornare lo stato',
      });
    }
  };

  return (
    <div className="w-full max-w-2xl">
      <ModalHeader title={`Spedizione #${s.trackingNumber}`} onClose={onClose} />
      
      <div className="p-6 max-h-[70vh] overflow-y-auto">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-20 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Status Badge */}
            <div className="flex items-center justify-between">
              <div
                className="px-4 py-2 rounded-lg font-medium"
                style={{
                  background: `${getStatusColor(s.status)}20`,
                  color: getStatusColor(s.status),
                }}
              >
                {formatStatus(s.status)}
              </div>
              <button
                onClick={handleTrackOnMap}
                className="btn-primary flex items-center gap-2"
              >
                <MapPin className="w-4 h-4" />
                Traccia sulla Mappa
              </button>
            </div>

            {/* Route Info */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-surface border border-border">
                <div className="flex items-center gap-2 text-text-secondary mb-2">
                  <MapPin className="w-4 h-4" />
                  <span className="text-sm">Origine</span>
                </div>
                <p className="font-semibold">{s.origin.city}</p>
                <p className="text-sm text-text-secondary">{s.origin.address}</p>
              </div>
              
              <div className="p-4 rounded-xl bg-surface border border-border">
                <div className="flex items-center gap-2 text-text-secondary mb-2">
                  <MapPin className="w-4 h-4" />
                  <span className="text-sm">Destinazione</span>
                </div>
                <p className="font-semibold">{s.destination.city}</p>
                <p className="text-sm text-text-secondary">{s.destination.address}</p>
              </div>
            </div>

            {/* Details Grid */}
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-surface border border-border text-center">
                <Truck className="w-5 h-5 mx-auto mb-2 text-primary" />
                <p className="text-xs text-text-secondary">Carrier</p>
                <p className="font-medium">{s.carrier.name}</p>
              </div>
              
              <div className="p-4 rounded-xl bg-surface border border-border text-center">
                <Package className="w-5 h-5 mx-auto mb-2 text-primary" />
                <p className="text-xs text-text-secondary">Peso</p>
                <p className="font-medium">{s.weight} kg</p>
              </div>
              
              <div className="p-4 rounded-xl bg-surface border border-border text-center">
                <DollarSign className="w-5 h-5 mx-auto mb-2 text-success" />
                <p className="text-xs text-text-secondary">Valore</p>
                <p className="font-medium">{formatCurrency(s.value)}</p>
              </div>
            </div>

            {/* Margin Info */}
            <div className="p-4 rounded-xl bg-surface border border-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-text-secondary">Margine</span>
                <span
                  className={`font-bold ${
                    s.marginPercent >= 25
                      ? 'text-success'
                      : s.marginPercent >= 15
                      ? 'text-warning'
                      : 'text-danger'
                  }`}
                >
                  {s.marginPercent.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 bg-surface rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    s.marginPercent >= 25
                      ? 'bg-success'
                      : s.marginPercent >= 15
                      ? 'bg-warning'
                      : 'bg-danger'
                  }`}
                  style={{ width: `${Math.min(s.marginPercent, 100)}%` }}
                />
              </div>
              <p className="text-right text-sm mt-1">{formatCurrency(s.margin)}</p>
            </div>

            {/* Customer Info */}
            <div className="p-4 rounded-xl bg-surface border border-border">
              <div className="flex items-center gap-2 text-text-secondary mb-2">
                <User className="w-4 h-4" />
                <span className="text-sm">Cliente</span>
              </div>
              <p className="font-semibold">{s.customerName}</p>
              <p className="text-sm text-text-secondary">{s.customerEmail}</p>
            </div>

            {/* Notes */}
            {s.notes && (
              <div className="p-4 rounded-xl bg-surface border border-border">
                <div className="flex items-center gap-2 text-text-secondary mb-2">
                  <FileText className="w-4 h-4" />
                  <span className="text-sm">Note</span>
                </div>
                <p className="text-sm">{s.notes}</p>
              </div>
            )}

            {/* Timestamps */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-text-secondary">Creato</p>
                <p>{formatDateTime(s.createdAt)}</p>
              </div>
              <div>
                <p className="text-text-secondary">Consegna stimata</p>
                <p>{formatDateTime(s.estimatedDelivery)}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="p-6 border-t border-border flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 text-text-secondary hover:text-text-primary">
          Chiudi
        </button>
        <button className="btn-primary">
          Modifica Spedizione
        </button>
      </div>
    </div>
  );
};