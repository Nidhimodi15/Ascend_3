/**
 * app.js — Main dashboard controller & Security Layer Integrator.
 * Binds buttons, manages state, handles Auth & Audit logs,
 * and orchestrates MySQL → WriteOperation → API → render pipeline.
 *
 * RUNTIME DATA FLOW:
 *   MySQL DB → fetch transactions → user selects txn_id
 *   → POST /run-all {txn_id} → backend fetches from MySQL
 *   → WriteOperation → 12 hooks → Recovery → Invariants → Agent
 */

import {
  API, setAuthToken, getAuthToken, setOnUnauthorized
} from './api.js';
import {
  renderHookGrid, renderStats, resetStats,
  renderInspector, resetInspector,
  renderComparison, hideComparison,
  openInspectModal, closeInspectModal,
  renderAgentReport,
} from './components.js';
import { renderTimeline, resetTimeline } from './timeline.js';
import { logEvent, clearLog, animateCounter, shake } from './animations.js';

// ─── State ───────────────────────────────────────────────────────────────────
let currentReport    = null;
let currentTxnId     = null;   // Selected MySQL transaction ID (e.g. "T101")
let currentStrategy  = 'naive';
let currentUser      = null;
let mysqlTransactions = [];    // Cache of fetched MySQL transactions

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setOnUnauthorized(onUnauthorizedAccess);
  bindControls();
  bindAuthControls();
  renderHookGrid(null, () => {});
  resetTimeline();
  logEvent(null, 'KillPoint Verifier ready.', 'info');

  // Load MySQL transactions silently in background (no visible panel)
  loadMySQLTransactions();

  // Auto-check auth & security panel status
  refreshSecurityAudit();
});

// ─── MySQL Status Panel ───────────────────────────────────────────────────────

async function loadMySQLStatus() {
  const badge   = document.getElementById('mysql-status-badge');
  const connVal = document.getElementById('mysql-conn-val');
  const dbVal   = document.getElementById('mysql-db-val');
  const cntVal  = document.getElementById('mysql-count-val');
  const tblVal  = document.getElementById('mysql-table-val');

  try {
    const status = await API.mysqlStatus();

    if (status.connected) {
      if (badge)   { badge.textContent = 'CONNECTED'; badge.className = 'control-status-badge safe'; }
      if (connVal) { connVal.textContent = `✓ Connected  (${status.host})`; connVal.className = 'mysql-status-val connected'; }
      if (dbVal)   { dbVal.textContent = status.database; }
      if (cntVal)  { cntVal.textContent = `${status.row_count} transaction(s)`; }
      if (tblVal)  { tblVal.textContent = status.table; }
    } else {
      renderMySQLError(status.error);
    }
  } catch (err) {
    renderMySQLError(err.message);
  }
}

function renderMySQLError(msg) {
  const badge   = document.getElementById('mysql-status-badge');
  const connVal = document.getElementById('mysql-conn-val');
  const notice  = document.getElementById('mysql-seed-notice');
  const select  = document.getElementById('mysql-txn-select');

  if (badge)   { badge.textContent = 'DISCONNECTED'; badge.className = 'control-status-badge bug'; }
  if (connVal) { connVal.textContent = `✗ Error — ${msg}`; connVal.className = 'mysql-status-val disconnected'; }
  if (notice)  { notice.classList.remove('hidden'); notice.innerHTML = `⚠ MySQL connection failed. <br>Make sure MySQL is running and run: <code>python scripts/seed_mysql.py</code>`; }
  if (select)  { select.innerHTML = '<option value="">— MySQL unavailable —</option>'; }
  logEvent(null, `MySQL connection failed: ${msg}`, 'bug');
}

