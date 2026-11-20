/**
 * src/services/api.js — CareLoop Centralized API Service
 *
 * Core Rule: "The LLM talks. Rules decide. Humans act."
 * All patient operations strictly use the authenticated JWT token.
 * Flags and clinical workflows are backed by MySQL 8.0 views & stored procedures.
 */

const getApiBase = () => {
  if (process.env.REACT_APP_API_URL) return process.env.REACT_APP_API_URL;
  if (typeof window !== 'undefined' && window.location.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return 'http://127.0.0.1:8000';
};

export const API_BASE = getApiBase();

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

const patch = (path, body) =>
  fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(body || {}),
  }).then(handleResponse);

const del = (path) =>
  fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
  }).then(handleResponse);

const postFormData = (path, formData) => {
  const token = getToken();
  return fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  }).then(handleResponse);
};

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

export const getAppointmentGoogleCalendarUrl = (appointmentId) =>
  get(`/patient/me/appointments/${appointmentId}/google-calendar-url`);

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

export const getChatHistory = (conversation_id = null) =>
  get(`/patient/me/chat/history${conversation_id ? `?conversation_id=${encodeURIComponent(conversation_id)}` : ''}`);

export const startNewChat = () => post('/patient/me/chat/new', {});

export const clearChatHistory = () => post('/patient/me/chat/clear', {});

export const askCareTeamForChatMessage = (messageId) =>
  post(`/patient/me/chat/${messageId}/ask-care-team`, {});

export const submitChatFeedback = (messageId, rating, comment = null) =>
  post(`/patient/me/chat/${messageId}/feedback`, { rating, comment });

// Phase 4: Action Cards & Proactive Updates
export const executePatientAction = (actionType, payload = {}) =>
  post(`/patient/me/actions/${actionType}`, payload);

export const getPatientUpdates = () => get('/patient/me/updates');

export const markPatientUpdateSeen = (updateId) =>
  post(`/patient/me/updates/${updateId}/seen`, {});

export const updatePatientSettings = (settings) =>
  patch('/patient/me/settings', settings);

export const getStaffAssistantQuestions = () =>
  get('/staff/assistant-questions');

export const replyAssistantQuestion = (messageId, replyText, templateId = null) =>
  post(`/staff/assistant-questions/${messageId}/reply`, { reply_text: replyText, template_id: templateId });

export const markAssistantQuestionDone = (messageId) =>
  post(`/staff/assistant-questions/${messageId}/done`, {});

export const getStaffAssistantReview = () =>
  get('/staff/assistant-review');

// ─── Staff & Clinical Workflow Endpoints ─────────────────────────────────────

export const getStaffProfile = () => get('/staff/me/profile');

const buildQuery = (params = {}) => {
  const clean = {};
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== 'undefined' && v !== 'null') {
      clean[k] = v;
    }
  });
  const q = new URLSearchParams(clean).toString();
  return q ? `?${q}` : '';
};

export const getStaffMembers = () => get('/staff/members');

export const getTriageBoard = () => get('/staff/triage');

export const getStaffWorklist = (params = {}) =>
  get(`/staff/worklist${buildQuery(params)}`);

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

export const getStaffTasks = (params = {}) =>
  get(`/staff/tasks${buildQuery(params)}`);

export const claimTask = (taskId) =>
  post(`/staff/tasks/${taskId}/claim`, {});

export const assignTask = (taskId, targetStaffId, note = '') =>
  post(`/staff/tasks/${taskId}/assign`, { target_staff_id: targetStaffId, note });

export const completeTask = (taskId, outcomeCode, outcomeNotes = '') =>
  post(`/staff/tasks/${taskId}/complete`, { outcome_code: outcomeCode, outcome_notes: outcomeNotes });

export const snoozeTask = (taskId, hours, reason) =>
  post(`/staff/tasks/${taskId}/snooze`, { hours, reason });

export const getStaffSummaries = (params = {}) =>
  get(`/staff/summaries${buildQuery(params)}`);

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


export const getPatientPipelineStatus = () => Promise.resolve({ status: 'active' });

export const getPatientPersonalization = () =>
  get('/patient/me/profile').catch(() => ({}));

export const sendVoiceMessage = () => Promise.reject(new Error("Voice clinical advice is disabled as per safety rule."));

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

export const sendWoundImage = () => Promise.reject(new Error("AI wound evaluation is disabled as per safety rule."));

