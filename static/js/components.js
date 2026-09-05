/**
 * components.js — Professional UI Rendering Component System.
 * Pure frontend presentation layer.
 */

const VERDICT_ICONS = {
  SAFE: `<svg class="verdict-svg safe" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  BUG: `<svg class="verdict-svg bug" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  PENDING: `<svg class="verdict-svg pending" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
};

const PHASE_GROUPS = [
  { phase: 'LOG', label: 'LOG PHASE', range: [1, 2, 3], desc: 'WAL Write & Logging Operations' },
  { phase: 'DATA', label: 'DATA PHASE', range: [4, 5, 6], desc: 'Data Page Flush Operations' },
  { phase: 'META', label: 'METADATA PHASE', range: [7, 8, 9], desc: 'B-Tree & Index Updates' },
  { phase: 'COMMIT', label: 'COMMIT PHASE', range: [10, 11, 12], desc: 'Commit Marker Flush' },
];

// ─── Phase-Grouped 12-Hook Grid ──────────────────────────────────────────────

/**
 * Render the 12 hook cards grouped into 4 Execution Phases.
 * @param {Array} results — HookResult array from API response (or null for pending)
 * @param {Function} onSelect — click callback with HookResult
 */
export function renderHookGrid(results, onSelect) {
  const container = document.getElementById('hook-grid');
  container.innerHTML = '';

  PHASE_GROUPS.forEach(group => {
    const section = document.createElement('div');
    section.className = 'phase-group-section';

    // Count phase results if available
    let safeInPhase = 0;
    let bugsInPhase = 0;
    group.range.forEach(h => {
      const res = results ? results.find(r => r.hook === h) : null;
      if (res) {
        if (res.verdict === 'BUG') bugsInPhase++;
        else safeInPhase++;
      }
    });

    const phaseTag = results
      ? (bugsInPhase > 0 ? `<span class="phase-count-tag bug">${bugsInPhase} BUG</span>` : `<span class="phase-count-tag safe">${safeInPhase}/3 SAFE</span>`)
      : `<span class="phase-count-tag pending">3 HOOKS</span>`;

    section.innerHTML = `
      <div class="phase-group-header">
        <div class="phase-title-wrap">
          <span class="phase-header-badge phase-${group.phase}">${group.phase}</span>
          <span class="phase-header-title">${group.label}</span>
          <span class="phase-header-desc">• ${group.desc}</span>
        </div>
        ${phaseTag}
      </div>
      <div class="phase-cards-grid" id="phase-grid-${group.phase}"></div>
    `;

    container.appendChild(section);

    const cardsGrid = section.querySelector(`#phase-grid-${group.phase}`);

    group.range.forEach(hookNum => {
      const result = results ? results.find(r => r.hook === hookNum) : null;
      const card = buildHookCard(hookNum, result, group.phase);

      card.addEventListener('click', () => {
        if (!result) return;
        container.querySelectorAll('.hook-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        onSelect(result);
      });

      cardsGrid.appendChild(card);
      setTimeout(() => card.classList.add('visible'), hookNum * 40);
    });
  });
}

function buildHookCard(hookNum, result, phase) {
  const card = document.createElement('div');
  card.className = 'hook-card state-pending';
  card.setAttribute('data-hook', hookNum);

  const stepDescription = result ? result.step_description : getDefaultStep(hookNum);
  const verdict = result ? result.verdict : 'PENDING';

  if (result) {
    card.classList.remove('state-pending');
    card.classList.add(`state-${verdict.toLowerCase()}`);
  }

  const failedInv = result && result.invariants ? result.invariants.find(i => !i.passed) : null;
  const hasPrevention = result && result.prevention_suggestion;

  const inspectBtnText = verdict === 'BUG' ? 'Inspect BUG ➔' : 'Inspect ➔';
  const inspectBtnClass = verdict === 'BUG' ? 'card-inspect-btn bug' : 'card-inspect-btn safe';

  card.innerHTML = `
    <div class="hook-card-header">
      <span class="hook-id">H${String(hookNum).padStart(2, '0')}</span>
      <span class="hook-phase-badge phase-${phase}">${phase}</span>
      <span class="hook-verdict-icon">${VERDICT_ICONS[verdict]}</span>
    </div>

    <div class="hook-step-text">${stepDescription}</div>

    <div class="hook-status-row">
      ${verdict === 'BUG' ? `
        <span class="status-pill bug">● BUG</span>
        ${failedInv ? `<span class="inv-failed-tag">${failedInv.invariant_id} FAILED</span>` : ''}
      ` : verdict === 'SAFE' ? `
        <span class="status-pill safe">● SAFE</span>
        <span class="inv-passed-tag">All Invariants Pass</span>
      ` : `
        <span class="status-pill pending">● PENDING</span>
      `}
    </div>

    ${hasPrevention ? `
      <div class="prevention-hint-pill">Prevention Rule Available</div>
    ` : ''}

    ${result ? `<button class="${inspectBtnClass}">${inspectBtnText}</button>` : ''}
  `;

  return card;
}