async function loadMySQLTransactions() {
  const select  = document.getElementById('mysql-txn-select');
  const infoBox = document.getElementById('mysql-txn-info');

  try {
    const data = await API.mysqlTransactions();
    mysqlTransactions = data.transactions || [];

    if (!select) return;

    if (mysqlTransactions.length === 0) {
      select.innerHTML = '<option value="">No transactions found in MySQL database</option>';
      if (infoBox) infoBox.innerHTML = '<span style="color:var(--warning);">No records found in MySQL. Please run python scripts/seed_mysql.py.</span>';
      return;
    }

    select.innerHTML = '';
    mysqlTransactions.forEach(txn => {
      const opt = document.createElement('option');
      opt.value = txn.txn_id;
      opt.textContent = `${txn.txn_id}: SET "${txn.acct_key}" = ${txn.value} (Ver: ${txn.version})`;
      select.appendChild(opt);
    });

    // Auto-select first transaction
    select.value = mysqlTransactions[0].txn_id;
    onTransactionSelected();
    logEvent(null, `Loaded ${mysqlTransactions.length} transactions. Active: ${mysqlTransactions[0].txn_id}`, 'safe');

  } catch (err) {
    if (select) {
      select.innerHTML = `<option value="">Error loading transactions: ${err.message}</option>`;
    }
  }
}


function onTransactionSelected() {
  const select   = document.getElementById('mysql-txn-select');
  const infoBox  = document.getElementById('mysql-txn-info');

  if (!select || !select.value) {
    currentTxnId = null;
    if (infoBox) infoBox.innerHTML = '<span style="color:var(--text-muted);">No transaction selected</span>';
    return;
  }

  currentTxnId = select.value;
  const txn = mysqlTransactions.find(t => t.txn_id === currentTxnId);

  if (infoBox && txn) {
    infoBox.innerHTML = `
      <div class="txn-field"><span class="txn-key" style="color:var(--text-muted);font-weight:600;">Transaction:</span> <span class="txn-val" style="color:var(--accent-light);font-weight:700;">${txn.txn_id}</span></div>
      <div class="txn-field"><span class="txn-key" style="color:var(--text-muted);">Account Key:</span> <span class="txn-val" style="color:var(--text-primary);font-weight:600;">${txn.acct_key}</span></div>
      <div class="txn-field"><span class="txn-key" style="color:var(--text-muted);">Operation:</span> <span class="txn-val" style="color:var(--safe);font-weight:700;">SET</span></div>
      <div class="txn-field"><span class="txn-key" style="color:var(--text-muted);">New Value:</span> <span class="txn-val" style="color:#38bdf8;font-weight:600;">${txn.value}</span></div>
      <div class="txn-field"><span class="txn-key" style="color:var(--text-muted);">Old Value:</span> <span class="txn-val" style="color:var(--text-muted);">${txn.old_value !== null ? txn.old_value : 'null'}</span></div>
      <div class="txn-field"><span class="txn-key" style="color:var(--text-muted);">Version:</span> <span class="txn-val" style="color:var(--text-secondary);">${txn.version}</span></div>
    `;
    infoBox.classList.remove('hidden');
  }
}


// ─── Control Bindings ─────────────────────────────────────────────────────────
function bindControls() {
  // Strategy toggle
  document.querySelectorAll('.strategy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.strategy-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentStrategy = btn.dataset.strategy;
      const stratEl = document.getElementById('stat-strategy');
      if (stratEl) stratEl.textContent = currentStrategy.toUpperCase();

      // Clear previous results on strategy switch
      currentReport = null;
      closeInspectModal();
      resetStats();
      resetInspector();
      hideComparison();
      resetTimeline();
      renderHookGrid(null, () => {});
      clearLog();
      logEvent(null, `Strategy set to '${currentStrategy.toUpperCase()}'. Ready to verify.`, 'info');
    });
  });

  // Admin Transaction Selector change listener
  const txnSelect = document.getElementById('mysql-txn-select');
  if (txnSelect) {
    txnSelect.addEventListener('change', () => {
      onTransactionSelected();
      if (currentTxnId) {
        logEvent(null, `Selected transaction: ${currentTxnId}. Ready to verify.`, 'info');
      }
    });
  }

  // Run all
  document.getElementById('btn-run-all').addEventListener('click', onRunAll);

  // Compare
  document.getElementById('btn-compare').addEventListener('click', onCompare);

  // Agent Investigate
  const agentBtn = document.getElementById('btn-agent-investigate');
  if (agentBtn) {
    agentBtn.addEventListener('click', onStartInvestigation);
  }
}

