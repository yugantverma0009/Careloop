/**
 * src/services/api.js — CareLoop Centralized API Service
 *
 * Core Rule: "The LLM talks. Rules decide. Humans act."
 * All patient operations strictly use the authenticated JWT token.
 * Flags and clinical workflows are backed by MySQL 8.0 views & stored procedures.
 */

export const API_BASE =
  process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

// ─── Token & Auth Management ────────────────────────────────────────────────

export const getToken = () => localStorage.getItem('careloop_token');

export const setToken = (token) => {
  if (token) {
    localStorage.setItem('careloop_token', token);
  } else {
    localStorage.removeItem('careloop_token');
  }
};

export const getUser = () => {
  try {
    const raw = localStorage.getItem('careloop_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const setUser = (user) => {
  if (user) {
    localStorage.setItem('careloop_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('careloop_user');
  }
};

export const logout = () => {
  setToken(null);
  setUser(null);
  window.location.href = '/login';
};

// ─── Generic Fetch Helpers ──────────────────────────────────────────────────

const handleResponse = async (res) => {
  if (!res.ok) {
    if (res.status === 401 && window.location.pathname !== '/login') {
      logout();
    }
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
  return res.json();
};

const authHeaders = () => {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const get = (path) =>
  fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
  }).then(handleResponse);

const post = (path, body) =>
  fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body || {}),
  }).then(handleResponse);

// ─── Auth Endpoints ─────────────────────────────────────────────────────────

export const login = async (email, password) => {
  const data = await post('/auth/login', { email, password });
  setToken(data.access_token);
  setUser(data);
  return data;
};

export const getMe = () => get('/auth/me');

// ─── Patient Endpoints ──────────────────────────────────────────────────────

export const getMyProfile = () => get('/patient/me/profile');

export const getMyDoses = () => get('/patient/me/doses');

export const confirmMyDose = (logId, status = 'Taken_Confirmed') =>
  post(`/patient/me/doses/${logId}/confirm`, { status });

export const submitSymptomCheckin = (text, painLevel = 0, inputMethod = 'Text', language = 'en') =>
  post('/patient/me/symptoms', {
    text,
    pain_level: Number(painLevel),
    input_method: inputMethod,
    language,
  });

export const getMyStatus = () => get('/patient/me/status');

export const sendChatMessage = (message, language = 'en') =>
  post('/patient/me/chat', { message, language });

export const getChatHistory = () => get('/patient/me/chat/history');

// ─── Staff & Clinical Workflow Endpoints ─────────────────────────────────────

export const getStaffProfile = () => get('/staff/me/profile');

export const getTriageBoard = () => get('/staff/triage');

export const acknowledgeFlag = (flagId, note = 'Acknowledged via portal') =>
  post(`/staff/flags/${flagId}/acknowledge`, { note });

export const getFollowUps = () => get('/staff/follow-ups');

export const getPatientTimeline = (patientId) =>
  get(`/staff/patients/${patientId}/timeline`);

export const generateSummary = (patientId, summaryDate = null) => {
  const query = summaryDate ? `?summary_date=${summaryDate}` : '';
  return post(`/staff/patients/${patientId}/summaries/generate${query}`, {});
};

export const getPendingSummaries = () => get('/staff/summaries/pending');

export const reviewSummary = (summaryId, action = 'Approve', notes = '') =>
  post(`/staff/summaries/${summaryId}/review`, { action, notes });

// Backward compatibility helper
export const checkHealth = () =>
  fetch(`${API_BASE}/health`).then(handleResponse);

// Legacy compatibility shims
export const getAllPatients = () =>
  get('/staff/triage').catch(() => []);

export const seedDemoPatient = () => Promise.resolve({ ok: true });

export const admitPatient = () => Promise.resolve({ ok: true });

export const getPatientPipelineStatus = () => Promise.resolve({ status: 'active' });

export const getPatientPersonalization = () =>
  get('/patient/me/profile').catch(() => ({}));

export const sendVoiceMessage = () => Promise.reject(new Error("Voice diagnosis is disabled as per safety rule."));

export const sendWoundImage = () => Promise.reject(new Error("AI wound diagnosis is disabled as per safety rule."));

export const triggerReminder = () => Promise.resolve({ ok: true });

export const submitPatientReply = () => Promise.resolve({ ok: true });

export const markTaskComplete = (pid, taskId) =>
  post(`/patient/me/doses/${taskId}/confirm`, { status: 'Taken_Confirmed' }).catch(() => ({}));