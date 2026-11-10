const API_BASE = import.meta.env.VITE_API_URL !== undefined ? import.meta.env.VITE_API_URL : '';

export function getToken() {
  return localStorage.getItem('securerag_token');
}

export function setToken(token) {
  if (token) {
    localStorage.setItem('securerag_token', token);
  } else {
    localStorage.removeItem('securerag_token');
  }
}

export function getUser() {
  const u = localStorage.getItem('securerag_user');
  return u ? JSON.parse(u) : null;
}

export function setUser(user) {
  if (user) {
    localStorage.setItem('securerag_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('securerag_user');
  }
}

async function request(endpoint, options = {}) {
  const headers = { ...options.headers };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err) {
    if (err.name === 'TypeError' || err.message?.toLowerCase().includes('fetch')) {
      throw new Error(`Cannot reach backend server. Please make sure the FastAPI backend is running on port 8000.`);
    }
    throw err;
  }

  if (!res.ok) {
    if (res.status === 401 && endpoint !== '/auth/login' && endpoint !== '/auth/register') {
      setToken(null);
      setUser(null);
      window.location.reload();
      throw new Error('Session expired. Please sign in again.');
    }
    let errDetail = 'Request failed';
    try {
      const text = await res.text();
      try {
        const errJson = JSON.parse(text);
        errDetail = errJson.detail || JSON.stringify(errJson);
      } catch {
        errDetail = text || `Request failed with status ${res.status}`;
      }
    } catch {
      errDetail = `Request failed with status ${res.status}`;
    }
    const err = new Error(errDetail);
    err.status = res.status;
    throw err;
  }

  return res.json();
}

export const api = {
  // Auth
  register: (data) => request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  // Organizations & Teams
  listMembers: () => request('/orgs/members'),
  inviteMember: (data) => request('/orgs/members', { method: 'POST', body: JSON.stringify(data) }),
  listTeams: () => request('/teams'),
  listTeamMembers: (teamId) => request(`/teams/${teamId}/members`),
  createTeam: (data) => request('/teams', { method: 'POST', body: JSON.stringify(data) }),
  addTeamMember: (teamId, userId) => request(`/teams/${teamId}/members`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }),

  // Documents
  listDocuments: () => request('/documents'),
  uploadDocument: (formData) => request('/documents', { method: 'POST', body: formData }),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),

  // Query & Chat
  runQuery: (data) => request('/query', { method: 'POST', body: JSON.stringify(data) }),
  submitFeedback: (data) => request('/feedback', { method: 'POST', body: JSON.stringify(data) }),

  // Evals & Metrics
  listEvalRuns: () => request('/evals/runs'),
  getEvalRunDetail: (runId) => request(`/evals/runs/${runId}`),
  runEval: (data) => request('/evals/run', { method: 'POST', body: JSON.stringify(data) }),
  listEvalCases: () => request('/evals/cases'),
  createEvalCase: (data) => request('/evals/cases', { method: 'POST', body: JSON.stringify(data) }),
  promoteFeedback: (data) => request('/evals/promote-feedback', { method: 'POST', body: JSON.stringify(data) }),

  // Admin & Usage
  getUsage: () => request('/admin/usage'),
  listApiKeys: () => request('/api-keys'),
  createApiKey: () => request('/api-keys', { method: 'POST' }),
  revokeApiKey: (id) => request(`/api-keys/${id}`, { method: 'DELETE' }),
};