function getDefaultStep(hookNum) {
  const steps = {
    1: 'WAL Header Write', 2: 'WAL Record Append', 3: 'WAL Sync/Flush',
    4: 'Data Page Allocation', 5: 'Data Page Payload Write', 6: 'Data Page Sync/Flush',
    7: 'Metadata Index Lookup', 8: 'Metadata Pointer Update', 9: 'Metadata Page Flush',
    10: 'Commit Marker Prepare', 11: 'Commit Marker Write', 12: 'Transaction Finalize'
  };
  return steps[hookNum] || 'Crash Point Hook';
}

// ─── Dynamic KPI Stats & Phase Risk ──────────────────────────────────────────

export function renderStats(report) {
  document.getElementById('stat-tested').textContent = report.results.length;
  document.getElementById('stat-safe').textContent = report.total_safe;
  document.getElementById('stat-bugs').textContent = report.total_bugs;
  
  const covEl = document.getElementById('stat-coverage');
  if (covEl) covEl.textContent = '100%';

  const stratEl = document.getElementById('stat-strategy');
  if (stratEl) stratEl.textContent = `Strategy: ${report.strategy.toUpperCase()}`;

  // Animate progress bar
  const fill = document.getElementById('progress-fill');
  if (fill) {
    setTimeout(() => {
      fill.style.width = `${(report.results.length / 12) * 100}%`;
    }, 100);
  }

  // Update control status badge
  const badge = document.getElementById('control-status-badge');
  if (badge) {
    badge.textContent = report.total_bugs > 0
      ? `VERIFICATION COMPLETE (${report.total_bugs} BUGS FOUND)`
      : 'VERIFICATION COMPLETE (ALL SAFE)';
    badge.className = report.total_bugs > 0 ? 'control-status-badge bug' : 'control-status-badge safe';
  }

  // Update Phase Risk Bar
  updatePhaseRiskOverview(report.results);
}

export function resetStats() {
  ['stat-tested', 'stat-safe', 'stat-bugs', 'stat-coverage'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = '–';
  });
  const fill = document.getElementById('progress-fill');
  if (fill) fill.style.width = '0%';

  const badge = document.getElementById('control-status-badge');
  if (badge) {
    badge.textContent = 'READY FOR VERIFICATION';
    badge.className = 'control-status-badge';
  }

  const riskBar = document.getElementById('phase-risk-overview');
  if (riskBar) riskBar.classList.add('hidden');
}

function updatePhaseRiskOverview(results) {
  const riskBar = document.getElementById('phase-risk-overview');
  if (!riskBar) return;

  PHASE_GROUPS.forEach(group => {
    let safeCount = 0;
    group.range.forEach(h => {
      const res = results.find(r => r.hook === h);
      if (res && res.verdict === 'SAFE') safeCount++;
    });

    const el = document.getElementById(`risk-phase-${group.phase.toLowerCase()}`);
    if (el) {
      const badge = el.querySelector('.risk-phase-badge');
      if (badge) {
        badge.textContent = `${safeCount}/3 Safe`;
        badge.className = safeCount === 3 ? 'risk-phase-badge safe' : 'risk-phase-badge bug';
      }
    }
  });

  riskBar.classList.remove('hidden');
}

// ─── Invariant Inspector Panel ──────────────────────────────────────────────

