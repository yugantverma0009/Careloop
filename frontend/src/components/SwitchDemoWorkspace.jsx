import React, { useState, useRef, useEffect } from 'react';
import { login, getUser, resetDemo, simulateReading } from '../services/api';
import {
  IconStethoscope,
  IconNurse,
  IconPatient,
  IconCaregiver,
  IconChevronDown,
  IconCheck,
  IconShieldCheck,
} from './Icons';

const DEMO_WORKSPACES = [
  {
    id: 'doctor',
    role: 'Doctor',
    initials: 'DR',
    title: 'Attending Physician',
    name: 'Dr. Ananya Sharma',
    department: 'Attending Physician & Clinical Decisions',
    email: 'ananya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/doctor',
    badgeColor: '#7c3aed',
    IconComponent: IconStethoscope,
  },
  {
    id: 'nurse',
    role: 'Nurse',
    initials: 'PN',
    title: 'Triage Nurse',
    name: 'Priya Nair',
    department: 'Triage Board & Patient Call List',
    email: 'priya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/nurse',
    badgeColor: 'var(--accent-blue)',
    IconComponent: IconNurse,
  },
  {
    id: 'patient',
    role: 'Patient',
    initials: 'AP',
    title: 'Recovering Patient',
    name: 'Aarav Patel',
    department: 'Post-CABG Day 3 Telemetry & Doses',
    email: 'aarav.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/patient',
    badgeColor: 'var(--accent-teal)',
    IconComponent: IconPatient,
  },
  {
    id: 'caregiver',
    role: 'Caregiver',
    initials: 'NP',
    title: 'Family Helper',
    name: 'Neha Patel',
    department: 'Family Support & Emergency Contacts',
    email: 'caregiver1.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/family',
    badgeColor: 'var(--warning-amber)',
    IconComponent: IconCaregiver,
  },
];

