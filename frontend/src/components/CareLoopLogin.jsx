import React, { useState } from 'react';
import { login } from '../services/api';

const DEMO_ROLES = [
  {
    id: 'doctor',
    title: 'Attending Physician',
    name: 'Dr. Ananya Rao',
    email: 'ananya.demo@example.test',
    password: 'Demo@12345',
    icon: '🩺',
    badge: 'Doctor · Clinical Escalations & Prescriptions',
    dashboardRoute: '/staff',
  },
  {
    id: 'nurse',
    title: 'Triage Nurse',
    name: 'Nurse Priya Sharma',
    email: 'priya.demo@example.test',
    password: 'Demo@12345',
    icon: '👩‍⚕️',
    badge: 'Nurse · Triage Board & Flag Acknowledgment',
    dashboardRoute: '/staff',
  },
  {
    id: 'patient',
    title: 'Recovering Patient',
    name: 'Aarav Patel (Post-CABG Day 3)',
    email: 'aarav.demo@example.test',
    password: 'Demo@12345',
    icon: '🧑',
    badge: 'Patient · Med Doses, Telemetry & Chat',
    dashboardRoute: '/patient',
  },
  {
    id: 'caregiver',
    title: 'Family Caregiver',
    name: 'Sunita Patel',
    email: 'caregiver1.demo@example.test',
    password: 'Demo@12345',
    icon: '🤝',
    badge: 'Caregiver · Proxy Dose Confirmation & Vitals',
    dashboardRoute: '/patient',
  },
];