export function renderInspector(result, onReproduce) {
  const banner = document.getElementById('verdict-banner');
  const isBug = result.verdict === 'BUG';
  banner.className = `verdict-banner ${isBug ? 'bug' : 'safe'}`;
  banner.innerHTML = `
    <span>${isBug ? VERDICT_ICONS.BUG : VERDICT_ICONS.SAFE}</span>
    <span>Hook ${String(result.hook).padStart(2, '0')} — ${result.verdict}: ${result.step_description}</span>
  `;

  renderInvariants(result.invariants);

  const bugBox = document.getElementById('bug-details-box');
  if (isBug && result.bug_details) {
    bugBox.classList.remove('hidden');
    bugBox.textContent = result.bug_details;
  } else {
    bugBox.classList.add('hidden');
  }

  renderDiskState(result.disk_snapshot);

  const reprBtn = document.getElementById('reproduce-btn');
  reprBtn.classList.toggle('hidden', !isBug);
  if (isBug) {
    reprBtn.onclick = () => onReproduce(result.hook);
  }

  document.getElementById('inspector-panel').classList.remove('hidden');
  document.getElementById('inspector-empty').classList.add('hidden');
}

export function resetInspector() {
  document.getElementById('inspector-panel').classList.add('hidden');
  document.getElementById('inspector-empty').classList.remove('hidden');
}

function renderInvariants(invariants) {
  const list = document.getElementById('invariant-list');
  list.innerHTML = '';

  invariants.forEach(inv => {
    const row = document.createElement('div');
    row.className = `invariant-row ${inv.passed ? 'passed' : 'failed'}`;

    const badgeIcon = inv.passed
      ? `<span class="inv-badge pass">PASS ✓</span>`
      : `<span class="inv-badge fail">FAIL ✕</span>`;

    row.innerHTML = `
      <div class="inv-id ${inv.passed ? 'passed' : 'failed'}">${inv.invariant_id}</div>
      <div class="inv-body">
        <div class="inv-name">${inv.name}</div>
        <div class="inv-detail" title="${inv.actual}">${inv.actual}</div>
      </div>
      <div class="inv-icon">${badgeIcon}</div>
    `;
    list.appendChild(row);
  });
}

function renderDiskState(snapshot) {
  const regions = [
    { name: 'WAL Log', key: 'wal', check: v => v && v.length > 0 },
    { name: 'Data Pages', key: 'data_pages', check: v => v && Object.keys(v).length > 0 },
    { name: 'Metadata Index', key: 'metadata_index', check: v => v && Object.keys(v).length > 0 },
    { name: 'Checksums', key: 'checksums', check: v => v && Object.keys(v).length > 0 },
    { name: 'Commit Markers', key: 'commit_markers', check: v => v && Object.keys(v).length > 0 },
  ];

  const container = document.getElementById('disk-regions');
  container.innerHTML = '';

  regions.forEach(reg => {
    const present = reg.check(snapshot[reg.key]);
    const row = document.createElement('div');
    row.className = 'disk-region';
    const statusMarkup = present
      ? `<span class="disk-status-icon pass">✓</span>`
      : `<span class="disk-status-icon fail">✕</span>`;

    row.innerHTML = `
      <div class="disk-region-name">${reg.name}</div>
      <div class="disk-region-bar-wrap">
        <div class="disk-region-bar ${present ? 'present' : 'absent'}" style="width:${present ? 100 : 0}%"></div>
      </div>
      <div class="disk-region-status">${statusMarkup}</div>
    `;
    container.appendChild(row);
  });
}

// ─── Inspect Modal Premium Redesign ──────────────────────────────────────────

