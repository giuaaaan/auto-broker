import { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  AlertOctagon, 
  Zap, 
  RefreshCw, 
  Plus,
  Power,
  TrendingUp,
  Settings,
} from 'lucide-react';
import { useUIStore, useCommandStore } from '@/store';
import { useEmergencyStop, useForceLevel } from '@/hooks/useDashboard';
import { formatLevel } from '@/utils/formatters';
import type { EconomicLevel } from '@/types';

const levels: { value: EconomicLevel | 'auto'; label: string }[] = [
  { value: 'auto', label: 'Automatico' },
  { value: 'level_0_survival', label: 'L0 - Sopravvivenza' },
  { value: 'level_1_bootstrap', label: 'L1 - Bootstrap' },
  { value: 'level_2_growth', label: 'L2 - Crescita' },
  { value: 'level_3_scale', label: 'L3 - Scala' },
  { value: 'level_4_enterprise', label: 'L4 - Enterprise' },
];

export const CommandCenter = () => {
  const { openModal } = useUIStore();
  const { emergencyStopActive, forcedLevel, setEmergencyStop, setForcedLevel } = useCommandStore();
  const [blackFridayPercent, setBlackFridayPercent] = useState(10);
  const [blackFridayEnabled, setBlackFridayEnabled] = useState(false);
  
  const emergencyStopMutation = useEmergencyStop();
  const forceLevelMutation = useForceLevel();

  const handleEmergencyStop = () => {
    openModal('emergencyStop', {
      onConfirm: (reason: string) => {
        emergencyStopMutation.mutate({
          reason,
          operatorId: 'current_user',
          scope: 'all',
        }, {
          onSuccess: () => setEmergencyStop(true),
        });
      },
    });
  };

  const handleForceLevel = (level: EconomicLevel | 'auto') => {
    setForcedLevel(level);
    if (level !== 'auto') {
      forceLevelMutation.mutate(level);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel-strong p-4"
    >
      <div className="flex items-center justify-between gap-6 flex-wrap">
        {/* Quick Create */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => openModal('createShipment')}
            className="btn-success flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Nuova Spedizione
          </button>
        </div>

        {/* Emergency Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleEmergencyStop}
            disabled={emergencyStopActive}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all
              ${emergencyStopActive
                ? 'bg-danger text-white cursor-not-allowed'
                : 'bg-danger/20 text-danger border border-danger/50 hover:bg-danger/30'}
            `}
          >
            <AlertOctagon className="w-4 h-4" />
            {emergencyStopActive ? 'EMERGENCY STOP ATTIVO' : 'EMERGENCY STOP'}
          </button>

          {emergencyStopActive && (
            <button
              onClick={() => setEmergencyStop(false)}
              className="btn-primary"
            >
              <Power className="w-4 h-4" />
              Ripristina
            </button>
          )}
        </div>

        {/* Black Friday Mode */}
        <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-surface border border-border">
          <Zap className={`w-4 h-4 ${blackFridayEnabled ? 'text-warning' : 'text-text-secondary'}`} />
          <span className="text-sm font-medium">Black Friday</span>
          
          <button
            onClick={() => setBlackFridayEnabled(!blackFridayEnabled)}
            className={`
              relative w-12 h-6 rounded-full transition-colors
              ${blackFridayEnabled ? 'bg-warning' : 'bg-surface border border-border'}
            `}
          >
            <motion.div
              animate={{ x: blackFridayEnabled ? 24 : 2 }}
              className="absolute top-1 w-4 h-4 rounded-full bg-white shadow"
            />
          </button>
          
          {blackFridayEnabled && (
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="5"
                max="50"
                value={blackFridayPercent}
                onChange={(e) => setBlackFridayPercent(Number(e.target.value))}
                className="w-20 accent-warning"
              />
              <span className="text-sm font-mono text-warning">{blackFridayPercent}%</span>
            </div>
          )}
        </div>

        {/* Force Level */}
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-text-secondary" />
          <span className="text-sm text-text-secondary">Livello:</span>
          <select
            value={forcedLevel}
            onChange={(e) => handleForceLevel(e.target.value as EconomicLevel | 'auto')}
            className="input-glass text-sm py-1.5"
          >
            {levels.map((level) => (
              <option key={level.value} value={level.value}>
                {level.label}
              </option>
            ))}
          </select>
        </div>

        {/* Refresh */}
        <button
          onClick={() => window.location.reload()}
          className="p-2 text-text-secondary hover:text-primary transition-colors"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>
    </motion.div>
  );
};