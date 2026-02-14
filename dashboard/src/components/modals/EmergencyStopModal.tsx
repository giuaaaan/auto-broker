import { useState } from 'react';
import { AlertOctagon, AlertTriangle } from 'lucide-react';
import { ModalHeader } from '../ui/ModalContainer';
import { useUIStore } from '@/store';

interface EmergencyStopModalProps {
  data: {
    onConfirm: (reason: string) => void;
  };
  onClose: () => void;
}

export const EmergencyStopModal = ({ data, onClose }: EmergencyStopModalProps) => {
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const { addToast } = useUIStore();

  const handleConfirm = () => {
    if (!reason.trim()) {
      addToast({
        type: 'error',
        title: 'Errore',
        message: 'Inserisci un motivo',
      });
      return;
    }
    
    data.onConfirm(reason);
    onClose();
  };

  return (
    <div className="w-full max-w-md">
      <div className="p-6 text-center">
        <div className="w-20 h-20 mx-auto rounded-full bg-danger/20 flex items-center justify-center mb-4">
          <AlertOctagon className="w-10 h-10 text-danger" />
        </div>
        
        <h2 className="text-2xl font-bold text-danger mb-2">EMERGENCY STOP</h2>
        <p className="text-text-secondary mb-6">
          Questa azione bloccherà immediatamente tutte le operazioni automatiche di PAOLO e GIULIA.
          Richiede autorizzazione manuale per riprendere.
        </p>

        <div className="space-y-4 text-left">
          <div>
            <label className="block text-sm font-medium mb-2">
              Motivo dell'emergency stop *
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Descrivi il motivo..."
              className="input-glass w-full h-24 resize-none"
            />
          </div>

          <label className="flex items-start gap-3 p-3 rounded-lg bg-danger/10 border border-danger/30 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-1"
            />
            <span className="text-sm">
              Confermo di voler attivare l'emergency stop. Sono consapevole che questa azione
              bloccherà tutte le operazioni AI e richiederà intervento manuale per ripristinare.
            </span>
          </label>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 rounded-xl bg-surface text-text-primary font-medium hover:bg-surface/80 transition-colors"
          >
            Annulla
          </button>
          <button
            onClick={handleConfirm}
            disabled={!confirmed || !reason.trim()}
            className="flex-1 px-4 py-3 rounded-xl bg-danger text-white font-medium hover:bg-danger/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            CONFERMA STOP
          </button>
        </div>
      </div>
    </div>
  );
};