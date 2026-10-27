import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgenticLogo } from '../App';

const API_BASE = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

const getAuthHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${sessionStorage.getItem('authToken') || ''}`,
});

const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons+Round');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, #root { height: 100%; }

    :root {
      --teal:         var(--accent);
      --teal-dark:    var(--accent-dark);
      --teal-pale:    var(--accent-dim);
      --teal-glow:    var(--accent-glow);
      --navy:         var(--text-1);
      --slate:        var(--text-2);
      --muted:        var(--text-3);
      --bg:           var(--bg-base);
      --bg-white:     var(--bg-surface);
      --bg-card:      var(--bg-surface);
      --green:        var(--green);
      --green-pale:   var(--green-dim);
      --amber:        var(--amber);
      --amber-pale:   var(--amber-dim);
      --red:          var(--red-alert);
      --red-pale:     var(--red-dim);
      --orange:       var(--amber);
      --orange-pale:  var(--amber-dim);
      --border:       var(--border);
      --border-bright:var(--border-bright);
      --shadow:       var(--shadow);
      --shadow-md:    var(--shadow-card);
      --shadow-lg:    var(--shadow-lg);
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

    @keyframes pageIn  { from{opacity:0;transform:translateY(22px)} to{opacity:1;transform:translateY(0)} }
    @keyframes fadeUp  { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }
    @keyframes spin    { to{transform:rotate(360deg)} }
    @keyframes pulse   { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.3)} }
    @keyframes shimmer { from{background-position:-600px 0} to{background-position:600px 0} }
    @keyframes slideIn { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }
    @keyframes slideOut{ from{opacity:1;transform:translateX(0)} to{opacity:0;transform:translateX(60px)} }

    .page-in   { animation: pageIn .55s cubic-bezier(.22,1,.36,1) both; }
    .fade-up-2 { animation: fadeUp .5s cubic-bezier(.22,1,.36,1) .14s both; }
    .fade-up-3 { animation: fadeUp .5s cubic-bezier(.22,1,.36,1) .22s both; }

    .alert-row { animation: slideIn .4s cubic-bezier(.22,1,.36,1) both; }
    .alert-row:nth-child(1) { animation-delay:.08s }
    .alert-row:nth-child(2) { animation-delay:.15s }
    .alert-row:nth-child(3) { animation-delay:.22s }
    .alert-row:nth-child(4) { animation-delay:.29s }
    .alert-row:nth-child(n+5){ animation-delay:.36s }
    .alert-row.removing     { animation: slideOut .35s cubic-bezier(.22,1,.36,1) forwards; }

    .skeleton {
      background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 75%);
      background-size: 600px 100%;
      animation: shimmer 1.5s ease infinite;
      border-radius: 16px;
      border: 1px solid var(--border);
    }

    .btn-primary {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 10px 22px; border-radius: 50px;
      background: linear-gradient(135deg, var(--teal) 0%, var(--teal-dark) 100%);
      color: #07090F;
      font-family: 'Inter', sans-serif; font-weight: 700; font-size: 14px;
      border: none; cursor: pointer;
      box-shadow: 0 4px 18px rgba(0, 212, 170, 0.25);
      transition: all .2s;
    }
    .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0, 212, 170, 0.4); }

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

    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--teal); }
  `}</style>
);

const StatCard = ({ label, value, icon, accent }) => (
  <div style={{
    background: 'var(--bg-card)', borderRadius: 20,
    border: '1px solid var(--border)', padding: '24px 26px',
    display: 'flex', alignItems: 'center', gap: 16,
    boxShadow: 'var(--shadow)', transition: 'all .25s ease',
  }}
    onMouseEnter={e=>{ e.currentTarget.style.transform='translateY(-3px)'; e.currentTarget.style.borderColor='var(--border-bright)'; e.currentTarget.style.boxShadow='var(--shadow-md)'; }}
    onMouseLeave={e=>{ e.currentTarget.style.transform=''; e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.boxShadow='var(--shadow)'; }}
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
      <div className="font-display" style={{ fontSize: 36, fontWeight: 800, color: accent, lineHeight: 1, letterSpacing: '-0.5px' }}>
        {value}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--slate)', marginTop: 6, letterSpacing: .5 }}>
        {label}
      </div>
    </div>
  </div>
);