export const triggerReminder = () => Promise.resolve({ ok: true });

export const submitPatientReply = () => Promise.resolve({ ok: true });

export const markTaskComplete = (pid, taskId) =>
  post(`/patient/me/doses/${taskId}/confirm`, { status: 'Taken_Confirmed' }).catch(() => ({}));

// ─── Phase 5: Governance & Interoperability ──────────────────────────────────

export const getPathwayTemplates = () =>
  get('/staff/pathway-templates');

export const applyPathwayTemplate = (patientId, templateId, rules) =>
  post(`/staff/patients/${patientId}/apply-pathway`, { template_id: templateId, rules });

export const getRuleHistory = (ruleId) =>
  get(`/staff/rules/${ruleId}/history`);

export const updateAlertRule = (ruleId, thresholdValue, reason, windowHours = null, severity = null) =>
  post(`/staff/rules/${ruleId}/update`, {
    threshold_value: thresholdValue,
    window_hours: windowHours,
    severity: severity,
    change_reason: reason,
  });

export const getOperationalInsights = (dateRange = '30d') =>
  get(`/staff/insights?date_range=${encodeURIComponent(dateRange)}`);

export const exportInsightsAudit = (dateRange = '30d') =>
  post('/staff/insights/export-log', { date_range: dateRange });

export const getPatientFhirBundle = (patientId) =>
  get(`/staff/patients/${patientId}/fhir`);

export const getPatientLace = (patientId) =>
  get(`/staff/patients/${patientId}/lace`);

export const recordPatientLace = (patientId, losDays, acute, charlson, edVisits) =>
  post(`/staff/patients/${patientId}/lace`, {
    length_of_stay_days: losDays,
    acute_admission: acute,
    charlson_index: charlson,
    ed_visits_6m: edVisits,
  });

// ─── Phase 2: Role Model, Family Helper & Consent ───────────────────────────

export const toggleFamilySharing = (enabled) =>
  post('/patient/me/sharing', { enabled });

export const getFamilySharingStatus = () =>
  get('/patient/me/sharing');

export const getFamilyToday = () =>
  get('/family/today');

export const confirmFamilyDoseHelped = (logId) =>
  post(`/family/doses/${logId}/helped`);

export const getFamilyCalendar = () =>
  get('/family/calendar');

export const getFamilyContacts = () =>
  get('/family/contacts');

export const escalateFlagToDoctor = (flagId, note = 'Nurse requested doctor review') =>
  post(`/staff/flags/${flagId}/escalate-doctor`, { note });

export const proposeLimitChange = (ruleId, thresholdValue, reason, windowHours = null, severity = null) =>
  post('/staff/rules/propose-limit', {
    rule_id: ruleId,
    threshold_value: thresholdValue,
    change_reason: reason,
    window_hours: windowHours,
    severity,
  });

export const getDoctorDecisions = () =>
  get('/staff/doctor/decisions');

export const getRuleProposals = () =>
  get('/staff/rules/proposals');

export const approveRuleProposal = (historyId) =>
  post(`/staff/rules/proposals/${historyId}/approve`, {});

export const rejectRuleProposal = (historyId, reason) =>
  post(`/staff/rules/proposals/${historyId}/reject`, { reason });

export const getAllApprovedRules = (patientId = null) =>
  get(`/staff/rules/all${patientId ? `?patient_id=${patientId}` : ''}`);

export const getNurseCallList = () =>
  get('/staff/nurse/call-list');

export const logContactCall = (data) =>
  post('/staff/contacts/log', data);

export const completeCareTask = (taskId, outcomeCode, outcomeNotes = '') =>
  post(`/staff/tasks/${taskId}/complete`, { outcome_code: outcomeCode, outcome_notes: outcomeNotes });

export const resolveRoutineFlag = (flagId, resolutionCode = 'Phone_Resolved', resolutionNote = 'Resolved via nurse telephone protocol') =>
  post(`/staff/flags/${flagId}/resolve`, { resolution_code: resolutionCode, resolution_note: resolutionNote });

export const resetDemo = () =>
  post('/demo/reset', {});

export const simulateReading = (payload = {}) =>
  post('/demo/simulate-reading', payload);

// ─── Feature F1: Rounds & Background Automation API ──────────────────────────

export const getRounds = () =>
  get('/staff/rounds');

export const pauseRounds = (patientId, hours, reason) =>
  post('/staff/rounds/pause', { patient_id: patientId, hours, reason });

