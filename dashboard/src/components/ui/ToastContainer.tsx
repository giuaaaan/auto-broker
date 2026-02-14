import { AnimatePresence, motion } from 'framer-motion';
import { useUIStore } from '@/store';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { useEffect } from 'react';

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const colors = {
  success: 'text-success border-success/30 bg-success/10',
  error: 'text-danger border-danger/30 bg-danger/10',
  warning: 'text-warning border-warning/30 bg-warning/10',
  info: 'text-primary border-primary/30 bg-primary/10',
};

export const ToastContainer = () => {
  const { toasts, removeToast } = useUIStore();

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-full max-w-md">
      <AnimatePresence>
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
        ))}
      </AnimatePresence>
    </div>
  );
};

interface ToastItemProps {
  toast: {
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    title: string;
    message?: string;
    duration?: number;
  };
  onClose: () => void;
}

const ToastItem = ({ toast, onClose }: ToastItemProps) => {
  const Icon = icons[toast.type];
  const colorClass = colors[toast.type];

  useEffect(() => {
    if (toast.duration) {
      const timer = setTimeout(onClose, toast.duration);
      return () => clearTimeout(timer);
    }
  }, [toast.duration, onClose]);

  return (
    <motion.div
      initial={{ opacity: 0, x: 100, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 100, scale: 0.9 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`glass-panel p-4 border ${colorClass} flex items-start gap-3`}
    >
      <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <h4 className="font-medium text-sm">{toast.title}</h4>
        {toast.message && (
          <p className="text-xs text-text-secondary mt-1">{toast.message}</p>
        )}
      </div>
      <button
        onClick={onClose}
        className="text-text-secondary hover:text-text-primary transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </motion.div>
  );
};