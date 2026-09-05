/**
 * animations.js — Micro-animations and visual transitions.
 */

/**
 * Append a line to the event log terminal.
 */
export function logEvent(hookNum, message, type = '') {
  const log = document.getElementById('event-log');
  const now = new Date();
  const ts  = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;

  const line = document.createElement('div');
  line.className = 'log-line';
  line.style.animation = 'slide-right 0.2s ease';
  line.innerHTML = `
    <span class="log-time">${ts}</span>
    <span class="log-hook">${hookNum !== null ? `[H${String(hookNum).padStart(2,'0')}]` : '[SYS]'}</span>
    <span class="log-msg ${type}">${message}</span>
  `;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

/**
 * Clear the event log.
 */
export function clearLog() {
  document.getElementById('event-log').innerHTML = '';
}

/**
 * Flash a status badge briefly.
 */
export function flashBadge(el, colorClass) {
  el.classList.add(colorClass);
  setTimeout(() => el.classList.remove(colorClass), 600);
}

/**
 * Animate a number counter counting up to target.
 */
export function animateCounter(el, target, duration = 600) {
  const start    = 0;
  const startTs  = performance.now();

  function tick(now) {
    const elapsed = now - startTs;
    const pct     = Math.min(elapsed / duration, 1);
    el.textContent = Math.round(start + (target - start) * pct);
    if (pct < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

/**
 * Shake an element briefly (used on error).
 */
export function shake(el) {
  el.style.transition = 'transform 0.1s';
  const frames = [0, -6, 6, -4, 4, 0];
  let i = 0;
  const interval = setInterval(() => {
    el.style.transform = `translateX(${frames[i]}px)`;
    i++;
    if (i >= frames.length) {
      clearInterval(interval);
      el.style.transform = '';
    }
  }, 50);
}
