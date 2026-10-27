import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Loader2 } from 'lucide-react';
import toast, { Toaster } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { getAllPatients, admitPatient, getPatientPipelineStatus } from '../services/api';
import { AgenticLogo } from '../App';

const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons+Round');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, #root { height: 100%; }

    :root {
      --teal:         var(--accent);
      --teal-dark:    var(--accent-dark);
      --teal-light:   var(--accent);
      --teal-pale:    var(--accent-dim);
      --teal-glow:    var(--accent-glow);
      --navy:         var(--text-1);
      --navy-mid:     var(--text-2);
      --slate:        var(--text-2);
      --muted:        var(--text-3);
      --bg:           var(--bg-base);
      --bg-white:     var(--bg-surface);
      --bg-card:      var(--bg-surface);
      --accent:       var(--accent);
      --green:        var(--green);
      --green-pale:   var(--green-dim);
      --amber:        var(--amber);
      --amber-pale:   var(--amber-dim);
      --red:          var(--red-alert);
      --red-pale:     var(--red-dim);
      --border:       var(--border);
      --border-bright:var(--border-bright);
      --shadow:       var(--shadow);
      --shadow-md:    var(--shadow-card);
      --shadow-lg:    var(--shadow-lg);
      --shadow-accent:var(--shadow-accent);
    }

    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--navy);
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }

    .font-display { font-family: 'Outfit', sans-serif; }
    .font-mono    { font-family: 'JetBrains Mono', monospace; }

    @keyframes pageIn {
      from { opacity: 0; transform: translateY(22px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(16px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes spin   { to { transform: rotate(360deg); } }
    @keyframes pulse  { 0%,100%{ opacity:1; transform:scale(1); } 50%{ opacity:.55; transform:scale(1.35); } }
    @keyframes shimmer {
      from { background-position: -600px 0; }
      to   { background-position:  600px 0; }
    }

    .page-in   { animation: pageIn  .55s cubic-bezier(.22,1,.36,1) both; }
    .fade-up-1 { animation: fadeUp  .5s  cubic-bezier(.22,1,.36,1) .06s  both; }
    .fade-up-2 { animation: fadeUp  .5s  cubic-bezier(.22,1,.36,1) .14s  both; }
    .fade-up-3 { animation: fadeUp  .5s  cubic-bezier(.22,1,.36,1) .22s  both; }
    .fade-up-4 { animation: fadeUp  .5s  cubic-bezier(.22,1,.36,1) .30s  both; }

    .card-grid > * { animation: fadeUp .45s cubic-bezier(.22,1,.36,1) both; }
    .card-grid > *:nth-child(1)   { animation-delay: .10s; }
    .card-grid > *:nth-child(2)   { animation-delay: .17s; }
    .card-grid > *:nth-child(3)   { animation-delay: .24s; }
    .card-grid > *:nth-child(4)   { animation-delay: .31s; }
    .card-grid > *:nth-child(5)   { animation-delay: .38s; }
    .card-grid > *:nth-child(6)   { animation-delay: .45s; }
    .card-grid > *:nth-child(n+7) { animation-delay: .45s; }

    .skeleton {
      background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 75%);
      background-size: 600px 100%;
      animation: shimmer 1.5s ease infinite;
      border-radius: 20px;
      border: 1px solid var(--border);
    }

    .btn-primary {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 11px 24px; border-radius: 50px;
      background: linear-gradient(135deg, var(--teal) 0%, var(--teal-dark) 100%);
      color: #07090F;
      font-family: 'Inter', sans-serif; font-weight: 700; font-size: 14px;
      border: none; cursor: pointer;
      box-shadow: 0 4px 18px rgba(0, 212, 170, 0.25);
      transition: all .2s;
    }
    .btn-primary:hover   { transform: translateY(-2px); box-shadow: 0 8px 28px rgba(0, 212, 170, 0.4); filter: brightness(1.08); }
    .btn-primary:disabled { opacity: .5; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

    .btn-ghost {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 8px 18px; border-radius: 50px;
      background: rgba(255,255,255,0.04); color: var(--slate);
      font-family: 'Inter', sans-serif; font-weight: 600; font-size: 13px;
      border: 1px solid var(--border); cursor: pointer;
      transition: all .2s;
    }
    .btn-ghost:hover { border-color: var(--teal); color: var(--teal); background: var(--teal-pale); }

    .section-label {
      display: inline-block;
      font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600;
      letter-spacing: 2px; text-transform: uppercase;
      color: var(--teal); padding: 4px 14px;
      background: var(--teal-pale); border-radius: 50px; margin-bottom: 12px;
      border: 1px solid rgba(0, 212, 170, 0.25);
    }

    input[type="file"] { display: none; }
    .drop-active { border-color: var(--teal) !important; background: var(--teal-pale) !important; box-shadow: 0 0 20px var(--teal-glow) !important; }

    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--teal); }
  `}</style>
);

const useActivationPoller = (patientId, onActivated) => {
  const intervalRef = useRef(null);
  useEffect(() => {
    if (!patientId) return;
    let attempts = 0;
    intervalRef.current = setInterval(async () => {
      attempts++;
      try {
        const s = await getPatientPipelineStatus(patientId);
        if (s.monitoring_active) { clearInterval(intervalRef.current); onActivated(patientId, s); }
      } catch { /* ignore */ }
      if (attempts >= 40) clearInterval(intervalRef.current);
    }, 3000);
    return () => clearInterval(intervalRef.current);
  }, [patientId, onActivated]);
};

const StatusBadge = ({ status }) => {
  const map = {
    Active:     { bg: 'var(--green-pale)', color: 'var(--green)', icon: 'favorite' },
    Pending:    { bg: 'var(--amber-pale)', color: 'var(--amber)', icon: 'hourglass_top' },
    Critical:   { bg: 'var(--red-pale)',   color: 'var(--red)',   icon: 'crisis_alert' },
    Discharged: { bg: '#EEF2FF',           color: '#6366F1',      icon: 'check_circle' },
  };
  const s = map[status] || map.Pending;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 11px', borderRadius: 50,
      background: s.bg, color: s.color,
      fontFamily: "'DM Mono',monospace", fontSize: 9,
      fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase',
    }}>
      <span className="material-icons-round" style={{ fontSize: 11 }}>{s.icon}</span>
      {status}
    </span>
  );
};

const PipelineRow = ({ ready, label, readyLabel, pendingLabel }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <div style={{
      width: 26, height: 26, borderRadius: 7, flexShrink: 0,
      background: ready ? 'var(--green-pale)' : 'var(--teal-pale)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {ready
        ? <span className="material-icons-round" style={{ fontSize: 14, color: 'var(--green)' }}>check_circle</span>
        : <Loader2 size={13} style={{ color: 'var(--teal)', animation: 'spin 1.1s linear infinite' }} />
      }
    </div>
    <span style={{ fontSize: 12.5, fontWeight: 500, color: ready ? 'var(--navy)' : 'var(--muted)' }}>
      {label} —{' '}
      <span style={{ color: ready ? 'var(--green)' : 'var(--muted)' }}>
        {ready ? readyLabel : pendingLabel}
      </span>
    </span>
  </div>
);

const StatCard = ({ label, value, icon, accent }) => (
  <div style={{
    background: 'var(--bg-card)', borderRadius: 20,
    border: '1px solid var(--border)', padding: '24px 26px',
    display: 'flex', alignItems: 'center', gap: 16,
    boxShadow: 'var(--shadow)',
    transition: 'all .25s ease',
  }}
    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.borderColor = 'var(--border-bright)'; e.currentTarget.style.boxShadow = 'var(--shadow-md)'; }}
    onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'var(--shadow)'; }}
  >
    <div style={{
      width: 52, height: 52, borderRadius: 14, flexShrink: 0,
      background: `${accent}18`,
      border: `1px solid ${accent}30`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <span className="material-icons-round" style={{ fontSize: 26, color: accent }}>{icon}</span>
    </div>
    <div>
      <div className="font-display" style={{
        fontSize: 36, fontWeight: 800, color: accent, lineHeight: 1, letterSpacing: '-0.5px'
      }}>{value}</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--slate)', marginTop: 6, letterSpacing: .5 }}>
        {label}
      </div>
    </div>
  </div>
);

const DropZone = ({ file, onFile }) => {
  const inputRef = useRef(null);
  const zoneRef  = useRef(null);
  const handleDrop = e => {
    e.preventDefault();
    zoneRef.current?.classList.remove('drop-active');
    const f = e.dataTransfer.files?.[0];
    if (f?.type === 'application/pdf') onFile(f);
    else toast.error('Only PDF files are accepted.');
  };
  return (
    <div ref={zoneRef}
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); zoneRef.current?.classList.add('drop-active'); }}
      onDragLeave={() => zoneRef.current?.classList.remove('drop-active')}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${file ? 'var(--teal)' : 'var(--border-bright)'}`,
        borderRadius: 14, padding: '13px 18px', cursor: 'pointer',
        background: file ? 'var(--teal-pale)' : 'rgba(255,255,255,0.02)',
        display: 'flex', alignItems: 'center', gap: 12, minWidth: 260,
        transition: 'all .2s',
      }}>
      <input ref={inputRef} type="file" accept=".pdf" onChange={e => onFile(e.target.files?.[0] ?? null)} />
      <div style={{
        width: 36, height: 36, borderRadius: 10, flexShrink: 0,
        background: file ? 'var(--teal-pale)' : 'rgba(255,255,255,0.05)',
        border: `1px solid ${file ? 'rgba(0,212,170,0.3)' : 'var(--border)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span className="material-icons-round" style={{ fontSize: 18, color: file ? 'var(--teal)' : 'var(--muted)' }}>
          {file ? 'description' : 'upload_file'}
        </span>
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{
          fontSize: 13, fontWeight: 600, color: file ? 'var(--teal)' : 'var(--navy)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 200,
        }}>
          {file ? file.name : 'Drop discharge PDF here'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
          {file ? `${(file.size / 1024).toFixed(1)} KB · PDF` : 'or click to browse'}
        </div>
      </div>
      {file && (
        <button onClick={e => { e.stopPropagation(); onFile(null); }}
          style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', padding: 4, flexShrink: 0, lineHeight: 0 }}>
          <span className="material-icons-round" style={{ fontSize: 17 }}>close</span>
        </button>
      )}
    </div>
  );
};

const accentFor = status => ({ Active: 'var(--green)', Pending: 'var(--amber)', Critical: 'var(--red)', Discharged: '#8B5CF6' }[status] || 'var(--teal)');

const PatientCard = ({ patient, onClick }) => {
  const status     = patient.status || 'Pending';
  const isPending  = status === 'Pending';
  const isCritical = status === 'Critical';
  const accent     = accentFor(status);
  const initials   = (patient.name || 'UN').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <div onClick={() => !isPending && onClick(patient.patient_id)}
      style={{
        background: 'var(--bg-white)', borderRadius: 20, overflow: 'hidden',
        border: `1px solid ${isCritical ? 'rgba(255,68,68,0.4)' : 'var(--border)'}`,
        boxShadow: isCritical ? '0 0 20px rgba(255,68,68,0.15), var(--shadow)' : 'var(--shadow)',
        display: 'flex', flexDirection: 'column',
        cursor: isPending ? 'default' : 'pointer',
        opacity: isPending ? .88 : 1,
        transition: 'all .25s ease',
      }}
      onMouseEnter={e => {
        if (isPending) return;
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.borderColor = isCritical ? 'rgba(255,68,68,0.6)' : 'rgba(0,212,170,0.3)';
        e.currentTarget.style.boxShadow = isCritical ? '0 0 24px rgba(255,68,68,0.25), var(--shadow-md)' : 'var(--shadow-md)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = '';
        e.currentTarget.style.borderColor = isCritical ? 'rgba(255,68,68,0.4)' : 'var(--border)';
        e.currentTarget.style.boxShadow = isCritical ? '0 0 20px rgba(255,68,68,0.15), var(--shadow)' : 'var(--shadow)';
      }}
    >
      <div style={{ height: 4, background: accent }} />

      <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 12, flexShrink: 0,
              background: `${accent}18`,
              border: `1px solid ${accent}30`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'JetBrains Mono',monospace", fontSize: 14, fontWeight: 700, color: accent,
            }}>
              {initials}
            </div>
            <div>
              <h3 className="font-display" style={{
                fontSize: 17, fontWeight: 700, color: 'var(--navy)', lineHeight: 1.2,
              }}>
                {patient.name || 'Unknown Patient'}
              </h3>
              <span className="font-mono" style={{
                fontSize: 11, color: 'var(--muted)', marginTop: 3, display: 'block', letterSpacing: .5,
              }}>
                {patient.patient_id}
              </span>
            </div>
          </div>
          <StatusBadge status={status} />
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: 'var(--border)' }} />

        {/* Pipeline */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <PipelineRow ready={patient.kb_initialized}    label="Knowledge Base" readyLabel="Indexed"  pendingLabel="Building…"   />
          <PipelineRow ready={patient.monitoring_active} label="AI Monitoring"  readyLabel="Active"   pendingLabel="Activating…" />
        </div>

        {/* Banners */}
        {isPending && (
          <div style={{
            marginTop: 'auto', padding: '10px 14px', borderRadius: 12,
            background: 'var(--amber-pale)', border: '1px solid rgba(245,158,11,0.25)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <span className="material-icons-round" style={{ color: 'var(--amber)', fontSize: 16 }}>memory</span>
            <p style={{ fontSize: 12, color: '#FCD34D', fontWeight: 600, lineHeight: 1.4 }}>
              Agent activating — building knowledge base…
            </p>
          </div>
        )}

        {isCritical && (
          <div style={{
            marginTop: 'auto', padding: '10px 14px', borderRadius: 12,
            background: 'var(--red-pale)', border: '1px solid rgba(255,68,68,0.3)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <span className="material-icons-round" style={{ color: 'var(--red)', fontSize: 16, animation: 'pulse 1.8s ease infinite' }}>crisis_alert</span>
            <p style={{ fontSize: 12, color: 'var(--red)', fontWeight: 700, letterSpacing: .5 }}>
              ESCALATION REQUIRED — Open now
            </p>
          </div>
        )}

        {!isPending && !isCritical && (
          <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 5, color: 'var(--teal)' }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>Open patient dashboard</span>
            <span className="material-icons-round" style={{ fontSize: 13 }}>arrow_forward</span>
          </div>
        )}
      </div>
    </div>
  );
};

const Navbar = ({ patientCount }) => (
  <nav style={{
    position: 'sticky', top: 0, zIndex: 100,
    background: 'rgba(7, 9, 15, 0.85)', backdropFilter: 'blur(16px)',
    borderBottom: '1px solid var(--border)',
    padding: '0 5%', display: 'flex', alignItems: 'center', height: 64, gap: 16,
  }}>
    <a href="/" style={{ display: 'flex', alignItems: 'center', textDecoration: 'none', flexShrink: 0 }}>
      <AgenticLogo className="h-9" />
    </a>

    <div style={{
      padding: '4px 12px', borderRadius: 50,
      background: 'var(--teal-pale)', border: '1px solid rgba(0,212,170,0.25)',
      display: 'flex', alignItems: 'center', gap: 6,
    }}>
      <span className="material-icons-round" style={{ fontSize: 13, color: 'var(--teal)' }}>local_hospital</span>
      <span className="font-mono" style={{
        fontSize: 10, fontWeight: 600,
        color: 'var(--teal)', letterSpacing: 1.2, textTransform: 'uppercase',
      }}>Nurse Station</span>
    </div>

    <div style={{ flex: 1 }} />

    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: 'var(--green)',
        display: 'block', animation: 'pulse 2s ease infinite',
      }} />
      <span style={{ fontSize: 12, color: 'var(--slate)', fontWeight: 500 }}>
        {patientCount} patient{patientCount !== 1 ? 's' : ''} monitored
      </span>
    </div>

    <button className="btn-ghost" onClick={() => { sessionStorage.clear(); window.location.href = '/'; }}>
      <span className="material-icons-round" style={{ fontSize: 15 }}>logout</span>
      Sign out
    </button>
  </nav>
);


const NurseDashboard = () => {
  const [patients,     setPatients]     = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [uploading,    setUploading]    = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [activatingId, setActivatingId] = useState(null);
  const navigate = useNavigate();

  const fetchPatients = useCallback(async () => {
    try {
      setError(null);
      const data = await getAllPatients();
      if (!Array.isArray(data)) throw new Error('Invalid response');
      setPatients(data);
    } catch {
      setError('Failed to reach the backend. Check that the server is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPatients();
    const iv = setInterval(fetchPatients, 5000);
    return () => clearInterval(iv);
  }, [fetchPatients]);

  const handleActivated = useCallback((patientId) => {
    toast.success(`AI Agent live for patient ${patientId}`, { duration: 5000 });
    setActivatingId(null);
    fetchPatients();
  }, [fetchPatients]);

  useActivationPoller(activatingId, handleActivated);

  const handleAdmit = async () => {
    if (!selectedFile) return;
    setUploading(true);
    const tid = toast.loading('Uploading & parsing discharge summary…');
    try {
      const data = await admitPatient(selectedFile);
      if (data.status === 'error') throw new Error(data.message);
      toast.success(`Patient admitted (${data.patient_id || '?'}). AI activating…`, { id: tid, duration: 6000 });
      setSelectedFile(null);
      if (data.patient_id) setActivatingId(data.patient_id);
      await fetchPatients();
    } catch (err) {
      toast.error(`Admission failed: ${err.message}`, { id: tid });
    } finally {
      setUploading(false);
    }
  };

  const activeCount   = patients.filter(p => p.status === 'Active').length;
  const pendingCount  = patients.filter(p => p.status === 'Pending').length;
  const criticalCount = patients.filter(p => p.status === 'Critical').length;

  return (
    <>
      <GlobalStyles />
      <Toaster position="top-right" toastOptions={{
        style: {
          fontFamily: "'Inter',sans-serif", borderRadius: 12, fontSize: 13,
          background: 'var(--bg-elevated)', color: 'var(--navy)',
          boxShadow: '0 8px 32px rgba(0,0,0,.6)', border: '1px solid var(--border)',
        },
      }} />

      <div style={{ minHeight: '100vh', background: 'var(--bg)', paddingBottom: 72 }}>

        <Navbar patientCount={patients.length} />

        <div style={{ maxWidth: 1180, margin: '0 auto', padding: '40px 5% 0' }}>

          {/* ── Page header ── */}
          <div className="page-in" style={{ marginBottom: 36 }}>
            <span className="section-label">Ward Management</span>
            <h1 className="font-display" style={{
              fontSize: 'clamp(28px,3.5vw,44px)', fontWeight: 800,
              color: 'var(--navy)', lineHeight: 1.15, marginBottom: 10, letterSpacing: '-0.5px'
            }}>
              Ward Monitoring
            </h1>
            <p style={{ fontSize: 15, color: 'var(--slate)', maxWidth: 500, lineHeight: 1.65 }}>
              Admit patients via discharge PDF, track AI agent activation in real time,
              and monitor every recovery from a single view.
            </p>
          </div>

          <div className="fade-up-2" style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 16, marginBottom: 28,
          }}>
            <StatCard label="Active Patients"    value={activeCount}   icon="favorite"      accent="var(--green)" />
            <StatCard label="Pending Activation" value={pendingCount}  icon="hourglass_top" accent="var(--amber)" />
            <StatCard label="Critical Alerts"    value={criticalCount} icon="crisis_alert"  accent="var(--red)"   />
          </div>

          <div className="fade-up-3" style={{
            background: 'var(--bg-white)', borderRadius: 22,
            border: '1px solid var(--border)', boxShadow: 'var(--shadow)',
            padding: '26px 32px', marginBottom: 36,
          }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 14, background: 'var(--teal-pale)',
                  border: '1px solid rgba(0,212,170,0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <span className="material-icons-round" style={{ color: 'var(--teal)', fontSize: 24 }}>upload_file</span>
                </div>
                <div>
                  <h2 className="font-display" style={{
                    fontSize: 18, fontWeight: 700, color: 'var(--navy)',
                  }}>Admit New Patient</h2>
                  <p style={{ fontSize: 13, color: 'var(--slate)', marginTop: 3, maxWidth: 420 }}>
                    Upload a discharge PDF — NurseAI parses it, indexes the knowledge base, and activates monitoring automatically.
                  </p>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <DropZone file={selectedFile} onFile={setSelectedFile} />
                <button className="btn-primary" onClick={handleAdmit} disabled={!selectedFile || uploading}>
                  {uploading
                    ? <><Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> Analysing…</>
                    : <><span className="material-icons-round" style={{ fontSize: 17 }}>person_add</span> Admit Patient</>
                  }
                </button>
              </div>
            </div>
          </div>

          <div className="fade-up-4">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <h2 className="font-display" style={{
                fontSize: 22, fontWeight: 700, color: 'var(--navy)',
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                Admitted Patients
                {patients.length > 0 && (
                  <span className="font-mono" style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 500 }}>
                    {patients.length} total
                  </span>
                )}
              </h2>
              <button className="btn-ghost" onClick={fetchPatients}>
                <span className="material-icons-round" style={{ fontSize: 15 }}>refresh</span>
                Refresh
              </button>
            </div>

            {loading && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 20 }}>
                {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 230 }} />)}
              </div>
            )}

            {!loading && error && (
              <div style={{
                background: 'var(--bg-white)', border: '1px solid rgba(255,68,68,.3)',
                borderRadius: 22, padding: '56px 32px', textAlign: 'center',
              }}>
                <span className="material-icons-round" style={{ fontSize: 52, color: 'var(--red)', display: 'block', marginBottom: 16 }}>wifi_off</span>
                <h3 className="font-display" style={{ fontSize: 22, color: 'var(--red)', marginBottom: 8, fontWeight: 700 }}>Connection Issue</h3>
                <p style={{ fontSize: 14, color: 'var(--slate)', marginBottom: 24 }}>{error}</p>
                <button className="btn-primary" onClick={fetchPatients}
                  style={{ background: 'var(--red)', color: '#fff' }}>
                  <span className="material-icons-round" style={{ fontSize: 17 }}>refresh</span>
                  Retry connection
                </button>
              </div>
            )}

            {!loading && !error && patients.length === 0 && (
              <div style={{
                background: 'var(--bg-white)', borderRadius: 22,
                border: '1px dashed var(--border-bright)', padding: '80px 32px', textAlign: 'center',
              }}>
                <div style={{
                  width: 68, height: 68, borderRadius: 20, background: 'var(--teal-pale)',
                  border: '1px solid rgba(0,212,170,0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
                }}>
                  <span className="material-icons-round" style={{ fontSize: 34, color: 'var(--teal)' }}>group_add</span>
                </div>
                <h3 className="font-display" style={{ fontSize: 24, color: 'var(--navy)', marginBottom: 8, fontWeight: 700 }}>
                  No patients admitted yet
                </h3>
                <p style={{ fontSize: 14, color: 'var(--slate)', maxWidth: 340, margin: '0 auto' }}>
                  Upload a discharge summary PDF above to admit your first patient and activate AI monitoring.
                </p>
              </div>
            )}

            {!loading && !error && patients.length > 0 && (
              <div className="card-grid" style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: 20,
              }}>
                {patients.map(p => (
                  <PatientCard
                    key={p.patient_id}
                    patient={p}
                    onClick={id => navigate('/patient', { state: { patientId: id } })}
                  />
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
};

export default NurseDashboard;