import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { ThemeProvider } from './ThemeContext';
import LandingPage from './components/Landingpage';
import CareLoopLogin from './components/CareLoopLogin';
import CareLoopPatientPortal from './components/CareLoopPatientPortal';
import CareLoopStaffPortal from './components/CareLoopStaffPortal';
import FamilyPortal from './components/FamilyPortal';
import { getUser, getToken } from './services/api';

/**
 * Route protection guard enforcing the CareLoop Role Contract (Section 2.3 & 2.4).
 * If a signed-in user visits a route designated for another role, shows a polite
 * explanation and a direct button to their own workspace.
 */
function RoleRouteGuard({ allowedRoles, user, children }) {
  if (!user || !user.role) {
    return <Navigate to="/login" replace />;
  }

  const role = user.role || user.account_role;
  if (!allowedRoles.includes(role)) {
    const roleDestinations = {
      Doctor: '/doctor',
      Nurse: '/nurse',
      Patient: '/patient',
      Caregiver: '/family',
    };
    const dest = roleDestinations[role] || '/';
    const friendlyRoleNames = allowedRoles.map((r) => (r === 'Caregiver' ? 'Family helpers' : `${r}s`)).join(' or ');

    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--bg-base)',
          padding: 24,
        }}
      >
        <div
          style={{
            maxWidth: 480,
            width: '100%',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 12,
            padding: 32,
            textAlign: 'center',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 800,
              color: 'var(--role-family)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginBottom: 8,
            }}
          >
            Access Notice
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 12 }}>
            This page is for {friendlyRoleNames}
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 24 }}>
            You are currently signed in as <strong>{user.name || role}</strong> ({role}). Each role in CareLoop has its own dedicated workspace.
          </p>
          <Link
            to={dest}
            style={{
              display: 'inline-block',
              padding: '10px 22px',
              borderRadius: 8,
              backgroundColor: 'var(--navy-deep, #0b1528)',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: 14,
              textDecoration: 'none',
            }}
          >
            Go to my workspace
          </Link>
        </div>
      </div>
    );
  }

  return children;
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => getUser());

  useEffect(() => {
    const handleStorage = () => {
      setCurrentUser(getUser());
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
  };

  const isLoggedIn = Boolean(getToken() && currentUser);

  const getHomeRouteForRole = (user) => {
    if (!user) return '/login';
    const role = user.role || user.account_role;
    if (role === 'Doctor') return '/doctor';
    if (role === 'Nurse') return '/nurse';
    if (role === 'Caregiver') return '/family';
    return '/patient';
  };

  return (
    <ThemeProvider>
      <Router>
        <Routes>
          {/* Public Landing Page */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/landing" element={<LandingPage />} />

          {/* Login Page */}
          <Route
            path="/login"
            element={
              !isLoggedIn ? (
                <CareLoopLogin onLoginSuccess={handleLoginSuccess} />
              ) : (
                <Navigate to={getHomeRouteForRole(currentUser)} replace />
              )
            }
          />

          {/* Doctor Desk */}
          <Route
            path="/doctor"
            element={
              isLoggedIn ? (
                <RoleRouteGuard allowedRoles={['Doctor']} user={currentUser}>
                  <CareLoopStaffPortal user={currentUser} defaultRole="Doctor" />
                </RoleRouteGuard>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          {/* Nurse Desk */}
          <Route
            path="/nurse"
            element={
              isLoggedIn ? (
                <RoleRouteGuard allowedRoles={['Nurse']} user={currentUser}>
                  <CareLoopStaffPortal user={currentUser} defaultRole="Nurse" />
                </RoleRouteGuard>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          {/* Legacy Staff Route (Redirects to role workspace) */}
          <Route
            path="/staff"
            element={
              isLoggedIn ? (
                currentUser.role === 'Nurse' ? (
                  <Navigate to="/nurse" replace />
                ) : (
                  <Navigate to="/doctor" replace />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          {/* Patient Recovery Portal */}
          <Route
            path="/patient"
            element={
              isLoggedIn ? (
                <RoleRouteGuard allowedRoles={['Patient']} user={currentUser}>
                  <CareLoopPatientPortal user={currentUser} />
                </RoleRouteGuard>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          {/* Family Helper Portal */}
          <Route
            path="/family"
            element={
              isLoggedIn ? (
                <RoleRouteGuard allowedRoles={['Caregiver']} user={currentUser}>
                  <FamilyPortal user={currentUser} />
                </RoleRouteGuard>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}