const RiskRing = ({ score }) => {
  const color = score >= 8 ? 'var(--red)' : score >= 4 ? 'var(--orange)' : 'var(--amber)';
  const pct   = (score / 10) * 100;
  return (
    <div style={{ position:'relative', width:64, height:64, flexShrink:0 }}>
      <svg width="64" height="64" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r="26" fill="none" stroke={`${color}22`} strokeWidth="6" />
        <circle cx="32" cy="32" r="26" fill="none"
          stroke={color} strokeWidth="6"
          strokeDasharray={`${2 * Math.PI * 26}`}
          strokeDashoffset={`${2 * Math.PI * 26 * (1 - pct / 100)}`}
          strokeLinecap="round"
          transform="rotate(-90 32 32)"
          style={{ transition:'stroke-dashoffset .6s ease' }}
        />
      </svg>
      <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center' }}>
        <span className="font-mono" style={{ fontSize:17, fontWeight:700, color, lineHeight:1 }}>{score}</span>
        <span style={{ fontSize:9, color:'var(--muted)', fontWeight:600 }}>/10</span>
      </div>
    </div>
  );
};

const ActionBadge = ({ action }) => {
  const map = {
    ALERT: { bg:'var(--red-pale)',    color:'var(--red)',    border:'rgba(255,68,68,0.3)',    icon:'crisis_alert' },
    FLAG:  { bg:'var(--orange-pale)', color:'var(--orange)', border:'rgba(249,115,22,0.3)',   icon:'flag'         },
    LOG:   { bg:'rgba(255,255,255,0.06)', color:'var(--slate)', border:'var(--border)',     icon:'assignment'   },
  };
  const s = map[action] || map.LOG;
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:4,
      padding:'3px 10px', borderRadius:50,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`,
      fontFamily:"'JetBrains Mono',monospace", fontSize:9,
      fontWeight:700, letterSpacing:'1.2px', textTransform:'uppercase',
    }}>
      <span className="material-icons-round" style={{ fontSize:11 }}>{s.icon}</span>
      {action || 'LOG'}
    </span>
  );
};

const SeverityBadge = ({ score }) => {
  const isCritical = score >= 8;
  const isMedium   = score >= 4;
  const label = isCritical ? 'Critical' : isMedium ? 'Monitor' : 'Low';
  const icon  = isCritical ? 'crisis_alert' : isMedium ? 'warning' : 'info';
  const bg    = isCritical ? 'var(--red-pale)'    : isMedium ? 'var(--orange-pale)' : 'var(--amber-pale)';
  const color = isCritical ? 'var(--red)'         : isMedium ? 'var(--orange)'      : 'var(--amber)';
  const border= isCritical ? 'rgba(255,68,68,0.3)' : isMedium ? 'rgba(249,115,22,0.3)' : 'rgba(245,158,11,0.3)';
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:5,
      padding:'4px 11px', borderRadius:50,
      background:bg, color, border:`1px solid ${border}`,
      fontFamily:"'JetBrains Mono',monospace", fontSize:9,
      fontWeight:700, letterSpacing:'1.2px', textTransform:'uppercase',
    }}>
      <span className="material-icons-round" style={{ fontSize:11 }}>{icon}</span>
      {label}
    </span>
  );
};

const AlertCard = ({ alert, onAcknowledge, onViewLogs }) => {
  const isCritical = alert.risk_score >= 8;
  const isMedium   = alert.risk_score >= 4;
  const accent     = isCritical ? 'var(--red)' : isMedium ? 'var(--orange)' : 'var(--amber)';
  const [removing,  setRemoving]  = useState(false);
  const [ackError,  setAckError]  = useState('');
  const [acking,    setAcking]    = useState(false);

  const handleAck = async () => {
    if (acking || removing) return;
    setAcking(true);
    setAckError('');
    try {
      const res = await fetch(`${API_BASE}/doctor/alerts/${alert.alert_id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setAckError(err.detail || 'Could not acknowledge. Try again.');
        setAcking(false);
        return;
      }
      setRemoving(true);
      setTimeout(() => onAcknowledge(alert.alert_id), 370);
    } catch {
      setAckError('Network error. Try again.');
      setAcking(false);
    }
  };

  return (
    <div
      className={`alert-row${removing ? ' removing' : ''}`}
      style={{
        background:'var(--bg-white)', borderRadius:20, overflow:'hidden',
        border:`1px solid ${isCritical ? 'rgba(255,68,68,.4)' : 'var(--border)'}`,
        boxShadow: isCritical
          ? '0 0 20px rgba(255,68,68,.12), var(--shadow)'
          : 'var(--shadow)',
        display:'flex', flexDirection:'column',
        transition:'all .25s ease',
      }}
      onMouseEnter={e=>{ if(!removing){ e.currentTarget.style.transform='translateY(-3px)'; e.currentTarget.style.boxShadow=isCritical ? '0 0 24px rgba(255,68,68,.25),var(--shadow-md)' : 'var(--shadow-md)'; }}}
      onMouseLeave={e=>{ if(!removing){ e.currentTarget.style.transform=''; e.currentTarget.style.boxShadow=isCritical ? '0 0 20px rgba(255,68,68,.12),var(--shadow)' : 'var(--shadow)'; }}}
    >
      {/* Accent top bar */}
      <div style={{ height:4, background:accent }} />

      <div style={{ display:'flex', flexDirection:'row', flex:1, flexWrap:'wrap' }}>
        {/* Main content */}
        <div style={{ flex:1, padding:'24px 26px', display:'flex', flexDirection:'column', gap:14, minWidth:280 }}>

          {/* Top meta row */}
          <div style={{ display:'flex', flexWrap:'wrap', alignItems:'center', justifyContent:'space-between', gap:10 }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
              <SeverityBadge score={alert.risk_score} />
              <ActionBadge action={alert.action} />
              <span className="font-mono" style={{
                fontSize:11, fontWeight:600,
                color:'var(--navy)', padding:'3px 10px',
                background:'rgba(255,255,255,0.06)', borderRadius:8,
                border:'1px solid var(--border)',
              }}>
                Patient #{alert.patient_id}
              </span>
              {/* Treating doctor tag — always shown */}
              <span className="font-mono" style={{
                fontSize:11, fontWeight:600,
                color: alert.primary_doctor_name ? '#A78BFA' : 'var(--muted)',
                padding:'3px 10px',
                background: alert.primary_doctor_name ? 'rgba(167,139,250,0.12)' : 'rgba(255,255,255,0.04)',
                borderRadius:8, border:`1px solid ${alert.primary_doctor_name ? 'rgba(167,139,250,0.25)' : 'var(--border)'}`,
              }}>
                <span style={{ verticalAlign:'middle', marginRight:4 }}>👨‍⚕️</span>
                {alert.primary_doctor_name ? `Dr. ${alert.primary_doctor_name}` : 'Doctor Unassigned'}
              </span>
            </div>
            <div style={{ display:'flex', alignItems:'center', gap:6, color:'var(--muted)' }}>
              <span className="material-icons-round" style={{ fontSize:14 }}>schedule</span>
              <span className="font-mono" style={{ fontSize:11, fontWeight:500 }}>
                {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : 'Just now'}
              </span>
            </div>
          </div>

          <div style={{ height:1, background:'var(--border)' }} />

          {/* Reason + risk ring */}
          <div style={{ display:'flex', alignItems:'flex-start', gap:20 }}>
            <p style={{ flex:1, fontSize:14, color:'var(--navy)', lineHeight:1.7, fontWeight:400 }}>
              {alert.reason || 'No additional context recorded.'}
            </p>
            <RiskRing score={alert.risk_score} />
          </div>

          {/* Inline error if acknowledge fails */}
          {ackError && (
            <div style={{
              background:'var(--red-pale)', border:'1px solid rgba(255,68,68,.3)',
              borderRadius:10, padding:'8px 12px', fontSize:12, color:'var(--red)',
              display:'flex', alignItems:'center', gap:6,
            }}>
              <span className="material-icons-round" style={{ fontSize:14 }}>error_outline</span>
              {ackError}
            </div>
          )}
        </div>

        {/* Action sidebar */}
        <div style={{
          width:150, flexShrink:0,
          background:'var(--bg-card)',
          borderLeft:'1px solid var(--border)',
          padding:'22px 16px',
          display:'flex', flexDirection:'column',
          justifyContent:'center', gap:10,
        }}>
          <button
            onClick={handleAck}
            disabled={acking || removing}
            style={{
              width:'100%', padding:'10px 0', borderRadius:50,
              background: isCritical ? 'linear-gradient(135deg, #FF4444 0%, #DC2626 100%)' : 'linear-gradient(135deg, var(--teal) 0%, var(--teal-dark) 100%)',
              color: isCritical ? '#fff' : '#07090F', border:'none', cursor: (acking || removing) ? 'not-allowed' : 'pointer',
              fontFamily:"'Inter',sans-serif", fontWeight:700, fontSize:12,
              display:'flex', alignItems:'center', justifyContent:'center', gap:6,
              boxShadow: isCritical ? '0 4px 14px rgba(255,68,68,0.3)' : '0 4px 14px rgba(0,212,170,0.3)',
              transition:'all .2s', opacity: (acking || removing) ? .55 : 1,
            }}
          >
            {acking ? (
              <span style={{ width:14, height:14, border:'2px solid rgba(255,255,255,.4)', borderTopColor:'#fff', borderRadius:'50%', animation:'spin .7s linear infinite', display:'inline-block' }} />
            ) : (
              <span className="material-icons-round" style={{ fontSize:15 }}>check_circle</span>
            )}
            {acking ? 'Removing…' : 'Acknowledge'}
          </button>

          <button
            onClick={() => onViewLogs(alert.patient_id)}
            style={{
              width:'100%', padding:'10px 0', borderRadius:50,
              background:'rgba(255,255,255,0.04)', color:'var(--slate)',
              border:'1px solid var(--border)', cursor:'pointer',
              fontFamily:"'Inter',sans-serif", fontWeight:600, fontSize:12,
              display:'flex', alignItems:'center', justifyContent:'center', gap:6,
              transition:'all .2s',
            }}
            onMouseEnter={e=>{ e.currentTarget.style.borderColor='var(--teal)'; e.currentTarget.style.color='var(--teal)'; e.currentTarget.style.background='var(--teal-pale)'; }}
            onMouseLeave={e=>{ e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.color='var(--slate)'; e.currentTarget.style.background='rgba(255,255,255,0.04)'; }}
          >
            <span className="material-icons-round" style={{ fontSize:15 }}>open_in_new</span>
            View Logs
          </button>
        </div>
      </div>
    </div>
  );
};