// ─── Auth Controls & Modal ────────────────────────────────────────────────────
function bindAuthControls() {
  const headerAuthBtn = document.getElementById('btn-header-auth');
  const loginForm     = document.getElementById('login-form');
  const loginCloseBtn = document.getElementById('login-close-btn');

  if (headerAuthBtn) {
    headerAuthBtn.addEventListener('click', () => {
      if (currentUser || getAuthToken()) {
        // Logout
        setAuthToken('');
        currentUser = null;
        updateAuthUI(false);
        logEvent(null, 'User logged out. Authentication required for verification APIs.', 'info');
        refreshSecurityAudit();
      } else {
        openLoginModal();
      }
    });
  }

  if (loginCloseBtn) {
    loginCloseBtn.addEventListener('click', closeLoginModal);
  }

  if (loginForm) {
    loginForm.addEventListener('submit', onLoginSubmit);
  }
}

function openLoginModal() {
  const modal  = document.getElementById('login-modal-overlay');
  const errMsg = document.getElementById('login-error-msg');
  if (errMsg) errMsg.classList.add('hidden');
  if (modal)  modal.classList.remove('hidden');
}

function closeLoginModal() {
  const modal = document.getElementById('login-modal-overlay');
  if (modal) modal.classList.add('hidden');
}

function onUnauthorizedAccess() {
  updateAuthUI(false);
  openLoginModal();
}

async function onLoginSubmit(e) {
  e.preventDefault();
  const userInp = document.getElementById('login-username');
  const passInp = document.getElementById('login-password');
  const errMsg  = document.getElementById('login-error-msg');

  const username = userInp ? userInp.value.trim() : 'admin';
  const password = passInp ? passInp.value.trim() : '';

  try {
    const res = await API.login(username, password);
    setAuthToken(res.token);
    currentUser = res.username;
    updateAuthUI(true);
    closeLoginModal();
    logEvent(null, `Authenticated successfully as '${res.username}'.`, 'safe');
    refreshSecurityAudit();
  } catch (err) {
    if (errMsg) {
      errMsg.textContent = err.message || 'Invalid username or password';
      errMsg.classList.remove('hidden');
    }
    shake(document.getElementById('login-form'));
  }
}

function updateAuthUI(authenticated) {
  const label = document.getElementById('header-auth-label');
  const val   = document.getElementById('sec-auth-val');

  if (authenticated || getAuthToken()) {
    if (label) label.textContent = 'Logout';
    if (val) {
      val.textContent = `Authenticated (${currentUser || 'admin'})`;
      val.className = 'sec-value safe';
    }
  } else {
    if (label) label.textContent = 'Login';
    if (val) {
      val.textContent = 'Unauthenticated (401)';
      val.className = 'sec-value bug';
    }
  }
}

// ─── Security & Audit Panel Refresh ──────────────────────────────────────────
async function refreshSecurityAudit() {
  try {
    const statusData = await API.authStatus();
    if (statusData) {
      const encVal   = document.getElementById('sec-enc-val');
      const auditVal = document.getElementById('sec-audit-val');
      if (encVal)   encVal.textContent   = `${statusData.encryption.algorithm} (Active)`;
      if (auditVal) auditVal.textContent = `Active (${statusData.audit_logging.total_events} events)`;
    }

    const auditData = await API.auditLogs();
    if (auditData && auditData.events) {
      renderAuditLogs(auditData.events);
      updateAuthUI(true);
    }
  } catch (err) {
    // If 401 unauthenticated
    updateAuthUI(false);
  }
}

