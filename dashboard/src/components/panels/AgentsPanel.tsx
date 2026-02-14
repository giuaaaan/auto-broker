import { motion } from 'framer-motion';
import { Activity, AlertCircle, Bot, Eye } from 'lucide-react';
import { useAgents } from '@/hooks/useDashboard';
import { useUIStore } from '@/store';
import { formatAgentStatus, getAgentStatusColor } from '@/utils/formatters';
import type { Agent } from '@/types';

const agentDescriptions: Record<string, string> = {
  SARA: 'Sentiment Analysis & Response Automation',
  MARCO: 'Market Intelligence & Pricing',
  PAOLO: 'Carrier Failover & Optimization',
  GIULIA: 'Dispute Resolution & Claims',
};

export const AgentsPanel = () => {
  const { data: agents, isLoading } = useAgents();
  const { openModal } = useUIStore();

  if (isLoading) {
    return (
      <div className="glass-panel p-4">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <Bot className="w-5 h-5 text-primary" />
          AI Agents Status
        </h3>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const sortedAgents = agents?.sort((a, b) => {
    // Priority: warning/error > processing > active > standby
    const priority = { warning: 0, error: 0, processing: 1, active: 2, standby: 3 };
    return (priority[a.status] || 4) - (priority[b.status] || 4);
  });

  return (
    <div className="glass-panel p-4">
      <h3 className="font-semibold mb-4 flex items-center gap-2">
        <Bot className="w-5 h-5 text-primary" />
        AI Agents Status
      </h3>
      
      <div className="space-y-3">
        {sortedAgents?.map((agent, index) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            index={index}
            onClick={() => openModal('agentLogs', agent.id)}
          />
        ))}
      </div>
    </div>
  );
};

interface AgentCardProps {
  agent: Agent;
  index: number;
  onClick: () => void;
}

const AgentCard = ({ agent, index, onClick }: AgentCardProps) => {
  const statusColor = getAgentStatusColor(agent.status);
  const hasSuggestion = agent.suggestion && agent.id === 'PAOLO';

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      onClick={onClick}
      className={`
        relative p-4 rounded-xl border cursor-pointer card-hover overflow-hidden
        ${hasSuggestion ? 'bg-warning/10 border-warning/50' : 'bg-surface border-border'}
      `}
    >
      {/* Flashing indicator for PAOLO suggestion */}
      {hasSuggestion && (
        <div className="absolute inset-0 border-2 border-warning/50 rounded-xl animate-pulse pointer-events-none" />
      )}

      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center font-bold text-lg flex-shrink-0"
          style={{
            background: `linear-gradient(135deg, ${statusColor}20 0%, ${statusColor}40 100%)`,
            color: statusColor,
            border: `1px solid ${statusColor}50`,
          }}
        >
          {agent.id[0]}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold">{agent.id}</h4>
            <div
              className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium"
              style={{
                background: `${statusColor}20`,
                color: statusColor,
              }}
            >
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: statusColor,
                  boxShadow: `0 0 8px ${statusColor}`,
                }}
              />
              {formatAgentStatus(agent.status)}
            </div>
          </div>
          
          <p className="text-xs text-text-secondary mt-1">
            {agentDescriptions[agent.id]}
          </p>

          {/* Activity Bar */}
          <div className="mt-3">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-text-secondary">Attività</span>
              <span className="font-mono">{agent.activityLevel}%</span>
            </div>
            <div className="h-1.5 bg-surface rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${agent.activityLevel}%` }}
                className="h-full rounded-full"
                style={{
                  background: `linear-gradient(90deg, ${statusColor} 0%, #00FF88 100%)`,
                }}
              />
            </div>
          </div>

          {/* Suggestion Alert */}
          {hasSuggestion && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-3 p-2 rounded-lg bg-warning/20 border border-warning/30 flex items-center gap-2"
            >
              <AlertCircle className="w-4 h-4 text-warning flex-shrink-0" />
              <span className="text-xs text-warning font-medium truncate">
                {agent.suggestion?.title}
              </span>
              <button className="ml-auto text-xs px-2 py-1 bg-warning text-background rounded font-medium">
                VEDI
              </button>
            </motion.div>
          )}

          {/* Current Task */}
          {agent.currentTask && (
            <p className="text-xs text-text-secondary mt-2 truncate">
              <Activity className="w-3 h-3 inline mr-1" />
              {agent.currentTask}
            </p>
          )}
        </div>

        {/* View Button */}
        <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <Eye className="w-4 h-4 text-text-secondary" />
        </div>
      </div>
    </motion.div>
  );
};