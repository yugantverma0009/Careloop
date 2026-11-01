import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../services/api';
import {
  IconLogo,
  IconShieldCheck,
  IconArrowRight,
  IconCheck,
  IconStethoscope,
  IconNurse,
  IconPatient,
  IconCaregiver,
  IconAlertTriangle,
} from './Icons';

export default function LandingPage() {
  const navigate = useNavigate();
  const [loggingInRole, setLoggingInRole] = useState(null);

  const handleRoleEnter = async (email, route, roleKey) => {
    setLoggingInRole(roleKey);
    try {
      await login(email, 'Demo@12345');
      navigate(route);
    } catch (err) {
      console.warn('Direct login failed, redirecting to login page', err);
      navigate('/login');
    } finally {
      setLoggingInRole(null);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#ffffff',
        color: '#0f172a',
        fontFamily: "'Plus Jakarta Sans', sans-serif",
      }}
    >
      {/* ======================================================== */}
      {/* 1. TOP NAVIGATION BAR                                    */}
      {/* ======================================================== */}
      <header
        style={{
          height: '70px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 48px',
          background: '#ffffff',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <IconLogo size={38} />
          <div>
            <div
              style={{
                fontSize: '18px',
                fontWeight: 800,
                color: '#0f172a',
                letterSpacing: '-0.02em',
              }}
            >
              CareLoop
            </div>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>
              Follow-up after discharge
            </div>
          </div>
        </div>

        {/* Center Links */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
          {[
            { label: 'Platform Principle', id: 'platform' },
            { label: 'Four Roles', id: 'roles' },
            { label: 'How a Day Works', id: 'day-in-the-life' },
            { label: 'Safety & Privacy', id: 'transparency' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                const el = document.getElementById(item.id);
                if (el) {
                  el.scrollIntoView({ behavior: 'smooth' });
                }
              }}
              style={{
                background: 'none',
                border: 'none',
                padding: '4px 8px',
                fontSize: '13px',
                fontWeight: 600,
                color: '#475569',
                cursor: 'pointer',
                transition: 'color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#0284c7')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#475569')}
            >
              {item.label}
            </button>
          ))}
        </nav>

        {/* Right CTA */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            type="button"
            onClick={() => navigate('/login')}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '13px',
              fontWeight: 600,
              color: '#0f172a',
              cursor: 'pointer',
            }}
          >
            Sign in
          </button>

          <button
            type="button"
            onClick={() => handleRoleEnter('ananya.demo@example.test', '/doctor', 'doctor')}
            style={{
              padding: '9px 18px',
              borderRadius: '24px',
              background: '#0b1528',
              color: '#ffffff',
              border: 'none',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'background 0.15s ease',
            }}
          >
            <span>Launch demo</span>
            <IconArrowRight width={14} height={14} />
          </button>
        </div>
      </header>

      {/* ======================================================== */}
      {/* 2. HERO SECTION                                          */}
      {/* ======================================================== */}
      <section
        className="bg-grid-bhoomi"
        style={{
          padding: '60px 48px 70px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          maxWidth: '1360px',
          margin: '0 auto',
          position: 'relative',
        }}
      >
        {/* Left Hero Column */}
        <div style={{ maxWidth: '600px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '5px 12px',
              borderRadius: '16px',
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              fontSize: '11px',
              fontWeight: 700,
              color: '#0284c7',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              marginBottom: '20px',
            }}
          >
            <IconShieldCheck width={14} height={14} />
            <span>POST-DISCHARGE RECOVERY SYSTEM</span>
          </div>

          <h1
            style={{
              fontSize: '46px',
              fontWeight: 800,
              lineHeight: 1.14,
              letterSpacing: '-0.035em',
              color: '#0b1528',
              marginBottom: '18px',
            }}
          >
            Four people. Four jobs. One connected recovery loop.
          </h1>

          <p
            style={{
              fontSize: '16px',
              lineHeight: 1.6,
              color: '#475569',
              marginBottom: '28px',
            }}
          >
            CareLoop makes each role genuinely different: patients act and check in, family helpers support with consent, nurses work the prioritized queue, and doctors decide and approve.
          </p>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '28px' }}>
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('roles');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }}
              style={{
                padding: '12px 24px',
                borderRadius: '8px',
                background: '#0b1528',
                color: '#ffffff',
                border: 'none',
                fontSize: '14px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>Explore the four roles</span>
              <IconArrowRight width={15} height={15} />
            </button>

            <button
              type="button"
              onClick={() => navigate('/login')}
              style={{
                padding: '12px 22px',
                borderRadius: '8px',
                background: '#ffffff',
                color: '#0b1528',
                border: '1px solid #cbd5e1',
                fontSize: '14px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Sign in with password
            </button>
          </div>

          {/* 3 Checkpoints */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            {[
              '4 genuinely different roles',
              'Rules create flags; LLM drafts only',
              'Synthetic sample cohort',
            ].map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    border: '1px solid #0d9488',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#0d9488',
                  }}
                >
                  <IconCheck width={10} height={10} />
                </span>
                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>{item}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Floating Cohort Mockup */}
        <div style={{ position: 'relative', width: '540px' }}>
          {/* Top Floating Pill */}
          <div
            style={{
              position: 'absolute',
              top: '-16px',
              right: '24px',
              background: '#ffffff',
              borderRadius: '10px',
              padding: '8px 14px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.08)',
              border: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              zIndex: 10,
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                background: '#fef3c7',
                color: '#d97706',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <IconAlertTriangle width={15} height={15} />
            </div>
            <div>
              <div style={{ fontSize: '9px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                Open flags
              </div>
              <div style={{ fontSize: '11px', fontWeight: 800, color: '#0f172a' }}>
                3 active alerts
              </div>
            </div>
          </div>

          {/* Main Card Mockup */}
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 20px 40px -10px rgba(15, 23, 42, 0.1)',
              padding: '24px',
            }}
          >
            <div style={{ fontSize: '10px', fontWeight: 800, color: '#0284c7', textTransform: 'uppercase', marginBottom: '4px' }}>
              DEMO COHORT SUMMARY
            </div>
            <div style={{ fontSize: '17px', fontWeight: 800, color: '#0f172a', marginBottom: '16px' }}>
              Current Recovery Worklist
            </div>

            {/* Sub-cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '16px' }}>
              <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700 }}>PATIENTS</div>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '2px 0' }}>5</div>
                <div style={{ fontSize: '9px', color: '#059669', fontWeight: 600 }}>Synthetic cohort</div>
              </div>

              <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700 }}>CARE STAFF</div>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '2px 0' }}>2</div>
                <div style={{ fontSize: '9px', color: '#0284c7', fontWeight: 600 }}>1 Doctor, 1 Nurse</div>
              </div>

              <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700 }}>OPEN TASKS</div>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '2px 0' }}>5</div>
                <div style={{ fontSize: '9px', color: '#d97706', fontWeight: 600 }}>Follow-ups due</div>
              </div>
            </div>

            {/* Signal Stream Visualization */}
            <div
              style={{
                height: '136px',
                background: '#f8fafc',
                borderRadius: '8px',
                border: '1px dashed #cbd5e1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                padding: '12px 16px 8px',
                gap: '8px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  justifyContent: 'center',
                  height: '80px',
                  gap: '10px',
                  width: '100%',
                  borderBottom: '2px solid #e2e8f0',
                  paddingBottom: '2px',
                }}
              >
                {[
                  { h: 42, label: '08:00' },
                  { h: 54, label: '10:00' },
                  { h: 68, label: '12:00' },
                  { h: 48, label: '14:00' },
                  { h: 72, label: '16:00' },
                  { h: 80, label: '18:00' },
                  { h: 64, label: '20:00' },
                  { h: 74, label: '22:00' },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <div
                      style={{
                        width: '18px',
                        height: `${item.h}px`,
                        borderRadius: '4px 4px 0 0',
                        background: 'linear-gradient(to top, #0284c7, #38bdf8)',
                      }}
                    />
                  </div>
                ))}
              </div>
              <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                <span>Simulated watch telemetry readings (rules decide; LLM does not diagnose)</span>
              </div>
            </div>
          </div>

          {/* Bottom Floating Pill */}
          <div
            style={{
              position: 'absolute',
              bottom: '-16px',
              left: '20px',
              background: '#ffffff',
              borderRadius: '10px',
              padding: '8px 14px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.08)',
              border: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              zIndex: 10,
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                background: '#f0fdf4',
                color: '#15803d',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <IconCheck width={15} height={15} />
            </div>
            <div>
              <div style={{ fontSize: '9px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                Quality guard
              </div>
              <div style={{ fontSize: '11px', fontWeight: 800, color: '#0f172a' }}>
                Invalid 450 bpm filtered out from headline
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ======================================================== */}
      {/* 3. AT A GLANCE BANNER (Real Database Counts)             */}
      {/* ======================================================== */}
      <section
        style={{
          background: '#070e1c',
          color: '#ffffff',
          padding: '36px 48px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <div
          style={{
            maxWidth: '1360px',
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '24px',
          }}
        >
          <div style={{ maxWidth: '380px' }}>
            <div style={{ fontSize: '10px', fontWeight: 800, color: '#38bdf8', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              DATABASE AT A GLANCE
            </div>
            <div style={{ fontSize: '17px', fontWeight: 800, lineHeight: 1.3, marginTop: '4px' }}>
              Real counts from local MySQL schema. No exaggerated claims.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '48px', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em', color: '#38bdf8' }}>5</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Patients in cohort</div>
            </div>

            <div>
              <div style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em', color: '#34d399' }}>2</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Care staff (1 MD, 1 RN)</div>
            </div>

            <div>
              <div style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em', color: '#fbbf24' }}>3</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Open baseline flags</div>
            </div>

            <div>
              <div style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em', color: '#c084fc' }}>100%</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Doctor-approved limits</div>
            </div>

            <div>
              <div style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em', color: '#f87171' }}>4-Step</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Escalation ladder</div>
            </div>
          </div>
        </div>
        <div style={{ textAlign: 'center', fontSize: '11px', color: '#64748b', marginTop: '14px' }}>
          Synthetic demo data. All names, medicine regimens and sensor streams are generated for testing.
        </div>
      </section>

      {/* ======================================================== */}
      {/* 4. PLATFORM PRINCIPLE SECTION (#platform)                */}
      {/* ======================================================== */}
      <section
        id="platform"
        style={{
          padding: '70px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
          borderBottom: '1px solid #e2e8f0',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 40px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '12px',
              background: '#f0f9ff',
              color: '#0284c7',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              marginBottom: '12px',
            }}
          >
            Core Architecture
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '10px' }}>
            "The LLM talks. Rules decide. Humans act."
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            The LLM never raises, closes or changes a flag, task, limit or prescription. Deterministic rules detect problems; conversational AI explains; licensed clinicians decide.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
          {[
            {
              title: 'Rules Engine Safety',
              desc: 'Threshold breaches (SpO₂ < 94%, HR > 100) are evaluated purely in SQL triggers. The LLM has zero authority to flag.',
              tag: 'Deterministic',
              color: '#0284c7',
              bg: '#f0f9ff',
            },
            {
              title: 'Emergency Keyword Path',
              desc: 'Critical words (English and Hindi) are caught instantly by plain code and never wait for the LLM to complete.',
              tag: 'Zero Latency',
              color: '#dc2626',
              bg: '#fef2f2',
            },
            {
              title: 'Cited Assistant Papers',
              desc: 'Answers patient questions strictly from discharge documents, displaying clickable source chips and refusing dose changes.',
              tag: 'Grounded RAG',
              color: '#7c3aed',
              bg: '#f5f3ff',
            },
            {
              title: 'Tamper-Evident Audit',
              desc: 'Every dose confirmation, rule breach, SMS dispatch, nurse call, doctor approval and consent toggle is logged.',
              tag: 'Full Trace',
              color: '#059669',
              bg: '#ecfdf5',
            },
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                padding: '24px',
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                background: '#ffffff',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
              }}
            >
              <span
                style={{
                  display: 'inline-block',
                  fontSize: '10px',
                  fontWeight: 700,
                  color: item.color,
                  background: item.bg,
                  padding: '3px 8px',
                  borderRadius: '6px',
                  marginBottom: '14px',
                  textTransform: 'uppercase',
                }}
              >
                {item.tag}
              </span>
              <h3 style={{ fontSize: '17px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
                {item.title}
              </h3>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.55 }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ======================================================== */}
      {/* 5. FOUR ROLE CARDS (#roles)                              */}
      {/* ======================================================== */}
      <section
        id="roles"
        style={{
          padding: '70px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 40px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '12px',
              background: '#e0e7ff',
              color: '#4338ca',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              marginBottom: '12px',
            }}
          >
            Role Specialization
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '10px' }}>
            Four Logins. Four Different Jobs.
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            Each role differs by content, navigation, wording and dedicated accent colour. Click any card to launch straight into that workspace.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '22px' }}>
          {[
            {
              id: 'doctor',
              role: 'Doctor',
              name: 'Dr. Ananya Sharma',
              pitch: 'The doctor decides, approves and exports.',
              firstScreen: 'Needs my decision',
              email: 'ananya.demo@example.test',
              accent: '#7c3aed',
              accentSoft: '#f5f3ff',
              route: '/doctor',
              IconComponent: IconStethoscope,
            },
            {
              id: 'nurse',
              role: 'Nurse',
              name: 'Priya Nair',
              pitch: 'The nurse calls, logs, rechecks and escalates.',
              firstScreen: 'My call list',
              email: 'priya.demo@example.test',
              accent: '#0d9488',
              accentSoft: '#f0fdfa',
              route: '/nurse',
              IconComponent: IconNurse,
            },
            {
              id: 'patient',
              role: 'Patient',
              name: 'Aarav Patel',
              pitch: 'The patient acts, checks in and asks their papers.',
              firstScreen: 'Home',
              email: 'aarav.demo@example.test',
              accent: '#2563eb',
              accentSoft: '#eff6ff',
              route: '/patient',
              IconComponent: IconPatient,
            },
            {
              id: 'caregiver',
              role: 'Family Helper',
              name: 'Neha Patel',
              pitch: 'The family helper supports, is informed with consent, and calls 112 if needed.',
              firstScreen: 'Today',
              email: 'caregiver1.demo@example.test',
              accent: '#ea580c',
              accentSoft: '#fff7ed',
              route: '/family',
              IconComponent: IconCaregiver,
            },
          ].map((card) => {
            const RoleIcon = card.IconComponent;
            const isPending = loggingInRole === card.id;

            return (
              <div
                key={card.id}
                style={{
                  background: '#ffffff',
                  border: `1px solid #e2e8f0`,
                  borderTop: `4px solid ${card.accent}`,
                  borderRadius: '16px',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
              >
                <div>
                  {/* Top Role Header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div
                        style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '8px',
                          background: card.accentSoft,
                          color: card.accent,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <RoleIcon width={18} height={18} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: card.accent, letterSpacing: '0.04em' }}>
                          {card.role}
                        </div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                          {card.name}
                        </div>
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: '10px',
                        padding: '2px 8px',
                        borderRadius: '6px',
                        background: '#f1f5f9',
                        color: '#64748b',
                        fontWeight: 600,
                      }}
                    >
                      {card.firstScreen}
                    </span>
                  </div>

                  {/* Exact One-Line Pitch from Section 2.1 */}
                  <div
                    style={{
                      fontSize: '15px',
                      fontWeight: 800,
                      color: '#0f172a',
                      lineHeight: 1.4,
                      marginBottom: '16px',
                      minHeight: '44px',
                    }}
                  >
                    "{card.pitch}"
                  </div>

                  {/* Sign-in Details Box (Visible for Judges) */}
                  <div
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      padding: '10px 12px',
                      marginBottom: '20px',
                    }}
                  >
                    <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', marginBottom: '2px' }}>
                      Sign-in credentials (Judge Access)
                    </div>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#0f172a', fontFamily: 'monospace' }}>
                      {card.email}
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                      Password: <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#0f172a' }}>Demo@12345</span>
                    </div>
                  </div>
                </div>

                {/* Direct Entry Button */}
                <button
                  type="button"
                  onClick={() => handleRoleEnter(card.email, card.route, card.id)}
                  disabled={isPending}
                  style={{
                    width: '100%',
                    padding: '11px 16px',
                    borderRadius: '8px',
                    background: card.accent,
                    color: '#ffffff',
                    border: 'none',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: isPending ? 'wait' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    transition: 'opacity 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.9')}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = '1.0')}
                >
                  <span>{isPending ? 'Signing in...' : `Enter as ${card.role}`}</span>
                  <IconArrowRight width={14} height={14} />
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* ======================================================== */}
      {/* 6. HOW A DAY WORKS STRIP (5 Chronological Steps)         */}
      {/* ======================================================== */}
      <section
        id="day-in-the-life"
        style={{
          padding: '70px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
          borderBottom: '1px solid #e2e8f0',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 40px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '12px',
              background: '#fef3c7',
              color: '#d97706',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              marginBottom: '12px',
            }}
          >
            Connected Patient Journey
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '10px' }}>
            How a Day Works
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            Five steps connect Aarav, Neha, Priya and Dr. Sharma when a real-world recovery event occurs.
          </p>
        </div>

        {/* 5-Step Horizontal Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: '16px',
          }}
        >
          {[
            {
              step: 'Step 1',
              title: 'Patient Morning Action',
              who: 'Aarav Patel (Patient)',
              desc: 'Taps Taken on morning medicines, sends pain check-in, and asks his discharge notes when his follow-up is.',
              color: '#2563eb',
              bg: '#eff6ff',
            },
            {
              step: 'Step 2',
              title: 'Continuous Telemetry',
              who: 'Wearable Watch (DEV-ESP32-001)',
              desc: 'Streams heart rate & oxygen. Rule engine filters out impossible values (450 bpm) and evaluates valid readings.',
              color: '#0284c7',
              bg: '#f0f9ff',
            },
            {
              step: 'Step 3',
              title: 'Prompt & Caregiver Alert',
              who: 'Neha Patel (Family)',
              desc: 'SpO₂ drops to 91% (< 94% limit). Aarav sees a calm 112 guidance banner. Neha gets SMS notification with Aarav’s consent.',
              color: '#ea580c',
              bg: '#fff7ed',
            },
            {
              step: 'Step 4',
              title: 'Nurse Queue & Escalation',
              who: 'Priya Nair (Lead Nurse)',
              desc: 'Aarav appears at top of My Call List with reason. Priya calls him, logs notes, and escalates to Dr. Sharma.',
              color: '#0d9488',
              bg: '#f0fdfa',
            },
            {
              step: 'Step 5',
              title: 'Physician Review & Sign-Off',
              who: 'Dr. Ananya Sharma (Attending)',
              desc: 'Aarav appears in Needs My Decision. Dr. Sharma inspects escalation evidence, resolves flag, and approves AI summaries.',
              color: '#7c3aed',
              bg: '#f5f3ff',
            },
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                padding: '20px 16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                position: 'relative',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      color: item.color,
                      background: item.bg,
                      padding: '3px 8px',
                      borderRadius: '6px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {item.step}
                  </span>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8' }}>
                    0{idx + 1}
                  </span>
                </div>

                <div style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a', marginBottom: '4px' }}>
                  {item.title}
                </div>

                <div style={{ fontSize: '11px', fontWeight: 700, color: item.color, marginBottom: '8px' }}>
                  {item.who}
                </div>

                <p style={{ fontSize: '12px', color: '#64748b', lineHeight: 1.5, margin: 0 }}>
                  {item.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ======================================================== */}
      {/* 7. SAFETY & PRIVACY STANDARDS (#transparency)            */}
      {/* ======================================================== */}
      <section
        id="transparency"
        style={{
          padding: '70px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 40px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '12px',
              background: '#f3e8ff',
              color: '#7c3aed',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              marginBottom: '12px',
            }}
          >
            Safety Protocols
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '10px' }}>
            Safety and Privacy Principles
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            CareLoop is built on clear clinical safeguards. We make no unprovable claims: no readmission prevention guarantees, no arbitrary accuracy percentages, no medical device classification.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          <div style={{ padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Sample Data & Demo Scope
            </h4>
            <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
              All 5 patients, discharge notes and vitals are synthetic sample records. CareLoop is an academic prototype for clinical handoffs and not a cleared medical device.
            </p>
          </div>

          <div style={{ padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Patient Consent Gating
            </h4>
            <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
              The family helper sees only what the patient explicitly allowed. If the patient turns sharing off, family access is revoked immediately with a clear message.
            </p>
          </div>

          <div style={{ padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Doctor-Approved Rules
            </h4>
            <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
              Every safety threshold (SpO₂ limit, HR bounds) is approved by Dr. Sharma. Proposed changes require physician sign-off before becoming active.
            </p>
          </div>
        </div>
      </section>

      {/* ======================================================== */}
      {/* 8. FOOTER WITH REQUIRED NOTE                             */}
      {/* ======================================================== */}
      <footer
        style={{
          background: '#0b1528',
          color: '#94a3b8',
          padding: '36px 48px',
          borderTop: '1px solid #1e293b',
          fontSize: '12px',
        }}
      >
        <div
          style={{
            maxWidth: '1360px',
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div>
            <span style={{ fontWeight: 700, color: '#ffffff' }}>CareLoop</span> — Follow-up after discharge
          </div>
          <div style={{ color: '#cbd5e1', fontWeight: 500 }}>
            Sample data. Not medical advice. Synthetic-data prototype, not a medical device.
          </div>
        </div>
      </footer>
    </div>
  );
}
