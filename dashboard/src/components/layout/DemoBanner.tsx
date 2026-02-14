import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Gamepad2, X, Info } from 'lucide-react';

export const DemoBanner = () => {
  const [isVisible, setIsVisible] = useState(true);
  const [isDemoMode, setIsDemoMode] = useState(false);

  useEffect(() => {
    // Check if API is in demo mode
    const checkDemoStatus = async () => {
      try {
        const response = await fetch('/demo/status');
        if (response.ok) {
          const data = await response.json();
          setIsDemoMode(data.demo_mode);
        }
      } catch (error) {
        // If endpoint doesn't exist, we're not in demo mode
        setIsDemoMode(false);
      }
    };

    checkDemoStatus();
  }, []);

  if (!isDemoMode || !isVisible) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -100, opacity: 0 }}
        className="fixed top-0 left-0 right-0 z-50 bg-gradient-to-r from-warning/90 via-warning/80 to-warning/90 backdrop-blur-md border-b border-warning/30"
      >
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-warning/20 flex items-center justify-center">
              <Gamepad2 className="w-4 h-4 text-warning-foreground" />
            </div>
            <div>
              <p className="font-semibold text-sm text-warning-foreground">
                🎮 DEMO MODE
              </p>
              <p className="text-xs text-warning-foreground/80">
                Dati simulati - Nessun costo reale - Test gratuito
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 text-xs text-warning-foreground/70">
              <Info className="w-3 h-3" />
              <span>Hume AI: Mock</span>
              <span className="opacity-50">|</span>
              <span>Insighto: Mock</span>
              <span className="opacity-50">|</span>
              <span>Blockchain: Mock</span>
            </div>
            
            <button
              onClick={() => setIsVisible(false)}
              className="p-1 rounded-lg hover:bg-warning-foreground/10 transition-colors"
              title="Chiudi banner"
            >
              <X className="w-4 h-4 text-warning-foreground" />
            </button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

export default DemoBanner;