function renderAuditLogs(events) {
  const container = document.getElementById('sec-audit-events');
  const countTag  = document.getElementById('sec-event-count');
  if (!container) return;

  if (countTag) countTag.textContent = `${events.length} event(s)`;

  if (!events || events.length === 0) {
    container.innerHTML = `<div class="empty-state" style="padding:15px;font-size:12px;">No audit events logged yet.</div>`;
    return;
  }

  container.innerHTML = '';
  events.slice(0, 10).forEach(ev => {
    const row = document.createElement('div');
    row.className = 'sec-event-row';

    const timeStr = ev.timestamp ? ev.timestamp.split('T')[1].slice(0, 8) : '';
    const descStr = ev.masked_details || (ev.hook ? `Hook ${ev.hook} (${ev.verdict})` : ev.action);

    row.innerHTML = `
      <span class="sec-event-action">${ev.action}</span>
      <span class="sec-event-details">${descStr}</span>
      <span class="sec-event-user">${ev.user} @ ${timeStr}</span>
    `;
    container.appendChild(row);
  });
}

// ─── Run All 12 Hooks — Transaction Path ─────────────────────────────────────
async function onRunAll() {
  if (!currentTxnId) {
    // If no transaction loaded yet, wait silently
    logEvent(null, 'Loading transaction data, please try again...', 'info');
    return;
  }

  const btn = document.getElementById('btn-run-all');
  setLoading(btn, true);
  closeInspectModal();
  clearLog();
  resetInspector();
  hideComparison();
  resetStats();

  logEvent(null, `Starting verification: transaction=${currentTxnId}, strategy=${currentStrategy.toUpperCase()}`, 'info');

  setPipelineStep(3);

  try {
    // Send txn_id → backend fetches from DB → WriteOperation → engine
    const report = await API.runAll(currentTxnId, currentStrategy);
    currentReport = report;

    const verdicts = {};
    report.results.forEach(r => { verdicts[r.hook] = r.verdict; });

    renderHookGrid(report.results, onHookSelected);
    renderStats(report);

    animateCounter(document.getElementById('stat-safe'), report.total_safe);
    animateCounter(document.getElementById('stat-bugs'), report.total_bugs);

    setPipelineStep(5);
    renderTimeline(null, verdicts);

    report.results.forEach(r => {
      const type = r.verdict === 'BUG' ? 'bug' : 'safe';
      const msg  = r.verdict === 'BUG'
        ? `[BUG] Hook ${r.hook} (${r.step_description}): ${r.violations.join(', ')}`
        : `[PASS] Hook ${r.hook} (${r.step_description}): all invariants satisfied`;
      logEvent(r.hook, msg, type);
    });

    logEvent(null,
      `Verification complete: ${report.total_safe} safe, ${report.total_bugs} bugs discovered.`,
      report.total_bugs > 0 ? 'bug' : 'safe'
    );

    refreshSecurityAudit();

  } catch (err) {
    setPipelineStep(1);
    logEvent(null, `Error: ${err.message}`, 'bug');
    shake(document.getElementById('btn-run-all'));
  } finally {
    setLoading(btn, false);
  }
}

function setPipelineStep(stepNum) {
  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById(`pipe-step-${i}`);
    if (el) {
      if (i <= stepNum) el.classList.add('active');
      else el.classList.remove('active');
    }
  }
}

// ─── Hook Card Selected ───────────────────────────────────────────────────────
function onHookSelected(result) {
  const verdicts = {};
  currentReport.results.forEach(r => { verdicts[r.hook] = r.verdict; });
  renderTimeline(result.hook, verdicts);
  renderInspector(result, onReproduce);
  openInspectModal(result, currentStrategy, onReproduce);

  logEvent(result.hook,
    `Inspecting Hook ${result.hook}: ${result.step_description}`,
    result.verdict === 'BUG' ? 'bug' : 'info'
  );
}

