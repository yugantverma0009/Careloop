import React, { useState, useEffect } from 'react';
import PatientIdentity from './PatientIdentity';
import {
  getStaffSummaries,
  generateClinicalSummary,
  approveClinicalSummary,
  rejectClinicalSummary,
  generateAllMineSummaries,
  getRuleProposals,
  approveRuleProposal,
  rejectRuleProposal,
} from '../services/api';

export default function ClinicalSummaries({ user = {}, onSelectPatient }) {
  const [summaries, setSummaries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'draft', 'approved', 'rejected'
  const [selectedSummary, setSelectedSummary] = useState(null);
  const [showSources, setShowSources] = useState(true);
  const [actionMsg, setActionMsg] = useState('');
  const [batchLoading, setBatchLoading] = useState(false);

  // Edit in place
  const [editedText, setEditedText] = useState('');

  // Reject modal
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // New draft patient selector
  const [newDraftPid, setNewDraftPid] = useState(1);
  const [generateLoading, setGenerateLoading] = useState(false);

  // Phase 3: Limit Proposals State
  const [approvalTab, setApprovalTab] = useState('summaries'); // 'summaries' or 'limits'
  const [proposals, setProposals] = useState([]);
  const [proposalsLoading, setProposalsLoading] = useState(false);
  const [rejectPropModalOpen, setRejectPropModalOpen] = useState(false);
  const [rejectPropId, setRejectPropId] = useState(null);
  const [rejectPropReason, setRejectPropReason] = useState('');

  const fetchProposals = async () => {
    setProposalsLoading(true);
    try {
      const data = await getRuleProposals();
      setProposals(data || []);
    } catch (err) {
      console.error('Failed to load rule proposals:', err);
    } finally {
      setProposalsLoading(false);
    }
  };

  const handleApproveProposal = async (historyId) => {
    try {
      await approveRuleProposal(historyId);
      setActionMsg('Limit change proposal approved and active threshold updated.');
      setTimeout(() => setActionMsg(''), 4000);
      await fetchProposals();
    } catch (err) {
      alert(`Approval failed: ${err.message || 'Error'}`);
    }
  };

  const handleRejectProposalSubmit = async (e) => {
    e.preventDefault();
    if (!rejectPropId || !rejectPropReason.trim() || rejectPropReason.trim().length < 3) return;
    try {
      await rejectRuleProposal(rejectPropId, rejectPropReason.trim());
      setRejectPropModalOpen(false);
      setRejectPropId(null);
      setRejectPropReason('');
      setActionMsg('Limit change proposal rejected with clinical reason.');
      setTimeout(() => setActionMsg(''), 4000);
      await fetchProposals();
    } catch (err) {
      alert(`Rejection failed: ${err.message || 'Error'}`);
    }
  };

  useEffect(() => {
    if (approvalTab === 'limits') {
      fetchProposals();
    }
  }, [approvalTab]);

  const fetchSummaries = async () => {
    setLoading(true);
    try {
      const data = await getStaffSummaries({ status: statusFilter });
      setSummaries(data || []);
      if (data && data.length > 0) {
        // preserve or set first
        if (!selectedSummary) {
          setSelectedSummary(data[0]);
          setEditedText(data[0].edited_text || data[0].summary_text || '');
        } else {
          const updated = data.find((s) => s.summary_id === selectedSummary.summary_id) || data[0];
          setSelectedSummary(updated);
          setEditedText(updated.edited_text || updated.summary_text || '');
        }
      } else {
        setSelectedSummary(null);
      }
    } catch (err) {
      console.error('Failed to load clinical summaries:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummaries();
  }, [statusFilter]);

  const handleSelectSummary = (s) => {
    setSelectedSummary(s);
    setEditedText(s.edited_text || s.summary_text || '');
  };

  const handleGenerateSingle = async () => {
    setGenerateLoading(true);
    try {
      const created = await generateClinicalSummary(newDraftPid);
      setActionMsg(`Draft summary created for Patient #${newDraftPid}.`);
      setTimeout(() => setActionMsg(''), 4000);
      await fetchSummaries();
    } catch (err) {
      alert(`Generation failed: ${err.message || 'Error'}`);
    } finally {
      setGenerateLoading(false);
    }
  };

  const handleBatchGenerate = async () => {
    setBatchLoading(true);
    try {
      const res = await generateAllMineSummaries();
      setActionMsg(`Generated ${res.generated_count || 0} fresh drafts for assigned patients.`);
      setTimeout(() => setActionMsg(''), 5000);
      await fetchSummaries();
    } catch (err) {
      alert(`Batch generation failed: ${err.message || 'Error'}`);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedSummary) return;
    try {
      await approveClinicalSummary(selectedSummary.summary_id, editedText);
      setActionMsg(`Summary #${selectedSummary.summary_id} approved.`);
      setTimeout(() => setActionMsg(''), 4000);
      await fetchSummaries();
    } catch (err) {
      alert(`Approve failed: ${err.message || 'Error'}`);
    }
  };

  const handleRejectSubmit = async (e) => {
    e.preventDefault();
    if (!selectedSummary || !rejectReason.trim() || rejectReason.trim().length < 3) return;
    try {
      await rejectClinicalSummary(selectedSummary.summary_id, rejectReason.trim());
      setRejectModalOpen(false);
      setRejectReason('');
      setActionMsg(`Summary #${selectedSummary.summary_id} rejected.`);
      setTimeout(() => setActionMsg(''), 4000);
      await fetchSummaries();
    } catch (err) {
      alert(`Reject failed: ${err.message || 'Error'}`);
    }
  };

  const isDoctor = user.role === 'Doctor';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Toast Alert */}
      {actionMsg && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            background: 'var(--accent-tint, #ecfdf5)',
            border: '1px solid var(--accent-subtle, #a7f3d0)',
            color: 'var(--accent-color, #059669)',
            fontSize: '13px',
            fontWeight: 700,
          }}
        >
          ✓ {actionMsg}
        </div>
      )}

      {/* Top Approvals Navigation Tabs (Phase 3) */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          borderBottom: '2px solid var(--border-subtle, #e2e8f0)',
          paddingBottom: '8px',
        }}
      >
        <button
          type="button"
          onClick={() => setApprovalTab('summaries')}
          style={{
            padding: '8px 18px',
            borderRadius: '8px',
            border: 'none',
            background: approvalTab === 'summaries' ? 'var(--role-doctor, #7c3aed)' : 'transparent',
            color: approvalTab === 'summaries' ? '#ffffff' : 'var(--text-secondary, #475569)',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>📄 AI Discharge Summaries</span>
          <span
            style={{
              fontSize: '11px',
              padding: '2px 7px',
              borderRadius: '10px',
              background: approvalTab === 'summaries' ? 'rgba(255,255,255,0.25)' : '#e2e8f0',
              color: approvalTab === 'summaries' ? '#ffffff' : '#475569',
              fontWeight: 800,
            }}
          >
            {summaries.filter((s) => s.status === 'Draft').length} drafts
          </span>
        </button>

        <button
          type="button"
          onClick={() => setApprovalTab('limits')}
          style={{
            padding: '8px 18px',
            borderRadius: '8px',
            border: 'none',
            background: approvalTab === 'limits' ? 'var(--role-doctor, #7c3aed)' : 'transparent',
            color: approvalTab === 'limits' ? '#ffffff' : 'var(--text-secondary, #475569)',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>🛡️ Rule Limit Proposals</span>
          <span
            style={{
              fontSize: '11px',
              padding: '2px 7px',
              borderRadius: '10px',
              background: approvalTab === 'limits' ? 'rgba(255,255,255,0.25)' : '#e2e8f0',
              color: approvalTab === 'limits' ? '#ffffff' : '#475569',
              fontWeight: 800,
            }}
          >
            {proposals.length} pending
          </span>
        </button>
      </div>

      {/* SECTION B: LIMIT PROPOSALS (Phase 3 Task 3) */}
      {approvalTab === 'limits' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              padding: '20px 24px',
              boxShadow: 'var(--shadow-card)',
            }}
          >
            <div style={{ marginBottom: '16px' }}>
              <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                Nurse-Proposed Rule Limit Adjustments ({proposals.length})
              </h3>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                Nurses may propose telemetry boundary changes based on clinical observation. Changes require attending physician approval to take effect.
              </p>
            </div>

            {proposals.length === 0 ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                ✓ No pending rule limit change proposals from nursing staff.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {proposals.map((pr) => {
                  const ov = pr.old_values || {};
                  const nv = pr.new_values || {};
                  return (
                    <div
                      key={pr.history_id}
                      style={{
                        border: '1px solid var(--border-subtle, #e2e8f0)',
                        borderLeft: '4px solid #d97706',
                        borderRadius: '8px',
                        padding: '16px 20px',
                        background: 'var(--bg-surface, #ffffff)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <span style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                              {pr.patient_name}
                            </span>
                            <span style={{ fontSize: '11px', color: '#64748b' }}>
                              {pr.patient_age} y · {pr.patient_code}
                            </span>
                            <span style={{ fontSize: '11px', padding: '1px 7px', borderRadius: '4px', background: 'var(--bg-base, #f1f5f9)', color: '#475569', fontWeight: 600 }}>
                              {pr.condition_summary || 'Post-Op'}
                            </span>
                          </div>
                          <div style={{ fontSize: '13px', fontWeight: 700, color: '#b45309' }}>
                            Metric: {pr.rule_type} {pr.measurement_type ? `(${pr.measurement_type})` : ''}
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{ textAlign: 'right', fontSize: '12px' }}>
                            <div style={{ color: '#64748b' }}>Current limit: <strong>{ov.threshold_value}</strong></div>
                            <div style={{ color: '#047857', fontWeight: 700 }}>Proposed limit: <strong>{nv.threshold_value}</strong></div>
                          </div>
                        </div>
                      </div>

                      <div style={{ padding: '10px 14px', borderRadius: '6px', background: 'var(--bg-base, #f8fafc)', border: '1px solid var(--border-subtle, #f1f5f9)', fontSize: '12px', color: '#334155' }}>
                        <strong>Clinical Justification:</strong> &ldquo;{pr.change_reason}&rdquo;
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                          Proposed by: <strong>{pr.proposed_by_name} ({pr.proposed_by_role})</strong> on {new Date(pr.changed_at).toLocaleString()}
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '4px' }}>
                        <button
                          type="button"
                          onClick={() => {
                            setRejectPropId(pr.history_id);
                            setRejectPropModalOpen(true);
                          }}
                          style={{
                            padding: '7px 14px',
                            borderRadius: '6px',
                            border: '1px solid #fca5a5',
                            background: '#fef2f2',
                            color: '#b91c1c',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          onClick={() => handleApproveProposal(pr.history_id)}
                          style={{
                            padding: '7px 18px',
                            borderRadius: '6px',
                            border: 'none',
                            background: 'var(--role-doctor, #7c3aed)',
                            color: '#ffffff',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Approve limit
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Reject Limit Proposal Modal */}
          {rejectPropModalOpen && (
            <div className="modal-overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ background: 'var(--bg-surface, #ffffff)', borderRadius: '12px', padding: '24px', maxWidth: '440px', width: '100%', boxShadow: 'var(--shadow-lg)' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 10px 0', color: '#ef4444' }}>
                  Reject Limit Change Proposal
                </h3>
                <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 14px 0' }}>
                  Please state the clinical justification for rejecting the nurse-proposed threshold modification.
                </p>
                <form onSubmit={handleRejectProposalSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <textarea
                    rows={3}
                    required
                    placeholder="e.g. Current threshold remains clinically indicated for post-CABG arrhythmia monitoring"
                    value={rejectPropReason}
                    onChange={(e) => setRejectPropReason(e.target.value)}
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '12px' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setRejectPropModalOpen(false);
                        setRejectPropId(null);
                      }}
                      style={{ padding: '7px 14px', borderRadius: '6px', border: '1px solid #cbd5e1', background: 'transparent', fontSize: '12px', cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!rejectPropReason.trim() || rejectPropReason.trim().length < 3}
                      style={{ padding: '7px 16px', borderRadius: '6px', border: 'none', background: '#ef4444', color: '#ffffff', fontSize: '12px', fontWeight: 700, cursor: 'pointer' }}
                    >
                      Confirm Rejection
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SECTION A: AI DISCHARGE SUMMARIES */}
      {approvalTab === 'summaries' && (
      <>
      {/* Top Action Bar */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '16px 20px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '14px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {/* Status filter chips */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {[
            { id: 'all', label: 'All summaries' },
            { id: 'draft', label: 'Drafts to review' },
            { id: 'approved', label: 'Approved' },
            { id: 'rejected', label: 'Rejected' },
          ].map((st) => (
            <button
              key={st.id}
              type="button"
              onClick={() => setStatusFilter(st.id)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: 'none',
                background: statusFilter === st.id ? '#0284c7' : 'var(--bg-base, #f1f5f9)',
                color: statusFilter === st.id ? '#ffffff' : 'var(--text-secondary, #475569)',
                fontWeight: statusFilter === st.id ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              {st.label}
            </button>
          ))}
        </div>

        {/* Generate actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <select
              value={newDraftPid}
              onChange={(e) => setNewDraftPid(Number(e.target.value))}
              style={{
                padding: '6px 10px',
                borderRadius: '8px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: 'var(--bg-base, #ffffff)',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((id) => (
                <option key={id} value={id}>
                  Patient #{id} (CL-0000{id})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleGenerateSingle}
              disabled={generateLoading}
              style={{
                padding: '7px 12px',
                borderRadius: '8px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: 'transparent',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {generateLoading ? 'Generating...' : '+ Create Draft'}
            </button>
          </div>

          <button
            type="button"
            onClick={handleBatchGenerate}
            disabled={batchLoading}
            style={{
              padding: '7px 14px',
              borderRadius: '8px',
              border: 'none',
              background: '#0f172a',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {batchLoading ? 'Generating...' : '⚡ Generate Drafts for My Patients'}
          </button>
        </div>
      </div>

      {/* Main 2-Column Review Interface */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '20px', alignItems: 'start' }}>
        {/* Left Column: List of Summaries */}
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '12px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxHeight: '800px',
            overflowY: 'auto',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '13px', fontWeight: 800, color: '#64748b', marginBottom: '4px' }}>
            SUMMARIES QUEUE ({summaries.length})
          </div>
          {loading ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: '12px' }}>
              Loading summaries...
            </div>
          ) : summaries.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: '12px' }}>
              No summaries found.
            </div>
          ) : (
            summaries.map((s) => {
              const isSelected = selectedSummary?.summary_id === s.summary_id;
              return (
                <div
                  key={s.summary_id}
                  onClick={() => handleSelectSummary(s)}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    border: isSelected ? '2px solid #0284c7' : '1px solid var(--border-subtle, #e2e8f0)',
                    background: isSelected ? '#f0f9ff' : 'var(--bg-base, #f8fafc)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontWeight: 800, fontSize: '12px', color: '#0284c7' }}>
                      {s.patient_code}
                    </span>
                    <span
                      className={`status-pill ${
                        s.status === 'Approved'
                          ? 'status-pill-green'
                          : s.status === 'Rejected'
                          ? 'status-pill-red'
                          : 'status-pill-amber'
                      }`}
                      style={{ fontSize: '10px', padding: '2px 6px' }}
                    >
                      {s.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    {s.patient_name}
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                    {s.primary_diagnosis || 'Recovery'}
                  </div>
                  <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '4px' }}>
                    Generated: {s.generated_at ? s.generated_at.slice(0, 16).replace('T', ' ') : 'Today'}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Review & Approval Workplace */}
        {selectedSummary ? (
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              boxShadow: 'var(--shadow-card)',
            }}
          >
            {/* Summary Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', paddingBottom: '16px' }}>
              <div>
                <PatientIdentity
                  patientCode={selectedSummary.patient_code}
                  fullName={selectedSummary.patient_name}
                  ageYears={selectedSummary.age_years}
                  onClick={() => onSelectPatient && onSelectPatient(selectedSummary.patient_id)}
                />
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                  Diagnosis: <strong>{selectedSummary.primary_diagnosis}</strong> · Period: {selectedSummary.period_start?.slice(0, 10)} · Model: <code>{selectedSummary.model_name}</code>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span
                  style={{
                    display: 'inline-block',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 700,
                    background:
                      selectedSummary.status === 'Approved'
                        ? '#ecfdf5'
                        : selectedSummary.status === 'Rejected'
                        ? '#fef2f2'
                        : '#fffbeb',
                    color:
                      selectedSummary.status === 'Approved'
                        ? '#059669'
                        : selectedSummary.status === 'Rejected'
                        ? '#ef4444'
                        : '#d97706',
                    border: `1px solid ${
                      selectedSummary.status === 'Approved'
                        ? '#a7f3d0'
                        : selectedSummary.status === 'Rejected'
                        ? '#fecaca'
                        : '#fde68a'
                    }`,
                  }}
                >
                  {selectedSummary.status_label}
                </span>
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                  Summary ID #{selectedSummary.summary_id}
                </div>
              </div>
            </div>

            {/* SBAR Structured Content Display */}
            {selectedSummary.parsed_sbar ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px', borderLeft: '4px solid #0284c7' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: '#0284c7', textTransform: 'uppercase', marginBottom: '4px' }}>
                    SITUATION
                  </div>
                  <div style={{ fontSize: '13px', lineHeight: '1.5', color: 'var(--text-primary, #0f172a)' }}>
                    {selectedSummary.parsed_sbar.situation}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px', borderLeft: '4px solid #6366f1' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: '#6366f1', textTransform: 'uppercase', marginBottom: '4px' }}>
                    BACKGROUND
                  </div>
                  <div style={{ fontSize: '13px', lineHeight: '1.5', color: 'var(--text-primary, #0f172a)' }}>
                    {selectedSummary.parsed_sbar.background}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px', borderLeft: '4px solid #059669' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: '#059669', textTransform: 'uppercase', marginBottom: '6px' }}>
                    ASSESSMENT FACTS
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', lineHeight: '1.6', color: 'var(--text-primary, #0f172a)' }}>
                    {(Array.isArray(selectedSummary.parsed_sbar.assessment_facts)
                      ? selectedSummary.parsed_sbar.assessment_facts
                      : [selectedSummary.parsed_sbar.assessment_facts]
                    ).map((fact, i) => (
                      <li key={i}>{fact}</li>
                    ))}
                  </ul>
                </div>

                <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px', borderLeft: '4px solid #f59e0b' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: '#f59e0b', textTransform: 'uppercase', marginBottom: '6px' }}>
                    ITEMS FOR CLINICAL REVIEW
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', lineHeight: '1.6', color: 'var(--text-primary, #0f172a)' }}>
                    {(Array.isArray(selectedSummary.parsed_sbar.items_for_review)
                      ? selectedSummary.parsed_sbar.items_for_review
                      : [selectedSummary.parsed_sbar.items_for_review]
                    ).map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '16px', borderRadius: '8px', fontSize: '13px', lineHeight: '1.6' }}>
                {selectedSummary.summary_text}
              </div>
            )}

            {/* In-Place Clinician Editing */}
            {selectedSummary.status === 'Draft' && (
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px', color: '#475569' }}>
                  Clinician Edits (Optional refinements prior to approval)
                </label>
                <textarea
                  rows={4}
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  placeholder="Review or refine summary text before doctor sign-off..."
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                    lineHeight: '1.5',
                  }}
                />
              </div>
            )}

            {/* Doctor Actions */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle, #e2e8f0)', paddingTop: '16px' }}>
              <button
                type="button"
                onClick={() => setShowSources(!showSources)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  background: 'transparent',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {showSources ? 'Hide Source Facts' : 'View Source Facts Snapshot'}
              </button>

              <div style={{ display: 'flex', gap: '10px' }}>
                {selectedSummary.status === 'Draft' ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setRejectModalOpen(true)}
                      disabled={!isDoctor}
                      title={!isDoctor ? 'Only doctors can reject clinical summaries' : ''}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '8px',
                        border: '1px solid #ef4444',
                        background: '#fef2f2',
                        color: '#ef4444',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: isDoctor ? 'pointer' : 'not-allowed',
                        opacity: isDoctor ? 1 : 0.6,
                      }}
                    >
                      Reject Summary
                    </button>
                    <button
                      type="button"
                      onClick={handleApprove}
                      disabled={!isDoctor}
                      title={!isDoctor ? 'Only doctors can approve clinical summaries' : ''}
                      style={{
                        padding: '8px 18px',
                        borderRadius: '8px',
                        border: 'none',
                        background: '#059669',
                        color: '#ffffff',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: isDoctor ? 'pointer' : 'not-allowed',
                        opacity: isDoctor ? 1 : 0.6,
                      }}
                    >
                      ✓ Approve as Doctor
                    </button>
                  </>
                ) : (
                  <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>
                    {selectedSummary.status === 'Approved' ? 'Locked & Approved for Medical Record' : 'Summary Rejected'}
                  </div>
                )}
              </div>
            </div>

            {/* Sources Panel Drawer */}
            {showSources && selectedSummary.source_snapshot && (
              <div
                style={{
                  background: 'var(--bg-base, #f8fafc)',
                  border: '1px dashed var(--border-strong, #cbd5e1)',
                  borderRadius: '8px',
                  padding: '16px',
                  fontSize: '12px',
                }}
              >
                <div style={{ fontWeight: 800, fontSize: '12px', color: '#475569', marginBottom: '8px' }}>
                  DETERMINISTIC FACT SHEET SNAPSHOT (No Patient Names Sent to AI Engine)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                  <div>
                    <span style={{ color: '#64748b' }}>Post-Discharge Day:</span>{' '}
                    <strong>Day {selectedSummary.source_snapshot.day_number}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b' }}>Discharge Date:</span>{' '}
                    <strong>{selectedSummary.source_snapshot.discharge_date}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b' }}>Active Prescriptions:</span>{' '}
                    <strong>{selectedSummary.source_snapshot.total_medications_scheduled} medications</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b' }}>Adherence Recorded:</span>{' '}
                    <strong>
                      {selectedSummary.source_snapshot.total_doses_taken} taken,{' '}
                      {selectedSummary.source_snapshot.total_doses_skipped} skipped,{' '}
                      {selectedSummary.source_snapshot.total_doses_unconfirmed} unconfirmed
                    </strong>
                  </div>
                </div>

                {/* Latest readings with quality badges */}
                {selectedSummary.source_snapshot.latest_readings?.length > 0 && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ fontWeight: 700, color: '#64748b', marginBottom: '4px' }}>Latest Vitals:</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {selectedSummary.source_snapshot.latest_readings.map((r, i) => (
                        <div
                          key={i}
                          style={{
                            padding: '4px 8px',
                            borderRadius: '6px',
                            background: '#ffffff',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            fontSize: '11px',
                          }}
                        >
                          <strong>{r.measurement_type}</strong>: {r.value} {r.unit} ·{' '}
                          <span style={{ color: r.quality_status === 'Good' ? '#059669' : '#d97706', fontWeight: 600 }}>
                            {r.quality_status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
            Select a summary from the queue on the left to review.
          </div>
        )}
      </div>

      {/* REJECT MODAL (Doctor Mandatory Reason) */}
      {rejectModalOpen && selectedSummary && (
        <div className="modal-overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '440px',
              width: '100%',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 12px 0', color: '#ef4444' }}>
              Reject Summary #{selectedSummary.summary_id}
            </h3>
            <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 16px 0' }}>
              Please specify the clinical reason for rejection. This reason will be logged in the permanent audit trail.
            </p>
            <form onSubmit={handleRejectSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Rejection Reason *
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="e.g. Incomplete medication adherence data, please regenerate with evening logs"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setRejectModalOpen(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'transparent',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!rejectReason.trim() || rejectReason.trim().length < 3}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#ef4444',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Confirm Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}
