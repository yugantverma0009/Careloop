import React from 'react';

/**
 * PatientIdentity Component (D-01, Clinical Safety Policy)
 *
 * Strict Requirement: Always display at least two patient identifiers
 * (Full Name, Age, Patient Code CL-0000X) to eliminate wrong-patient errors.
 */
export default function PatientIdentity({
  patient = {},
  patientCode,
  fullName,
  patientName,
  ageYears,
  size = 'md',
  showCondition = true,
  inline = false,
  style = {},
  onClick,
}) {
  const name = fullName || patientName || patient.full_name || patient.patient_name || (patient.patient_id ? `Patient #${patient.patient_id}` : 'Unknown Patient');
  const code = patientCode || patient.patient_code || (patient.patient_id ? `CL-${String(patient.patient_id).padStart(5, '0')}` : 'CL-00000');
  const age = (ageYears !== undefined && ageYears !== null) ? `${ageYears}y` : (patient.age_years !== undefined && patient.age_years !== null ? `${patient.age_years}y` : (patient.age ? `${patient.age}y` : null));
  const condition = patient.condition || patient.condition_summary;

  const fontSizes = {
    sm: { name: '13px', meta: '11px', badge: '10px' },
    md: { name: '14px', meta: '12px', badge: '11px' },
    lg: { name: '16px', meta: '13px', badge: '12px' },
  }[size] || { name: '14px', meta: '12px', badge: '11px' };

  if (inline) {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          fontFamily: "'Inter', sans-serif",
          ...style,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: fontSizes.name, color: 'var(--text-primary, #0f172a)' }}>
          {name}
        </span>
        {age && (
          <span style={{ fontSize: fontSizes.meta, color: 'var(--text-muted, #94a3b8)', fontWeight: 500 }}>
            ({age})
          </span>
        )}
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: fontSizes.badge,
            fontWeight: 600,
            padding: '1px 5px',
            borderRadius: '4px',
            background: 'var(--bg-base, #f1f5f9)',
            color: 'var(--text-secondary, #475569)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
          }}
        >
          {code}
        </span>
        {showCondition && condition && (
          <span style={{ fontSize: fontSizes.meta, color: 'var(--text-muted, #94a3b8)' }}>
            · {condition}
          </span>
        )}
      </span>
    );
  }

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '2px',
        fontFamily: "'Inter', sans-serif",
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: fontSizes.name, color: 'var(--text-primary, #0f172a)' }}>
          {name}
        </span>
        {age && (
          <span style={{ fontSize: fontSizes.meta, color: 'var(--text-muted, #94a3b8)', fontWeight: 500 }}>
            {age}
          </span>
        )}
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: fontSizes.badge,
            fontWeight: 600,
            padding: '1px 6px',
            borderRadius: '4px',
            background: 'var(--bg-base, #f1f5f9)',
            color: 'var(--text-secondary, #475569)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            letterSpacing: '0.02em',
          }}
          title="Synthetic Patient Code (Identifier)"
        >
          {code}
        </span>
      </div>
      {showCondition && condition && (
        <div style={{ fontSize: fontSizes.meta, color: 'var(--text-secondary, #64748b)', fontWeight: 500 }}>
          {condition}
        </div>
      )}
    </div>
  );
}
