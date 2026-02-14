import { useAgent, useAgentLogs } from '@/hooks/useDashboard';
import { ModalHeader } from '../ui/ModalContainer';
import { Activity, CheckCircle, AlertCircle, Info, XCircle } from 'lucide-react';
import { formatRelative } from '@/utils/formatters';

interface AgentLogsModalProps {
  data: string; // agent id
  onClose: () => void;
}

const activityIcons = {
  success: CheckCircle,
  warning: AlertCircle,
  error: XCircle,
  info: Info,
};

const activityColors = {
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-danger',
  info: 'text-primary',
};

export const AgentLogsModal = ({ data: agentId, onClose }: AgentLogsModalProps) => {
  const { data: agent, isLoading: agentLoading } = useAgent(agentId);
  const { data: logs, isLoading: logsLoading } = useAgentLogs(agentId, 50);

  const isLoading = agentLoading || logsLoading;

  return (
    <div className="w-full max-w-2xl">
      <ModalHeader title={`${agent?.name || agentId} - Activity Log`} onClose={onClose} />
      
      <div className="p-6 max-h-[70vh] overflow-y-auto">
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="skeleton h-16 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Current Status */}
            <div className="p-4 rounded-xl bg-surface border border-border mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-text-secondary text-sm">Stato Attuale</p>
                  <p className="text-lg font-semibold capitalize">{agent?.status}</p>
                </div>
                <div className="text-right">
                  <p className="text-text-secondary text-sm">Livello Attività</p>
                  <p className="text-lg font-semibold">{agent?.activityLevel}%</p>
                </div>
              </div>
              {agent?.currentTask && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-text-secondary text-sm">Task Corrente</p>
                  <p>{agent.currentTask}</p>
                </div>
              )}
            </div>

            {/* Activity Log */}
            <h4 className="font-semibold mb-3">Log Attività Recenti</h4>
            
            {logs?.map((log, index) => {
              const Icon = activityIcons[log.status];
              const colorClass = activityColors[log.status];
              
              return (
                <div
                  key={log.id}
                  className="flex items-start gap-3 p-3 rounded-lg bg-surface border border-border"
                >
                  <Icon className={`w-5 h-5 ${colorClass} flex-shrink-0 mt-0.5`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{log.type}</span>
                      <span className="text-xs text-text-secondary">
                        {formatRelative(log.timestamp)}
                      </span>
                    </div>
                    <p className="text-sm text-text-secondary mt-1">{log.description}</p>
                    {log.metadata && (
                      <pre className="mt-2 p-2 rounded bg-background text-xs overflow-x-auto">
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              );
            })}

            {!logs?.length && (
              <p className="text-center text-text-secondary py-8">
                Nessuna attività recente
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};