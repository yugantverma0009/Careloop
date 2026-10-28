import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { login } from '../services/api';
import ThemeToggle from './ThemeToggle';
import {
  IconLogo,
  IconShieldCheck,
  IconLock,
  IconEye,
  IconEyeOff,
  IconArrowRight,
  IconCheck,
  IconUser,
  IconStethoscope,
  IconNurse,
  IconPatient,
  IconCaregiver,
} from './Icons';

const DEMO_ROLES = [
  {
    id: 'doctor',
    title: 'Attending Physician',
    name: 'Dr. Ananya Rao',
    email: 'ananya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/staff',
    roleTag: 'Doctor',
    IconComponent: IconStethoscope,
  },
  {
    id: 'nurse',
    title: 'Triage Nurse',
    name: 'Nurse Priya Sharma',
    email: 'priya.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/staff',
    roleTag: 'Nurse',
    IconComponent: IconNurse,
  },
  {
    id: 'patient',
    title: 'Recovering Patient',
    name: 'Aarav Patel (Post-CABG Day 3)',
    email: 'aarav.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/patient',
    roleTag: 'Patient',
    IconComponent: IconPatient,
  },
  {
    id: 'caregiver',
    title: 'Family Caregiver',
    name: 'Sunita Patel',
    email: 'caregiver1.demo@example.test',
    password: 'Demo@12345',
    targetRoute: '/patient',
    roleTag: 'Caregiver',
    IconComponent: IconCaregiver,
  },
];