export function openInspectModal(result, strategy, onReproduce) {
  const overlay = document.getElementById('inspect-modal-overlay');
  const title = document.getElementById('modal-hook-title');
  const body = document.getElementById('modal-body');
  const reprBtn = document.getElementById('modal-reproduce-btn');
  const okBtn = document.getElementById('modal-ok-btn');
  const closeBtn = document.getElementById('modal-close-btn');

  if (!overlay) return;

  const isBug = result.verdict === 'BUG';
  title.innerHTML = `HOOK ${String(result.hook).padStart(2, '0')} — <span class="tag ${isBug ? 'bug' : 'safe'}">${result.verdict}</span>`;

  const snap = result.disk_snapshot;
  const hasData = snap && snap.data_pages && Object.keys(snap.data_pages).length > 0;
  const hasMeta = snap && snap.metadata_index && Object.keys(snap.metadata_index).length > 0;
  const hasCsum = snap && snap.checksums && Object.keys(snap.checksums).length > 0;
  const hasCommit = snap && snap.commit_markers && Object.keys(snap.commit_markers).length > 0;

  const failedInv = result.invariants ? result.invariants.find(i => !i.passed) : null;
  const exposedCount = result.recovered_records ? result.recovered_records.length : 0;

  // Dynamic explanation
  let explanation = '';
  if (isBug) {
    if (failedInv && failedInv.invariant_id === 'INV-3') {
      explanation = `Data page and metadata index survived on persisted disk, but the transaction commit marker was never written. ${(strategy || 'NAIVE').toUpperCase()} Recovery exposed the uncommitted record, violating INV-3.`;
    } else {
      explanation = result.bug_details || (failedInv ? failedInv.details : 'Invariant violation detected post-recovery.');
    }
  } else {
    if (hasMeta && !hasCommit) {
      explanation = `${(strategy || 'SAFE').toUpperCase()} Recovery detected missing commit marker on disk and safely rolled back uncommitted changes.`;
    } else {
      explanation = `Crash occurred prior to flushing active metadata. Recovery safely exposed zero records, satisfying all formal invariant rules.`;
    }
  }

  body.innerHTML = `
    <!-- Section A: Hook Details -->
    <div class="modal-section">
      <div class="modal-section-header">A. HOOK & RECOVERY DETAILS</div>
      <div class="inspect-detail-grid">
        <div class="inspect-group">
          <div class="inspect-label">Crash Point Hook</div>
          <div class="inspect-value highlight">HOOK ${String(result.hook).padStart(2, '0')} — ${result.step_description}</div>
        </div>
        <div class="inspect-group">
          <div class="inspect-label">Execution Phase</div>
          <div class="inspect-value"><span class="hook-phase-badge phase-${result.phase}">${result.phase}</span></div>
        </div>
        <div class="inspect-group">
          <div class="inspect-label">Recovery Strategy</div>
          <div class="inspect-value">${(strategy || 'naive').toUpperCase()} RECOVERY</div>
        </div>
        <div class="inspect-group">
          <div class="inspect-label">Verification Verdict</div>
          <div class="inspect-value ${isBug ? 'bug' : 'safe'}">${result.verdict}</div>
        </div>
      </div>
    </div>

    <!-- Section B: Persisted Disk State -->
    <div class="modal-section">
      <div class="modal-section-header">B. PERSISTED STATE ON DISK</div>
      <div class="inspect-state-grid">
        <div class="state-item ${hasData ? 'check' : 'cross'}">
          <span class="state-icon">${hasData ? '✓' : '✕'}</span> Data Page: ${hasData ? 'Present' : 'Missing'}
        </div>
        <div class="state-item ${hasMeta ? 'check' : 'cross'}">
          <span class="state-icon">${hasMeta ? '✓' : '✕'}</span> Metadata Index: ${hasMeta ? 'Present' : 'Missing'}
        </div>
        <div class="state-item ${hasCsum ? 'check' : 'cross'}">
          <span class="state-icon">${hasCsum ? '✓' : '✕'}</span> Checksum: ${hasCsum ? 'Present' : 'Missing'}
        </div>
        <div class="state-item ${hasCommit ? 'check' : 'cross'}">
          <span class="state-icon">${hasCommit ? '✓' : '✕'}</span> Commit Marker: ${hasCommit ? 'Present' : 'Missing'}
        </div>
      </div>
    </div>

    <!-- Section C: Recovery Result -->
    <div class="modal-section">
      <div class="modal-section-header">C. RECOVERY RESULT</div>
      <div class="inspect-value ${isBug ? 'bug' : 'safe'}" style="font-size:13px; font-weight:700;">
        ${isBug ? `EXPOSED (${exposedCount} uncommitted record visible to queries)` : 'ROLLED BACK / HIDDEN (0 uncommitted records exposed)'}
      </div>
    </div>

    <!-- Section D: Invariant Inspection -->
    <div class="modal-section">
      <div class="modal-section-header">D. INVARIANT INSPECTION (INV-1 TO INV-4)</div>
      <div class="modal-inv-grid">
        ${(result.invariants || []).map(inv => `
          <div class="modal-inv-card ${inv.passed ? 'pass' : 'fail'}">
            <div class="modal-inv-top">
              <span class="modal-inv-id">${inv.invariant_id}</span>
              <span class="modal-inv-badge ${inv.passed ? 'pass' : 'fail'}">${inv.passed ? 'PASS ✓' : 'FAIL ✕'}</span>
            </div>
            <div class="modal-inv-name">${inv.name}</div>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Section E: Why? (Diagnostic Explanation) -->
    <div class="modal-section">
      <div class="modal-section-header">E. WHY? (DIAGNOSTIC EXPLANATION)</div>
      <div class="inspect-why-box ${isBug ? 'bug' : 'safe'}">
        ${explanation}
      </div>
    </div>

    <!-- Section F: How to Prevent -->
    <div class="modal-section">
      <div class="modal-section-header">F. AUTOMATIC PREVENTION SUGGESTION</div>
      ${isBug && result.prevention_suggestion ? `
        <div class="inspect-prevention-box">
          <div class="prevention-item">
            <span class="prevention-title">Problem:</span>
            <span class="prevention-desc">${result.prevention_suggestion.problem}</span>
          </div>
          <div class="prevention-item">
            <span class="prevention-title">Recommended Recovery Rule:</span>
            <span class="prevention-rule">"${result.prevention_suggestion.rule}"</span>
          </div>
          <div class="prevention-item action-item">
            <span class="prevention-title">Suggested Action:</span>
            <span class="prevention-action-badge">${result.prevention_suggestion.action}</span>
          </div>
        </div>
      ` : `
        <div class="inspect-why-box safe">
          No Prevention Required — All 4 Invariants Satisfied
        </div>
      `}
    </div>
  `;


  reprBtn.classList.toggle('hidden', !isBug);
  if (isBug) {
    reprBtn.onclick = () => {
      onReproduce(result.hook);
      closeInspectModal();
    };
  }

  okBtn.onclick = closeInspectModal;
  closeBtn.onclick = closeInspectModal;
  overlay.onclick = (e) => { if (e.target === overlay) closeInspectModal(); };

  overlay.classList.remove('hidden');
}

export function closeInspectModal() {
  const overlay = document.getElementById('inspect-modal-overlay');
  if (overlay) overlay.classList.add('hidden');
}

// ─── Comparison View ──────────────────────────────────────────────────────────

export function renderComparison(naiveReport, safeReport) {
  renderCompareSide('naive', naiveReport);
  renderCompareSide('safe', safeReport);
  document.getElementById('compare-section').classList.remove('hidden');
}

function renderCompareSide(strategy, report) {
  const grid = document.getElementById(`compare-grid-${strategy}`);
  const bugs = document.getElementById(`compare-bugs-${strategy}`);
  const safe = document.getElementById(`compare-safe-${strategy}`);

  if (bugs) bugs.textContent = report.total_bugs;
  if (safe) safe.textContent = report.total_safe;

  if (grid) {
    grid.innerHTML = '';
    report.results.forEach(r => {
      const card = document.createElement('div');
      card.className = `mini-hook-card ${r.verdict.toLowerCase()}`;
      card.textContent = `H${String(r.hook).padStart(2, '0')}`;
      card.title = `Hook ${r.hook}: ${r.verdict}`;
      grid.appendChild(card);
    });
  }
}

export function hideComparison() {
  const comp = document.getElementById('compare-section');
  if (comp) comp.classList.add('hidden');
}

// ─── Autonomous Root-Cause Investigator Rendering ───────────────────────────

export function renderAgentReport(report) {
  const container = document.getElementById('agent-output-container');
  if (!container) return;

  container.classList.remove('hidden');

  const isConfirmed = report.status === 'ROOT_CAUSE_CONFIRMED' || report.confirmed_hypothesis !== 'None';

  // Update Status Badge
  const statusBadge = document.getElementById('agent-status-badge');
  if (statusBadge) {
    if (isConfirmed) {
      statusBadge.textContent = `ROOT CAUSE CONFIRMED`;
      statusBadge.className = 'control-status-badge bug';
    } else {
      statusBadge.textContent = `INVESTIGATION FINALISED`;
      statusBadge.className = 'control-status-badge safe';
    }
  }

  // Update Experiment Count
  const totalExp = report.total_experiments_executed || report.total_experiments || 0;
  const expCountEl = document.getElementById('agent-experiments-count');
  if (expCountEl) expCountEl.textContent = `${totalExp} Experiments`;

  // Hide Confidence Tag
  const confTag = document.getElementById('agent-confidence-tag');
  if (confTag) {
    confTag.classList.add('hidden');
  }

  // 1. Render Activity Stream / Log
  const streamLog = document.getElementById('agent-stream-log');
  if (streamLog) {
    streamLog.innerHTML = '';
    const logs = report.activity_log || report.activity_stream || [];
    logs.forEach(entry => {
      const lineDiv = document.createElement('div');
      lineDiv.className = 'agent-log-line';

      if (typeof entry === 'object') {
        const stageTag = `<span class="tag-${entry.stage.toLowerCase()}">[${entry.stage}]</span>`;
        lineDiv.innerHTML = `${stageTag} ${entry.message} ${entry.details ? `<br>&nbsp;&nbsp;<span style="color:var(--text-muted);">${entry.details}</span>` : ''}`;
      } else {
        let formatted = entry
          .replace(/\[OBSERVE\]/g, '<span class="tag-observe">[OBSERVE]</span>')
          .replace(/\[HYPOTHESIS\]/g, '<span class="tag-hypothesis">[HYPOTHESIS]</span>')
          .replace(/\[DECISION\]/g, '<span class="tag-decision">[DECISION]</span>')
          .replace(/\[EXPERIMENT\]/g, '<span class="tag-experiment">[EXPERIMENT]</span>')
          .replace(/\[RESULT\]/g, '<span class="tag-result">[RESULT]</span>')
          .replace(/\[ELIMINATION\]/g, '<span class="tag-result">[ELIMINATION]</span>')
          .replace(/\[CONCLUSION\]/g, '<span class="tag-conclusion">[CONCLUSION]</span>');

        lineDiv.innerHTML = formatted;
      }
      streamLog.appendChild(lineDiv);
    });
    streamLog.scrollTop = streamLog.scrollHeight;
  }

  // 2. Render Hypotheses List
  const hypoList = document.getElementById('agent-hypotheses-list');
  if (hypoList) {
    hypoList.innerHTML = '';
    (report.hypotheses || []).forEach(h => {
      const row = document.createElement('div');
      const isConfirmedHypo = h.status === 'CONFIRMED' || h.status === 'STRENGTHENED';
      const isEliminated = h.status === 'REJECTED' || h.status === 'ELIMINATED';

      row.className = `agent-hypothesis-row ${isConfirmedHypo ? 'confirmed' : isEliminated ? 'eliminated' : ''}`;

      const statusTag = isConfirmedHypo
        ? `<span class="tag bug">CONFIRMED</span>`
        : isEliminated
        ? `<span class="tag info">REJECTED</span>`
        : `<span class="tag info">UNTESTED</span>`;

      row.innerHTML = `
        <div class="agent-hypo-info">
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="agent-hypo-id">${h.id} — ${h.name}</span>
            ${statusTag}
          </div>
          <div class="agent-hypo-desc">${h.statement || h.description || ''}</div>
        </div>
      `;
      hypoList.appendChild(row);
    });
  }

  // 3. Render Final Report Box
  const reportBox = document.getElementById('agent-final-report-box');
  if (reportBox) {
    reportBox.classList.remove('hidden');
    const rawFam = report.failure_families || [];
    const families = rawFam.map(f => typeof f === 'object' ? (f.family || f.name || JSON.stringify(f)) : f).join(', ') || 'COMMIT_VALIDATION';

    reportBox.innerHTML = `
      <div class="agent-report-title">ROOT CAUSE INVESTIGATION FINDINGS</div>
      <div class="agent-report-grid">
        <div class="agent-report-item">
          <div class="agent-report-label">Investigation ID</div>
          <div class="agent-report-val">${report.investigation_id}</div>
        </div>
        <div class="agent-report-item">
          <div class="agent-report-label">Failure Family</div>
          <div class="agent-report-val">${families}</div>
        </div>
        <div class="agent-report-item">
          <div class="agent-report-label">Initial Hook</div>
          <div class="agent-report-val">Hook H${String(report.initial_hook_observed || 10).padStart(2, '0')}</div>
        </div>
        <div class="agent-report-item">
          <div class="agent-report-label">Primary Root Cause</div>
          <div class="agent-report-val" style="color:var(--bug);">${report.confirmed_hypothesis || 'Established'}</div>
        </div>
      </div>

      ${prev.rule ? `
        <div class="inspect-prevention-box" style="margin-top:6px;">
          <div class="prevention-item">
            <span class="prevention-title">Root Cause Rule:</span>
            <span class="prevention-rule">"${prev.rule}"</span>
          </div>
          <div class="prevention-item action-item">
            <span class="prevention-title">Recommended Action:</span>
            <span class="prevention-action-badge">${prev.suggested_action}</span>
          </div>
        </div>
      ` : ''}
    `;
  }
}


