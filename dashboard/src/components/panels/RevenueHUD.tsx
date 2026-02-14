import { motion } from 'framer-motion';
import CountUp from 'react-countup';
import { TrendingUp, TrendingDown, Info, Zap } from 'lucide-react';
import { useCurrentLevel } from '@/hooks/useDashboard';
import { useUIStore } from '@/store';
import { formatCurrency, formatLevel, getLevelColor, calculateProgress } from '@/utils/formatters';

export const RevenueHUD = () => {
  const { data: currentLevel, isLoading } = useCurrentLevel();
  const { openModal } = useUIStore();

  if (isLoading || !currentLevel) {
    return (
      <div className="glass-panel p-6 min-w-[320px]">
        <div className="skeleton h-12 w-48 mb-2" />
        <div className="skeleton h-4 w-32" />
      </div>
    );
  }

  const levelColor = getLevelColor(currentLevel.levelId);
  const progress = currentLevel.nextLevel
    ? calculateProgress(currentLevel.mrr, currentLevel.nextLevel.threshold)
    : 100;

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel p-6 min-w-[320px]"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-text-secondary text-sm mb-1">MRR (Monthly Recurring Revenue)</p>
          <div className="flex items-baseline gap-2">
            <h2 className="text-4xl font-bold number-mono">
              <CountUp
                start={0}
                end={currentLevel.mrr}
                duration={2}
                separator="."
                decimals={0}
                prefix="€"
              />
            </h2>
            {currentLevel.mrr > 0 && (
              <span className="text-success text-sm flex items-center">
                <TrendingUp className="w-4 h-4 mr-1" />
                +12%
              </span>
            )}
          </div>
        </div>
        
        <button
          onClick={() => openModal('revenueDetails', currentLevel)}
          className="p-2 text-text-secondary hover:text-primary transition-colors"
        >
          <Info className="w-5 h-5" />
        </button>
      </div>

      {/* Level Badge */}
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-4 h-4" style={{ color: levelColor }} />
        <span
          className="font-semibold text-sm"
          style={{ color: levelColor }}
        >
          Livello {currentLevel.levelId.split('_')[1].toUpperCase()}
        </span>
        <span className="text-text-secondary">-</span>
        <span className="text-text-secondary text-sm">
          {formatLevel(currentLevel.levelId)}
        </span>
      </div>

      {/* Progress Bar */}
      {currentLevel.nextLevel && (
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-text-secondary">Progresso verso prossimo livello</span>
            <span className="text-primary font-mono">{progress.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-surface rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 1, ease: 'easeOut' }}
              className="h-full rounded-full"
              style={{
                background: `linear-gradient(90deg, ${levelColor} 0%, #00FF88 100%)`,
              }}
            />
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-text-secondary">
              Mancano {formatCurrency(currentLevel.nextLevel.threshold - currentLevel.mrr)} al livello{' '}
              {formatLevel(currentLevel.nextLevel.id)}
            </span>
          </div>
        </div>
      )}

      {/* Cost Ratio */}
      <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
        <div>
          <p className="text-text-secondary text-xs mb-1">Rapporto Costo/Revenue</p>
          <p
            className={`font-mono font-semibold ${
              currentLevel.costRatio > 0.8
                ? 'text-danger'
                : currentLevel.costRatio > 0.6
                ? 'text-warning'
                : 'text-success'
            }`}
          >
            {(currentLevel.costRatio * 100).toFixed(1)}%
          </p>
        </div>
        <div className="text-right">
          <p className="text-text-secondary text-xs mb-1">Max Burn</p>
          <p className="font-mono font-semibold text-text-primary">
            {formatCurrency(currentLevel.maxBurn)}
          </p>
        </div>
      </div>
    </motion.div>
  );
};