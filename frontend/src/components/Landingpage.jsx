import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  IconLogo,
  IconShieldCheck,
  IconArrowRight,
  IconCheck,
  IconActivity,
} from './Icons';

export default function LandingPage() {
  const navigate = useNavigate();

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
      {/* 1. TOP NAVIGATION BAR (BhoomiSetu Style)                 */}
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
            { label: 'Platform', id: 'platform' },
            { label: 'Capabilities', id: 'capabilities' },
            { label: 'Impact', id: 'impact' },
            { label: 'Public Transparency', id: 'transparency' },
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
            onClick={() => navigate('/patient')}
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
            <span>See care team view</span>
            <IconArrowRight width={14} height={14} />
          </button>
        </div>
      </header>

      {/* ======================================================== */}
      {/* 2. HERO SECTION WITH GRID & FLOATING DASHBOARD MOCKUP    */}
      {/* ======================================================== */}
      <section
        className="bg-grid-bhoomi"
        style={{
          padding: '60px 48px 80px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          maxWidth: '1360px',
          margin: '0 auto',
          position: 'relative',
        }}
      >
        {/* Left Hero Column */}
        <div style={{ maxWidth: '580px' }}>
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
              marginBottom: '24px',
            }}
          >
            <IconShieldCheck width={14} height={14} />
            <span>POST-DISCHARGE FOLLOW-UP</span>
          </div>

          <h1
            style={{
              fontSize: '48px',
              fontWeight: 800,
              lineHeight: 1.12,
              letterSpacing: '-0.035em',
              color: '#0b1528',
              marginBottom: '20px',
            }}
          >
            Recovering at home, with your care team in the loop.
          </h1>

          <p
            style={{
              fontSize: '15px',
              lineHeight: 1.6,
              color: '#475569',
              marginBottom: '32px',
            }}
          >
            CareLoop helps patients follow their discharge plan, and shows nurses and doctors who needs attention first, with the reason for every alert.
          </p>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '28px' }}>
            <button
              type="button"
              onClick={() => navigate('/patient')}
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
              <span>See the care-team view</span>
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
              Sign in
            </button>
          </div>

          {/* 3 Checkpoints */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            {['A separate view for each role', 'Sample patient records', 'Wearable readings (watch)'].map((item, i) => (
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

        {/* Right Floating Dashboard Mockup matching Image 2 */}
        <div style={{ position: 'relative', width: '560px' }}>
          {/* Top Floating Pill */}
          <div
            style={{
              position: 'absolute',
              top: '-18px',
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
              <IconActivity width={15} height={15} />
            </div>
            <div>
              <div style={{ fontSize: '9px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                Flags raised
              </div>
              <div style={{ fontSize: '11px', fontWeight: 800, color: '#0f172a' }}>
                12 open flags
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
              CARE OVERVIEW
            </div>
            <div style={{ fontSize: '17px', fontWeight: 800, color: '#0f172a', marginBottom: '16px' }}>
              Recovery overview
            </div>

            {/* Sub-cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '16px' }}>
              <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700 }}>ACTIVE PATIENTS</div>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '2px 0' }}>5</div>
                <div style={{ fontSize: '9px', color: '#059669', fontWeight: 600 }}>Monitored cohort</div>
              </div>

              <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700 }}>TELEMETRY STREAM</div>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '2px 0' }}>Active</div>
                <div style={{ fontSize: '9px', color: '#0284c7', fontWeight: 600 }}>Wearable watch</div>
              </div>

              <div style={{ padding: '10px 12px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 700 }}>DOSES TRACKED</div>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '2px 0' }}>Logged</div>
                <div style={{ fontSize: '9px', color: '#059669', fontWeight: 600 }}>Self-reported</div>
              </div>
            </div>

            {/* Simulated progress area (FIXED: Bar chart aligned to bottom baseline) */}
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
              {/* Bars container aligned to bottom baseline */}
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
                  { h: 36, label: '08:00' },
                  { h: 48, label: '10:00' },
                  { h: 62, label: '12:00' },
                  { h: 44, label: '14:00' },
                  { h: 72, label: '16:00' },
                  { h: 80, label: '18:00' },
                  { h: 68, label: '20:00' },
                  { h: 76, label: '22:00' },
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
                        transition: 'height 0.3s ease',
                      }}
                    />
                  </div>
                ))}
              </div>
              <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                <span>Heart rate and oxygen readings (not a diagnosis)</span>
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
                Quality check
              </div>
              <div style={{ fontSize: '11px', fontWeight: 800, color: '#0f172a' }}>
                Every reading carries a quality label
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ======================================================== */}
      {/* 3. AT A GLANCE BANNER                                    */}
      {/* ======================================================== */}
      <section
        style={{
          background: '#070e1c',
          color: '#ffffff',
          padding: '40px 48px',
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
          }}
        >
          <div style={{ maxWidth: '340px' }}>
            <div style={{ fontSize: '10px', fontWeight: 800, color: '#38bdf8', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              AT A GLANCE
            </div>
            <div style={{ fontSize: '18px', fontWeight: 800, lineHeight: 1.3, marginTop: '4px' }}>
              One record for patients, family helpers, nurses and doctors.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '64px' }}>
            <div>
              <div style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em' }}>5</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Monitored patients</div>
            </div>

            <div>
              <div style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em' }}>Active</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Telemetry stream</div>
            </div>

            <div>
              <div style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em' }}>Logged</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Doses confirmed</div>
            </div>

            <div>
              <div style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em' }}>4-Step</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Escalation ladder</div>
            </div>
          </div>
        </div>
        <div style={{ textAlign: 'center', fontSize: '11px', color: '#94a3b8', marginTop: '16px' }}>
          Figures shown are sample data.
        </div>
      </section>

      {/* ======================================================== */}
      {/* 4. PLATFORM SECTION (#platform)                          */}
      {/* ======================================================== */}
      <section
        id="platform"
        style={{
          padding: '80px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
          borderBottom: '1px solid #e2e8f0',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 48px' }}>
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
            How CareLoop Works
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '12px' }}>
            "The LLM talks. Rules decide. Humans act."
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            CareLoop separates medical rules from conversational AI. Clinical safety rules trigger alerts while care teams keep full oversight.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
          {[
            {
              title: 'Safety Rules Engine',
              desc: 'Safety thresholds check oxygen and pulse readings. The AI assistant never creates medical flags on its own.',
              tag: 'Rule-Based Safety',
              color: '#0284c7',
              bg: '#f0f9ff',
            },
            {
              title: 'Permanent Audit Trail',
              desc: 'Every dose confirmation, flag alert, and staff review is saved permanently in an audit log.',
              tag: 'Tamper Evident',
              color: '#059669',
              bg: '#ecfdf5',
            },
            {
              title: 'Wearable Readings Check',
              desc: 'Automatic checks filter out impossible sensor readings before alerts are created.',
              tag: 'Quality Guard',
              color: '#d97706',
              bg: '#fffbeb',
            },
            {
              title: 'Discharge Notes Assistant',
              desc: 'Answers questions using only your discharge notes, citing the exact sections.',
              tag: 'Cited Evidence',
              color: '#7c3aed',
              bg: '#f5f3ff',
            },
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                padding: '28px',
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                background: '#ffffff',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)';
                e.currentTarget.style.boxShadow = '0 12px 20px -2px rgba(15, 23, 42, 0.08)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.05)';
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
                  marginBottom: '16px',
                  textTransform: 'uppercase',
                }}
              >
                {item.tag}
              </span>
              <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
                {item.title}
              </h3>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ======================================================== */}
      {/* 5. CAPABILITIES SECTION (#capabilities)                  */}
      {/* ======================================================== */}
      <section
        id="capabilities"
        style={{
          padding: '80px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
          borderBottom: '1px solid #e2e8f0',
          background: '#f8fafc',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 48px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '12px',
              background: '#ecfdf5',
              color: '#059669',
              fontSize: '11px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              marginBottom: '12px',
            }}
          >
            Portals for Each Role
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '12px' }}>
            Explore Portals & Live Dashboards
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            Each member accesses a portal made for their role with protected access.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
          {[
            {
              role: 'Doctor',
              title: "Doctor's View",
              email: 'ananya.demo@example.test',
              desc: 'Triage list sorted by priority, symptom trends, and one-click review for daily summaries.',
              badge: 'Doctor',
              badgeColor: '#0284c7',
            },
            {
              role: 'Nurse',
              title: "Nurse's View",
              email: 'priya.demo@example.test',
              desc: 'Alert ladder queue, follow-up task dispatching, and quick vitals acknowledgement.',
              badge: 'Nurse',
              badgeColor: '#059669',
            },
            {
              role: 'Patient',
              title: 'Patient Portal',
              email: 'aarav.demo@example.test',
              desc: 'Daily medicine checklist, live watch vitals, Hindi/English emergency guidance, and discharge chat.',
              badge: 'Patient',
              badgeColor: '#7c3aed',
            },
            {
              role: 'Caregiver',
              title: 'Family Helper View',
              email: 'caregiver1.demo@example.test',
              desc: 'Readings with patient consent, text notifications, and daily milestones.',
              badge: 'Caregiver',
              badgeColor: '#d97706',
            },
          ].map((card, idx) => (
            <div
              key={idx}
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '16px',
                padding: '28px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      color: card.badgeColor,
                      background: '#f1f5f9',
                      padding: '4px 10px',
                      borderRadius: '8px',
                    }}
                  >
                    {card.badge}
                  </span>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>Ready</span>
                </div>

                <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0f172a', marginBottom: '8px' }}>
                  {card.title}
                </h3>
                <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6, marginBottom: '16px' }}>
                  {card.desc}
                </p>

                <div
                  style={{
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '8px 12px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase' }}>
                    Sign-in details (Password: Demo@12345)
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#0f172a', fontFamily: 'monospace' }}>
                    {card.email}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => navigate('/login')}
                style={{
                  width: '100%',
                  padding: '10px 16px',
                  borderRadius: '8px',
                  background: '#0b1528',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  transition: 'background 0.15s ease',
                }}
              >
                <span>Open {card.role} Portal</span>
                <IconArrowRight width={14} height={14} />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* ======================================================== */}
      {/* 6. IMPACT SECTION (#impact)                              */}
      {/* ======================================================== */}
      <section
        id="impact"
        style={{
          padding: '80px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
          borderBottom: '1px solid #e2e8f0',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 48px' }}>
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
            Target Outcomes
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '12px' }}>
            Clinical Follow-Up Targets
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            Supports post-discharge care coordination through wearable telemetry and clinical escalation ladders.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
          {[
            { metric: 'Active', label: 'Signal Quality Checking', detail: 'Sensor check filters out impossible readings to avoid false alarms.' },
            { metric: 'Self-Reported', label: 'Doses Confirmed by Patients', detail: 'Daily dose check-ins with caregiver and staff alerts when doses are missed.' },
            { metric: 'Code-Level', label: 'Emergency Keyword Engine', detail: 'Immediate deterministic safety keyword checks in Hindi and English.' },
            { metric: '4-Tier', label: 'Clinical Escalation Ladder', detail: 'Patient prompt -> Caregiver SMS (consent-gated) -> Nurse alert -> Doctor decision.' },
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                padding: '24px',
                borderRadius: '12px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
              }}
            >
              <div style={{ fontSize: '36px', fontWeight: 800, color: '#0284c7', marginBottom: '6px' }}>
                {item.metric}
              </div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
                {item.label}
              </div>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5 }}>
                {item.detail}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ======================================================== */}
      {/* 7. PUBLIC TRANSPARENCY SECTION (#transparency)           */}
      {/* ======================================================== */}
      <section
        id="transparency"
        style={{
          padding: '80px 48px',
          maxWidth: '1360px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '720px', margin: '0 auto 48px' }}>
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
            Safety Standards
          </div>
          <h2 style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em', marginBottom: '12px' }}>
            Safety and Privacy Standards
          </h2>
          <p style={{ fontSize: '15px', color: '#64748b', lineHeight: 1.6 }}>
            CareLoop is built for clear clinical records. All sample data and limits follow standard guidelines.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
          <div style={{ padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Sample Data Notice
            </h4>
            <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
              All patient records and readings shown here are sample data. No real personal health records are used.
            </p>
          </div>

          <div style={{ padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Permanent Audit Trail
            </h4>
            <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
              Every dose confirmation, alert update, and care team action is saved in a permanent log.
            </p>
          </div>

          <div style={{ padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff' }}>
            <h4 style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', marginBottom: '8px' }}>
              Doctor Makes Final Decision
            </h4>
            <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
              AI drafts are clearly marked until a doctor reviews them. The assistant cannot change medicines.
            </p>
          </div>
        </div>
      </section>

      {/* ======================================================== */}
      {/* 8. FOOTER                                                */}
      {/* ======================================================== */}
      <footer
        style={{
          background: '#0b1528',
          color: '#94a3b8',
          padding: '40px 48px',
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
          <div>
            Sample data. Not medical advice.
          </div>
        </div>
      </footer>
    </div>
  );
}