const Navbar = ({ alertCount, doctorName }) => (
  <nav style={{
    position:'sticky', top:0, zIndex:100,
    background:'rgba(7, 9, 15, 0.85)', backdropFilter:'blur(16px)',
    borderBottom:'1px solid var(--border)',
    padding:'0 5%', display:'flex', alignItems:'center', height:64, gap:16,
  }}>
    <a href="/" style={{ display:'flex', alignItems:'center', textDecoration:'none', flexShrink:0 }}>
      <AgenticLogo className="h-9" />
    </a>

    <div style={{ padding:'4px 12px', borderRadius:50, background:'rgba(139,92,246,0.12)', border:'1px solid rgba(139,92,246,0.3)', display:'flex', alignItems:'center', gap:6 }}>
      <span className="material-icons-round" style={{ fontSize:13, color:'#A78BFA' }}>medical_services</span>
      <span className="font-mono" style={{ fontSize:10, fontWeight:600, color:'#A78BFA', letterSpacing:1.2, textTransform:'uppercase' }}>
        {doctorName ? `Dr. ${doctorName.split(' ').slice(-1)[0]}` : 'Doctor Admin'}
      </span>
    </div>

    <div style={{ flex:1 }} />

    {alertCount > 0 ? (
      <div style={{ display:'flex', alignItems:'center', gap:7, padding:'5px 14px', borderRadius:50, background:'var(--red-pale)', border:'1px solid rgba(255,68,68,0.3)' }}>
        <span style={{ width:7, height:7, borderRadius:'50%', background:'var(--red)', display:'block', animation:'pulse 1.6s ease infinite' }} />
        <span className="font-mono" style={{ fontSize:11, color:'var(--red)', fontWeight:700 }}>{alertCount} active alert{alertCount !== 1 ? 's' : ''}</span>
      </div>
    ) : (
      <div style={{ display:'flex', alignItems:'center', gap:7 }}>
        <span style={{ width:7, height:7, borderRadius:'50%', background:'var(--green)', display:'block', animation:'pulse 2s ease infinite' }} />
        <span style={{ fontSize:12, color:'var(--slate)', fontWeight:500 }}>All clear</span>
      </div>
    )}

    <button className="btn-ghost" onClick={() => { sessionStorage.clear(); window.location.href = '/'; }}>
      <span className="material-icons-round" style={{ fontSize:15 }}>logout</span>
      Sign out
    </button>
  </nav>
);

