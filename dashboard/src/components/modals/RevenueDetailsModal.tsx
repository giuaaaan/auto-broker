import { useState } from 'react';
import { motion } from 'framer-motion';
import { DollarSign, TrendingUp, TrendingDown, Zap, Server, Bot, Shield } from 'lucide-react';
import { ModalHeader } from '../ui/ModalContainer';
import { useCurrentLevel } from '@/hooks/useDashboard';
import { formatCurrency, formatLevel, getLevelColor } from '@/utils/formatters';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';

interface RevenueDetailsModalProps {
  onClose: () => void;
}

// Mock data for the chart
const mockData = [
  { day: '1', revenue: 4200, costs: 800 },
  { day: '5', revenue: 4800, costs: 850 },
  { day: '10', revenue: 5100, costs: 900 },
  { day: '15', revenue: 5800, costs: 1100 },
  { day: '20', revenue: 6200, costs: 1200 },
  { day: '25', revenue: 6800, costs: 1300 },
  { day: '30', revenue: 7200, costs: 1400 },
];

export const RevenueDetailsModal = ({ onClose }: RevenueDetailsModalProps) => {
  const { data: currentLevel, isLoading } = useCurrentLevel();
  const [activeTab, setActiveTab] = useState<'overview' | 'components' | 'history'>('overview');

  if (isLoading || !currentLevel) {
    return (
      <div className="w-full max-w-3xl">
        <ModalHeader title="Dettagli Revenue" onClose={onClose} />
        <div className="p-6 space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const levelColor = getLevelColor(currentLevel.levelId);

  return (
    <div className="w-full max-w-3xl">
      <ModalHeader title="Dettagli Revenue & Costi" onClose={onClose} />
      
      <div className="p-6 max-h-[80vh] overflow-y-auto">
        {/* Header Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-4 rounded-xl bg-surface border border-border text-center">
            <DollarSign className="w-6 h-6 mx-auto mb-2 text-success" />
            <p className="text-2xl font-bold number-mono">{formatCurrency(currentLevel.mrr)}</p>
            <p className="text-xs text-text-secondary">MRR Attuale</p>
          </div>
          
          <div className="p-4 rounded-xl bg-surface border border-border text-center">
            <Zap className="w-6 h-6 mx-auto mb-2" style={{ color: levelColor }} />
            <p className="text-2xl font-bold" style={{ color: levelColor }}>
              {formatLevel(currentLevel.levelId)}
            </p>
            <p className="text-xs text-text-secondary">Livello Attuale</p>
          </div>
          
          <div className="p-4 rounded-xl bg-surface border border-border text-center">
            <TrendingUp className="w-6 h-6 mx-auto mb-2 text-primary" />
            <p className="text-2xl font-bold number-mono">
              {(currentLevel.costRatio * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-text-secondary">Costo/Revenue</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-border">
          {(['overview', 'components', 'history'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab === 'overview' && 'Panoramica'}
              {tab === 'components' && 'Componenti'}
              {tab === 'history' && 'Storico'}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Chart */}
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockData}>
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
                  <XAxis dataKey="day" stroke="#A0A0A0" />
                  <YAxis stroke="#A0A0A0" />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(10, 10, 10, 0.9)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: '8px',
                    }}
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

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-surface border border-border">
                <p className="text-text-secondary text-sm mb-1">Max Burn Ammissibile</p>
                <p className="text-xl font-bold number-mono">{formatCurrency(currentLevel.maxBurn)}</p>
              </div>
              <div className="p-4 rounded-xl bg-surface border border-border">
                <p className="text-text-secondary text-sm mb-1">Buffer Sicurezza</p>
                <p className="text-xl font-bold number-mono text-success">
                  {formatCurrency(currentLevel.mrr - currentLevel.maxBurn)}
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'components' && (
          <div className="space-y-3">
            <h4 className="font-semibold mb-3">Componenti Attivi</h4>
            {currentLevel.activeComponents.map((component) => (
              <div
                key={component}
                className="flex items-center justify-between p-3 rounded-lg bg-success/10 border border-success/30"
              >
                <div className="flex items-center gap-3">
                  <Server className="w-5 h-5 text-success" />
                  <span>{component}</span>
                </div>
                <span className="badge badge-success">Attivo</span>
              </div>
            ))}

            <h4 className="font-semibold mb-3 mt-6">Componenti Disabilitati</h4>
            {currentLevel.disabledComponents.map((component) => (
              <div
                key={component}
                className="flex items-center justify-between p-3 rounded-lg bg-surface border border-border"
              >
                <div className="flex items-center gap-3">
                  <Server className="w-5 h-5 text-text-secondary" />
                  <span className="text-text-secondary">{component}</span>
                </div>
                <span className="badge bg-surface text-text-secondary">Inattivo</span>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-3">
            {[
              { date: '2026-02-15', event: 'Upgrade a Livello 2 - Growth', value: 2800 },
              { date: '2026-01-20', event: 'Upgrade a Livello 1 - Bootstrap', value: 600 },
              { date: '2026-01-01', event: 'Inizio operazioni - Livello 0', value: 50 },
            ].map((item, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 rounded-lg bg-surface border border-border"
              >
                <div>
                  <p className="font-medium">{item.event}</p>
                  <p className="text-sm text-text-secondary">{item.date}</p>
                </div>
                <span className="font-mono">{formatCurrency(item.value)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};