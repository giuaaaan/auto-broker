/**
 * AUTO-BROKER HITL Dashboard - Emergency Override Component
 * React/TypeScript component for emergency interventions
 * Security & Compliance - P0 Critical
 */

import React, { useState, useEffect } from 'react';
import { AlertCircle, StopCircle, Play, Shield, Activity } from 'lucide-react';

interface OverrideFormData {
  overrideType: 'pricing' | 'shipment_block' | 'agent_halt' | 'carrier_change';
  targetId: string;
  reason: string;
  newValue?: Record<string, any>;
  requiresImmediate: boolean;
}

interface AgentStatus {
  agentName: string;
  status: 'active' | 'paused' | 'error' | 'overridden';
  currentLeadId: string | null;
  lastLogs: Array<{
    timestamp: string;
    action: string;
    leadId?: string;
  }>;
  metrics: {
    conversionRate: number;
    avgCallDuration: number;
    escalationRate: number;
  };
}

export const EmergencyOverride: React.FC = () => {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [overrideForm, setOverrideForm] = useState<OverrideFormData>({
    overrideType: 'pricing',
    targetId: '',
    reason: '',
    requiresImmediate: false
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showKillSwitch, setShowKillSwitch] = useState(false);
  const [mfaCode, setMfaCode] = useState('');

  // Fetch agent status
  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await fetch('/hitl/agents/status', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (response.ok) {
          const data = await response.json();
          setAgents(data);
        }
      } catch (error) {
        console.error('Failed to fetch agent status:', error);
      }
    };

    fetchAgents();
    const interval = setInterval(fetchAgents, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const token = localStorage.getItem('token');
    const ws = new WebSocket(`wss://${window.location.host}/hitl/ws?token=${token}`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'agent_update') {
        // Update agent status
        setAgents(prev => prev.map(agent => 
          agent.agentName === message.data.agentName 
            ? { ...agent, status: message.data.status }
            : agent
        ));
      }
    };

    return () => ws.close();
  }, []);

  const handleSubmitOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (overrideForm.reason.length < 20) {
      alert('Reason must be at least 20 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch(`/hitl/override/${overrideForm.overrideType}/${overrideForm.targetId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          ...overrideForm,
          mfa_code: mfaCode // MFA required
        })
      });

      if (response.ok) {
        alert('Override executed successfully');
        setOverrideForm({
          overrideType: 'pricing',
          targetId: '',
          reason: '',
          requiresImmediate: false
        });
        setMfaCode('');
      } else {
        const error = await response.text();
        alert(`Override failed: ${error}`);
      }
    } catch (error) {
      alert('Network error - check console');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKillSwitch = async () => {
    if (!confirm('EMERGENCY: This will halt ALL AI agents. Are you sure?')) {
      return;
    }

    try {
      // Halt each agent
      for (const agent of agents) {
        if (agent.status === 'active') {
          await fetch(`/hitl/agents/${agent.agentName}/halt`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({
              reason: 'EMERGENCY KILL SWITCH - Supervisor initiated system halt'
            })
          });
        }
      }
      alert('All agents halted');
    } catch (error) {
      alert('Kill switch failed');
    }
    setShowKillSwitch(false);
  };

  return (
    <div className="emergency-override-container">
      {/* Kill Switch Button */}
      <div className="kill-switch-section" style={{ marginBottom: '24px' }}>
        <button
          onClick={() => setShowKillSwitch(true)}
          style={{
            backgroundColor: '#dc2626',
            color: 'white',
            padding: '16px 32px',
            fontSize: '18px',
            fontWeight: 'bold',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <StopCircle size={24} />
          EMERGENCY: BLOCK ALL SHIPMENTS
        </button>
        <p style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
          Immediately halts all AI agents. Requires supervisor + MFA.
        </p>
      </div>

      {/* Kill Switch Modal */}
      {showKillSwitch && (
        <div className="modal" style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: 'white',
            padding: '32px',
            borderRadius: '12px',
            maxWidth: '500px',
            width: '90%'
          }}>
            <div style={{ color: '#dc2626', marginBottom: '16px' }}>
              <AlertCircle size={48} />
            </div>
            <h2 style={{ color: '#dc2626', marginBottom: '16px' }}>
              CONFIRM EMERGENCY HALT
            </h2>
            <p style={{ marginBottom: '16px' }}>
              This will immediately stop all AI agents (SARA, MARCO, CARLO, etc.).
              All active calls will be terminated.
            </p>
            <div style={{ marginBottom: '16px' }}>
              <label>Enter MFA Code:</label>
              <input
                type="text"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                placeholder="6-digit MFA code"
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '18px',
                  border: '2px solid #dc2626',
                  borderRadius: '6px',
                  marginTop: '8px'
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => setShowKillSwitch(false)}
                style={{
                  flex: 1,
                  padding: '12px',
                  backgroundColor: '#e5e7eb',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleKillSwitch}
                disabled={mfaCode.length !== 6}
                style={{
                  flex: 1,
                  padding: '12px',
                  backgroundColor: mfaCode.length === 6 ? '#dc2626' : '#fca5a5',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: mfaCode.length === 6 ? 'pointer' : 'not-allowed'
                }}
              >
                CONFIRM HALT
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Agent Status Grid */}
      <div className="agent-status-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        {agents.map(agent => (
          <div
            key={agent.agentName}
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '16px',
              backgroundColor: agent.status === 'active' ? '#f0fdf4' : '#fef2f2'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>{agent.agentName}</h3>
              <span style={{
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '12px',
                backgroundColor: agent.status === 'active' ? '#22c55e' : '#ef4444',
                color: 'white'
              }}>
                {agent.status.toUpperCase()}
              </span>
            </div>
            <p style={{ fontSize: '14px', color: '#666' }}>
              Lead: {agent.currentLeadId || 'None'}
            </p>
            <div style={{ marginTop: '12px' }}>
              <div style={{ fontSize: '12px', color: '#666' }}>Recent Activity:</div>
              {agent.lastLogs.slice(0, 3).map((log, i) => (
                <div key={i} style={{ fontSize: '12px', marginTop: '4px' }}>
                  {new Date(log.timestamp).toLocaleTimeString()}: {log.action}
                </div>
              ))}
            </div>
            <div style={{ marginTop: '12px', display: 'flex', gap: '16px', fontSize: '12px' }}>
              <span>Conv: {(agent.metrics.conversionRate * 100).toFixed(1)}%</span>
              <span>Avg: {Math.round(agent.metrics.avgCallDuration)}s</span>
              <span>Esc: {(agent.metrics.escalationRate * 100).toFixed(1)}%</span>
            </div>
          </div>
        ))}
      </div>

      {/* Override Form */}
      <div className="override-form" style={{
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        padding: '24px'
      }}>
        <h2 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Shield size={24} />
          Manual Override
        </h2>
        <form onSubmit={handleSubmitOverride}>
          <div style={{ marginBottom: '16px' }}>
            <label>Override Type:</label>
            <select
              value={overrideForm.overrideType}
              onChange={(e) => setOverrideForm({
                ...overrideForm,
                overrideType: e.target.value as OverrideFormData['overrideType']
              })}
              style={{ width: '100%', padding: '8px', marginTop: '4px' }}
            >
              <option value="pricing">Pricing Adjustment</option>
              <option value="shipment_block">Block Shipment</option>
              <option value="agent_halt">Halt Agent</option>
              <option value="carrier_change">Change Carrier</option>
            </select>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label>Target ID (Shipment/Agent ID):</label>
            <input
              type="text"
              value={overrideForm.targetId}
              onChange={(e) => setOverrideForm({ ...overrideForm, targetId: e.target.value })}
              placeholder="e.g., SHIP-12345"
              style={{ width: '100%', padding: '8px', marginTop: '4px' }}
              required
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label>Reason (min 20 chars):</label>
            <textarea
              value={overrideForm.reason}
              onChange={(e) => setOverrideForm({ ...overrideForm, reason: e.target.value })}
              placeholder="Detailed justification for override..."
              style={{ width: '100%', padding: '8px', marginTop: '4px', minHeight: '80px' }}
              required
              minLength={20}
            />
            <div style={{ fontSize: '12px', color: overrideForm.reason.length >= 20 ? '#22c55e' : '#ef4444' }}>
              {overrideForm.reason.length}/20 characters
            </div>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label>MFA Code:</label>
            <input
              type="text"
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              placeholder="6-digit code"
              maxLength={6}
              style={{ width: '200px', padding: '8px', marginTop: '4px' }}
              required
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={overrideForm.requiresImmediate}
                onChange={(e) => setOverrideForm({ ...overrideForm, requiresImmediate: e.target.checked })}
              />
              Requires immediate execution
            </label>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || overrideForm.reason.length < 20 || mfaCode.length !== 6}
            style={{
              padding: '12px 24px',
              backgroundColor: isSubmitting ? '#9ca3af' : '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: isSubmitting ? 'not-allowed' : 'pointer'
            }}
          >
            {isSubmitting ? 'Executing...' : 'Execute Override'}
          </button>
        </form>
      </div>
    </div>
  );
};
