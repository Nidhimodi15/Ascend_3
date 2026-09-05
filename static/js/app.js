/**
 * app.js — Main dashboard controller & Security Layer Integrator.
 * Binds buttons, manages state, handles Auth & Audit logs,
 * and orchestrates API → render → animate pipeline.
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
let currentReport   = null;
let currentSeed     = 48291;
let currentStrategy = 'naive';
let currentUser     = null;

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setOnUnauthorized(onUnauthorizedAccess);
  bindControls();
  bindAuthControls();
  renderHookGrid(null, () => {});
  resetTimeline();
  logEvent(null, 'KillPoint Verifier ready. Select a seed and strategy, then run.', 'info');
  
  // Auto-check auth & security panel status
  refreshSecurityAudit();
});

// ─── Control Bindings ─────────────────────────────────────────────────────────
function bindControls() {
  // Seed input
  const seedInput = document.getElementById('seed-input');
  seedInput.value = currentSeed;
  seedInput.addEventListener('change', () => {
    const v = parseInt(seedInput.value, 10);
    if (!isNaN(v) && v > 0) {
      currentSeed = v;
    } else {
      seedInput.value = currentSeed;
      shake(seedInput);
    }
  });

  // Strategy toggle
  document.querySelectorAll('.strategy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.strategy-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentStrategy = btn.dataset.strategy;
      document.getElementById('stat-strategy').textContent = currentStrategy.toUpperCase();

      // Clear previous verification results and close modal on strategy switch
      currentReport = null;
      closeInspectModal();
      resetStats();
      resetInspector();
      hideComparison();
      resetTimeline();
      renderHookGrid(null, () => {});
      clearLog();
      logEvent(null, `Strategy set to '${currentStrategy.toUpperCase()}'. Run verification to execute backend engine.`, 'info');
    });
  });

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
  const modal = document.getElementById('login-modal-overlay');
  const errMsg = document.getElementById('login-error-msg');
  if (errMsg) errMsg.classList.add('hidden');
  if (modal) modal.classList.remove('hidden');
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
      if (encVal) encVal.textContent = `${statusData.encryption.algorithm} (Active)`;
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
  const container  = document.getElementById('sec-audit-events');
  const countTag   = document.getElementById('sec-event-count');
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

// ─── Run All 12 Hooks ─────────────────────────────────────────────────────────
async function onRunAll() {
  const btn = document.getElementById('btn-run-all');
  setLoading(btn, true);
  closeInspectModal();
  clearLog();
  resetInspector();
  hideComparison();
  resetStats();

  logEvent(null, `Starting verification: seed=${currentSeed}, strategy=${currentStrategy}`, 'info');

  // Pipeline step visual feedback
  setPipelineStep(3);

  try {
    const report = await API.runAll(currentSeed, currentStrategy);
    currentReport = report;

    // Build verdicts map for timeline
    const verdicts = {};
    report.results.forEach(r => { verdicts[r.hook] = r.verdict; });

    // Render grid
    renderHookGrid(report.results, onHookSelected);

    // Render stats
    renderStats(report);

    // Animate counters
    animateCounter(document.getElementById('stat-safe'), report.total_safe);
    animateCounter(document.getElementById('stat-bugs'), report.total_bugs);

    // Complete pipeline step
    setPipelineStep(5);

    // Reset timeline (no specific hook selected yet)
    renderTimeline(null, verdicts);

    // Log each result
    report.results.forEach(r => {
      const type = r.verdict === 'BUG' ? 'bug' : 'safe';
      const msg  = r.verdict === 'BUG'
        ? `[BUG DISCOVERED] — ${r.step_description} → ${r.bug_details || 'Invariant failure'}`
        : `[SAFE] — ${r.step_description}`;
      logEvent(r.hook, msg, type);
    });

    logEvent(null,
      `Verification complete. ${report.total_bugs} bug(s) discovered out of 12 hooks.`,
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
  // Update timeline to show crash point
  const verdicts = {};
  currentReport.results.forEach(r => { verdicts[r.hook] = r.verdict; });
  renderTimeline(result.hook, verdicts);

  // Render inspector panel
  renderInspector(result, onReproduce);

  // Open "Why BUG? / Inspect" Modal Panel with dynamic backend data
  openInspectModal(result, currentStrategy, onReproduce);

  logEvent(result.hook,
    `Inspecting Hook ${result.hook}: ${result.step_description}`,
    result.verdict === 'BUG' ? 'bug' : 'info'
  );
}

// ─── Reproduce ────────────────────────────────────────────────────────────────
async function onReproduce(hookNum) {
  const btn = document.getElementById('reproduce-btn');
  setLoading(btn, true);
  logEvent(hookNum, `Reproducing deterministically with seed=${currentSeed}...`, 'info');

  try {
    const res = await API.reproduce(currentSeed, hookNum, currentStrategy);
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

// ─── Compare ─────────────────────────────────────────────────────────────────
async function onCompare() {
  const btn = document.getElementById('btn-compare');
  setLoading(btn, true);
  clearLog();
  closeInspectModal();
  logEvent(null, `Comparing naive vs safe recovery with seed=${currentSeed}...`, 'info');

  try {
    const data = await API.compare(currentSeed);
    renderComparison(data.naive, data.safe);

    logEvent(null,
      `Naive: ${data.naive.total_bugs} bug(s) | Safe: ${data.safe.total_bugs} bug(s)`,
      data.naive.total_bugs > 0 ? 'bug' : 'safe'
    );
    logEvent(null,
      'The verifier discovered whichever hooks violate invariants at runtime.',
      'info'
    );
    refreshSecurityAudit();
  } catch (err) {
    logEvent(null, `Compare error: ${err.message}`, 'bug');
    shake(btn);
  } finally {
    setLoading(btn, false);
  }
}

// ─── Autonomous Root-Cause Investigator ──────────────────────────────────────
async function onStartInvestigation() {
  const btn = document.getElementById('btn-agent-investigate');
  const hookSelect = document.getElementById('agent-hook-select');
  const initialHookVal = hookSelect ? hookSelect.value : '10';

  let initialHook = null;
  if (initialHookVal !== 'sweep') {
    initialHook = parseInt(initialHookVal, 10);
  }

  setLoading(btn, true);
  logEvent(null, `Starting Autonomous Root-Cause Investigation loop with seed=${currentSeed}, target_hook=${initialHook || 'auto'}...`, 'info');

  const statusBadge = document.getElementById('agent-status-badge');
  if (statusBadge) {
    statusBadge.textContent = 'RUNNING INVESTIGATION...';
    statusBadge.className = 'control-status-badge warning';
  }

  try {
    const report = await API.investigate(currentSeed, currentStrategy, initialHook);
    renderAgentReport(report);

    logEvent(null,
      `Autonomous Investigation completed with ${report.confidence} confidence. Root Cause: ${report.root_cause_confirmed ? 'CONFIRMED' : 'NOT CONFIRMED'}.`,
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
  btn.disabled = loading;
  if (loading) {
    btn._original = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Running...`;
  } else {
    btn.innerHTML = btn._original || btn.innerHTML;
  }
}

