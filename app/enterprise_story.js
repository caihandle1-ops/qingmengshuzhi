/* Local presentation only. No widget values, requests, financial maths or wheel interception. */
(() => {
  const quiet = () => reduced.matches || document.documentElement.dataset.qmMotionMode === 'research';
  const VERSION = 'enterprise-story-20261011-20-annual-body-ready20';
  if (window.__qmEnterpriseStory?.version === VERSION) { window.__qmEnterpriseStory.refresh(); return; }
  window.__qmEnterpriseStory?.dispose();
  const abort = new AbortController();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const narrow = matchMedia('(max-width:680px)');
  const mounted = new Map();
  const saved = new Map();
  let frame = 0, disposed = false;
  const labels = ['经营概览', '年度变化', '风险依据', '报告路径'];
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  function restore(node) {
    node.classList.remove('is-enhanced');
    ['--es-camera-x','--es-camera-y','--es-camera-turn','--es-camera-scale'].forEach(name => node.style.removeProperty(name));
    node.querySelectorAll('[data-es-pane]').forEach(pane => { pane.removeAttribute('aria-hidden'); pane.removeAttribute('inert'); });
  }
  function measure(node, state) {
    const chapters = state.chapters;
    if (!chapters.length) return;
    const viewport = node.closest('[data-testid="stMain"]');
    const top = viewport ? Math.max(0, viewport.getBoundingClientRect().top) : 0;
    const height = viewport ? viewport.clientHeight : innerHeight;
    const probe = top + Math.min(300, height * .4);
    const rects = chapters.map(chapter => chapter.getBoundingClientRect());
    if (rects[0].top > top + height || rects[rects.length - 1].bottom < top) {
      state.timeline?.kill(); state.timeline = null;
      state.rules.forEach(rule => { rule.style.transform = ''; });
      return;
    }
    let current = 0;
    rects.forEach((rect, index) => { if (rect.top <= probe) current = index; });
    const local = clamp((probe - rects[current].top) / Math.max(1, rects[current].height), 0, 1);
    const progress = clamp((current + local) / 4, 0, 1);
    node.dataset.esDirection = progress < state.progress ? 'reverse' : 'forward';
    if (current !== state.current || state.initial || state.narrow !== narrow.matches) {
      state.timeline?.kill(); state.timeline = null;
      state.rules.forEach(rule => { rule.style.transform = ''; });
      // The rule is inert artwork. The financial text and chapter hit areas
      // never move; revisiting a mounted chapter has one reversible flourish.
      if ((!state.initial || !state.restored) && !quiet() && window.gsap?.timeline && state.rules[current]) {
        state.timeline = window.gsap.timeline({defaults: {ease: 'power3.out'}})
          .fromTo(state.rules[current], {scaleX: .12}, {scaleX: 1, duration: .75}, 0);
      }
      state.chapters.forEach((chapter, index) => chapter.classList.toggle('is-active', index === current));
      state.links.forEach((link, index) => { if (index === current) link.setAttribute('aria-current', 'step'); else link.removeAttribute('aria-current'); });
      state.panes.forEach((pane, index) => {
        pane.classList.toggle('is-active', index === current);
        if (narrow.matches) { pane.removeAttribute('aria-hidden'); pane.removeAttribute('inert'); }
        else { pane.setAttribute('aria-hidden', String(index !== current)); pane.toggleAttribute('inert', index !== current); }
      });
      node.querySelector('.es-current-chapter').textContent = labels[current];
      node.querySelector('.es-stage-count').textContent = '0' + (current + 1) + ' / 04';
      state.current = current;
      state.initial = false;
      state.narrow = narrow.matches;
    }
    if (!quiet() && !narrow.matches) {
      // A reversible horizontal camera through the same ribbon, orbit and paper.
      node.style.setProperty('--es-camera-x', (-210 * Math.sin(progress * Math.PI)).toFixed(2) + 'px');
      node.style.setProperty('--es-camera-y', (80 * Math.sin(progress * Math.PI * 2)).toFixed(2) + 'px');
      node.style.setProperty('--es-camera-turn', (-18 + progress * 105).toFixed(2) + 'deg');
      node.style.setProperty('--es-camera-scale', (1 + Math.sin(progress * Math.PI) * 1.15).toFixed(3));
    } else {
      state.timeline?.kill(); state.timeline = null;
      state.rules.forEach(rule => { rule.style.transform = ''; });
      ['--es-camera-x','--es-camera-y','--es-camera-turn','--es-camera-scale'].forEach(name => node.style.removeProperty(name));
    }
    state.progress = progress;
    saved.set(node.dataset.enterpriseStory, {current, progress});
    if (saved.size > 20) saved.delete(saved.keys().next().value);
  }
  function update() {
    frame = 0;
    if (disposed || document.hidden) return;
    for (const [node, state] of mounted) if (node.isConnected) measure(node, state);
  }
  function schedule() {
    if (!frame && !disposed && !document.hidden) frame = requestAnimationFrame(update);
  }
  const resize = new ResizeObserver(schedule);
  function refresh() {
    if (disposed) return;
    for (const [node,state] of mounted) if (!node.isConnected) { state.timeline?.kill(); resize.unobserve(node); mounted.delete(node); }
    document.querySelectorAll('[data-enterprise-story]').forEach(node => {
      if (mounted.has(node)) return;
      const previous = saved.get(node.dataset.enterpriseStory) || {current: 0, progress: 0};
      const state = {...previous, initial: true, restored: saved.has(node.dataset.enterpriseStory), narrow: narrow.matches,
        timeline: null, rules: [...node.querySelectorAll('.es-chapter-rule')],
        chapters: [...node.querySelectorAll('[data-es-chapter]')],
        panes: [...node.querySelectorAll('[data-es-pane]')], links: [...node.querySelectorAll('[data-es-jump]')]};
      mounted.set(node, state);
      node.classList.add('is-enhanced');
      resize.observe(node);
    });
    schedule();
  }
  document.addEventListener('click', event => {
    const link = event.target.closest?.('[data-es-jump]');
    if (!link) return;
    const root = link.closest('[data-enterprise-story]');
    const state = mounted.get(root);
    if (!state) return;
    const chapter = state.chapters[Number(link.dataset.esJump)];
    if (!chapter) return;
    event.preventDefault();
    chapter.scrollIntoView({behavior: quiet() ? 'auto' : 'smooth', block: 'start'});
    chapter.focus({preventScroll: true});
    schedule();
  }, {signal: abort.signal});
  document.addEventListener('scroll', schedule, {capture: true, passive: true, signal: abort.signal});
  window.addEventListener('resize', schedule, {passive: true, signal: abort.signal});
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && frame) { cancelAnimationFrame(frame); frame = 0; }
    if (document.hidden) for (const state of mounted.values()) { state.timeline?.kill(); state.timeline = null; state.rules.forEach(rule => { rule.style.transform = ''; }); }
    if (!document.hidden) schedule();
  }, {signal: abort.signal});
  reduced.addEventListener('change', schedule, {signal: abort.signal});
  narrow.addEventListener('change', schedule, {signal: abort.signal});
  const observer = new MutationObserver(refresh);
  observer.observe(document, {childList: true, subtree: true});
  window.addEventListener('qm-motion-preference-change', schedule, {signal: abort.signal});
  const api = {version: VERSION, refresh, dispose() {
    disposed = true;
    abort.abort(); observer.disconnect(); resize.disconnect();
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    for (const [node,state] of mounted) { state.timeline?.kill(); state.rules.forEach(rule => { rule.style.transform = ''; }); restore(node); }
    mounted.clear(); saved.clear();
    if (window.__qmEnterpriseStory === api) delete window.__qmEnterpriseStory;
  }};
  window.__qmEnterpriseStory = api;
  refresh();
})();
