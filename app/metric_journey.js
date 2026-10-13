/* Only the empty identity rail moves; native controls own all research state. */
(() => {
  const quiet = () => reduced.matches || document.documentElement.dataset.qmMotionMode === 'research';
  const version = 'metric-journey-20261005-1-global-2-body-ready20';
  if (window.__qmMetricJourney?.version === version) { window.__qmMetricJourney.refresh(); return; }
  window.__qmMetricJourney?.dispose();
  const seen = new Set(), effects = new Set(), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let disposed = false;
  function refresh() {
    if (disposed || document.hidden) return;
    document.querySelectorAll('[data-metric-journey]').forEach(node => {
      const id = node.dataset.metricJourney;
      if (seen.has(id)) return;
      seen.add(id);
      if (seen.size > 32) seen.delete(seen.values().next().value);
      const rail = node.querySelector('i[aria-hidden="true"]'), box = node.getBoundingClientRect();
      if (quiet() || !rail?.animate || box.bottom <= 0 || box.top >= innerHeight) return;
      const effect = rail.animate([{transform:'scaleY(.12)',opacity:.35},{transform:'scaleY(1)',opacity:1}],
        {duration:560,easing:'cubic-bezier(.2,.7,.2,1)'});
      effects.add(effect); effect.finished.catch(() => {}).finally(() => effects.delete(effect));
    });
  }
  const stop = () => { for (const effect of effects) effect.cancel(); effects.clear(); };
  const visible = () => { if (document.hidden) stop(); else refresh(); };
  const observer = new MutationObserver(refresh);
  observer.observe(document,{childList:true,subtree:true});
  document.addEventListener('visibilitychange',visible);
  reduced.addEventListener('change',stop);
  window.addEventListener('qm-motion-preference-change', stop);
  const api = {version,refresh,dispose() { disposed=true;stop();window.removeEventListener('qm-motion-preference-change',stop);observer.disconnect();document.removeEventListener('visibilitychange',visible);reduced.removeEventListener('change',stop);if(window.__qmMetricJourney===api)delete window.__qmMetricJourney; }};
  window.__qmMetricJourney=api;refresh();
})();
