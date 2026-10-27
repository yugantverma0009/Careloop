import React, { useState, useRef, useEffect } from 'react';
import { login, getUser } from '../services/api';

const DEMO_WORKSPACES = [
  {
    id: 'doctor',
    role: 'Doctor',
    initials: 'DR',
    title: 'Attending Physician',
    name: 'Dr. Ananya Rao',
    department: 'Cardiology & Surgical Recovery',
    email: 'ananya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/staff',
    badgeColor: '#0284c7',
  },
  {
    id: 'nurse',
    role: 'Nurse',
    initials: 'PN',
    title: 'Triage Nurse',
    name: 'Nurse Priya Sharma',
    department: 'Post-Op Triage & Flag Response',
    email: 'priya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/staff',
    badgeColor: '#7c3aed',
  },
  {
    id: 'patient',
    role: 'Patient',
    initials: 'AP',
    title: 'Recovering Patient',
    name: 'Aarav Patel',
    department: 'Post-CABG Day 3 Telemetry',
    email: 'aarav.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/patient',
    badgeColor: '#059669',
  },
  {
    id: 'caregiver',
    role: 'Caregiver',
    initials: 'SP',
    title: 'Family Caregiver',
    name: 'Sunita Patel',
    department: 'Proxy Medication & Vitals Guardian',
    email: 'caregiver1.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/patient',
    badgeColor: '#d97706',
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
  const currentWorkspace = DEMO_WORKSPACES.find(
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
      // Navigate to target route
      if (window.location.pathname !== workspace.targetRoute) {
        window.location.href = workspace.targetRoute;
      } else {
        window.location.reload();
      }
    } catch (err) {
      console.error('Failed to switch workspace', err);
      alert(`Could not switch demo workspace: ${err.message}`);
    } finally {
      setSwitching(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', position: 'relative' }} ref={menuRef}>
      {/* Notification Bell with alert dot */}
      <div
        style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          border: '1px solid rgba(226, 232, 240, 0.4)',
          background: 'rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          cursor: 'pointer',
          color: '#cbd5e1',
          transition: 'all 0.2s',
        }}
        title="Active Clinical Alerts"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {/* Red pulse notification dot */}
        <span
          style={{
            position: 'absolute',
            top: '8px',
            right: '8px',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#ef4444',
            boxShadow: '0 0 0 2px #0f172a',
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
          gap: '10px',
          padding: '5px 12px 5px 6px',
          borderRadius: '10px',
          border: isOpen ? '1.5px solid #0284c7' : '1px solid rgba(226, 232, 240, 0.25)',
          background: isOpen ? 'rgba(2, 132, 199, 0.15)' : 'rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(8px)',
          cursor: switching ? 'not-allowed' : 'pointer',
          color: '#ffffff',
          transition: 'all 0.2s ease',
          outline: 'none',
        }}
      >
        {/* Avatar box with initials */}
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: currentWorkspace.badgeColor,
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '13px',
            fontWeight: 800,
            letterSpacing: '0.02em',
            boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
          }}
        >
          {currentWorkspace.initials}
        </div>

        {/* User Info Label */}
        <div style={{ textAlign: 'left', lineHeight: 1.25 }}>
          <div style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc', whiteSpace: 'nowrap' }}>
            {currentWorkspace.name}
          </div>
          <div style={{ fontSize: '11px', color: '#94a3b8', whiteSpace: 'nowrap' }}>
            {currentWorkspace.title}
          </div>
        </div>

        {/* Chevron Icon */}
        <div style={{
          color: '#94a3b8',
          fontSize: '11px',
          marginLeft: '4px',
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease',
        }}>
          ▼
        </div>
      </button>

      {/* ─── DROPDOWN POPOVER (Exact BhoomiSetu Style) ─────────────────── */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '320px',
            background: '#ffffff',
            borderRadius: '14px',
            boxShadow: '0 20px 45px -10px rgba(15, 23, 42, 0.25), 0 4px 12px rgba(0, 0, 0, 0.08)',
            border: '1px solid #e2e8f0',
            padding: '14px',
            zIndex: 1000,
            animation: 'fadeIn 0.18s ease-out',
          }}
        >
          {/* Header Title */}
          <div
            style={{
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: '#64748b',
              padding: '4px 8px 10px 8px',
              borderBottom: '1px solid #f1f5f9',
              marginBottom: '8px',
            }}
          >
            SWITCH DEMO WORKSPACE
          </div>

          {/* List of Roles */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {DEMO_WORKSPACES.map((workspace) => {
              const isActive =
                activeUser.email === workspace.email ||
                activeRole.toLowerCase() === workspace.role.toLowerCase();

              return (
                <div
                  key={workspace.id}
                  onClick={() => handleSelectWorkspace(workspace)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    cursor: switching ? 'not-allowed' : 'pointer',
                    background: isActive ? '#f0fdf4' : 'transparent',
                    border: isActive ? '1px solid #bbf7d0' : '1px solid transparent',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = '#f8fafc';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {/* Initials Badge */}
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        background: isActive ? '#dcfce7' : '#f1f5f9',
                        color: isActive ? '#15803d' : '#0284c7',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: 800,
                        flexShrink: 0,
                      }}
                    >
                      {workspace.initials}
                    </div>

                    {/* Role Details */}
                    <div>
                      <div style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        color: isActive ? '#166534' : '#0f172a',
                        lineHeight: 1.25,
                      }}>
                        {workspace.title}
                      </div>
                      <div style={{
                        fontSize: '11px',
                        color: '#64748b',
                        lineHeight: 1.25,
                        marginTop: '2px',
                      }}>
                        {workspace.name} · {workspace.role}
                      </div>
                    </div>
                  </div>

                  {/* Active Indicator Shield */}
                  {isActive && (
                    <div
                      style={{
                        color: '#16a34a',
                        display: 'flex',
                        alignItems: 'center',
                        marginLeft: '8px',
                      }}
                      title="Currently active demo workspace"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                        <path d="M9 12l2 2 4-4" />
                      </svg>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Quick Helper Note */}
          <div
            style={{
              marginTop: '10px',
              paddingTop: '8px',
              borderTop: '1px solid #f1f5f9',
              fontSize: '11px',
              color: '#94a3b8',
              textAlign: 'center',
            }}
          >
            {switching ? 'Switching workspace...' : 'Click any role to switch workspace instantly'}
          </div>
        </div>
      )}
    </div>
  );
}
