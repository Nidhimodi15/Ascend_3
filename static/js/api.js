/**
 * api.js — REST client for the KillPoint backend with Bearer token authentication.
 */

const BASE = '/api';
let authToken = localStorage.getItem('kp_session_token') || '';
let onUnauthorizedCallback = null;

export function setAuthToken(token) {
  authToken = token;
  if (token) {
    localStorage.setItem('kp_session_token', token);
  } else {
    localStorage.removeItem('kp_session_token');
  }
}

export function getAuthToken() {
  return authToken;
}

export function setOnUnauthorized(cb) {
  onUnauthorizedCallback = cb;
}

function _getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  return headers;
}

async function _post(endpoint, body = {}) {
  const res = await fetch(`${BASE}${endpoint}`, {
    method: 'POST',
    headers: _getHeaders(),
    body: JSON.stringify(body),
  });

  if (res.status === 401) {
    if (onUnauthorizedCallback) onUnauthorizedCallback();
    const err = await res.json().catch(() => ({ detail: 'Unauthorized' }));
    throw new Error(err.detail || 'Authentication required');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function _get(endpoint) {
  const res = await fetch(`${BASE}${endpoint}`, {
    headers: _getHeaders(),
  });

  if (res.status === 401) {
    if (onUnauthorizedCallback) onUnauthorizedCallback();
    const err = await res.json().catch(() => ({ detail: 'Unauthorized' }));
    throw new Error(err.detail || 'Authentication required');
  }

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const API = {
  health:          ()               => _get('/health'),
  hooks:           ()               => _get('/hooks'),
  login:           (username, password) => _post('/auth/login', { username, password }),
  authStatus:      ()               => _get('/auth/status'),
  auditLogs:       ()               => _get('/security/audit-logs'),
  runAll:          (seed, strategy) => _post('/run-all',  { seed, strategy }),
  compare:         (seed)           => _post('/compare',  { seed }),
  reproduce:       (seed, hook, strategy) => _post('/reproduce', { seed, hook, strategy }),
  investigate:     (seed, strategy, initial_hook) => _post('/agent/investigate', { seed, strategy, initial_hook }),
};