export default function CareLoopLogin({ onLoginSuccess }) {
  const [selectedRoleIndex, setSelectedRoleIndex] = useState(2); // default: Aarav Patel (Patient)
  const [email, setEmail] = useState(DEMO_ROLES[2].email);
  const [password, setPassword] = useState(DEMO_ROLES[2].password);
  const [showPassword, setShowPassword] = useState(false);
  const [rememberRole, setRememberRole] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleRoleSelect = (e) => {
    const idx = parseInt(e.target.value, 10);
    setSelectedRoleIndex(idx);
    setEmail(DEMO_ROLES[idx].email);
    setPassword(DEMO_ROLES[idx].password);
    setError('');
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await login(email, password);
      const userObj = data.user || data;
      if (onLoginSuccess) {
        onLoginSuccess(userObj);
      }
      const role = userObj.role || activeRole.roleTag;
      const target =
        role === 'Patient' || role === 'Caregiver'
          ? '/patient'
          : '/staff';
      window.location.href = target;
    } catch (err) {
      console.error('Login error', err);
      setError(err.message || 'Invalid credentials. Please select one of the roles.');
    } finally {
      setLoading(false);
    }
  };

  const activeRole = DEMO_ROLES[selectedRoleIndex];

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        background: '#0b1528',
        color: '#ffffff',
        fontFamily: "'Plus Jakarta Sans', sans-serif",
      }}
    >
      {/* ======================================================== */}
      {/* LEFT PANEL: Deep Navy (#0b1528) Signature BhoomiSetu Style */}
      {/* ======================================================== */}
      <div
        style={{
          flex: '1 1 50%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '48px 64px',
          background: '#0b1528',
          position: 'relative',
          borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <div>
          {/* Top navigation link */}
          <div style={{ marginBottom: '44px' }}>
            <Link
              to="/"
              style={{
                color: '#94a3b8',
                fontSize: '12px',
                fontWeight: 600,
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'color 0.2s',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#ffffff')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
            >
              <span>←</span>
              <span>Back to CareLoop</span>
            </Link>
          </div>

          {/* Logo & Brand Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '40px' }}>
            <IconLogo size={42} />
            <div>
              <div
                style={{
                  fontSize: '22px',
                  fontWeight: 800,
                  color: '#ffffff',
                  letterSpacing: '-0.02em',
                }}
              >
                CareLoop
              </div>
              <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 500 }}>
                Follow-up after discharge
              </div>
            </div>
          </div>

          {/* Section Kicker */}
          <div
            style={{
              fontSize: '11px',
              fontWeight: 800,
              letterSpacing: '0.08em',
              color: '#38bdf8',
              textTransform: 'uppercase',
              marginBottom: '14px',
            }}
          >
            FOLLOW-UP AFTER DISCHARGE
          </div>

          {/* Main Hero Headline */}
          <h1
            style={{
              fontSize: '38px',
              fontWeight: 800,
              lineHeight: 1.15,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              maxWidth: '500px',
              marginBottom: '18px',
            }}
          >
            From discharge day to full recovery, in one place.
          </h1>

          {/* Hero Paragraph */}
          <p
            style={{
              fontSize: '14px',
              lineHeight: 1.65,
              color: '#94a3b8',
              maxWidth: '460px',
              marginBottom: '36px',
            }}
          >
            Separate views for doctors, triage nurses, recovering patients, and family helpers.
          </p>

          {/* 3 Checkmark Items matching BhoomiSetu */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', maxWidth: '480px' }}>
            {[
              'Wearable readings, checked for impossible values',
              'Answers taken from your own discharge papers',
              'A 3-step escalation ladder with timers; people stay in charge',
            ].map((text, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    border: '1.5px solid #0d9488',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#2dd4bf',
                    flexShrink: 0,
                  }}
                >
                  <IconCheck width={12} height={12} />
                </span>
                <span style={{ fontSize: '13px', color: '#cbd5e1', fontWeight: 500 }}>
                  {text}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{ marginTop: '48px', paddingTop: '20px' }}>
          <div style={{ fontSize: '11px', color: '#475569', letterSpacing: '0.02em' }}>
            CareLoop · Follow-up after discharge
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* RIGHT PANEL: Soft Off-White (#f8fafc) with Floating Card */}
      {/* ======================================================== */}
      <div
        className="bg-grid-bhoomi"
        style={{
          flex: '1 1 50%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 32px',
          background: 'var(--bg-base, #f8fafc)',
          position: 'relative',
        }}
      >
        {/* Top-Right Theme Toggle */}
        <div style={{ position: 'absolute', top: '32px', right: '40px' }}>
          <ThemeToggle />
        </div>

        {/* Floating Card Container */}
        <div
          style={{
            width: '100%',
            maxWidth: '460px',
            background: 'var(--bg-surface, #ffffff)',
            borderRadius: '16px',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            boxShadow: 'var(--shadow-float, 0 10px 25px -3px rgba(15, 23, 42, 0.08))',
            padding: '36px 38px',
          }}
        >
          {/* Top Pill Badge */}
          <div style={{ marginBottom: '16px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: '14px',
                background: 'var(--accent-teal-soft, #f0fdf4)',
                color: 'var(--accent-teal-text, #166534)',
                border: '1px solid rgba(13, 148, 136, 0.25)',
                fontSize: '11px',
                fontWeight: 600,
              }}
            >
              <IconShieldCheck width={12} height={12} />
              <span>Secure sign-in</span>
            </span>
          </div>

          {/* Heading & Subtitle */}
          <h2
            style={{
              fontSize: '22px',
              fontWeight: 800,
              color: 'var(--text-primary, #0f172a)',
              letterSpacing: '-0.02em',
              marginBottom: '6px',
            }}
          >
            Welcome back
          </h2>
          <p
            style={{
              fontSize: '13px',
              color: 'var(--text-muted, #64748b)',
              marginBottom: '24px',
              lineHeight: 1.5,
            }}
          >
            Pick your role to continue.
          </p>

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {error && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: '8px',
                  background: 'var(--alert-red-soft, #fef2f2)',
                  color: 'var(--alert-red-text, #991b1b)',
                  fontSize: '12px',
                  fontWeight: 600,
                  border: '1px solid var(--alert-red, #dc2626)',
                }}
              >
                {error}
              </div>
            )}

            {/* Field 1: Demo role select dropdown */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--text-secondary, #334155)',
                  marginBottom: '6px',
                }}
              >
                Role
              </label>
              <div style={{ position: 'relative' }}>
                <select
                  value={selectedRoleIndex}
                  onChange={handleRoleSelect}
                  style={{
                    width: '100%',
                    height: '42px',
                    padding: '0 36px 0 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-input, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '13px',
                    fontWeight: 600,
                    appearance: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {DEMO_ROLES.map((role, idx) => (
                    <option key={role.id} value={idx}>
                      {role.title} ({role.name})
                    </option>
                  ))}
                </select>
                <div
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    pointerEvents: 'none',
                    color: 'var(--text-muted, #64748b)',
                    fontSize: '11px',
                  }}
                >
                  ▼
                </div>
              </div>
            </div>

            {/* Field 2: Email or employee ID */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--text-secondary, #334155)',
                  marginBottom: '6px',
                }}
              >
                Email or staff ID
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '42px',
                    padding: '0 14px 0 38px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-input, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '13px',
                  }}
                />
                <span
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted, #64748b)',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <IconUser width={15} height={15} />
                </span>
              </div>
            </div>

            {/* Field 3: Password */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: 'var(--text-secondary, #334155)',
                  marginBottom: '6px',
                }}
              >
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    height: '42px',
                    padding: '0 38px 0 38px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-input, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '13px',
                    letterSpacing: showPassword ? 'normal' : '0.15em',
                  }}
                />
                <span
                  style={{
                    position: 'absolute',
                    left: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted, #64748b)',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <IconLock width={15} height={15} />
                </span>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted, #64748b)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  {showPassword ? <IconEyeOff width={16} height={16} /> : <IconEye width={16} height={16} />}
                </button>
              </div>
            </div>

            {/* Checkbox Row: Remember this role / Demo access only */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12px',
                color: 'var(--text-secondary, #475569)',
              }}
            >
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={rememberRole}
                  onChange={(e) => setRememberRole(e.target.checked)}
                  style={{ accentColor: '#0f172a', width: '15px', height: '15px' }}
                />
                <span>Remember this role</span>
              </label>
              <span style={{ color: 'var(--text-muted, #94a3b8)', fontSize: '11px' }}>
              </span>
            </div>

            {/* Action Button: Enter demo workspace -> */}
            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: '6px',
                width: '100%',
                height: '44px',
                borderRadius: '8px',
                border: 'none',
                background: '#0f172a',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!loading) e.currentTarget.style.background = '#1e293b';
              }}
              onMouseLeave={(e) => {
                if (!loading) e.currentTarget.style.background = '#0f172a';
              }}
            >
              <span>{loading ? 'Signing in...' : 'Sign in'}</span>
              <IconArrowRight width={15} height={15} />
            </button>

            {/* Helper Callout Box */}
            <div
              style={{
                marginTop: '8px',
                padding: '12px 14px',
                borderRadius: '8px',
                background: 'var(--accent-blue-soft, #f0f7ff)',
                border: '1px solid rgba(2, 132, 199, 0.15)',
              }}
            >
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  color: 'var(--accent-blue, #0284c7)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  marginBottom: '4px',
                }}
              >
                Sign-in details for this role
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: 'var(--text-primary, #0f172a)',
                  fontFamily: "'JetBrains Mono', monospace",
                  marginBottom: '2px',
                }}
              >
                {activeRole.email}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                Password: <span style={{ fontWeight: 600 }}>Demo@12345</span>
              </div>
            </div>
          </form>
        </div>

        {/* Footer Acknowledgement */}
        <div style={{ marginTop: '20px', textAlign: 'center' }}>
          <div>
            <a
              href="/patient"
              style={{
                fontSize: '12px',
                color: 'var(--text-primary, #0f172a)',
                fontWeight: 600,
                textDecoration: 'underline',
              }}
            >
              Open public dashboard
            </a>
          </div>
          <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted, #94a3b8)' }}>
            Sample data. Not medical advice.
          </div>
        </div>
      </div>
    </div>
  );
}