export const resumeRounds = (patientId) =>
  post('/staff/rounds/resume', { patient_id: patientId });

export const runRoundsNow = () =>
  post('/staff/rounds/run-now', {});

export const getAgentActivity = (patientId) =>
  get(`/staff/patients/${patientId}/agent-activity`);

export const getAgentProposals = (status = 'Pending') =>
  get(`/staff/agent/proposals?status=${encodeURIComponent(status)}`);

export const acceptProposal = (proposalId) =>
  post(`/staff/agent/proposals/${proposalId}/accept`, {});

export const dismissProposal = (proposalId, dismissReason) =>
  post(`/staff/agent/proposals/${proposalId}/dismiss`, { dismiss_reason: dismissReason });

// ─── Feature F2 & F3: Check-in Guide & Two-Way SMS API ───────────────────────

export const getActiveCheckinTemplate = () =>
  get('/patient/me/checkin/template');

export const getPatientCheckinContext = (lang = 'en') =>
  get(`/patient/me/checkin/context?lang=${lang}`);

export const startCheckinSession = (channel = 'App_Guided') =>
  post('/patient/me/checkin/start', { channel });

export const recordCheckinAnswer = (sessionId, questionId, answerValue, rawInput = null, language = 'en') =>
  post('/patient/me/checkin/answer', {
    session_id: sessionId,
    question_id: questionId,
    answer_value: String(answerValue),
    raw_input: rawInput,
    language: language,
  });

export const getDoctorCheckinTemplates = () =>
  get('/staff/checkin-templates');

export const approveDoctorCheckinTemplate = (templateId) =>
  post(`/staff/checkin-templates/${templateId}/approve`, {});

export const getPhraseBank = () =>
  get('/staff/phrase-bank');

export const updatePhraseStatus = (phraseId, status) =>
  post(`/staff/phrase-bank/${phraseId}/status`, { status });

// ─── Phase 3: Recovery Coach & Medication Support API ───────────────────────

export const getPatientThreeThings = (lang = 'en') =>
  get(`/patient/me/three-things?lang=${lang}`);

export const recordDailyItemNotToday = (itemType, reasonCode, note = null) =>
  post(`/patient/me/daily-items/${itemType}/not-today`, { reason_code: reasonCode, note });

export const recordDoseBarrier = (medicationLogId, reasonCode, note = null) =>
  post('/patient/me/dose-barriers', { medication_log_id: medicationLogId, reason_code: reasonCode, note });

export const getPatientWeeklyRecap = (lang = 'en') =>
  get(`/patient/me/weekly-recap?lang=${lang}`);

export const updatePatientReminderPreferences = (leadMin, channelPref, lang = null) =>
  post('/patient/me/preferences/reminders', { reminder_lead_min: leadMin, channel_pref: channelPref, language: lang });

export const simulateInboundSms = (fromPhone, body) =>
  post('/staff/sms/simulate-inbound', { from_phone: fromPhone, body });

export const getPatientSmsMessages = (patientId) =>
  get(`/staff/patients/${patientId}/messages`);

// ─── Feature F5 & F6: Recovery Plan & Patient Admission API ──────────────────

export const getMyPlan = () =>
  get('/patient/me/plan');

export const getPatientUnderstandingCheck = () =>
  get('/patient/me/plan/understanding-check');

export const submitUnderstandingAnswer = (checkId, selectedIndex) =>
  post('/patient/me/plan/understanding-check/answer', {
    check_id: checkId,
    selected_option_index: selectedIndex,
  });

export const draftRecoveryPlan = (patientId, sourceDocumentId = null) =>
  post('/staff/plans/draft', {
    patient_id: patientId,
    source_document_id: sourceDocumentId,
  });

export const getPendingRecoveryPlans = () =>
  get('/staff/plans/pending');

export const getStaffPatientPlans = (patientId) =>
  get(`/staff/patients/${patientId}/plans`);

export const verifyPlanItem = (itemId) =>
  post(`/staff/plans/items/${itemId}/verify`);

export const approveRecoveryPlan = (planId) =>
  post(`/staff/plans/${planId}/approve`);

export const rejectRecoveryPlan = (planId, reason = '') =>
  post(`/staff/plans/${planId}/reject`, { reason });

export const admitPatient = (payload) =>
  post('/staff/admit', payload);

// ─── Watch Events & Possible Fall Endpoints ─────────────────────────────────

