(() => {
  'use strict';
  const VERSION = '2026-10-04.probe.1';
  if (window.__qmProbeVisual?.version === VERSION) { window.__qmProbeVisual.refresh(); return; }
  window.__qmProbeVisual?.dispose();
  const controller = new AbortController();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const known = new WeakSet();
  const jobs = new Map();
  let raf = 0;
  function cancel(root) { (jobs.get(root) || []).forEach(clearTimeout); jobs.delete(root); }
  function finish(root) { cancel(root); root.dataset.phase = 'final'; root.dataset.playing = 'false'; }
  function play(root) {
    finish(root);
    if (reduced.matches || document.hidden || root.dataset.canAnimate !== 'true') return;
    root.dataset.playing = 'true'; root.dataset.phase = 'first';
    const timers = [setTimeout(() => { if (root.isConnected) root.dataset.phase = 'second'; }, 420),
                    setTimeout(() => finish(root), 840)];
    jobs.set(root, timers);
    root.dataset.visualReplays = String(Number(root.dataset.visualReplays || 0) + 1);
  }
  function refresh() {
    document.querySelectorAll('.qm-probe-visual').forEach(root => {
      const button = root.querySelector('.qm-pv-replay');
      if (button) { button.disabled = reduced.matches; button.title = reduced.matches ? '已按系统减少动态效果设置显示静态比较' : '只重播视觉过程，不重新查询'; }
      if (!known.has(root)) { known.add(root); play(root); }
    });
    for (const root of jobs.keys()) if (!root.isConnected) cancel(root);
  }
  const observer = new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; refresh(); }); });
  observer.observe(document.body, {childList:true, subtree:true});
  document.addEventListener('click', event => {
    const button = event.target.closest?.('.qm-pv-replay');
    if (button) { const root = button.closest('.qm-probe-visual'); if (root) play(root); }
  }, {signal:controller.signal});
  function onReduced() { for (const root of jobs.keys()) finish(root); refresh(); }
  reduced.addEventListener('change', onReduced);
  document.addEventListener('visibilitychange', () => { if (document.hidden) for (const root of jobs.keys()) finish(root); }, {signal:controller.signal});
  window.__qmProbeVisual = {version:VERSION, refresh, dispose() {
    controller.abort(); observer.disconnect(); reduced.removeEventListener('change', onReduced);
    if (raf) cancelAnimationFrame(raf); for (const root of jobs.keys()) finish(root);
  }};
  refresh();
})();
