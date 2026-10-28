import React, { useState, useRef, useEffect } from 'react';
import { login, getUser } from '../services/api';
import {
  IconStethoscope,
  IconNurse,
  IconPatient,
  IconCaregiver,
  IconBell,
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
    name: 'Dr. Ananya Rao',
    department: 'Cardiology & Clinical Escalations',
    email: 'ananya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/staff',
    badgeColor: 'var(--accent-blue)',
    IconComponent: IconStethoscope,
  },
  {
    id: 'nurse',
    role: 'Nurse',
    initials: 'PN',
    title: 'Triage Nurse',
    name: 'Nurse Priya Sharma',
    department: 'Triage Board & Flag Acknowledgment',
    email: 'priya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/staff',
    badgeColor: 'var(--accent-teal)',
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
    badgeColor: 'var(--success-green)',
    IconComponent: IconPatient,
  },
  {
    id: 'caregiver',
    role: 'Caregiver',
    initials: 'SP',
    title: 'Family Caregiver',
    name: 'Sunita Patel',
    department: 'Proxy Medication & Adherence Guardian',
    email: 'caregiver1.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/patient',
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

  const ActiveIcon = currentWorkspace.IconComponent || IconPatient;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', position: 'relative' }} ref={menuRef}>
      {/* Notification Bell with pulse indicator */}
      <div
        style={{
          width: '36px',
          height: '36px',
          borderRadius: '9px',
          border: '1px solid var(--border-subtle)',
          background: 'var(--bg-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          cursor: 'pointer',
          color: 'var(--text-secondary)',
          boxShadow: 'var(--shadow-sm)',
        }}
        title="Alerts and notifications active"
      >
        <IconBell width={16} height={16} />
        <span
          className="pulse-dot"
          style={{
            position: 'absolute',
            top: '7px',
            right: '7px',
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            background: 'var(--alert-red)',
          }}
        />
      </div>

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
