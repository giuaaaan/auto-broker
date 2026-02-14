import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Plus, AlertCircle } from 'lucide-react';
import { ModalHeader } from '../ui/ModalContainer';
import { useCreateShipment } from '@/hooks/useDashboard';
import { useUIStore } from '@/store';
import { generateTrackingNumber } from '@/utils/formatters';

const createShipmentSchema = z.object({
  originAddress: z.string().min(5, 'Indirizzo troppo corto'),
  originCity: z.string().min(2, 'Città richiesta'),
  originCountry: z.string().min(2, 'Paese richiesto'),
  destAddress: z.string().min(5, 'Indirizzo troppo corto'),
  destCity: z.string().min(2, 'Città richiesta'),
  destCountry: z.string().min(2, 'Paese richiesto'),
  customerName: z.string().min(2, 'Nome cliente richiesto'),
  customerEmail: z.string().email('Email non valida'),
  weight: z.number().min(0.1, 'Peso minimo 0.1 kg'),
  value: z.number().min(1, 'Valore minimo €1'),
  notes: z.string().optional(),
});

type CreateShipmentForm = z.infer<typeof createShipmentSchema>;

interface CreateShipmentModalProps {
  onClose: () => void;
}

export const CreateShipmentModal = ({ onClose }: CreateShipmentModalProps) => {
  const createMutation = useCreateShipment();
  const { addToast } = useUIStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateShipmentForm>({
    resolver: zodResolver(createShipmentSchema),
  });

  const onSubmit = async (data: CreateShipmentForm) => {
    try {
      await createMutation.mutateAsync({
        trackingNumber: generateTrackingNumber(),
        origin: {
          lat: 0,
          lng: 0,
          address: data.originAddress,
          city: data.originCity,
          country: data.originCountry,
        },
        destination: {
          lat: 0,
          lng: 0,
          address: data.destAddress,
          city: data.destCity,
          country: data.destCountry,
        },
        customerName: data.customerName,
        customerEmail: data.customerEmail,
        weight: data.weight,
        value: data.value,
        notes: data.notes,
      });
      
      addToast({
        type: 'success',
        title: 'Spedizione creata',
        message: 'Nuova spedizione creata con successo',
      });
      onClose();
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile creare la spedizione',
      });
    }
  };

  return (
    <div className="w-full max-w-2xl">
      <ModalHeader title="Nuova Spedizione" onClose={onClose} />
      
      <form onSubmit={handleSubmit(onSubmit)} className="p-6 max-h-[70vh] overflow-y-auto">
        <div className="grid grid-cols-2 gap-4">
          {/* Origin */}
          <div className="col-span-2">
            <h4 className="font-semibold mb-3 text-primary">Origine</h4>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Indirizzo</label>
            <input {...register('originAddress')} className="input-glass w-full" />
            {errors.originAddress && (
              <p className="text-danger text-xs mt-1">{errors.originAddress.message}</p>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-sm font-medium mb-1">Città</label>
              <input {...register('originCity')} className="input-glass w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Paese</label>
              <input {...register('originCountry')} className="input-glass w-full" defaultValue="IT" />
            </div>
          </div>

          {/* Destination */}
          <div className="col-span-2 mt-4">
            <h4 className="font-semibold mb-3 text-primary">Destinazione</h4>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Indirizzo</label>
            <input {...register('destAddress')} className="input-glass w-full" />
            {errors.destAddress && (
              <p className="text-danger text-xs mt-1">{errors.destAddress.message}</p>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-sm font-medium mb-1">Città</label>
              <input {...register('destCity')} className="input-glass w-full" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Paese</label>
              <input {...register('destCountry')} className="input-glass w-full" defaultValue="DE" />
            </div>
          </div>

          {/* Customer */}
          <div className="col-span-2 mt-4">
            <h4 className="font-semibold mb-3 text-primary">Cliente</h4>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Nome</label>
            <input {...register('customerName')} className="input-glass w-full" />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input {...register('customerEmail')} className="input-glass w-full" />
          </div>

          {/* Shipment Details */}
          <div className="col-span-2 mt-4">
            <h4 className="font-semibold mb-3 text-primary">Dettagli Spedizione</h4>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Peso (kg)</label>
            <input
              type="number"
              step="0.1"
              {...register('weight', { valueAsNumber: true })}
              className="input-glass w-full"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Valore (€)</label>
            <input
              type="number"
              step="1"
              {...register('value', { valueAsNumber: true })}
              className="input-glass w-full"
            />
          </div>

          {/* Notes */}
          <div className="col-span-2">
            <label className="block text-sm font-medium mb-1">Note (opzionale)</label>
            <textarea {...register('notes')} className="input-glass w-full h-20 resize-none" />
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-border">
          <button type="button" onClick={onClose} className="px-4 py-2 text-text-secondary hover:text-text-primary">
            Annulla
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="btn-success flex items-center gap-2"
          >
            {createMutation.isPending ? (
              <div className="w-4 h-4 border-2 border-success/30 border-t-success rounded-full animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Crea Spedizione
          </button>
        </div>
      </form>
    </div>
  );
};