// ─── Reproduce Path ───────────────────────────────────────────────────────────
async function onReproduce(hookNum) {
  const btn = document.getElementById('reproduce-btn');
  setLoading(btn, true);
  logEvent(hookNum, `Reproducing deterministically [Txn:${currentTxnId}] hook ${hookNum}...`, 'info');

  try {
    const res = await API.reproduce(currentTxnId, hookNum, currentStrategy);
    if (res.reproducible) {
      logEvent(hookNum,
        `[REPRODUCED] Verdict: ${res.result.verdict} — identical to original run.`,
        res.result.verdict === 'BUG' ? 'bug' : 'safe'
      );
    }
    refreshSecurityAudit();
  } catch (err) {
    logEvent(hookNum, `Reproduce error: ${err.message}`, 'bug');
  } finally {
    setLoading(btn, false);
  }
}

// ─── Compare Path ─────────────────────────────────────────────────────────────
async function onCompare() {
  if (!currentTxnId) {
    logEvent(null, 'Loading transaction data, please try again...', 'info');
    return;
  }

  const btn = document.getElementById('btn-compare');
  setLoading(btn, true);
  clearLog();
  closeInspectModal();
  logEvent(null, `Comparing naive vs safe recovery [Txn:${currentTxnId}]...`, 'info');

  try {
    const data = await API.compare(currentTxnId);
    renderComparison(data.naive, data.safe);

    logEvent(null,
      `Naive: ${data.naive.total_bugs} bug(s) | Safe: ${data.safe.total_bugs} bug(s) [Txn:${currentTxnId}]`,
      data.naive.total_bugs > 0 ? 'bug' : 'safe'
    );
    logEvent(null, 'The verifier discovered whichever hooks violate invariants at runtime.', 'info');
    refreshSecurityAudit();
  } catch (err) {
    logEvent(null, `Compare error: ${err.message}`, 'bug');
    shake(btn);
  } finally {
    setLoading(btn, false);
  }
}

// ─── Autonomous Root-Cause Investigator Path ──────────────────────────────────
async function onStartInvestigation() {
  if (!currentTxnId) {
    logEvent(null, 'Loading transaction data, please try again...', 'info');
    return;
  }

  const btn        = document.getElementById('btn-agent-investigate');
  const hookSelect = document.getElementById('agent-hook-select');
  const hookVal    = hookSelect ? hookSelect.value : 'sweep';

  let initialHook = null;
  if (hookVal !== 'sweep') {
    initialHook = parseInt(hookVal, 10);
  }

  setLoading(btn, true);
  logEvent(null, `Starting Autonomous Investigation [MySQL:${currentTxnId}], target_hook=${initialHook || 'auto'}...`, 'info');

  const statusBadge = document.getElementById('agent-status-badge');
  if (statusBadge) {
    statusBadge.textContent = 'RUNNING INVESTIGATION...';
    statusBadge.className = 'control-status-badge warning';
  }

  try {
    const report = await API.investigate(currentTxnId, currentStrategy, initialHook);
    renderAgentReport(report);

    logEvent(null,
      `Autonomous Investigation completed [MySQL:${currentTxnId}]. Root Cause: ${report.root_cause_confirmed ? 'CONFIRMED' : 'NOT CONFIRMED'}.`,
      report.root_cause_confirmed ? 'bug' : 'safe'
    );
    refreshSecurityAudit();
  } catch (err) {
    logEvent(null, `Agent Investigation error: ${err.message}`, 'bug');
    shake(btn);
  } finally {
    setLoading(btn, false);
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  if (loading) {
    btn._original = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Running...`;
  } else {
    btn.innerHTML = btn._original || btn.innerHTML;
  }
}
