import React, { useState, useEffect } from 'react';
import { getPatientDirectory } from '../services/api';
import PatientIdentity from './PatientIdentity';
import { IconSearch, IconAlertTriangle } from './Icons';

/**
 * PatientDirectory Component (D-05)
 *
 * Provides a searchable, filterable directory of all post-discharge patients.
 * Enforces BhoomiSetu design tokens and 2-identifier clinical safety governance.
 */
export default function PatientDirectory({ onSelectPatient }) {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // 'all', 'mine', 'has_flags', 'silent_device'
  const [search, setSearch] = useState('');

  const fetchDirectory = async () => {
    setLoading(true);
    try {
      const data = await getPatientDirectory(filter, search);
      setPatients(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load patient directory:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDirectory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, search]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Directory Header & Stats */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h2
            style={{
              fontSize: '18px',
              fontWeight: 800,
              color: 'var(--text-primary, #0f172a)',
              letterSpacing: '-0.02em',
              margin: '0 0 4px 0',
            }}
          >
            Patient Directory
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
            Master post-discharge patient registry with device telemetry, adherence rates, and attending staff.
          </p>
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', width: '280px' }}>
          <div
            style={{
              position: 'absolute',
              left: '10px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#94a3b8',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <IconSearch width={14} height={14} />
          </div>
          <input
            type="text"
            placeholder="Search name, code, condition..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '7px 12px 7px 32px',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              background: 'var(--bg-surface, #ffffff)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
          paddingBottom: '10px',
          flexWrap: 'wrap',
        }}
      >
        {[
          { id: 'all', label: 'All Patients' },
          { id: 'mine', label: 'My Patients' },
          { id: 'has_flags', label: 'With Open Flags' },
          { id: 'silent_device', label: 'Silent Devices (Missing Data)' },
        ].map((tab) => {
          const isActive = filter === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilter(tab.id)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: isActive ? 700 : 500,
                border: 'none',
                cursor: 'pointer',
                background: isActive ? '#0b1528' : 'var(--bg-surface, #ffffff)',
                color: isActive ? '#ffffff' : 'var(--text-secondary, #475569)',
                boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Patients Table */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '950px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Patient Identity
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Condition & Day
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Care Team
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Open Flags
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Device Telemetry
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Last Check-in
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  7d Adherence
                </th>
                <th style={{ padding: '12px 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', textAlign: 'right' }}>
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    Loading patient directory...
                  </td>
                </tr>
              ) : patients.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    No patients match the active filter criteria.
                  </td>
                </tr>
              ) : (
                patients.map((p) => {
                  const isSilent = p.device_status !== 'Online';
                  const adherencePct = Math.round(Number(p.adherence_this_week || 100));
                  return (
                    <tr
                      key={p.patient_id}
                      onClick={() => onSelectPatient(p.patient_id)}
                      style={{
                        borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                        cursor: 'pointer',
                        transition: 'background 0.1s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--bg-card-hover, #f8fafc)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      {/* Identity Column */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <PatientIdentity
                          patient={{
                            patient_id: p.patient_id,
                            full_name: p.full_name,
                            age_years: p.age_years,
                            patient_code: p.patient_code,
                          }}
                          size="md"
                          showCondition={false}
                        />
                      </td>

                      {/* Condition & Discharge Day */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                          {p.condition_summary || 'Post-discharge monitoring'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                          Day {p.day_number || 1} post-op
                        </div>
                      </td>

                      {/* Care Team */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                          {p.attending_doctor || 'Dr. Ananya Sharma'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '1px' }}>
                          Nurse: {p.assigned_nurse || 'Priya Nair'}
                        </div>
                      </td>

                      {/* Open Flags */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        {p.open_flag_count > 0 ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontSize: '11px',
                              fontWeight: 700,
                              background: 'var(--alert-red-soft, #fef2f2)',
                              color: 'var(--alert-red, #dc2626)',
                              border: '1px solid rgba(220, 38, 38, 0.2)',
                            }}
                          >
                            <IconAlertTriangle width={12} height={12} />
                            {p.open_flag_count} {p.open_flag_count === 1 ? 'flag' : 'flags'}
                          </span>
                        ) : (
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontSize: '11px',
                              fontWeight: 600,
                              background: 'var(--success-green-soft, #f0fdf4)',
                              color: 'var(--success-green, #059669)',
                            }}
                          >
                            No open flags
                          </span>
                        )}
                      </td>

                      {/* Device Status */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        {isSilent ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '5px',
                                padding: '2px 8px',
                                borderRadius: '12px',
                                fontSize: '11px',
                                fontWeight: 700,
                                background: 'var(--warning-amber-soft, #fffbeb)',
                                color: 'var(--warning-amber, #d97706)',
                                width: 'fit-content',
                              }}
                            >
                              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#d97706' }} />
                              Missing Data
                            </span>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)' }}>
                              {p.minutes_since_last_seen ? `${Math.round(p.minutes_since_last_seen / 60)}h silent` : 'No reading yet'}
                            </span>
                          </div>
                        ) : (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '5px',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              fontSize: '11px',
                              fontWeight: 700,
                              background: 'var(--success-green-soft, #f0fdf4)',
                              color: 'var(--success-green, #059669)',
                            }}
                          >
                            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#059669' }} />
                            Online
                          </span>
                        )}
                      </td>

                      {/* Last Check-in */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        {p.last_checkin_pain !== null && p.last_checkin_pain !== undefined ? (
                          <div>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                              Pain {p.last_checkin_pain}/10
                            </div>
                            <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', marginTop: '1px' }}>
                              {p.last_checkin_at ? new Date(p.last_checkin_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : 'Recorded'}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>No check-in</span>
                        )}
                      </td>

                      {/* Adherence Rate */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', minWidth: '32px' }}>
                            {adherencePct}%
                          </span>
                          <div style={{ width: '60px', height: '6px', borderRadius: '3px', background: 'var(--bg-base, #e2e8f0)', overflow: 'hidden' }}>
                            <div
                              style={{
                                width: `${adherencePct}%`,
                                height: '100%',
                                background: adherencePct >= 80 ? 'var(--success-green, #059669)' : adherencePct >= 50 ? 'var(--warning-amber, #d97706)' : 'var(--alert-red, #dc2626)',
                              }}
                            />
                          </div>
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                          Self-reported
                        </div>
                      </td>

                      {/* Action */}
                      <td style={{ padding: '14px 16px', verticalAlign: 'middle', textAlign: 'right' }}>
                        <button
                          type="button"
                          id={`btn-view-chart-${p.patient_id}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectPatient(p.patient_id);
                          }}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-subtle, #cbd5e1)',
                            background: 'var(--bg-surface, #ffffff)',
                            color: 'var(--text-primary, #0f172a)',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'var(--navy-deep, #0b1528)';
                            e.currentTarget.style.color = '#ffffff';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'var(--bg-surface, #ffffff)';
                            e.currentTarget.style.color = 'var(--text-primary, #0f172a)';
                          }}
                        >
                          View chart →
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
