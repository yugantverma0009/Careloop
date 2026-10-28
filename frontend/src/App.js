import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './ThemeContext';
import LandingPage from './components/Landingpage';
import CareLoopLogin from './components/CareLoopLogin';
import CareLoopPatientPortal from './components/CareLoopPatientPortal';
import CareLoopStaffPortal from './components/CareLoopStaffPortal';
import { getUser, getToken } from './services/api';

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
              ) : currentUser.role === 'Patient' || currentUser.role === 'Caregiver' ? (
                <Navigate to="/patient" replace />
              ) : (
                <Navigate to="/staff" replace />
              )
            }
          />

          {/* Authenticated Patient Recovery Workspace */}
          <Route
            path="/patient"
            element={
              isLoggedIn ? (
                <CareLoopPatientPortal user={currentUser} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          {/* Authenticated Clinician Staff Command Hub */}
          <Route
            path="/staff"
            element={
              isLoggedIn ? (
                <CareLoopStaffPortal user={currentUser} />
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