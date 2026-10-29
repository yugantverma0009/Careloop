import React, { useState, useEffect } from 'react';
import {
  getFamilyToday,
  confirmFamilyDoseHelped,
  getFamilyCalendar,
  getFamilyContacts,
  logout,
} from '../services/api';
import ThemeToggle from './ThemeToggle';
import SwitchDemoWorkspace from './SwitchDemoWorkspace';
import {
  IconLogo,
  IconPill,
  IconHeartPulse,
  IconActivity,
  IconCalendar,
  IconClock,
  IconCheck,
  IconLogOut,
  IconShieldCheck,
  IconPhone,
  IconAlertTriangle,
  IconFileText,
  IconRefresh,
} from './Icons';

export default function FamilyPortal({ user }) {
  const [activeTab, setActiveTab] = useState('today'); // 'today', 'calendar', 'contacts'
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [todayData, setTodayData] = useState(null);
  const [calendarData, setCalendarData] = useState(null);
  const [contactsData, setContactsData] = useState(null);
  const [sharingBlocked, setSharingBlocked] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [successToast, setSuccessToast] = useState('');

  const fetchTodayData = async () => {
    try {
      setLoading(true);
      setErrorMsg('');
      const data = await getFamilyToday();
      setTodayData(data);
      setSharingBlocked(false);
    } catch (err) {
      if (err.message && err.message.toLowerCase().includes('sharing turned off')) {
        setSharingBlocked(true);
      } else {
        setErrorMsg(err.message || 'Unable to load family recovery overview.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchCalendar = async () => {
    try {
      const data = await getFamilyCalendar();
      setCalendarData(data);
    } catch (err) {
      console.error('Failed to load calendar', err);
    }
  };

  const fetchContacts = async () => {
    try {
      const data = await getFamilyContacts();
      setContactsData(data);
    } catch (err) {
      console.error('Failed to load contacts', err);
    }
  };

  useEffect(() => {
    fetchTodayData();
    fetchCalendar();
    fetchContacts();
  }, []);

  const handleHelpDose = async (doseId, medicineName) => {
    try {
      setActionLoading(true);
      await confirmFamilyDoseHelped(doseId);
      setSuccessToast(`Recorded: You helped Aarav take ${medicineName}.`);
      setTimeout(() => setSuccessToast(''), 4000);
      await fetchTodayData();
    } catch (err) {
      alert(err.message || 'Unable to record dose assistance.');
    } finally {
      setActionLoading(false);
    }
  };

  const patient = todayData?.patient || {
    full_name: 'Aarav Patel',
    patient_code: 'CL-00001',
    age: 41,
    condition: 'Post-CABG',
    day_number: 3,
  };

  const caregiver = todayData?.caregiver || {
    name: user?.name || 'Neha Patel',
    relationship: 'Spouse',
    sharing_badge: 'Sharing allowed by Aarav Patel',
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-base)' }}>
      {/* ── Left Sidebar ──────────────────────────────────────────────────────── */}
      <aside
        style={{
          width: 260,
          backgroundColor: 'var(--sidebar-bg)',
          borderRight: '1px solid var(--sidebar-border)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 20,
        }}
      >
        {/* Brand */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                backgroundColor: 'var(--role-family)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
              }}
            >
              <IconLogo size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                CareLoop
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--role-family)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Family View
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar Nav */}
        <div style={{ padding: '16px 12px', flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            onClick={() => setActiveTab('today')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              border: 'none',
              backgroundColor: activeTab === 'today' ? 'var(--role-family-soft)' : 'transparent',
              color: activeTab === 'today' ? 'var(--role-family-text)' : 'var(--text-secondary)',
              fontWeight: activeTab === 'today' ? 700 : 500,
              fontSize: 14,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
              transition: 'all 0.15s ease',
            }}
          >
            <IconHeartPulse size={18} />
            <span>Today</span>
          </button>

          <button
            onClick={() => setActiveTab('calendar')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              border: 'none',
              backgroundColor: activeTab === 'calendar' ? 'var(--role-family-soft)' : 'transparent',
              color: activeTab === 'calendar' ? 'var(--role-family-text)' : 'var(--text-secondary)',
              fontWeight: activeTab === 'calendar' ? 700 : 500,
              fontSize: 14,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
              transition: 'all 0.15s ease',
            }}
          >
            <IconCalendar size={18} />
            <span>Calendar</span>
          </button>

          <button
            onClick={() => setActiveTab('contacts')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              border: 'none',
              backgroundColor: activeTab === 'contacts' ? 'var(--role-family-soft)' : 'transparent',
              color: activeTab === 'contacts' ? 'var(--role-family-text)' : 'var(--text-secondary)',
              fontWeight: activeTab === 'contacts' ? 700 : 500,
              fontSize: 14,
              cursor: 'pointer',
              textAlign: 'left',
              width: '100%',
              transition: 'all 0.15s ease',
            }}
          >
            <IconPhone size={18} />
            <span>Contacts</span>
          </button>
        </div>

        {/* Family Helper Identity Card in Sidebar */}
        <div style={{ padding: '16px', borderTop: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-card-hover)' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
            {caregiver.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Supporting Aarav Patel ({caregiver.relationship})
          </div>
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--role-family-text)', fontWeight: 600 }}>
            <IconShieldCheck size={12} />
            <span>Consent Active</span>
          </div>
        </div>
      </aside>

      {/* ── Main Content Area ─────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top Header */}
        <header
          style={{
            height: 64,
            backgroundColor: 'var(--header-bg)',
            borderBottom: '1px solid var(--header-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 32px',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          {/* Breadcrumb / Kicker */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 800,
                color: 'var(--role-family)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                backgroundColor: 'var(--role-family-soft)',
                padding: '4px 10px',
                borderRadius: 6,
              }}
            >
              FAMILY VIEW
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
              Aarav's Recovery (Day {patient.day_number})
            </span>
          </div>

          {/* Right Header Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            {/* Role Chip */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 20,
                backgroundColor: 'var(--role-family-soft)',
                border: '1px solid var(--role-family)',
                color: 'var(--role-family-text)',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              <span>Family helper</span>
            </div>

            <SwitchDemoWorkspace currentUser={user} />
            <ThemeToggle />

            <button
              onClick={logout}
              title="Sign out"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 12px',
                borderRadius: 6,
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-surface)',
                color: 'var(--text-secondary)',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <IconLogOut size={14} />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        {/* Success Toast */}
        {successToast && (
          <div
            style={{
              backgroundColor: 'var(--success-green-soft)',
              color: 'var(--success-green-text)',
              padding: '12px 24px',
              borderBottom: '1px solid var(--success-green)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            <IconCheck size={16} />
            <span>{successToast}</span>
          </div>
        )}

        {/* Body Content */}
        <main style={{ padding: '32px', flex: 1, maxWidth: 1100, margin: '0 auto', width: '100%' }}>
          {sharingBlocked ? (
            /* ── Consent Revoked / Sharing Off State ── */
            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--warning-amber)',
                borderRadius: 12,
                padding: 40,
                textAlign: 'center',
                maxWidth: 600,
                margin: '40px auto',
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 28,
                  backgroundColor: 'var(--warning-amber-soft)',
                  color: 'var(--warning-amber-text)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px',
                }}
              >
                <IconAlertTriangle size={28} />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8 }}>
                Sharing is turned off
              </h2>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
                Aarav Patel has turned family sharing off. You do not currently have access to his recovery updates.
                Sharing controls belong solely to the patient and update in real time.
              </p>
              <button
                onClick={fetchTodayData}
                style={{
                  padding: '9px 18px',
                  borderRadius: 8,
                  backgroundColor: 'var(--role-family)',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 700,
                  fontSize: 13,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <IconRefresh size={14} />
                <span>Check for access</span>
              </button>
            </div>
          ) : loading && !todayData ? (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
              Loading family recovery overview...
            </div>
          ) : errorMsg ? (
            <div style={{ padding: 20, borderRadius: 8, backgroundColor: 'var(--alert-red-soft)', color: 'var(--alert-red-text)', fontSize: 14 }}>
              {errorMsg}
            </div>
          ) : activeTab === 'today' ? (
            /* ── TAB 1: TODAY ── */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* Patient Identity & Consent Banner */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px 20px',
                  borderRadius: 12,
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div>
                  <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                    Aarav's recovery, for family
                  </h1>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: 'var(--text-secondary)' }}>
                    <span>{patient.full_name}</span>
                    <span>•</span>
                    <span>{patient.patient_code}</span>
                    <span>•</span>
                    <span>Age {patient.age}</span>
                    <span>•</span>
                    <span>{patient.condition}</span>
                    <span>•</span>
                    <strong style={{ color: 'var(--role-family)' }}>Day {patient.day_number}</strong>
                  </div>
                </div>

                {/* Consent Badge */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '6px 12px',
                    borderRadius: 8,
                    backgroundColor: 'var(--success-green-soft)',
                    color: 'var(--success-green-text)',
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  <IconShieldCheck size={14} />
                  <span>{caregiver.sharing_badge}</span>
                </div>
              </div>

              {/* "What you may need to do" Guidance Card */}
              {todayData?.what_you_may_need_to_do && (
                <div
                  style={{
                    padding: '20px',
                    borderRadius: 12,
                    backgroundColor:
                      todayData.what_you_may_need_to_do.severity === 'urgent'
                        ? 'var(--alert-red-soft)'
                        : todayData.what_you_may_need_to_do.severity === 'action_needed'
                        ? 'var(--role-family-soft)'
                        : 'var(--success-green-soft)',
                    border: `1px solid ${
                      todayData.what_you_may_need_to_do.severity === 'urgent'
                        ? 'var(--alert-red)'
                        : todayData.what_you_may_need_to_do.severity === 'action_needed'
                        ? 'var(--role-family)'
                        : 'var(--success-green)'
                    }`,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4, color: 'var(--text-primary)' }}>
                    What you may need to do
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                    {todayData.what_you_may_need_to_do.text}
                  </div>
                </div>
              )}

              {/* Grid: Doses & Vitals */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24 }}>
                {/* Doses Card */}
                <div
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 12,
                    padding: '20px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <IconPill size={18} color="var(--role-family)" />
                      <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)' }}>
                        Today's Medicines
                      </h3>
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {todayData?.today_doses?.taken || 0} of {todayData?.today_doses?.total || 0} taken
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {todayData?.today_doses?.items?.map((d) => (
                      <div
                        key={d.dose_id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '12px 14px',
                          borderRadius: 8,
                          backgroundColor: 'var(--bg-card-hover)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>
                            {d.medicine_name}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                            <IconClock size={12} />
                            <span>{d.scheduled_time}</span>
                          </div>
                        </div>

                        <div>
                          {d.status === 'Taken' ? (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                                padding: '4px 10px',
                                borderRadius: 6,
                                backgroundColor: 'var(--success-green-soft)',
                                color: 'var(--success-green-text)',
                                fontSize: 12,
                                fontWeight: 700,
                              }}
                            >
                              <IconCheck size={12} />
                              <span>Taken</span>
                            </span>
                          ) : (
                            <button
                              disabled={actionLoading}
                              onClick={() => handleHelpDose(d.dose_id, d.medicine_name)}
                              style={{
                                padding: '6px 12px',
                                borderRadius: 6,
                                backgroundColor: 'var(--role-family)',
                                color: '#ffffff',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: 12,
                                cursor: 'pointer',
                                transition: 'opacity 0.15s ease',
                              }}
                            >
                              I helped Aarav take it
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Latest Valid Vitals Card */}
                <div
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 12,
                    padding: '20px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <IconActivity size={18} color="var(--role-family)" />
                      <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)' }}>
                        Latest Valid Readings
                      </h3>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {/* Heart Rate */}
                    <div
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        backgroundColor: 'var(--bg-card-hover)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Pulse Rate</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>
                          {todayData?.latest_vitals?.Heart_Rate
                            ? `${todayData.latest_vitals.Heart_Rate.value} ${todayData.latest_vitals.Heart_Rate.unit}`
                            : '74 bpm'}
                        </div>
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--success-green-text)', backgroundColor: 'var(--success-green-soft)', padding: '3px 8px', borderRadius: 4 }}>
                        Valid reading
                      </span>
                    </div>

                    {/* Oxygen SpO2 */}
                    <div
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        backgroundColor: 'var(--bg-card-hover)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Oxygen Level (SpO₂)</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>
                          {todayData?.latest_vitals?.SpO2
                            ? `${todayData.latest_vitals.SpO2.value} ${todayData.latest_vitals.SpO2.unit}`
                            : '96%'}
                        </div>
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--success-green-text)', backgroundColor: 'var(--success-green-soft)', padding: '3px 8px', borderRadius: 4 }}>
                        Valid reading
                      </span>
                    </div>

                    {/* Checkin Status Indicator (No raw symptom text!) */}
                    <div
                      style={{
                        padding: '12px 14px',
                        borderRadius: 8,
                        backgroundColor: 'var(--bg-card-hover)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Check-in Log</div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                          {todayData?.checkin_status?.message || 'Check-in recorded today'}
                        </div>
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        Status only
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Next Appointment & Emergency Guidance Card */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                {/* Next Appointment Card */}
                <div
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 12,
                    padding: '20px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <IconCalendar size={18} color="var(--role-family)" />
                    <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)' }}>
                      Next Appointment
                    </h3>
                  </div>

                  {todayData?.next_appointment ? (
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                        {todayData.next_appointment.date}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                        {todayData.next_appointment.doctor_name} ({todayData.next_appointment.specialization})
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                        Type: {todayData.next_appointment.type}
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                      No upcoming appointments scheduled.
                    </div>
                  )}
                </div>

                {/* Emergency Guidance Card */}
                <div
                  style={{
                    backgroundColor: 'var(--alert-red-soft)',
                    border: '1px solid var(--alert-red)',
                    borderRadius: 12,
                    padding: '20px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--alert-red-text)' }}>
                    <IconAlertTriangle size={18} />
                    <h3 style={{ fontSize: 16, fontWeight: 800 }}>
                      Emergency Assistance
                    </h3>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 12 }}>
                    If Aarav experiences severe chest pain, shortness of breath, or sudden weakness, call 112 immediately.
                  </p>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <a
                      href="tel:112"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '6px 12px',
                        borderRadius: 6,
                        backgroundColor: 'var(--alert-red)',
                        color: '#ffffff',
                        fontSize: 12,
                        fontWeight: 700,
                        textDecoration: 'none',
                      }}
                    >
                      <IconPhone size={14} />
                      <span>Call 112</span>
                    </a>
                    <a
                      href="tel:+911126598800"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '6px 12px',
                        borderRadius: 6,
                        backgroundColor: 'var(--bg-surface)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: 12,
                        fontWeight: 600,
                        textDecoration: 'none',
                      }}
                    >
                      <span>Hospital Desk</span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          ) : activeTab === 'calendar' ? (
            /* ── TAB 2: CALENDAR ── */
            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 12,
                padding: '24px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 16 }}>
                Scheduled Appointments & Follow-ups
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {calendarData?.appointments?.length ? (
                  calendarData.appointments.map((a) => (
                    <div
                      key={a.appointment_id}
                      style={{
                        padding: '16px',
                        borderRadius: 8,
                        backgroundColor: 'var(--bg-card-hover)',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {a.date} at {a.time}
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                          {a.doctor_name} · {a.department}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                          Type: {a.type}
                        </div>
                      </div>
                      <a
                        href={`http://127.0.0.1:8000${a.ics_url}`}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          padding: '6px 12px',
                          borderRadius: 6,
                          border: '1px solid var(--border-subtle)',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          fontSize: 12,
                          fontWeight: 600,
                          textDecoration: 'none',
                        }}
                      >
                        Download .ics
                      </a>
                    </div>
                  ))
                ) : (
                  <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
                    No appointments on file.
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* ── TAB 3: CONTACTS ── */
            <div
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 12,
                padding: '24px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <h2 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 20 }}>
                Care Team & Emergency Contacts
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                {/* Attending Doctor */}
                <div style={{ padding: 16, borderRadius: 8, border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-card-hover)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--role-doctor)', textTransform: 'uppercase' }}>
                    Attending Physician
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
                    {contactsData?.attending_doctor?.name || 'Dr. Ananya Sharma'}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                    Phone: {contactsData?.attending_doctor?.phone || '+91-98765-01001'}
                  </div>
                </div>

                {/* Assigned Nurse */}
                <div style={{ padding: 16, borderRadius: 8, border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-card-hover)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--role-nurse)', textTransform: 'uppercase' }}>
                    Assigned Care Nurse
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
                    {contactsData?.assigned_nurse?.name || 'Priya Nair'}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                    Phone: {contactsData?.assigned_nurse?.phone || '+91-98765-01002'}
                  </div>
                </div>

                {/* Hospital Desk */}
                <div style={{ padding: 16, borderRadius: 8, border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-card-hover)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    CareLoop Hospital 24/7 Desk
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
                    General Follow-Up Desk
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                    Phone: +91-11-2659-8800 (Mon-Sun 24/7)
                  </div>
                </div>

                {/* National Emergency */}
                <div style={{ padding: 16, borderRadius: 8, border: '1px solid var(--alert-red)', backgroundColor: 'var(--alert-red-soft)' }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--alert-red-text)', textTransform: 'uppercase' }}>
                    National Emergency Services
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--alert-red-text)', marginTop: 4 }}>
                    Dial 112
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4 }}>
                    For immediate medical emergency, chest pain, or collapse.
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