export const getFallPrompt = () => get('/patient/me/fall-prompt');

export const submitFallResponse = (eventId, response) =>
  post('/patient/me/fall-response', { event_id: eventId, response });

export const sendDeviceEvent = (payload) =>
  fetch(`${API_BASE}/device/events`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Device-Key': 'demo-device-key-change-me',
    },
    body: JSON.stringify(payload),
  }).then(handleResponse);

export const sendDeviceReading = (payload) =>
  fetch(`${API_BASE}/device/readings`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Device-Key': 'demo-device-key-change-me',
    },
    body: JSON.stringify(payload),
  }).then(handleResponse);

// ─── CareLoop Agents v2: Health, Incidents & Circuit Breaker API ────────────

export const getAgentHealth = (window = '24h') =>
  get(`/agent/health?window=${encodeURIComponent(window)}`);

export const reportAgentIncident = (runId, category, note) =>
  post('/agent/incidents', { run_id: runId, category, note });

export const getCandidateTests = (status = null) =>
  get(status ? `/agent/candidate-tests?status=${encodeURIComponent(status)}` : '/agent/candidate-tests');

export const approveCandidateTest = (candidateId) =>
  post(`/agent/candidate-tests/${candidateId}/approve`, {});

export const rejectCandidateTest = (candidateId) =>
  post(`/agent/candidate-tests/${candidateId}/reject`, {});

export const getCircuitBreakerDemotions = () =>
  get('/agent/circuit-breaker/demotions');

export const evaluateCircuitBreaker = () =>
  post('/agent/circuit-breaker/evaluate', {});

// ─── Phase 5: Proactive Help, Approved Examples & Transparency API ────────────

export const getPatientTransparency = () =>
  get('/patient/me/transparency');

export const getPatientVisitPrep = () =>
  get('/patient/me/visit-prep');

export const updatePatientConsent = (consentGranted, noticeVersion = null) =>
  post('/patient/me/consent', { consent_granted: consentGranted, notice_version: noticeVersion });

export const triggerPatternDetection = (patientId = null) =>
  post(patientId ? `/staff/patterns/detect?patient_id=${patientId}` : '/staff/patterns/detect', {});

export const getAgentExemplars = (draftType, limit = 3) =>
  get(`/agent/exemplars/${encodeURIComponent(draftType)}?limit=${limit}`);

export const generatePatientDayBrief = (language = 'en') =>
  post(`/patient/me/day-brief?language=${encodeURIComponent(language)}`, {});

// ─── Phase 4: Trust, Transparency & Safety API (5.F, 5.G, 5.H) ────────────────

export const getWhyToldExplainer = (flagId = null, lang = 'en') =>
  get(`/patient/me/why-told?${flagId ? `flag_id=${flagId}&` : ''}lang=${encodeURIComponent(lang)}`);

export const getReadingsTrend = (type = 'SpO2') =>
  get(`/patient/me/readings-trend?type=${encodeURIComponent(type)}`);

export const requestHelpCall = (category, note = null) =>
  post('/patient/me/help-call', { category, note });

export const getAiTransparency = () =>
  get('/patient/me/ai-transparency');

export const toggleAiHelp = (enabled) =>
  post('/patient/me/ai-help', { enabled });

export const requestChatPrivacy = (actionType) =>
  post('/patient/me/chat-privacy', { action_type: actionType });

// ─── Phase 5: Comprehension, Planning & Teach-back API (5.E, 5.I) ──────────────

export const explainSimply = (text, language = 'en') =>
  post('/patient/me/explain-simply', { text, language });

export const getSavedQuestions = () =>
  get('/patient/me/saved-questions');

export const saveQuestion = (questionText, forAppointmentId = null) =>
  post('/patient/me/saved-questions', { question_text: questionText, for_appointment_id: forAppointmentId });

export const dismissSavedQuestion = (questionId) =>
  del(`/patient/me/saved-questions/${questionId}`);

export const getTeachBack = () =>
  get('/patient/me/teach-back');

export const submitTeachBackAnswer = (checkId, selectedOptionIndex) =>
  post('/patient/me/teach-back/answer', { check_id: checkId, selected_option_index: selectedOptionIndex });

export const planMyDay = (language = 'en') =>
  post('/patient/me/plan-my-day', { language });

export const getPlanIcsUrl = () =>
  `${API_BASE}/patient/me/plan-my-day/ics`;








