import React, { useState, useEffect } from 'react';
import { API_BASE } from '../services/api';
import { IconX } from './Icons';

export default function AgentTraceModal({ runId, isOpen, onClose }) {
  const [traceData, setTraceData] = useState(null);
  const [loading, setLoading] = useState(false);
  const token = localStorage.getItem('careloop_token');

  useEffect(() => {
    if (!isOpen || !runId) {
      setTraceData(null);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE}/agent/runs/${runId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setTraceData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load trace', err);
        setLoading(false);
      });
  }, [isOpen, runId]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(15, 23, 42, 0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        backdropFilter: 'blur(3px)',
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '680px',
          maxHeight: '85vh',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid var(--border-subtle, #e2e8f0)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#f8fafc',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '16px' }}>⚡</span>
            <strong style={{ fontSize: '14px', color: '#0f172a' }}>Agent Execution Trace</strong>
            <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>{runId}</span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#64748b',
              padding: '4px',
              display: 'flex',
            }}
          >
            <IconX width={18} height={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>Loading trace data...</div>
          ) : traceData ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Agent</div>
                  <strong style={{ fontSize: '13px', color: '#0f172a' }}>{traceData.run?.agent_name}</strong>
                </div>
                <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Autonomy / Mode</div>
                  <strong style={{ fontSize: '13px', color: '#0f172a' }}>
                    {traceData.run?.autonomy_level} ({traceData.run?.mode})
                  </strong>
                </div>
                <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Latency</div>
                  <strong style={{ fontSize: '13px', color: '#0f172a' }}>{traceData.run?.latency_ms} ms</strong>
                </div>
              </div>

              <div>
                <h4 style={{ fontSize: '12px', fontWeight: 800, textTransform: 'uppercase', color: '#475569', marginBottom: '8px', letterSpacing: '0.04em' }}>
                  Pipeline Steps ({traceData.steps?.length || 0})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {traceData.steps?.map((step) => (
                    <div
                      key={step.step_id}
                      style={{
                        padding: '10px 12px',
                        borderRadius: '6px',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '12px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                        <span
                          style={{
                            fontWeight: 800,
                            fontSize: '10px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: step.step_type === 'Guard' ? '#dbeafe' : step.step_type === 'Plan' ? '#fef3c7' : '#e2e8f0',
                            color: step.step_type === 'Guard' ? '#1d4ed8' : step.step_type === 'Plan' ? '#b45309' : '#334155',
                          }}
                        >
                          {step.seq}. {step.step_type}
                        </span>
                        <span style={{ color: '#0f172a', fontWeight: 500 }}>{step.summary}</span>
                      </div>
                      <span style={{ fontSize: '11px', color: '#64748b', flexShrink: 0 }}>{step.ms} ms</span>
                    </div>
                  ))}
                </div>
              </div>

              {traceData.run?.guard_reasons && (
                <div style={{ padding: '12px', background: '#fff1f2', borderRadius: '8px', border: '1px solid #fecaca' }}>
                  <strong style={{ fontSize: '12px', color: '#991b1b' }}>Policy Guard Findings:</strong>
                  <div style={{ fontSize: '12px', color: '#7f1d1d', marginTop: '4px' }}>
                    {typeof traceData.run.guard_reasons === 'string'
                      ? traceData.run.guard_reasons
                      : JSON.stringify(traceData.run.guard_reasons)}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '30px', color: '#64748b' }}>No trace recorded for run ID {runId}</div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid #e2e8f0', background: '#f8fafc', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close Trace
          </button>
        </div>
      </div>
    </div>
  );
}

