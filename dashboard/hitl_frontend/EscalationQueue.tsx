/**
 * AUTO-BROKER HITL Dashboard - Escalation Queue Component
 * React/TypeScript component for managing customer escalations
 * Security & Compliance - P0 Critical
 */

import React, { useState, useEffect } from 'react';
import { Phone, CheckCircle, AlertTriangle, User, Clock, MessageSquare } from 'lucide-react';

interface EscalationItem {
  escalationId: string;
  leadId: string;
  shipmentId?: string;
  priority: 10 | 7 | 5 | 3; // CRITICAL, HIGH, MEDIUM, LOW
  sentimentScore: number;
  dominantEmotion: string;
  profileType: string;
  contextSummary: string;
  createdAt: string;
  assignedTo?: string;
  status: 'open' | 'assigned' | 'resolved';
}

interface LeadContext {
  nome: string;
  cognome: string;
  email: string;
  telefono: string;
  azienda: string;
  profileSummary: string;
  interactionHistory: Array<{
    timestamp: string;
    type: string;
    summary: string;
  }>;
}

export const EscalationQueue: React.FC = () => {
  const [escalations, setEscalations] = useState<EscalationItem[]>([]);
  const [selectedEscalation, setSelectedEscalation] = useState<EscalalationItem | null>(null);
  const [leadContext, setLeadContext] = useState<LeadContext | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [filter, setFilter] = useState<'all' | 'unassigned' | 'critical'>('all');

  // Fetch escalation queue
  useEffect(() => {
    const fetchQueue = async () => {
      try {
        const response = await fetch('/hitl/queue', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (response.ok) {
          const data = await response.json();
          setEscalations(data);
        }
      } catch (error) {
        console.error('Failed to fetch queue:', error);
      }
    };

    fetchQueue();
    const interval = setInterval(fetchQueue, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  // WebSocket for real-time updates
  useEffect(() => {
    const token = localStorage.getItem('token');
    const ws = new WebSocket(`wss://${window.location.host}/hitl/ws?token=${token}`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'new_escalation') {
        setEscalations(prev => [message.data, ...prev]);
        // Play notification sound
        new Audio('/notification.mp3').play().catch(() => {});
      }
    };

    return () => ws.close();
  }, []);

  const fetchLeadContext = async (leadId: string) => {
    try {
      const response = await fetch(`/api/leads/${leadId}/context`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (response.ok) {
        const data = await response.json();
        setLeadContext(data);
      }
    } catch (error) {
      console.error('Failed to fetch lead context:', error);
    }
  };

  const handleAssign = async (escalationId: string) => {
    try {
      const response = await fetch(`/hitl/queue/${escalationId}/assign`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (response.ok) {
        setEscalations(prev => prev.map(e => 
          e.escalationId === escalationId 
            ? { ...e, assignedTo: 'me', status: 'assigned' }
            : e
        ));
      }
    } catch (error) {
      alert('Failed to assign');
    }
  };

  const handleResolve = async (escalationId: string) => {
    if (resolutionNotes.length < 10) {
      alert('Resolution notes must be at least 10 characters');
      return;
    }

    try {
      const response = await fetch(`/hitl/queue/${escalationId}/resolve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ resolution_notes: resolutionNotes })
      });
      if (response.ok) {
        setEscalations(prev => prev.filter(e => e.escalationId !== escalationId));
        setSelectedEscalation(null);
        setResolutionNotes('');
      }
    } catch (error) {
      alert('Failed to resolve');
    }
  };

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 10: return '#dc2626'; // Critical - red
      case 7: return '#f97316';  // High - orange
      case 5: return '#eab308';  // Medium - yellow
      case 3: return '#22c55e';  // Low - green
      default: return '#6b7280';
    }
  };

  const getPriorityLabel = (priority: number) => {
    switch (priority) {
      case 10: return 'CRITICAL';
      case 7: return 'HIGH';
      case 5: return 'MEDIUM';
      case 3: return 'LOW';
      default: return 'UNKNOWN';
    }
  };

  const filteredEscalations = escalations.filter(e => {
    if (filter === 'unassigned') return !e.assignedTo;
    if (filter === 'critical') return e.priority >= 7;
    return true;
  }).sort((a, b) => b.priority - a.priority);

  return (
    <div className="escalation-queue-container" style={{ display: 'flex', height: '100vh' }}>
      {/* Left Panel - Queue List */}
      <div style={{ width: '400px', borderRight: '1px solid #e5e7eb', overflowY: 'auto' }}>
        <div style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
          <h2 style={{ marginBottom: '12px' }}>Escalation Queue ({filteredEscalations.length})</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            {(['all', 'unassigned', 'critical'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: '6px 12px',
                  border: '1px solid #e5e7eb',
                  borderRadius: '4px',
                  backgroundColor: filter === f ? '#3b82f6' : 'white',
                  color: filter === f ? 'white' : '#374151',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div>
          {filteredEscalations.map(escalation => (
            <div
              key={escalation.escalationId}
              onClick={() => {
                setSelectedEscalation(escalation);
                fetchLeadContext(escalation.leadId);
              }}
              style={{
                padding: '16px',
                borderBottom: '1px solid #e5e7eb',
                cursor: 'pointer',
                backgroundColor: selectedEscalation?.escalationId === escalation.escalationId ? '#eff6ff' : 'white'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 'bold',
                  backgroundColor: getPriorityColor(escalation.priority),
                  color: 'white'
                }}>
                  {getPriorityLabel(escalation.priority)}
                </span>
                {escalation.assignedTo && (
                  <span style={{ fontSize: '12px', color: '#3b82f6' }}>
                    <User size={12} style={{ display: 'inline', marginRight: '4px' }} />
                    Assigned
                  </span>
                )}
              </div>
              
              <div style={{ marginBottom: '8px' }}>
                <strong>Lead: {escalation.leadId}</strong>
                {escalation.shipmentId && (
                  <span style={{ fontSize: '12px', color: '#666', marginLeft: '8px' }}>
                    ({escalation.shipmentId})
                  </span>
                )}
              </div>

              <div style={{ fontSize: '14px', color: '#374151', marginBottom: '8px' }}>
                {escalation.contextSummary}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#666' }}>
                <span style={{
                  color: escalation.sentimentScore < -0.5 ? '#dc2626' : '#eab308'
                }}>
                  Sentiment: {(escalation.sentimentScore * 100).toFixed(0)}%
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={12} />
                  {Math.round((Date.now() - new Date(escalation.createdAt).getTime()) / 60000)}m
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right Panel - Detail View */}
      <div style={{ flex: 1, padding: '24px', overflowY: 'auto' }}>
        {selectedEscalation ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div>
                <h1 style={{ fontSize: '24px', marginBottom: '8px' }}>
                  Escalation {selectedEscalation.escalationId}
                </h1>
                <div style={{ display: 'flex', gap: '16px', color: '#666' }}>
                  <span>Lead: <strong>{selectedEscalation.leadId}</strong></span>
                  <span>Priority: <strong style={{ color: getPriorityColor(selectedEscalation.priority) }}>
                    {getPriorityLabel(selectedEscalation.priority)}
                  </strong></span>
                  <span>Profile: <strong>{selectedEscalation.profileType}</strong></span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                {!selectedEscalation.assignedTo && (
                  <button
                    onClick={() => handleAssign(selectedEscalation.escalationId)}
                    style={{
                      padding: '12px 24px',
                      backgroundColor: '#3b82f6',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <User size={18} />
                    Assign to Me
                  </button>
                )}
                <button
                  onClick={() => window.open(`tel:${leadContext?.telefono}`)}
                  style={{
                    padding: '12px 24px',
                    backgroundColor: '#22c55e',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Phone size={18} />
                  Call Now
                </button>
              </div>
            </div>

            {/* Lead Context */}
            {leadContext && (
              <div style={{
                backgroundColor: '#f9fafb',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '24px'
              }}>
                <h3 style={{ marginBottom: '12px' }}>Lead Context</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                  <div>
                    <span style={{ color: '#666', fontSize: '14px' }}>Name:</span>
                    <div>{leadContext.nome} {leadContext.cognome}</div>
                  </div>
                  <div>
                    <span style={{ color: '#666', fontSize: '14px' }}>Company:</span>
                    <div>{leadContext.azienda}</div>
                  </div>
                  <div>
                    <span style={{ color: '#666', fontSize: '14px' }}>Email:</span>
                    <div>{leadContext.email}</div>
                  </div>
                  <div>
                    <span style={{ color: '#666', fontSize: '14px' }}>Phone:</span>
                    <div>{leadContext.telefono}</div>
                  </div>
                </div>
                <div style={{ marginTop: '12px' }}>
                  <span style={{ color: '#666', fontSize: '14px' }}>Profile:</span>
                  <div>{leadContext.profileSummary}</div>
                </div>
              </div>
            )}

            {/* Interaction History */}
            {leadContext?.interactionHistory && (
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ marginBottom: '12px' }}>Recent Interactions</h3>
                {leadContext.interactionHistory.slice(0, 5).map((interaction, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '12px',
                      borderLeft: '3px solid #3b82f6',
                      backgroundColor: '#f9fafb',
                      marginBottom: '8px'
                    }}
                  >
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      {new Date(interaction.timestamp).toLocaleString()}
                    </div>
                    <div style={{ fontWeight: 'bold', marginTop: '4px' }}>
                      {interaction.type}
                    </div>
                    <div style={{ fontSize: '14px', marginTop: '4px' }}>
                      {interaction.summary}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Resolution */}
            <div style={{
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '16px'
            }}>
              <h3 style={{ marginBottom: '12px' }}>Resolution</h3>
              <textarea
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="Describe how you resolved this escalation... (min 10 chars)"
                style={{
                  width: '100%',
                  minHeight: '100px',
                  padding: '12px',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  marginBottom: '12px'
                }}
              />
              <button
                onClick={() => handleResolve(selectedEscalation.escalationId)}
                disabled={resolutionNotes.length < 10}
                style={{
                  padding: '12px 24px',
                  backgroundColor: resolutionNotes.length >= 10 ? '#22c55e' : '#9ca3af',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: resolutionNotes.length >= 10 ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <CheckCircle size={18} />
                Mark as Resolved
              </button>
            </div>
          </div>
        ) : (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#9ca3af'
          }}>
            <MessageSquare size={48} style={{ marginBottom: '16px' }} />
            <p>Select an escalation from the queue to view details</p>
          </div>
        )}
      </div>
    </div>
  );
};