export default function SwitchDemoWorkspace({ currentUser, onSwitchSuccess }) {
  const [isOpen, setIsOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const menuRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const activeUser = currentUser || getUser() || {};
  const activeRole = activeUser.role || 'Patient';

  // Determine active workspace metadata
  const currentWorkspace =
    DEMO_WORKSPACES.find(
      (w) => w.role.toLowerCase() === activeRole.toLowerCase()
    ) || DEMO_WORKSPACES[2];

  const handleSelectWorkspace = async (workspace) => {
    if (workspace.email === activeUser.email && !switching) {
      setIsOpen(false);
      return;
    }
    setSwitching(true);
    try {
      const data = await login(workspace.email, workspace.password);
      setIsOpen(false);
      if (onSwitchSuccess) {
        onSwitchSuccess(data);
      }
      if (window.location.pathname !== workspace.targetRoute) {
        window.location.href = workspace.targetRoute;
      } else {
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to switch workspace', err);
      alert(`Could not switch role: ${err.message}`);
    } finally {
      setSwitching(false);
    }
  };

  const [actionLoading, setActionLoading] = useState(false);
  const [actionFeedback, setActionFeedback] = useState('');

  const handleResetDemo = async () => {
    setActionLoading(true);
    setActionFeedback('Resetting demo state...');
    try {
      const res = await resetDemo();
      setActionFeedback(res?.message || 'Reset complete: 5 patients, 3 open flags, 5 tasks');
      setTimeout(() => {
        window.location.reload();
      }, 1200);
    } catch (err) {
      console.error('Failed to reset demo', err);
      setActionFeedback(`Reset failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSimulateReading = async () => {
    setActionLoading(true);
    setActionFeedback('Sending SpO₂ reading 91%...');
    try {
      const res = await simulateReading({
        patient_id: 1,
        device_id: 'DEV-ESP32-001',
        measurement_type: 'SpO2',
        value: 91.0,
        unit: '%',
      });
      setActionFeedback(res?.message || '✓ SpO₂ 91% sent! Urgent alert triggered.');
      setTimeout(() => {
        window.location.reload();
      }, 1200);
    } catch (err) {
      console.error('Failed to simulate reading', err);
      setActionFeedback(`Simulation failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const ActiveIcon = currentWorkspace.IconComponent || IconPatient;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', position: 'relative' }} ref={menuRef}>
      {/* Demo Switcher Capsule Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={switching}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '9px',
          padding: '5px 12px 5px 6px',
          borderRadius: '24px',
          border: '1px solid var(--border-subtle)',
          background: 'var(--bg-card)',
          color: 'var(--text-primary)',
          cursor: 'pointer',
          boxShadow: 'var(--shadow-sm)',
          transition: 'all 0.15s ease',
        }}
      >
        {/* Role Avatar Badge */}
        <div
          style={{
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            background: 'var(--accent-teal-soft)',
            color: 'var(--accent-teal)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '11px',
          }}
        >
          <ActiveIcon width={15} height={15} />
        </div>

        <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {activeUser.name ? activeUser.name.split(' ')[0] : currentWorkspace.name.split(' ')[0]}
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
            {currentWorkspace.title}
          </div>
        </div>

        <IconChevronDown
          width={13}
          height={13}
          style={{
            color: 'var(--text-muted)',
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
          }}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '320px',
            borderRadius: '14px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 1000,
            padding: '8px',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '10px 12px 8px',
              borderBottom: '1px solid var(--border-subtle)',
              marginBottom: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
                Switch Role
              </span>
              <span
                style={{
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: 'var(--accent-teal-soft)',
                  color: 'var(--accent-teal-text)',
                  fontWeight: 600,
                }}
              >
                Quick Switch
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Switch roles quickly to review different views
            </div>
          </div>

          {/* List of Workspaces */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {DEMO_WORKSPACES.map((w) => {
              const isCurrent =
                w.email.toLowerCase() === (activeUser.email || '').toLowerCase() ||
                w.role.toLowerCase() === activeRole.toLowerCase();
              const RoleIcon = w.IconComponent;

              return (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => handleSelectWorkspace(w)}
                  disabled={switching}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: isCurrent ? '1px solid var(--accent-teal)' : '1px solid transparent',
                    background: isCurrent ? 'var(--accent-teal-soft)' : 'transparent',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isCurrent) e.currentTarget.style.background = 'var(--bg-card-hover)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isCurrent) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: w.badgeColor,
                      flexShrink: 0,
                    }}
                  >
                    <RoleIcon width={16} height={16} />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {w.title}
                      </span>
                      <span
                        style={{
                          fontSize: '10px',
                          color: 'var(--text-muted)',
                        }}
                      >
                        · {w.role}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-secondary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {w.name}
                    </div>
                    <div
                      style={{
                        fontSize: '10px',
                        color: 'var(--text-muted)',
                        marginTop: '1px',
                      }}
                    >
                      {w.department}
                    </div>
                  </div>

                  {isCurrent && (
                    <div style={{ color: 'var(--accent-teal)', flexShrink: 0 }}>
                      <IconCheck width={15} height={15} />
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Presenter Demo Controls (Phase 6) */}
          <div
            style={{
              marginTop: '8px',
              padding: '10px 10px 8px',
              borderTop: '1px solid var(--border-subtle)',
              background: 'var(--bg-surface, #f8fafc)',
              borderRadius: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Presenter Controls
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
              <button
                type="button"
                onClick={handleSimulateReading}
                disabled={actionLoading}
                style={{
                  padding: '7px 8px',
                  borderRadius: '6px',
                  border: '1px solid #d97706',
                  background: '#fffbeb',
                  color: '#b45309',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: actionLoading ? 'wait' : 'pointer',
                  textAlign: 'center',
                }}
                title="Sends Aarav low SpO2 (91%) to trigger live cross-role alert"
              >
                ⚡ Send 91% SpO₂
              </button>
              <button
                type="button"
                onClick={handleResetDemo}
                disabled={actionLoading}
                style={{
                  padding: '7px 8px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  background: 'var(--bg-card, #ffffff)',
                  color: 'var(--text-primary, #0f172a)',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: actionLoading ? 'wait' : 'pointer',
                  textAlign: 'center',
                }}
                title="Restores demo to clean 5-patient starting state (<30s)"
              >
                🔄 Reset Demo
              </button>
            </div>
            {actionFeedback && (
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  color: actionFeedback.includes('failed') ? '#dc2626' : '#059669',
                  marginTop: '2px',
                  textAlign: 'center',
                  background: 'rgba(0,0,0,0.03)',
                  padding: '4px 6px',
                  borderRadius: '4px',
                }}
              >
                {actionFeedback}
              </div>
            )}
          </div>

          {/* Footer note */}
          <div
            style={{
              marginTop: '6px',
              padding: '8px 10px 4px',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '10px',
              color: 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <IconShieldCheck width={12} height={12} style={{ color: 'var(--accent-teal)' }} />
            <span>Access is protected by role-based rules.</span>
          </div>
        </div>
      )}
    </div>
  );
}
