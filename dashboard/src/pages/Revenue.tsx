import { useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, DollarSign, TrendingDown, Zap, Server, Bot, Shield, AlertTriangle } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useCurrentLevel, useRevenueMetrics, useSimulateRevenue } from '@/hooks/useDashboard';
import { useUIStore } from '@/store';
import { formatCurrency, formatLevel, getLevelColor, calculateProgress } from '@/utils/formatters';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

// Mock data
const monthlyData = [
  { month: 'Gen', revenue: 3200, costs: 800 },
  { month: 'Feb', revenue: 4500, costs: 950 },
  { month: 'Mar', revenue: 5800, costs: 1100 },
  { month: 'Apr', revenue: 6200, costs: 1200 },
  { month: 'Mag', revenue: 7800, costs: 1500 },
  { month: 'Giu', revenue: 9200, costs: 1800 },
];

const costBreakdown = [
  { name: 'Infrastructure', value: 3800, color: '#00D9FF' },
  { name: 'Team', value: 25000, color: '#00FF88' },
  { name: 'APIs', value: 900, color: '#FF6B00' },
  { name: 'Licenze', value: 2000, color: '#FF2D55' },
];

const RevenuePage = () => {
  const { data: currentLevel, isLoading: levelLoading } = useCurrentLevel();
  const { data: metrics, isLoading: metricsLoading } = useRevenueMetrics();
  const simulateMutation = useSimulateRevenue();
  const { addToast } = useUIStore();
  const [simulatedMrr, setSimulatedMrr] = useState<number>(10000);

  const isLoading = levelLoading || metricsLoading;

  const handleSimulate = async () => {
    try {
      const result = await simulateMutation.mutateAsync(simulatedMrr);
      addToast({
        type: 'info',
        title: 'Simulazione completata',
        message: `A ${formatCurrency(simulatedMrr)} MRR: ${formatLevel(result.simulatedLevel)}`,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Errore simulazione',
        message: 'Impossibile eseguire la simulazione',
      });
    }
  };

  if (isLoading || !currentLevel) {
    return (
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-12 h-12 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  const levelColor = getLevelColor(currentLevel.levelId);
  const progress = currentLevel.nextLevel
    ? calculateProgress(currentLevel.mrr, currentLevel.nextLevel.threshold)
    : 100;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      
      <div className="flex-1 flex flex-col min-w-0 overflow-auto">
        {/* Header */}
        <header className="px-6 py-4 border-b border-border">
          <h1 className="text-2xl font-bold">Revenue & Economics</h1>
          <p className="text-text-secondary text-sm">
            Analisi dettagliata dei ricavi e dei costi
          </p>
        </header>

        <div className="p-6 space-y-6">
          {/* Top Stats */}
          <div className="grid grid-cols-4 gap-6">
            <div className="glass-panel p-6">
              <div className="flex items-center justify-between mb-4">
                <DollarSign className="w-8 h-8 text-success" />
                <span className="text-xs text-text-secondary">MRR</span>
              </div>
              <p className="text-3xl font-bold number-mono">{formatCurrency(currentLevel.mrr)}</p>
              <p className="text-sm text-success mt-1">+12% vs mese scorso</p>
            </div>

            <div className="glass-panel p-6">
              <div className="flex items-center justify-between mb-4">
                <TrendingUp className="w-8 h-8 text-primary" />
                <span className="text-xs text-text-secondary">ARR</span>
              </div>
              <p className="text-3xl font-bold number-mono">{formatCurrency(currentLevel.mrr * 12)}</p>
              <p className="text-sm text-primary mt-1">Annualizzato</p>
            </div>

            <div className="glass-panel p-6">
              <div className="flex items-center justify-between mb-4">
                <TrendingDown className="w-8 h-8 text-danger" />
                <span className="text-xs text-text-secondary">Costi Mensili</span>
              </div>
              <p className="text-3xl font-bold number-mono">{formatCurrency(currentLevel.maxBurn)}</p>
              <p className="text-sm text-danger mt-1">{(currentLevel.costRatio * 100).toFixed(1)}% del MRR</p>
            </div>

            <div className="glass-panel p-6">
              <div className="flex items-center justify-between mb-4">
                <Zap className="w-8 h-8" style={{ color: levelColor }} />
                <span className="text-xs text-text-secondary">Livello</span>
              </div>
              <p className="text-3xl font-bold" style={{ color: levelColor }}>
                {formatLevel(currentLevel.levelId)}
              </p>
              <p className="text-sm text-text-secondary mt-1">
                {currentLevel.nextLevel
                  ? `${formatCurrency(currentLevel.nextLevel.threshold - currentLevel.mrr)} al prossimo`
                  : 'Livello massimo'}
              </p>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-2 gap-6">
            {/* Revenue Chart */}
            <div className="glass-panel p-6">
              <h3 className="font-semibold mb-4">Andamento Revenue vs Costi</h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={monthlyData}>
                    <defs>
                      <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00FF88" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#00FF88" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorCosts" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#FF2D55" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#FF2D55" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="month" stroke="#A0A0A0" />
                    <YAxis stroke="#A0A0A0" />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(10, 10, 10, 0.9)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '8px',
                      }}
                      formatter={(value: number) => formatCurrency(value)}
                    />
                    <Area
                      type="monotone"
                      dataKey="revenue"
                      stroke="#00FF88"
                      fillOpacity={1}
                      fill="url(#colorRevenue)"
                      name="Revenue"
                    />
                    <Area
                      type="monotone"
                      dataKey="costs"
                      stroke="#FF2D55"
                      fillOpacity={1}
                      fill="url(#colorCosts)"
                      name="Costi"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Cost Breakdown */}
            <div className="glass-panel p-6">
              <h3 className="font-semibold mb-4">Breakdown Costi</h3>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={costBreakdown}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {costBreakdown.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(10, 10, 10, 0.9)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '8px',
                      }}
                      formatter={(value: number) => formatCurrency(value)}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-center gap-4 mt-4">
                {costBreakdown.map((item) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ background: item.color }}
                    />
                    <span className="text-sm text-text-secondary">{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Level Progress & Simulation */}
          <div className="grid grid-cols-2 gap-6">
            {/* Level Progress */}
            <div className="glass-panel p-6">
              <h3 className="font-semibold mb-4">Progresso Livelli</h3>
              
              <div className="space-y-4">
                {['level_0_survival', 'level_1_bootstrap', 'level_2_growth', 'level_3_scale', 'level_4_enterprise'].map(
                  (level, index) => {
                    const isActive = currentLevel.levelId === level;
                    const isPast = ['level_0_survival', 'level_1_bootstrap', 'level_2_growth'].indexOf(currentLevel.levelId) >= index;
                    
                    return (
                      <div
                        key={level}
                        className={`flex items-center gap-4 p-3 rounded-lg ${
                          isActive ? 'bg-primary/10 border border-primary/30' : 'bg-surface'
                        }`}
                      >
                        <div
                          className="w-10 h-10 rounded-lg flex items-center justify-center font-bold"
                          style={{
                            background: isActive || isPast ? `${getLevelColor(level)}20` : 'rgba(255,255,255,0.05)',
                            color: isActive || isPast ? getLevelColor(level) : '#A0A0A0',
                          }}
                        >
                          {index}
                        </div>
                        <div className="flex-1">
                          <p className={`font-medium ${isActive ? 'text-primary' : ''}`}>
                            {formatLevel(level)}
                          </p>
                          <p className="text-xs text-text-secondary">
                            Threshold: {formatCurrency([0, 450, 800, 3000, 10000][index])}
                          </p>
                        </div>
                        {isActive && (
                          <div className="text-success text-sm font-medium">Attivo</div>
                        )}
                      </div>
                    );
                  }
                )}
              </div>
            </div>

            {/* Simulator */}
            <div className="glass-panel p-6">
              <h3 className="font-semibold mb-4">Simulatore Revenue</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">MRR Proiettato</label>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      value={simulatedMrr}
                      onChange={(e) => setSimulatedMrr(Number(e.target.value))}
                      className="input-glass flex-1"
                      placeholder="10000"
                    />
                    <button
                      onClick={handleSimulate}
                      disabled={simulateMutation.isPending}
                      className="btn-primary"
                    >
                      {simulateMutation.isPending ? '...' : 'Simula'}
                    </button>
                  </div>
                </div>

                {simulateMutation.data && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="p-4 rounded-xl bg-surface border border-border"
                  >
                    <h4 className="font-medium mb-2">Risultato Simulazione</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Livello attuale:</span>
                        <span>{formatLevel(simulateMutation.data.currentLevel)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Livello simulato:</span>
                        <span className="text-primary font-medium">
                          {formatLevel(simulateMutation.data.simulatedLevel)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Costi stimati:</span>
                        <span className="font-mono">
                          {formatCurrency(simulateMutation.data.projectedCosts?.simulated || 0)}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Active Components */}
                <div>
                  <h4 className="font-medium mb-2">Componenti Attivi</h4>
                  <div className="space-y-2">
                    {currentLevel.activeComponents.map((component) => (
                      <div
                        key={component}
                        className="flex items-center gap-2 p-2 rounded-lg bg-success/10 border border-success/30"
                      >
                        <Server className="w-4 h-4 text-success" />
                        <span className="text-sm">{component}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {currentLevel.costRatio > 0.8 && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-warning/10 border border-warning/30 text-warning">
                    <AlertTriangle className="w-5 h-5" />
                    <span className="text-sm">
                      Attenzione: i costi superano l'80% del revenue
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RevenuePage;