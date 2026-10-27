import React, { useState, useEffect } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useLocation,
} from 'react-router-dom';
import TriageDashboard from './components/TriageDashboard';
import DoctorDashboard from './components/DoctorDashboard';
import NurseDashboard from './components/NurseDashboard';
import { getAllPatients, seedDemoPatient, API_BASE } from './services/api';
import DevPanel from './components/DevPanel';
import LandingPage from './components/Landingpage';

export const AgenticLogo = ({ className = '' }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, textDecoration: 'none' }} className={className}>
    <svg viewBox="0 0 50 50" style={{ width: 36, height: 36, minWidth: 36, flexShrink: 0 }} fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="tealGrad" x1="0" y1="0" x2="50" y2="50" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--accent, #0D9488)" />
          <stop offset="1" stopColor="var(--accent-dark, #0F766E)" />
        </linearGradient>
      </defs>
      <path d="M18 5H32V18H45V32H32V45H18V32H5V18H18V5Z" fill="var(--accent)" fillOpacity="0.18" />
      <path d="M25 6V12M25 38V44M21 8V15M29 8V15M21 35V42M29 35V42" stroke="url(#tealGrad)" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M6 25H12M38 25H44M8 21H15M8 29H15M35 21H42M35 29H42" stroke="url(#tealGrad)" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M25 12L25 38M12 25H38" stroke="var(--text-1, #0F172A)" strokeWidth="3" strokeLinecap="round"/>
      <circle cx="25" cy="25" r="4.5" fill="var(--accent)" />
      <circle cx="25" cy="6" r="2" fill="var(--accent)"/>
      <circle cx="25" cy="44" r="2" fill="var(--accent)"/>
      <circle cx="6" cy="25" r="2" fill="var(--accent)"/>
      <circle cx="44" cy="25" r="2" fill="var(--accent)"/>
    </svg>
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', lineHeight: 1 }}>
      <span style={{ fontSize: 17, fontWeight: 800, color: 'var(--text-1)', letterSpacing: '-0.3px', fontFamily: "'Outfit', sans-serif" }}>
        Agentic<span style={{ color: "var(--accent)" }}>Nurse</span>
      </span>
      <span style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.22em', color: 'var(--text-3)', fontWeight: 700, marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }}>
        Clinical AI System
      </span>
    </div>
  </div>
);

/* ──────────────────────────────────────────────────────────────────────────
   PERSISTENT ACCESSIBLE GLOBAL CLINICAL HEADER
────────────────────────────────────────────────────────────────────────── */
const ClinicalHeader = ({ currentPatientId, onSeedDemo }) => {
  const location = useLocation();
  const [theme, setTheme] = useState(() => localStorage.getItem('nurse_theme') || 'light');
  const [apiOnline, setApiOnline] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/nurse/patients`)
      .then((res) => setApiOnline(res.ok))
      .catch(() => setApiOnline(false));
  }, []);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    localStorage.setItem('nurse_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const navItems = [
    { label: 'Clinical Hub', path: '/', icon: 'dashboard' },
    { label: 'Nurse Station', path: '/nurse', icon: 'local_hospital' },
    { label: 'Doctor Portal', path: '/doctor', icon: 'medical_services' },
    { label: 'Patient Recovery', path: '/patient', icon: 'personal_injury' },
  ];

  return (
    <header
      role="banner"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        backgroundColor: 'var(--header-bg)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1.5px solid var(--border)',
        boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
        padding: '10px 20px',
      }}
    >
      <div style={{ maxWidth: 1280, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        {/* Brand */}
        <Link
          to="/"
          style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}
          aria-label="Agentic Nurse Clinical AI - Home"
        >
          <AgenticLogo />
        </Link>

        {/* Clinical Navigation Tabs */}
        <nav
          role="navigation"
          aria-label="Clinical Portals Navigation"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: 4,
            borderRadius: 12,
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            flexWrap: 'wrap',
          }}
        >
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                aria-current={isActive ? 'page' : undefined}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '7px',
                  fontSize: '13.5px',
                  fontWeight: isActive ? 700 : 600,
                  textDecoration: 'none',
                  color: isActive ? 'var(--accent-contrast)' : 'var(--text-2)',
                  backgroundColor: isActive ? 'var(--accent)' : 'transparent',
                  transition: 'all 0.15s ease',
                  border: isActive ? '1px solid var(--accent-dark)' : '1px solid transparent',
                  cursor: 'pointer',
                }}
              >
                <span className="material-icons-round" style={{ fontSize: 17 }} aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right Action Tools: Patient Quick Status, Theme Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Quick Demo Loader if on patient tab without patient */}
          {location.pathname === '/patient' && !currentPatientId && (
            <button
              onClick={onSeedDemo}
              className="btn-primary"
              style={{ fontSize: 12, padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              title="Load Eleanor Vance demo patient"
            >
              <span className="material-icons-round" style={{ fontSize: 15 }}>person_add</span>
              <span>Load Demo Patient</span>
            </button>
          )}

          {/* System Telemetry Indicator */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '6px 12px',
              borderRadius: 8,
              backgroundColor: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              fontSize: 12,
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 600,
              color: 'var(--text-2)',
            }}
            title="FastAPI Autonomous Backend Status"
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: apiOnline ? 'var(--green)' : 'var(--red-alert)',
                boxShadow: apiOnline ? '0 0 8px var(--green)' : 'none',
                display: 'inline-block',
              }}
            />
            <span>SYSTEM ACTIVE</span>
          </div>

          {/* Theme Switcher Button */}
          <button
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Clinical Mode`}
            style={{
              padding: '7px 12px',
              borderRadius: 8,
              border: '1.5px solid var(--border)',
              backgroundColor: 'var(--bg-surface)',
              color: 'var(--text-1)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
              fontWeight: 600,
              fontFamily: "'Inter', sans-serif",
            }}
          >
            <span className="material-icons-round" style={{ fontSize: 16, color: 'var(--accent)' }} aria-hidden="true">
              {theme === 'light' ? 'dark_mode' : 'light_mode'}
            </span>
            <span>
              {theme === 'light' ? 'Dark' : 'Light'}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};

