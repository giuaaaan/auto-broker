import { useState } from 'react';
import { Bot, Activity, Clock, CheckCircle, AlertCircle, Brain } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { useAgents } from '@/hooks/useDashboard';
import { useUIStore } from '@/store';
import { formatAgentStatus, getAgentStatusColor, formatRelative } from '@/utils/formatters';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { Agent } from '@/types';

const mockActivityData = [
  { time: '00:00', tasks: 12 },
  { time: '04:00', tasks: 8 },
  { time: '08:00', tasks: 25 },
  { time: '12:00', tasks: 45 },
  { time: '16:00', tasks: 38 },
  { time: '20:00', tasks: 28 },
  { time: '23:59', tasks: 15 },
];

const AgentsPage = () => {
  const { data: agents, isLoading } = useAgents();
  const { openModal } = useUIStore();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const agent = agents?.find((a) => a.id === selectedAgent);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="px-6 py-4 border-b border-border">
          <h1 className="text-2xl font-bold">AI Agents</h1>
          <p className="text-text-secondary text-sm">
            Monitora e gestisci gli agenti AI del sistema
          </p>
        </header>

        <div className="flex-1 overflow-auto p-6">
          <div className="grid grid-cols-12 gap-6 h-full">
            {/* Agents List */}
            <div className="col-span-4 space-y-4">
              <h3 className="font-semibold mb-4">Agenti Disponibili</h3>
              
              {isLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="skeleton h-32 rounded-lg" />
                  ))}
                </div>
              ) : (
                agents?.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    isSelected={selectedAgent === agent.id}
                    onClick={() => setSelectedAgent(agent.id)}
                  />
                ))
              )}
            </div>

            {/* Agent Details */}
            <div className="col-span-8">
              {agent ? (
                <div className="space-y-6">
                  {/* Header */}
                  <div className="glass-panel p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div
                          className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold"
                          style={{
                            background: `linear-gradient(135deg, ${getAgentStatusColor(agent.status)}20 0%, ${getAgentStatusColor(agent.status)}40 100%)`,
                            color: getAgentStatusColor(agent.status),
                          }}
                        >
                          {agent.id[0]}
                        </div>
                        <div>
                          <h2 className="text-2xl font-bold">{agent.id}</h2>
                          <p className="text-text-secondary">{agent.name}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{
                                background: getAgentStatusColor(agent.status),
                                boxShadow: `0 0 8px ${getAgentStatusColor(agent.status)}`,
                              }}
                            />
                            <span
                              className="text-sm"
                              style={{ color: getAgentStatusColor(agent.status) }}
                            >
                              {formatAgentStatus(agent.status)}
                            </span>
                          </div>
                        </div>
                      </div>
                      
                      <button
                        onClick={() => openModal('agentLogs', agent.id)}
                        className="btn-primary"
                      >
                        <Activity className="w-4 h-4 mr-2" />
                        View Logs
                      </button>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-3 gap-4 mt-6">
                      <div className="p-4 rounded-xl bg-surface border border-border text-center">
                        <Brain className="w-6 h-6 mx-auto mb-2 text-primary" />
                        <p className="text-2xl font-bold">{agent.activityLevel}%</p>
                        <p className="text-xs text-text-secondary">Activity Level</p>
                      </div>
                      <div className="p-4 rounded-xl bg-surface border border-border text-center">
                        <CheckCircle className="w-6 h-6 mx-auto mb-2 text-success" />
                        <p className="text-2xl font-bold">{agent.recentActivities.length}</p>
                        <p className="text-xs text-text-secondary">Tasks Today</p>
                      </div>
                      <div className="p-4 rounded-xl bg-surface border border-border text-center">
                        <Clock className="w-6 h-6 mx-auto mb-2 text-warning" />
                        <p className="text-2xl font-bold">
                          {agent.lastActivity ? formatRelative(agent.lastActivity) : 'N/A'}
                        </p>
                        <p className="text-xs text-text-secondary">Last Activity</p>
                      </div>
                    </div>
                  </div>

                  {/* Activity Chart */}
                  <div className="glass-panel p-6">
                    <h4 className="font-semibold mb-4">Attività nelle ultime 24h</h4>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={mockActivityData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                          <XAxis dataKey="time" stroke="#A0A0A0" />
                          <YAxis stroke="#A0A0A0" />
                          <Tooltip
                            contentStyle={{
                              background: 'rgba(10, 10, 10, 0.9)',
                              border: '1px solid rgba(255, 255, 255, 0.1)',
                              borderRadius: '8px',
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="tasks"
                            stroke="#00D9FF"
                            strokeWidth={2}
                            dot={{ fill: '#00D9FF' }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Current Task */}
                  {agent.currentTask && (
                    <div className="glass-panel p-6">
                      <h4 className="font-semibold mb-2">Task Corrente</h4>
                      <p>{agent.currentTask}</p>
                    </div>
                  )}

                  {/* Recent Activities */}
                  <div className="glass-panel p-6">
                    <h4 className="font-semibold mb-4">Attività Recenti</h4>
                    <div className="space-y-3">
                      {agent.recentActivities.slice(0, 5).map((activity) => (
                        <div
                          key={activity.id}
                          className="flex items-start gap-3 p-3 rounded-lg bg-surface border border-border"
                        >
                          {activity.status === 'success' ? (
                            <CheckCircle className="w-5 h-5 text-success flex-shrink-0" />
                          ) : activity.status === 'error' ? (
                            <AlertCircle className="w-5 h-5 text-danger flex-shrink-0" />
                          ) : (
                            <Activity className="w-5 h-5 text-primary flex-shrink-0" />
                          )}
                          <div className="flex-1">
                            <p className="font-medium text-sm">{activity.type}</p>
                            <p className="text-sm text-text-secondary">{activity.description}</p>
                            <p className="text-xs text-text-secondary mt-1">
                              {formatRelative(activity.timestamp)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-text-secondary">
                  <div className="text-center">
                    <Bot className="w-16 h-16 mx-auto mb-4 opacity-30" />
                    <p>Seleziona un agente per vedere i dettagli</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

interface AgentCardProps {
  agent: Agent;
  isSelected: boolean;
  onClick: () => void;
}

const AgentCard = ({ agent, isSelected, onClick }: AgentCardProps) => {
  const statusColor = getAgentStatusColor(agent.status);

  return (
    <div
      onClick={onClick}
      className={`
        p-4 rounded-xl border cursor-pointer transition-all
        ${isSelected ? 'bg-primary/10 border-primary' : 'bg-surface border-border hover:border-primary/50'}
      `}
    >
      <div className="flex items-center gap-3">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center font-bold flex-shrink-0"
          style={{
            background: `linear-gradient(135deg, ${statusColor}20 0%, ${statusColor}40 100%)`,
            color: statusColor,
          }}
        >
          {agent.id[0]}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold">{agent.id}</h4>
          <div className="flex items-center gap-2">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background: statusColor,
                boxShadow: `0 0 6px ${statusColor}`,
              }}
            />
            <span className="text-xs text-text-secondary">
              {formatAgentStatus(agent.status)}
            </span>
          </div>
        </div>
      </div>
      
      {agent.suggestion && (
        <div className="mt-3 p-2 rounded-lg bg-warning/10 border border-warning/30">
          <p className="text-xs text-warning truncate">{agent.suggestion.title}</p>
        </div>
      )}
    </div>
  );
};

export default AgentsPage;