const DoctorDashboard = () => {
  const [alerts,    setAlerts]    = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [fetchError,setFetchError]= useState('');
  const navigate = useNavigate();

  const doctorName = sessionStorage.getItem('doctorName') || '';

  const fetchAlerts = useCallback(async () => {
    setFetchError('');
    try {
      const res = await fetch(`${API_BASE}/doctor/alerts`, {
        headers: getAuthHeaders(),
      });
      if (res.status === 401 || res.status === 403) {
        sessionStorage.clear();
        window.location.href = '/';
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAlerts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Alert fetch failed:', e);
      setFetchError('Could not load alerts. Check your connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    const iv = setInterval(fetchAlerts, 10_000);
    return () => clearInterval(iv);
  }, [fetchAlerts]);

  const handleAcknowledge = (alertId) => {
    setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
  };

  const handleViewLogs = (patientId) => navigate('/patient', { state: { patientId } });

  const criticalCount = alerts.filter(a => a.risk_score >= 8).length;
  const monitorCount  = alerts.filter(a => a.risk_score >= 4 && a.risk_score < 8).length;

  return (
    <>
      <GlobalStyles />
      <div style={{ minHeight:'100vh', background:'var(--bg)', paddingBottom:72 }}>

        <Navbar alertCount={alerts.length} doctorName={doctorName} />

        <div style={{ maxWidth:960, margin:'0 auto', padding:'40px 5% 0' }}>

          <div className="page-in" style={{ marginBottom:36 }}>
            <span className="section-label">Clinical Oversight</span>
            <h1 className="font-display" style={{
              fontSize:'clamp(28px,3.5vw,44px)', fontWeight:800,
              color:'var(--navy)', lineHeight:1.15, marginBottom:10, letterSpacing:'-0.5px'
            }}>
              Escalation Feed
            </h1>
            <p style={{ fontSize:15, color:'var(--slate)', maxWidth:520, lineHeight:1.65 }}>
              Real-time view of high-risk alerts for <strong>your patients</strong> — sourced
              from their discharge PDFs. Only critical deviations surface here.
            </p>
          </div>

          <div className="fade-up-2" style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))', gap:16, marginBottom:36 }}>
            <StatCard label="Total Alerts"   value={alerts.length}  icon="notifications_active" accent="var(--teal)"   />
            <StatCard label="Critical (≥ 8)" value={criticalCount}  icon="crisis_alert"          accent="var(--red)"    />
            <StatCard label="Monitor (4–7)"  value={monitorCount}   icon="warning"               accent="var(--orange)" />
          </div>

          <div className="fade-up-3">
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
              <h2 className="font-display" style={{ fontSize:22, fontWeight:700, color:'var(--navy)', display:'flex', alignItems:'center', gap:10 }}>
                Active Alerts
                {alerts.length > 0 && (
                  <span className="font-mono" style={{ fontSize:12, color:'var(--muted)', fontWeight:500 }}>
                    {alerts.length} unreviewed
                  </span>
                )}
              </h2>
              <button className="btn-ghost" onClick={fetchAlerts}>
                <span className="material-icons-round" style={{ fontSize:15 }}>refresh</span>
                Refresh
              </button>
            </div>

            {fetchError && (
              <div style={{ background:'var(--bg-white)', border:'1px solid rgba(255,68,68,.3)', borderRadius:14, padding:'14px 18px', marginBottom:16, fontSize:13, color:'var(--red)', display:'flex', alignItems:'center', gap:8 }}>
                <span className="material-icons-round" style={{ fontSize:18 }}>wifi_off</span>
                {fetchError}
              </div>
            )}

            {loading && alerts.length === 0 && (
              <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
                {[...Array(3)].map((_,i) => <div key={i} className="skeleton" style={{ height:160 }} />)}
              </div>
            )}

            {!loading && alerts.length === 0 && !fetchError && (
              <div style={{ background:'var(--bg-white)', borderRadius:22, border:'1px dashed var(--border-bright)', padding:'80px 32px', textAlign:'center' }}>
                <div style={{ width:72, height:72, borderRadius:20, background:'var(--green-pale)', border:'1px solid rgba(16,185,129,0.3)', display:'flex', alignItems:'center', justifyContent:'center', margin:'0 auto 20px' }}>
                  <span className="material-icons-round" style={{ fontSize:36, color:'var(--green)' }}>check_circle</span>
                </div>
                <h3 className="font-display" style={{ fontSize:24, color:'var(--navy)', marginBottom:8, fontWeight:700 }}>All clear</h3>
                <p style={{ fontSize:14, color:'var(--slate)', maxWidth:340, margin:'0 auto' }}>
                  No critical deviations detected in your patients' conversations. Monitoring is active.
                </p>
              </div>
            )}

            {!loading && alerts.length > 0 && (
              <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
                {alerts.map((alert) => (
                  <AlertCard
                    key={alert.alert_id}
                    alert={alert}
                    onAcknowledge={handleAcknowledge}
                    onViewLogs={handleViewLogs}
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

export default DoctorDashboard;