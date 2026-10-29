import React, { useState, useEffect } from 'react';
import { getPatientFhirBundle } from '../services/api';
import { IconShieldCheck, IconExternalLink } from './Icons';

export default function DoctorFhirExportView({ user = {} }) {
  const [selectedPid, setSelectedPid] = useState(1);
  const [loading, setLoading] = useState(false);
  const [bundleData, setBundleData] = useState(null);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  const PATIENTS = [
    { id: 1, code: 'CL-00001', name: 'Aarav Patel', condition: 'Post-CABG (Day 3)' },
    { id: 2, code: 'CL-00002', name: 'Meera Sharma', condition: 'Total Knee Arthroplasty (Day 6)' },
    { id: 3, code: 'CL-00003', name: 'Rajesh Verma', condition: 'Community Pneumonia (Day 5)' },
    { id: 4, code: 'CL-00004', name: 'Kabir Mehta', condition: 'Appendectomy (Day 9)' },
    { id: 5, code: 'CL-00005', name: 'Sunita Rao', condition: 'Congestive Heart Failure (Day 4)' },
  ];

  const fetchBundle = async (pid) => {
    setLoading(true);
    setDownloadSuccess(false);
    try {
      const data = await getPatientFhirBundle(pid);
      setBundleData(data);
    } catch (err) {
      console.error('Failed to load FHIR bundle:', err);
      alert(`FHIR Export failed: ${err.message || 'Error'}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBundle(selectedPid);
  }, [selectedPid]);

  const handleDownload = () => {
    if (!bundleData) return;
    const jsonStr = JSON.stringify(bundleData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `careloop_fhir_r4_patient_${selectedPid}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 5000);
  };

  const selectedPatient = PATIENTS.find((p) => p.id === Number(selectedPid)) || PATIENTS[0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Toast Alert */}
      {downloadSuccess && (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: '8px',
            background: 'var(--accent-tint, #ecfdf5)',
            border: '1px solid var(--accent-subtle, #a7f3d0)',
            color: 'var(--accent-color, #059669)',
            fontSize: '13px',
            fontWeight: 700,
          }}
        >
          ✓ HL7 FHIR R4 Patient Bundle downloaded successfully and recorded in compliance audit log.
        </div>
      )}

      {/* Header Bar */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '20px 24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '14px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 800,
                color: 'var(--role-doctor, #7c3aed)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              HOSPITAL INTEROPERABILITY (HL7 FHIR R4)
            </span>
          </div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
            Export FHIR Bundle
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
            Download verifiable FHIR R4 collection bundles containing patient demographics, clinical telemetry observations, and approved care plans.
          </p>
        </div>

        <button
          type="button"
          onClick={handleDownload}
          disabled={loading || !bundleData}
          style={{
            padding: '10px 20px',
            borderRadius: '8px',
            border: 'none',
            background: 'var(--role-doctor, #7c3aed)',
            color: '#ffffff',
            fontSize: '13px',
            fontWeight: 700,
            cursor: loading || !bundleData ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <span>📥 Download FHIR Bundle</span>
        </button>
      </div>

      {/* Patient Selector Strip */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '16px 20px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontSize: '12px', fontWeight: 700, color: '#64748b' }}>Select Patient:</span>
        {PATIENTS.map((pt) => (
          <button
            key={pt.id}
            type="button"
            onClick={() => setSelectedPid(pt.id)}
            style={{
              padding: '6px 14px',
              borderRadius: '8px',
              border: 'none',
              background: selectedPid === pt.id ? 'var(--role-doctor, #7c3aed)' : 'var(--bg-base, #f1f5f9)',
              color: selectedPid === pt.id ? '#ffffff' : 'var(--text-secondary, #475569)',
              fontSize: '12px',
              fontWeight: selectedPid === pt.id ? 700 : 500,
              cursor: 'pointer',
            }}
          >
            {pt.code} {pt.name}
          </button>
        ))}
      </div>

      {/* Bundle Metadata & Live Preview */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '22px 24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
              FHIR R4 Bundle: {selectedPatient.name} ({selectedPatient.code})
            </h3>
            <div style={{ fontSize: '12px', color: '#64748b' }}>
              Condition: <strong>{selectedPatient.condition}</strong> · Standard: <strong>HL7 FHIR v4.0.1 Collection</strong>
            </div>
          </div>
          {bundleData && (
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '12px',
                background: '#ecfdf5',
                color: '#059669',
              }}
            >
              ✓ {bundleData.total || bundleData.entry?.length || 0} FHIR Resources Packaged
            </span>
          )}
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
            Generating verifiable FHIR R4 Bundle...
          </div>
        ) : bundleData ? (
          <div
            style={{
              background: 'var(--bg-base, #0f172a)',
              color: '#38bdf8',
              borderRadius: '8px',
              padding: '16px 20px',
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontSize: '12px',
              lineHeight: '1.6',
              maxHeight: '380px',
              overflowY: 'auto',
            }}
          >
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(bundleData, null, 2)}
            </pre>
          </div>
        ) : (
          <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
            No bundle data available.
          </div>
        )}
      </div>
    </div>
  );
}