const Layout = ({ children, setPatientId, currentPatientId, onSeedDemo }) => {
  const location = useLocation();

  useEffect(() => {
    if (location.state?.patientId) setPatientId(location.state.patientId);
  }, [location.state, setPatientId]);

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-1)] font-sans flex flex-col">
      <ClinicalHeader currentPatientId={currentPatientId} onSeedDemo={onSeedDemo} />
      <main className="flex-1 w-full" role="main">
        {children}
      </main>
      <DevPanel />
    </div>
  );
};

function App() {
  const [currentPatientId, setCurrentPatientId] = useState(null);
  const [patientName,      setPatientName]       = useState('');
  const [messages,         setMessages]          = useState([]);
  const [viewMode,         setViewMode]          = useState('home');
  const [loadingDemo,      setLoadingDemo]       = useState(false);

  const fetchPatients = () => {
    getAllPatients()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setCurrentPatientId(data[0].patient_id);
          setPatientName(data[0].name);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchPatients();
  }, []);

  useEffect(() => {
    if (!currentPatientId) return;
    setMessages([{ sender: 'nurse', text: `Hello ${patientName || 'there'}. I am your AI Recovery Nurse. How are you feeling right now?` }]);
  }, [currentPatientId, patientName]);

  const handleSeedDemo = async () => {
    setLoadingDemo(true);
    try {
      const res = await seedDemoPatient();
      if (res && res.patient_id) {
        setCurrentPatientId(res.patient_id);
        setPatientName(res.name);
        fetchPatients();
      }
    } catch (err) {
      console.error('Failed to load demo patient:', err);
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <Router>
      <Layout
        setPatientId={setCurrentPatientId}
        currentPatientId={currentPatientId}
        onSeedDemo={handleSeedDemo}
      >
        <Routes>
          <Route path="/" element={<LandingPage onSeedDemo={handleSeedDemo} />} />

          <Route
            path="/patient"
            element={
              currentPatientId ? (
                <TriageDashboard
                  key={currentPatientId}
                  patientId={currentPatientId}
                  setPatientId={setCurrentPatientId}
                  messages={messages}
                  setMessages={setMessages}
                  viewMode={viewMode}
                  setViewMode={setViewMode}
                  onPatientNameLoad={setPatientName}
                />
              ) : (
                <div className="flex flex-col items-center justify-center min-h-[75vh] text-center px-4">
                  <div className="w-18 h-18 p-4 rounded-2xl bg-[var(--bg-elevated)] border-2 border-[var(--border)] flex items-center justify-center mb-5 shadow-lg">
                    <span className="material-icons-round text-4xl" style={{ color: 'var(--accent)' }}>
                      personal_injury
                    </span>
                  </div>
                  <h1 className="text-[var(--text-1)] font-bold text-2xl font-display mb-2">
                    No Patient Loaded for Recovery Triage
                  </h1>
                  <p className="text-[var(--text-2)] text-base max-w-md mx-auto mb-6">
                    Load our realistic clinical post-discharge patient (Eleanor Vance - CABG Post-Op) or admit a new patient via PDF at the Nurse Station.
                  </p>
                  <div className="flex flex-wrap items-center justify-center gap-3">
                    <button
                      onClick={handleSeedDemo}
                      disabled={loadingDemo}
                      className="btn-primary"
                    >
                      <span className="material-icons-round text-lg">play_arrow</span>
                      <span>{loadingDemo ? 'Initializing Patient...' : 'Load Eleanor Vance (Demo Patient)'}</span>
                    </button>
                    <Link to="/nurse" className="btn-secondary">
                      <span className="material-icons-round text-lg">upload_file</span>
                      <span>Admit via Nurse Station</span>
                    </Link>
                  </div>
                </div>
              )
            }
          />

          <Route path="/nurse" element={<NurseDashboard />} />
          <Route path="/doctor" element={<DoctorDashboard />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;