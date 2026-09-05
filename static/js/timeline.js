/**
 * timeline.js — SVG transaction timeline with phase bands, 12 nodes, and crash marker.
 */

const PHASES = [
  { label: 'LOG',    hooks: [1,2,3],      color: '#3b82f6' },
  { label: 'DATA',   hooks: [4,5,6],      color: '#8b5cf6' },
  { label: 'META',   hooks: [7,8,9],      color: '#f59e0b' },
  { label: 'COMMIT', hooks: [10,11,12],   color: '#ef4444' },
];

export function renderTimeline(crashHook, verdicts) {
  const svg    = document.getElementById('timeline-svg');
  const W      = svg.clientWidth  || 700;
  const H      = 100;
  const PAD    = 40;
  const usable = W - PAD * 2;

  svg.innerHTML = '';
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  // Phase bands
  const bandH = 28;
  const bandY = 10;
  PHASES.forEach((ph, pi) => {
    const startHook = ph.hooks[0];
    const endHook   = ph.hooks[ph.hooks.length - 1];
    const x1 = PAD + ((startHook - 1) / 11) * usable - 14;
    const x2 = PAD + ((endHook - 1)   / 11) * usable + 14;

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x',      x1);
    rect.setAttribute('y',      bandY);
    rect.setAttribute('width',  x2 - x1);
    rect.setAttribute('height', bandH);
    rect.setAttribute('rx',     6);
    rect.setAttribute('fill',   ph.color + '18');
    rect.setAttribute('stroke', ph.color + '40');
    rect.setAttribute('stroke-width', '1');
    svg.appendChild(rect);

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x',             (x1 + x2) / 2);
    text.setAttribute('y',             bandY + 18);
    text.setAttribute('text-anchor',   'middle');
    text.setAttribute('font-size',     '9');
    text.setAttribute('font-weight',   '700');
    text.setAttribute('fill',          ph.color);
    text.setAttribute('font-family',   'Inter, sans-serif');
    text.setAttribute('letter-spacing','0.08em');
    text.textContent = ph.label;
    svg.appendChild(text);
  });

  // Connector line
  const lineY = 68;
  const line  = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', PAD);
  line.setAttribute('x2', W - PAD);
  line.setAttribute('y1', lineY);
  line.setAttribute('y2', lineY);
  line.setAttribute('stroke', '#374151');
  line.setAttribute('stroke-width', '2');
  svg.appendChild(line);

  // Hook nodes
  for (let h = 1; h <= 12; h++) {
    const cx = PAD + ((h - 1) / 11) * usable;
    const cy = lineY;

    const verdict  = verdicts ? verdicts[h] : null;
    const isCrash  = (h === crashHook);
    const color    = isCrash ? '#ef4444'
                   : verdict === 'SAFE' ? '#22c55e'
                   : verdict === 'BUG'  ? '#ef4444'
                   : '#374151';

    // Outer glow for crash / bug
    if (isCrash || verdict === 'BUG') {
      const glow = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      glow.setAttribute('cx', cx);
      glow.setAttribute('cy', cy);
      glow.setAttribute('r',  12);
      glow.setAttribute('fill', color + '25');
      svg.appendChild(glow);
    }

    // Node circle
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx',   cx);
    circle.setAttribute('cy',   cy);
    circle.setAttribute('r',    6);
    circle.setAttribute('fill', color);
    circle.setAttribute('stroke', isCrash ? '#fff' : 'none');
    circle.setAttribute('stroke-width', '1.5');
    svg.appendChild(circle);

    // Hook number label
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x',           cx);
    label.setAttribute('y',           cy + 20);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('font-size',   '9');
    label.setAttribute('fill',        '#6b7280');
    label.setAttribute('font-family', 'JetBrains Mono, monospace');
    label.textContent = h;
    svg.appendChild(label);

    // Crash lightning bolt
    if (isCrash) {
      const bolt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      bolt.setAttribute('x',           cx);
      bolt.setAttribute('y',           cy - 14);
      bolt.setAttribute('text-anchor', 'middle');
      bolt.setAttribute('font-size',   '14');
      bolt.textContent = '💥';
      svg.appendChild(bolt);
    }
  }
}

export function resetTimeline() {
  renderTimeline(null, null);
}
