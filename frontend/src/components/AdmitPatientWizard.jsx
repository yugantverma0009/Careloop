import React, { useState } from 'react';
import { admitPatient } from '../services/api';
import { IconShieldCheck } from './Icons';

export default function AdmitPatientWizard({ onComplete, onCancel }) {
  const [currentStep, setCurrentStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [successData, setSuccessData] = useState(null);

  // Form states
  const [patientData, setPatientData] = useState({
    full_name: '',
    date_of_birth: '1975-06-15',
    phone: '+91-98765-12345',
    preferred_language: 'en',
  });

  const [dischargeData, setDischargeData] = useState({
    condition: 'Post-CABG Surgical Recovery',
    discharge_date: new Date().toISOString().split('T')[0],
    summary_text: `DISCHARGE SUMMARY
Condition: Post-CABG recovery. Sternal wound intact and healing well.

MEDICATIONS: CardioPulse-XR 1 tablet morning (08:00) and evening (20:00).
VasculoNorm-5 1 tablet afternoon (13:00) with water.

FOLLOW-UP: Cardiology OPD Clinic Room 302 in 7 days at 10:30 AM with Dr. Ananya Sharma.

WARNING SIGNS: Acute chest pain, shortness of breath, or SpO2 dropping below 94% requires immediate 112 emergency care.

ACTIVITY: Walk indoors for 10-15 minutes twice daily. Avoid lifting over 5 kg.

WOUND CARE: Keep sternal incision dry and clean. Daily inspection for drainage or redness.`,
  });

  const [prescriptions, setPrescriptions] = useState([
    { name: 'CardioPulse-XR', dosage: '1 tablet', frequency: 'Morning (08:00) and evening (20:00)' },
    { name: 'VasculoNorm-5', dosage: '1 tablet', frequency: 'Afternoon (13:00)' },
  ]);

  const [proposedLimits, setProposedLimits] = useState([
    { rule_type: 'Reading_Above', threshold_val: 100, severity: 'Review_Soon' },
    { rule_type: 'Reading_Below', threshold_val: 55, severity: 'Review_Soon' },
  ]);

  const [deviceData, setDeviceData] = useState({
    device_id: 'DEV-ESP32-NEW-01',
    model: 'ESP32_Wearable_V1',
  });

  const [caregiverData, setCaregiverData] = useState({
    full_name: 'Pooja Joshi',
    phone: '+91-98765-12346',
    relationship: 'Daughter / Family Helper',
    consent_granted: true,
  });

  const handleStartFollowUp = async () => {
    setSubmitting(true);
    try {
      const res = await admitPatient({
        patient: patientData,
        discharge: dischargeData,
        prescriptions,
        proposed_limits: proposedLimits,
        device: deviceData,
        caregiver: caregiverData,
      });
      setSuccessData(res);
      if (onComplete) onComplete(res);
    } catch (err) {
      alert(`Admission failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (successData) {
    return (
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid #10b981',
          borderRadius: '12px',
          padding: '32px',
          textAlign: 'center',
          maxWidth: '560px',
          margin: '30px auto',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ color: '#10b981', marginBottom: '14px' }}>
          <IconShieldCheck style={{ width: '48px', height: '48px', margin: '0 auto' }} />
        </div>
        <h3 style={{ margin: '0 0 8px 0', fontSize: '20px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
          Patient Follow-up Initiated
        </h3>
        <p style={{ margin: '0 0 16px 0', fontSize: '14px', color: 'var(--text-secondary, #475569)' }}>
          {successData.full_name} ({successData.patient_code}) successfully onboarded to CareLoop.
        </p>

        <div
          style={{
            background: 'var(--bg-subtle, #f8fafc)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '8px',
            padding: '16px',
            textAlign: 'left',
            fontSize: '13px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            marginBottom: '24px',
          }}
        >
          <div><strong>Patient Code:</strong> {successData.patient_code}</div>
          <div><strong>Welcome Call:</strong> Created task due within 48 hours (Nurse Phone Outreach)</div>
          <div><strong>Alert Limits:</strong> Waiting for doctor approval (Monitoring holds until approved)</div>
          <div><strong>Recovery Plan:</strong> Initial draft compiled from discharge papers</div>
        </div>

        <button
          type="button"
          onClick={() => {
            setSuccessData(null);
            setCurrentStep(1);
            if (onCancel) onCancel();
          }}
          style={{
            padding: '10px 24px',
            background: 'var(--accent-teal, #0f766e)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          Done &amp; Return to Call List
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'var(--bg-surface, #ffffff)',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        borderRadius: '14px',
        padding: '24px',
        boxShadow: 'var(--shadow-card)',
        maxWidth: '840px',
        margin: '0 auto',
      }}
    >
      {/* Stepper Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', paddingBottom: '16px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
            Admit Patient to CareLoop Follow-Up
          </h2>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)', marginTop: '4px' }}>
            Step {currentStep} of 7: {currentStep === 1 && 'Patient Demographics'}
            {currentStep === 2 && 'Discharge Summary & Paperwork'}
            {currentStep === 3 && 'Medications & Prescriptions'}
            {currentStep === 4 && 'Proposed Alert Limits'}
            {currentStep === 5 && 'Telemetry Device Binding'}
            {currentStep === 6 && 'Family Helper & Recorded Consent'}
            {currentStep === 7 && 'Review & Start Follow-Up'}
          </div>
        </div>

        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: '1px solid var(--border-subtle, #cbd5e1)',
            background: 'transparent',
            color: 'var(--text-secondary, #64748b)',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
      </div>

      {/* Step 1: Patient Demographics */}
      {currentStep === 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              Full Name *
            </label>
            <input
              type="text"
              value={patientData.full_name}
              onChange={(e) => setPatientData({ ...patientData, full_name: e.target.value })}
              placeholder="e.g. Ramesh Chandra"
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle, #cbd5e1)', fontSize: '13px', boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                Date of Birth
              </label>
              <input
                type="date"
                value={patientData.date_of_birth}
                onChange={(e) => setPatientData({ ...patientData, date_of_birth: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle, #cbd5e1)', fontSize: '13px', boxSizing: 'border-box' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                Phone Number *
              </label>
              <input
                type="text"
                value={patientData.phone}
                onChange={(e) => setPatientData({ ...patientData, phone: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle, #cbd5e1)', fontSize: '13px', boxSizing: 'border-box' }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              Preferred Language
            </label>
            <select
              value={patientData.preferred_language}
              onChange={(e) => setPatientData({ ...patientData, preferred_language: e.target.value })}
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle, #cbd5e1)', fontSize: '13px', boxSizing: 'border-box' }}
            >
              <option value="en">English</option>
              <option value="hi">हिंदी (Hindi)</option>
            </select>
          </div>
        </div>
      )}

      {/* Step 2: Discharge Summary & Indexing */}
      {currentStep === 2 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              Primary Condition / Diagnosis
            </label>
            <input
              type="text"
              value={dischargeData.condition}
              onChange={(e) => setDischargeData({ ...dischargeData, condition: e.target.value })}
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle, #cbd5e1)', fontSize: '13px', boxSizing: 'border-box' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              Discharge Papers Text (Automatic Section Indexing)
            </label>
            <textarea
              rows={8}
              value={dischargeData.summary_text}
              onChange={(e) => setDischargeData({ ...dischargeData, summary_text: e.target.value })}
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle, #cbd5e1)', fontSize: '12px', fontFamily: 'monospace', boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(15, 118, 110, 0.08)', border: '1px solid var(--accent-teal, #0f766e)', fontSize: '12px', color: '#0f766e' }}>
            ✓ Automatic Section Ingestion ready: will extract passages for <strong>Medications</strong>, <strong>Follow-up</strong>, <strong>Warning signs</strong>, <strong>Wound care</strong>, and <strong>Activity</strong>.
          </div>
        </div>
      )}

      {/* Step 3: Prescriptions */}
      {currentStep === 3 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
            Prescriptions extracted from discharge papers. Reconciled automatically against drafted recovery items.
          </div>

          {prescriptions.map((rx, idx) => (
            <div key={idx} style={{ padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle, #e2e8f0)', background: 'var(--bg-subtle, #f8fafc)', display: 'grid', gridTemplateColumns: '2fr 1fr 2fr', gap: '10px', alignItems: 'center' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Medication Name</label>
                <input
                  type="text"
                  value={rx.name}
                  onChange={(e) => {
                    const copy = [...prescriptions];
                    copy[idx].name = e.target.value;
                    setPrescriptions(copy);
                  }}
                  style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Dose</label>
                <input
                  type="text"
                  value={rx.dosage}
                  onChange={(e) => {
                    const copy = [...prescriptions];
                    copy[idx].dosage = e.target.value;
                    setPrescriptions(copy);
                  }}
                  style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Frequency</label>
                <input
                  type="text"
                  value={rx.frequency}
                  onChange={(e) => {
                    const copy = [...prescriptions];
                    copy[idx].frequency = e.target.value;
                    setPrescriptions(copy);
                  }}
                  style={{ width: '100%', padding: '6px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Step 4: Proposed Limits */}
      {currentStep === 4 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid #f59e0b', fontSize: '12px', color: '#92400e' }}>
            ⚠️ <strong>Doctor Approval Mandatory:</strong> Monitoring does not start until Dr. Ananya Sharma reviews and approves these proposed alert limits.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {proposedLimits.map((rule, idx) => (
              <div key={idx} style={{ padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0', display: 'flex', gap: '12px', alignItems: 'center' }}>
                <div style={{ flex: 1, fontSize: '13px', fontWeight: 600 }}>
                  {rule.rule_type === 'Reading_Above' ? 'Heart Rate Upper Limit (> bpm)' : 'Heart Rate Lower Limit (< bpm)'}
                </div>
                <input
                  type="number"
                  value={rule.threshold_val}
                  onChange={(e) => {
                    const copy = [...proposedLimits];
                    copy[idx].threshold_val = parseFloat(e.target.value) || 0;
                    setProposedLimits(copy);
                  }}
                  style={{ width: '90px', padding: '6px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                />
                <span style={{ fontSize: '11px', color: '#64748b' }}>bpm</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step 5: Telemetry Device Binding */}
      {currentStep === 5 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              Device Serial / Identifier
            </label>
            <input
              type="text"
              value={deviceData.device_id}
              onChange={(e) => setDeviceData({ ...deviceData, device_id: e.target.value })}
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg-subtle, #f8fafc)', border: '1px solid var(--border-subtle, #e2e8f0)', fontSize: '12px', color: '#64748b' }}>
            Device status: <strong>Simulator / DevKit V1</strong> ready. Heartbeat checks will be scheduled upon limit activation.
          </div>
        </div>
      )}

      {/* Step 6: Family Helper & Recorded Consent */}
      {currentStep === 6 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              Family Helper Full Name
            </label>
            <input
              type="text"
              value={caregiverData.full_name}
              onChange={(e) => setCaregiverData({ ...caregiverData, full_name: e.target.value })}
              style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                Phone Number
              </label>
              <input
                type="text"
                value={caregiverData.phone}
                onChange={(e) => setCaregiverData({ ...caregiverData, phone: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                Relationship
              </label>
              <input
                type="text"
                value={caregiverData.relationship}
                onChange={(e) => setCaregiverData({ ...caregiverData, relationship: e.target.value })}
                style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px', boxSizing: 'border-box' }}
              />
            </div>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--text-primary, #0f172a)', cursor: 'pointer', marginTop: '6px' }}>
            <input
              type="checkbox"
              checked={caregiverData.consent_granted}
              onChange={(e) => setCaregiverData({ ...caregiverData, consent_granted: e.target.checked })}
              style={{ accentColor: 'var(--accent-teal, #0f766e)' }}
            />
            <span>Record patient &amp; family telemetry sharing consent (audited under DPDP)</span>
          </label>
        </div>
      )}

      {/* Step 7: Review & Start Follow-Up */}
      {currentStep === 7 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
            Final Onboarding Confirmation
          </div>

          <div style={{ background: 'var(--bg-subtle, #f8fafc)', border: '1px solid var(--border-subtle, #e2e8f0)', borderRadius: '10px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
            <div><strong>Patient:</strong> {patientData.full_name} ({patientData.phone})</div>
            <div><strong>Condition:</strong> {dischargeData.condition}</div>
            <div><strong>Prescriptions:</strong> {prescriptions.length} items configured</div>
            <div><strong>Alert Limits:</strong> {proposedLimits.length} rules proposed (holds for Dr. Ananya Sharma review)</div>
            <div><strong>Automated Welcome Task:</strong> Call scheduled within 48 hours for nurse contact</div>
          </div>
        </div>
      )}

      {/* Stepper Buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '24px', borderTop: '1px solid var(--border-subtle, #e2e8f0)', paddingTop: '16px' }}>
        {currentStep > 1 ? (
          <button
            type="button"
            onClick={() => setCurrentStep(currentStep - 1)}
            style={{
              padding: '8px 18px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              background: 'transparent',
              color: 'var(--text-secondary, #475569)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            ← Back
          </button>
        ) : <div />}

        {currentStep < 7 ? (
          <button
            type="button"
            disabled={currentStep === 1 && (!patientData.full_name.trim() || !patientData.phone.trim())}
            onClick={() => setCurrentStep(currentStep + 1)}
            style={{
              padding: '8px 20px',
              borderRadius: '6px',
              background: 'var(--accent-teal, #0f766e)',
              color: '#ffffff',
              border: 'none',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Next Step →
          </button>
        ) : (
          <button
            type="button"
            disabled={submitting}
            onClick={handleStartFollowUp}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              background: '#10b981',
              color: '#ffffff',
              border: 'none',
              fontSize: '13px',
              fontWeight: 700,
              cursor: submitting ? 'not-allowed' : 'pointer',
            }}
          >
            {submitting ? 'Starting Follow-Up...' : '✓ Start Follow-Up & Create Welcome Task'}
          </button>
        )}
      </div>
    </div>
  );
}