export default function CareLoopLogin({ onLoginSuccess }) {
  const [selectedRoleIndex, setSelectedRoleIndex] = useState(2); // default to Patient (Aarav) for patient-centric showcase
  const [email, setEmail] = useState(DEMO_ROLES[2].email);
  const [password, setPassword] = useState(DEMO_ROLES[2].password);
  const [showPassword, setShowPassword] = useState(false);
  const [rememberRole, setRememberRole] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPublicModal, setShowPublicModal] = useState(false);

  const handleRoleChange = (index) => {
    const role = DEMO_ROLES[index];
    setSelectedRoleIndex(index);
    setEmail(role.email);
    setPassword(role.password);
    setError('');
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(email, password);
      if (onLoginSuccess) {
        onLoginSuccess(data);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const activeRole = DEMO_ROLES[selectedRoleIndex] || DEMO_ROLES[0];

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'row',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      background: '#f8fafc',
    }}>
      {/* ─── LEFT HERO PANEL (Deep Navy #03172c) ────────────────────────── */}
      <div
        className="login-hero-panel"
        style={{
          flex: '1.05',
          background: 'linear-gradient(165deg, #021226 0%, #041935 45%, #062348 100%)',
          padding: '48px 56px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          color: '#ffffff',
          position: 'relative',
          overflow: 'hidden',
          minWidth: '380px',
        }}
      >
        {/* Subtle decorative background glow */}
        <div style={{
          position: 'absolute',
          top: '-15%',
          left: '-15%',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(14, 165, 233, 0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Top bar with back link */}
        <div style={{ position: 'relative', zIndex: 2 }}>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '13px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              cursor: 'pointer',
              padding: 0,
              fontWeight: 500,
              transition: 'color 0.2s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            <span style={{ fontSize: '15px' }}>←</span> Back to CareLoop
          </button>
        </div>

        {/* Main Content Area */}
        <div style={{ position: 'relative', zIndex: 2, maxWidth: '520px', margin: '40px 0' }}>
          {/* Brand Emblem + Name */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '40px' }}>
            <div style={{
              width: '46px',
              height: '46px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #0284c7 0%, #0d9488 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 20px rgba(14, 165, 233, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
            }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: '20px', fontWeight: '800', letterSpacing: '-0.3px', color: '#ffffff' }}>
                Care<span style={{ color: '#38bdf8' }}>Loop</span>
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8', letterSpacing: '0.02em', fontWeight: 500 }}>
                Developed by HealthTitans
              </div>
            </div>
          </div>

          {/* Overline */}
          <div style={{
            fontSize: '11px',
            fontWeight: 800,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: '#38bdf8',
            marginBottom: '16px',
          }}>
            NATIONAL DIGITAL CLINICAL GOVERNANCE
          </div>

          {/* Headline */}
          <h1 style={{
            fontSize: '42px',
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: '-0.03em',
            color: '#ffffff',
            margin: '0 0 20px 0',
          }}>
            One trusted workflow <br />
            from discharge to <br />
            recovery.
          </h1>

          {/* Subtitle */}
          <p style={{
            fontSize: '15px',
            lineHeight: 1.6,
            color: '#94a3b8',
            margin: '0 0 34px 0',
          }}>
            Role-focused access for patient families, triage nurses, attending physicians and clinical leadership.
          </p>

          {/* Value Prop Checkmarks */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '22px',
                height: '22px',
                borderRadius: '50%',
                background: 'rgba(14, 165, 233, 0.15)',
                border: '1.5px solid #0284c7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38bdf8',
                fontSize: '12px',
                fontWeight: 'bold',
                flexShrink: 0,
              }}>
                ✓
              </div>
              <span style={{ fontSize: '13.5px', color: '#e2e8f0', fontWeight: 500 }}>
                Continuous IoT vitals & plausibility telemetry guard
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '22px',
                height: '22px',
                borderRadius: '50%',
                background: 'rgba(14, 165, 233, 0.15)',
                border: '1.5px solid #0284c7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38bdf8',
                fontSize: '12px',
                fontWeight: 'bold',
                flexShrink: 0,
              }}>
                ✓
              </div>
              <span style={{ fontSize: '13.5px', color: '#e2e8f0', fontWeight: 500 }}>
                Grounded clinical RAG & discharge instructions
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '22px',
                height: '22px',
                borderRadius: '50%',
                background: 'rgba(14, 165, 233, 0.15)',
                border: '1.5px solid #0284c7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#38bdf8',
                fontSize: '12px',
                fontWeight: 'bold',
                flexShrink: 0,
              }}>
                ✓
              </div>
              <span style={{ fontSize: '13.5px', color: '#e2e8f0', fontWeight: 500 }}>
                Autonomous 3-tier escalation ladder with audit trail
              </span>
            </div>
          </div>
        </div>

        {/* Footer Note */}
        <div style={{ position: 'relative', zIndex: 2, fontSize: '11px', color: '#64748b' }}>
          Smart Healthcare Hackathon 2026 · Demonstration environment
        </div>
      </div>

      {/* ─── RIGHT AUTHENTICATION PANEL (Clean White Card on Off-White) ─── */}
      <div style={{
        flex: '1.15',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px 24px',
        background: '#f8fafc',
      }}>
        {/* Floating Card */}
        <div style={{
          width: '100%',
          maxWidth: '460px',
          background: '#ffffff',
          borderRadius: '20px',
          padding: '38px 36px 32px 36px',
          boxShadow: '0 20px 45px -12px rgba(15, 23, 42, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04)',
          border: '1px solid #e2e8f0',
        }}>
          {/* Top Pill Badge */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            borderRadius: '999px',
            padding: '4px 12px',
            color: '#047857',
            fontSize: '12px',
            fontWeight: 600,
            marginBottom: '18px',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            Synthetic-data demonstration workspace
          </div>

          {/* Heading */}
          <h2 style={{
            fontSize: '25px',
            fontWeight: 800,
            color: '#0f172a',
            margin: '0 0 6px 0',
            letterSpacing: '-0.02em',
          }}>
            Welcome to CareLoop
          </h2>

          <p style={{
            fontSize: '13.5px',
            color: '#64748b',
            margin: '0 0 24px 0',
            lineHeight: 1.45,
          }}>
            Choose a stakeholder role and use the published demo credentials.
          </p>

          {/* Error Banner */}
          {error && (
            <div style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#b91c1c',
              padding: '11px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              marginBottom: '18px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Demo Role Selector Dropdown */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#475569',
                marginBottom: '6px',
              }}>
                Demo role
              </label>

              <div style={{ position: 'relative' }}>
                <div style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  fontSize: '16px',
                  pointerEvents: 'none',
                }}>
                  {activeRole.icon}
                </div>

                <select
                  value={selectedRoleIndex}
                  onChange={(e) => handleRoleChange(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '12px 36px 12px 38px',
                    borderRadius: '9px',
                    border: '1px solid #0284c7',
                    background: '#ffffff',
                    color: '#0f172a',
                    fontSize: '14px',
                    fontWeight: 600,
                    outline: 'none',
                    boxShadow: '0 0 0 3px rgba(2, 132, 199, 0.12)',
                    cursor: 'pointer',
                    appearance: 'none',
                    WebkitAppearance: 'none',
                    boxSizing: 'border-box',
                  }}
                >
                  {DEMO_ROLES.map((r, i) => (
                    <option key={r.id} value={i}>
                      {r.title} — {r.name}
                    </option>
                  ))}
                </select>

                {/* Dropdown Chevron */}
                <div style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  pointerEvents: 'none',
                  color: '#64748b',
                  fontSize: '12px',
                }}>
                  ▼
                </div>
              </div>
            </div>

            {/* Email Input */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#475569',
                marginBottom: '6px',
              }}>
                Email or employee ID
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="name@example.test"
                style={{
                  width: '100%',
                  padding: '11px 14px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#0f172a',
                  fontSize: '14px',
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                }}
                onFocus={(e) => (e.target.style.borderColor = '#0284c7')}
                onBlur={(e) => (e.target.style.borderColor = '#cbd5e1')}
              />
            </div>

            {/* Password Input with show/hide */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#475569',
                marginBottom: '6px',
              }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <div style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#94a3b8',
                  pointerEvents: 'none',
                  display: 'flex',
                  alignItems: 'center',
                }}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </div>

                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••••••"
                  style={{
                    width: '100%',
                    padding: '11px 40px 11px 36px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    background: '#ffffff',
                    color: '#0f172a',
                    fontSize: '14px',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'border-color 0.2s',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = '#0284c7')}
                  onBlur={(e) => (e.target.style.borderColor = '#cbd5e1')}
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'transparent',
                    border: 'none',
                    color: '#64748b',
                    cursor: 'pointer',
                    fontSize: '14px',
                    padding: 0,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Remember Role & Access Mode Row */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '20px',
              fontSize: '13px',
            }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#334155' }}>
                <input
                  type="checkbox"
                  checked={rememberRole}
                  onChange={(e) => setRememberRole(e.target.checked)}
                  style={{ accentColor: '#0284c7', width: '15px', height: '15px' }}
                />
                Remember this role
              </label>
              <span style={{ color: '#64748b', fontSize: '12px' }}>Demo access only</span>
            </div>

            {/* Enter Demo Workspace CTA */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '13px 20px',
                borderRadius: '8px',
                border: 'none',
                background: '#04162c',
                color: '#ffffff',
                fontSize: '14.5px',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 4px 14px rgba(4, 22, 44, 0.25)',
                transition: 'all 0.18s ease',
              }}
              onMouseEnter={(e) => {
                if (!loading) e.currentTarget.style.background = '#06254a';
              }}
              onMouseLeave={(e) => {
                if (!loading) e.currentTarget.style.background = '#04162c';
              }}
            >
              {loading ? (
                'Connecting to workspace...'
              ) : (
                <>
                  Enter demo workspace <span style={{ fontSize: '16px' }}>→</span>
                </>
              )}
            </button>
          </form>

          {/* Credentials Helper Callout Box */}
          <div style={{
            marginTop: '20px',
            padding: '12px 14px',
            borderRadius: '8px',
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
          }}>
            <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#0284c7', marginBottom: '2px' }}>
              {email}
            </div>
            <div style={{ fontSize: '11px', color: '#64748b' }}>
              Password: <strong style={{ color: '#334155' }}>Demo@12345</strong> · This is not production authentication.
            </div>
          </div>
        </div>

        {/* Disclaimer & Public Dashboard Link */}
        <div style={{
          marginTop: '20px',
          textAlign: 'center',
          fontSize: '12px',
          color: '#64748b',
          maxWidth: '460px',
        }}>
          By continuing, you acknowledge this is a synthetic-data prototype.{' '}
          <button
            type="button"
            onClick={() => setShowPublicModal(true)}
            style={{
              background: 'none',
              border: 'none',
              color: '#0284c7',
              textDecoration: 'underline',
              cursor: 'pointer',
              padding: 0,
              fontSize: '12px',
              fontWeight: 500,
            }}
          >
            Open public overview
          </button>
        </div>
      </div>

      {/* ─── PUBLIC OVERVIEW MODAL ─────────────────────────────────────── */}
      {showPublicModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(6px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px',
        }}>
          <div style={{
            background: '#ffffff',
            borderRadius: '16px',
            maxWidth: '560px',
            width: '100%',
            padding: '30px',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#0f172a' }}>
                CareLoop Demonstration Architecture
              </h3>
              <button
                type="button"
                onClick={() => setShowPublicModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '18px', cursor: 'pointer', color: '#64748b' }}
              >
                ✕
              </button>
            </div>
            <p style={{ fontSize: '13.5px', color: '#475569', lineHeight: 1.6, marginBottom: '20px' }}>
              CareLoop governs post-discharge recovery through a deterministic clinical safety protocol.
              The AI layer assists patients with grounded discharge education, but clinical flags and escalations are strictly created by MySQL 8.0 rules, stored procedures, and physician orders.
            </p>
            <div style={{
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '10px',
              padding: '14px',
              fontSize: '12.5px',
              color: '#334155',
              marginBottom: '20px',
            }}>
              <div style={{ fontWeight: 700, color: '#0284c7', marginBottom: '4px' }}>
                Core System Rule:
              </div>
              <div style={{ fontStyle: 'italic' }}>
                "The LLM talks. Rules decide. Humans act."
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowPublicModal(false)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '8px',
                background: '#04162c',
                color: '#ffffff',
                border: 'none',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Return to Login
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
