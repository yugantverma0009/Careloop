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
  const user = {
    account_id: data.account_id,
    email: email,
    role: data.role,
    name: data.name,
    patient_id: data.patient_id,
    caregiver_id: data.caregiver_id,
    staff_id: data.staff_id,
  };
  setUser(user);
  return { ...data, user };
};

export const getMe = () => get('/auth/me');

// ─── Patient Endpoints ──────────────────────────────────────────────────────

export const getPatientToday = () => get('/patient/me/today');

export const getPatientCalendar = (month = null) =>
  get(`/patient/me/calendar${month ? `?month=${month}` : ''}`);

export const getPatientDay = (date) =>
  get(`/patient/me/day?date=${encodeURIComponent(date)}`);

export const downloadAppointmentIcs = async (appointmentId) => {
  const token = getToken();
  const res = await fetch(`${API_BASE}/patient/me/appointments/${appointmentId}.ics`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Failed to download calendar event: HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `appointment_${appointmentId}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

export const markDoseTaken = (logId, takenAt = null) =>
  post(`/patient/me/doses/${logId}/taken`, { taken_at: takenAt });

export const skipDose = (logId, reason = 'other') =>
  post(`/patient/me/doses/${logId}/skip`, { reason });

export const undoDose = (logId) =>
  post(`/patient/me/doses/${logId}/undo`, {});

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

export const submitPatientCheckin = ({
  pain_level = null,
  chips = [],
  sites = [],
  trend = null,
  text = '',
  language = 'en',
  input_method = 'Text',
}) =>
  post('/patient/me/checkins', {
    pain_level: pain_level === null ? null : Number(pain_level),
    chips,
    sites,
    trend,
    text,
    language,
    input_method,
  });

export const getPatientCheckins = (days = 14) =>
  get(`/patient/me/checkins?days=${days}`);

export const getMyStatus = () => get('/patient/me/status');

export const sendChatMessage = (message, language = 'en', conversation_id = null) =>
  post('/patient/me/chat', { message, language, conversation_id });

export const getChatHistory = () => get('/patient/me/chat/history');

export const askCareTeamForChatMessage = (messageId) =>
  post(`/patient/me/chat/${messageId}/ask-care-team`, {});

export const submitChatFeedback = (messageId, rating, comment = null) =>
  post(`/patient/me/chat/${messageId}/feedback`, { rating, comment });

// ─── Staff & Clinical Workflow Endpoints ─────────────────────────────────────

export const getStaffProfile = () => get('/staff/me/profile');

export const getStaffMembers = () => get('/staff/members');

export const getTriageBoard = () => get('/staff/triage');

export const getStaffWorklist = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return get(`/staff/worklist${query ? `?${query}` : ''}`);
};

export const getFlagDetail = (flagId) => get(`/staff/flags/${flagId}`);

export const acknowledgeFlag = (flagId, note = 'Acknowledged via portal', createTask = false) =>
  post(`/staff/flags/${flagId}/acknowledge`, { note, create_task: createTask });

export const resolveFlag = (flagId, resolutionCode, resolutionNote = '') =>
  post(`/staff/flags/${flagId}/resolve`, { resolution_code: resolutionCode, resolution_note: resolutionNote });

export const dismissFlag = (flagId, resolutionCode = 'False_Alarm', resolutionNote = '') =>
  post(`/staff/flags/${flagId}/dismiss`, { resolution_code: resolutionCode, resolution_note: resolutionNote });

export const assignFlag = (flagId, targetStaffId, note = '') =>
  post(`/staff/flags/${flagId}/assign`, { target_staff_id: targetStaffId, note });

export const escalateFlagNow = (flagId, note = '') =>
  post(`/staff/flags/${flagId}/escalate`, { note });

export const getFollowUps = () => get('/staff/follow-ups');

export const getStaffTasks = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return get(`/staff/tasks${query ? `?${query}` : ''}`);
};

export const claimTask = (taskId) =>
  post(`/staff/tasks/${taskId}/claim`, {});

export const assignTask = (taskId, targetStaffId, note = '') =>
  post(`/staff/tasks/${taskId}/assign`, { target_staff_id: targetStaffId, note });

export const completeTask = (taskId, outcomeCode, outcomeNotes = '') =>
  post(`/staff/tasks/${taskId}/complete`, { outcome_code: outcomeCode, outcome_notes: outcomeNotes });

export const snoozeTask = (taskId, hours, reason) =>
  post(`/staff/tasks/${taskId}/snooze`, { hours, reason });

export const getStaffSummaries = (params = {}) => {
  const query = new URLSearchParams(params).toString();
  return get(`/staff/summaries${query ? `?${query}` : ''}`);
};

export const generateClinicalSummary = (patientId, targetDate = null) =>
  post('/staff/summaries/generate', { patient_id: patientId, target_date: targetDate });

export const approveClinicalSummary = (summaryId, editedText = null) =>
  post(`/staff/summaries/${summaryId}/approve`, { edited_text: editedText });

export const rejectClinicalSummary = (summaryId, reason) =>
  post(`/staff/summaries/${summaryId}/reject`, { reason });

export const generateAllMineSummaries = () =>
  post('/staff/summaries/generate-all-mine', {});

export const getShiftHandoff = (scope = 'mine') =>
  get(`/staff/handoff?scope=${encodeURIComponent(scope)}`);

export const receivePatientHandoff = (patientId) =>
  post(`/staff/handoff/${patientId}/receive`, {});

export const updatePatientContingency = (patientId, contingencyNote) =>
  post(`/staff/handoff/${patientId}/contingency`, { contingency_note: contingencyNote });

export const logHandoffExport = (exportFormat = 'PDF') =>
  post('/staff/handoff/export-log', { export_format: exportFormat });

export const getFlagEscalations = (flagId) =>
  get(`/staff/flags/${flagId}/escalations`);

export const getStaffNotifications = () =>
  get('/staff/notifications');

export const logCommunication = (patientId, channel, outcome, summary = '', flagId = null, taskId = null) =>
  post('/staff/contacts/log', {
    patient_id: patientId,
    channel,
    outcome,
    summary,
    flag_id: flagId,
    task_id: taskId,
  });

export const getPatientContacts = (patientId) =>
  get(`/staff/patients/${patientId}/contacts`);

export const getPatientNotes = (patientId) =>
  get(`/staff/patients/${patientId}/notes`);

export const addPatientNote = (patientId, noteText, noteType = 'General', amendsNoteId = null) =>
  post(`/staff/patients/${patientId}/notes`, {
    note_text: noteText,
    note_type: noteType,
    amends_note_id: amendsNoteId,
  });

export const getPatientDirectory = (filter = 'all', search = '') =>
  get(`/staff/patients?filter=${encodeURIComponent(filter)}&search=${encodeURIComponent(search)}`);

export const getPatientDetail = (patientId) =>
  get(`/staff/patients/${patientId}`);

export const breakGlassAccess = (patientId, reason) =>
  post(`/staff/patients/${patientId}/break-glass`, { reason });

export const getPatientMedicines = (patientId) =>
  get(`/staff/patients/${patientId}/medicines`);

export const getPatientRules = (patientId) =>
  get(`/staff/patients/${patientId}/rules`);

export const getPatientTimeline = (patientId, eventTypes = 'All', dateRange = 'all', limit = 200) =>
  get(`/staff/patients/${patientId}/timeline?event_types=${encodeURIComponent(eventTypes)}&date_range=${encodeURIComponent(dateRange)}&limit=${limit}`);

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

export const getAuditLog = (params = {}) => {
  const q = new URLSearchParams();
  if (params.patient_id) q.set('patient_id', params.patient_id);
  if (params.staff_id) q.set('staff_id', params.staff_id);
  if (params.action) q.set('action', params.action);
  if (params.start_date) q.set('start_date', params.start_date);
  if (params.end_date) q.set('end_date', params.end_date);
  if (params.limit) q.set('limit', params.limit);
  return get(`/staff/audit-log?${q.toString()}`);
};

export const exportAuditLogAudit = (count, filters) =>
  post('/staff/audit-log/export-log', { count, filters });

export const globalStaffSearch = (term) =>
  get(`/staff/search?q=${encodeURIComponent(term)}`);

export const sendWoundImage = () => Promise.reject(new Error("AI wound diagnosis is disabled as per safety rule."));

export const triggerReminder = () => Promise.resolve({ ok: true });

export const submitPatientReply = () => Promise.resolve({ ok: true });

export const markTaskComplete = (pid, taskId) =>
  post(`/patient/me/doses/${taskId}/confirm`, { status: 'Taken_Confirmed' }).catch(() => ({}));