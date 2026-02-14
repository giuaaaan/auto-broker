import { AnimatePresence, motion } from 'framer-motion';
import { useUIStore } from '@/store';
import { X } from 'lucide-react';
import { useEffect } from 'react';

// Modal content components
import { ShipmentDetailsModal } from '../modals/ShipmentDetailsModal';
import { AgentLogsModal } from '../modals/AgentLogsModal';
import { RevenueDetailsModal } from '../modals/RevenueDetailsModal';
import { CreateShipmentModal } from '../modals/CreateShipmentModal';
import { EmergencyStopModal } from '../modals/EmergencyStopModal';

const modalComponents: Record<string, React.ComponentType<{ data?: unknown; onClose: () => void }>> = {
  shipmentDetails: ShipmentDetailsModal,
  agentLogs: AgentLogsModal,
  revenueDetails: RevenueDetailsModal,
  createShipment: CreateShipmentModal,
  emergencyStop: EmergencyStopModal,
};

export const ModalContainer = () => {
  const { modal, closeModal } = useUIStore();
  
  const ModalContent = modal.type ? modalComponents[modal.type] : null;

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && modal.isOpen) {
        closeModal();
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [modal.isOpen, closeModal]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (modal.isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [modal.isOpen]);

  return (
    <AnimatePresence>
      {modal.isOpen && ModalContent && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={closeModal}
          />
          
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="glass-panel-strong w-full max-w-2xl max-h-[90vh] overflow-hidden pointer-events-auto">
              <ModalContent data={modal.data} onClose={closeModal} />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

// Base modal header component
export const ModalHeader = ({ title, onClose }: { title: string; onClose: () => void }) => (
  <div className="flex items-center justify-between p-6 border-b border-border">
    <h2 className="text-xl font-semibold">{title}</h2>
    <button
      onClick={onClose}
      className="p-2 text-text-secondary hover:text-text-primary transition-colors rounded-lg hover:bg-surface"
    >
      <X className="w-5 h-5" />
    </button>
  </div>
);