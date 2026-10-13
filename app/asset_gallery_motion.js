/* Local document geometry only. Native widgets remain the sole action path. */
(() => {
  const quiet = () => reduced.matches || document.documentElement.dataset.qmMotionMode === 'research';
  'use strict';
  const VERSION = '2026-10-05.1-global-2-body-ready20';
  if (window.__qmAssetGallery?.version === VERSION) { window.__qmAssetGallery.refresh(); return; }
  window.__qmAssetGallery?.dispose();
  const abort = new AbortController(), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const effects = new Set(), decorations = new Set(), root = document.documentElement;
  let records = new Map(), pending = null, committed = '', model = { selected: '', open: '' };
  let frame = 0, disposed = false, inView = true, observed = null, journey = null, route = null;
  const enabled = () => !disposed && !quiet() && !document.hidden && inView;
  const keyOf = node => node?.getAttribute('data-asset-record-id');
  const rect = node => {
    if (!node?.isConnected) return null;
    const box = node.getBoundingClientRect();
    if (![box.left, box.top, box.width, box.height].every(Number.isFinite) || box.width <= 0 || box.height <= 0) return null;
    return { left: box.left, top: box.top, width: box.width, height: box.height };
  };
  const visible = box => box && box.left + box.width > 0 && box.top + box.height > 0 && box.left < innerWidth && box.top < innerHeight;
  const currentRoute = () => document.querySelector('[data-studio-scene]')?.getAttribute('data-studio-scene') || 'isolated-gallery';
  const gallery = () => document.querySelector('.st-key-asset_gallery');
  function collect() {
    const found = new Map();
    for (const node of document.querySelectorAll('[data-asset-record-id]')) {
      const id = keyOf(node), box = rect(node), volume = node.querySelector('.asset-cover-volume');
      if (id && box) found.set(id, { node, box, volume, transform: volume ? getComputedStyle(volume).transform : 'none' });
    }
    return found;
  }
  function animate(node, frames, options, done) {
    if (!enabled() || !node?.animate) return null;
    const animation = node.animate(frames, options);
    effects.add(animation);
    animation.finished.then(() => { effects.delete(animation); done?.(); }, () => effects.delete(animation));
    return animation;
  }
  function cancelEffects() {
    for (const animation of effects) animation.cancel();
    effects.clear();
    for (const node of decorations) node.remove();
    decorations.clear(); journey = null;
  }
  function blankPaper(box) {
    const paper = document.createElement('div');
    paper.className = 'qm-asset-flight';
    paper.setAttribute('aria-hidden', 'true'); paper.inert = true;
    Object.assign(paper.style, { left: box.left + 'px', top: box.top + 'px', width: box.width + 'px', height: box.height + 'px' });
    for (const name of ['qm-asset-flight-back', 'qm-asset-flight-page', 'qm-asset-flight-front']) {
      const layer = document.createElement('i'); layer.className = name; paper.appendChild(layer);
    }
    document.body.appendChild(paper); decorations.add(paper); return paper;
  }
  const geometry = (from, to) => 'translate(' + (from.left - to.left) + 'px,' + (from.top - to.top) + 'px) scale(' + (from.width / to.width) + ',' + (from.height / to.height) + ')';
  function travel(from, to, opening) {
    if (!enabled() || !visible(from) || !visible(to)) return;
    const paper = blankPaper(to); journey = paper;
    root.dataset.qmAssetPhase = opening ? 'opening' : 'returning';
    const animation = animate(paper, [
      { transform: geometry(from, to), opacity: .78, offset: 0 },
      { opacity: .65, offset: .46 },
      { transform: 'translate(0px,0px) scale(1,1)', opacity: 0, offset: 1 }
    ], { duration: opening ? 880 : 700, easing: opening ? 'cubic-bezier(.16,.75,.19,1)' : 'cubic-bezier(.48,0,.22,1)', fill: 'forwards' }, () => {
      paper.remove(); decorations.delete(paper); if (journey === paper) journey = null;
      root.dataset.qmAssetPhase = opening ? 'open' : 'closed';
    });
    if (!animation) { paper.remove(); decorations.delete(paper); journey = null; return; }
    animate(paper.lastElementChild, [
      { transform: opening ? 'rotateY(-48deg) rotate(-8deg)' : 'rotateY(0deg)' },
      { transform: opening ? 'rotateY(0deg) rotate(0deg)' : 'rotateY(-38deg) rotate(5deg)' }
    ], { duration: opening ? 790 : 650, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'forwards' });
  }
  function rearrange(before, after, first) {
    let count = 0;
    for (const [id, item] of after) {
      if (!visible(item.box)) continue;
      const old = before.get(id);
      if (old && visible(old.box)) {
        const dx = old.box.left - item.box.left, dy = old.box.top - item.box.top;
        const sx = old.box.width / item.box.width, sy = old.box.height / item.box.height;
        if (Math.abs(dx) + Math.abs(dy) > 1 || Math.abs(sx - 1) + Math.abs(sy - 1) > .015) {
          animate(item.node, [{ translate: dx + 'px ' + dy + 'px', scale: sx + ' ' + sy }, { translate: '0px 0px', scale: '1 1' }],
            { duration: 720, easing: 'cubic-bezier(.18,.78,.2,1)' }); count++;
        }
        if (old.transform !== item.transform && item.volume) {
          animate(item.volume, [{ transform: old.transform }, { transform: item.transform }],
            { duration: 610, easing: 'cubic-bezier(.18,.8,.2,1)' });
        }
      } else {
        animate(item.node, [{ translate: (first ? 52 : 28) + 'px 10px', rotate: '0 1 0 -19deg', opacity: .1 },
          { translate: '0px 0px', rotate: '0 1 0 0deg', opacity: 1 }],
          { duration: 690, delay: Math.min(count * 72, 216), easing: 'cubic-bezier(.18,.78,.2,1)', fill: 'backwards' }); count++;
      }
    }
    root.dataset.qmAssetReordered = String(count);
  }
  function reset() {
    cancelEffects(); records.clear(); pending = null; committed = ''; model = { selected: '', open: '' };
    root.dataset.qmAssetPhase = 'static';
  }
  function scan() {
    frame = 0; if (disposed) return;
    const nextRoute = currentRoute();
    if (route !== null && nextRoute !== route) reset();
    route = nextRoute;
    const host = gallery(), marker = document.querySelector('[data-asset-gallery-commit]');
    if (!host || !marker) { if (!host) cancelEffects(); return; }
    if (host !== observed) { if (observed) intersection?.unobserve(observed); observed = host; intersection?.observe(host); }
    const commit = marker.getAttribute('data-asset-gallery-commit');
    if (commit === committed) { if (!pending && effects.size === 0) records = collect(); return; }
    const first = !committed, before = pending || records, previousModel = model;
    const inFlight = journey ? rect(journey) : null;
    pending = null; cancelEffects();
    const after = collect();
    model = { selected: marker.getAttribute('data-asset-selected') || '', open: marker.getAttribute('data-asset-open') || '' };
    committed = commit;
    if (enabled()) {
      rearrange(before, after, first);
      const desk = rect(document.querySelector('.asset-reading-heading'));
      if (model.open && model.open !== previousModel.open) {
        const origin = inFlight || before.get(model.open)?.box || after.get(model.open)?.box;
        travel(origin, desk, true);
      } else if (previousModel.open && !model.open) {
        const destination = after.get(previousModel.open)?.box;
        travel(inFlight || desk, destination, false);
      }
    } else root.dataset.qmAssetPhase = 'static';
    records = after;
  }
  const refresh = () => { if (!frame && !disposed) frame = requestAnimationFrame(scan); };
  const remember = event => {
    if (!gallery()) return;
    const owner = event.target.closest?.('[class*="st-key-library_"]');
    if (!owner || !/st-key-library_(?:cover_pick_|open_document|document|index_|gallery_previous|gallery_next|keyword|type)/.test(owner.className)) return;
    // Capture only element geometry; native values and financial text are never read.
    pending = collect();
  };
  for (const name of ['click', 'input', 'change']) document.addEventListener(name, remember, { capture: true, passive: true, signal: abort.signal });
  const intersection = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.target === observed) {
      inView = entry.isIntersecting; if (!inView) cancelEffects(); refresh();
    }
  }, { threshold: .01 }) : null;
  const mutation = new MutationObserver(changes => {
    if (changes.some(change => change.type === 'attributes' || Array.from(change.addedNodes || []).concat(Array.from(change.removedNodes || []))
      .some(node => node.nodeType === 1 && !node.matches?.('.qm-asset-flight,.qm-asset-flight *')))) refresh();
  });
  mutation.observe(document, { subtree: true, childList: true, attributes: true,
    attributeFilter: ['data-asset-gallery-commit', 'data-studio-scene'] });
  const stationary = () => { cancelEffects(); pending = null; records = collect(); refresh(); };
  const visibility = () => { if (document.hidden || quiet()) stationary(); else refresh(); };
  reduced.addEventListener('change', visibility);
  document.addEventListener('visibilitychange', visibility, { signal: abort.signal });
  window.addEventListener('resize', stationary, { passive: true, signal: abort.signal });
  window.addEventListener('scroll', () => { if (effects.size && !visible(rect(gallery()))) stationary(); }, { passive: true, capture: true, signal: abort.signal });
  window.addEventListener('qm-motion-preference-change', stationary, {signal: abort.signal});
  window.__qmAssetGallery = { version: VERSION, refresh, dispose() {
    disposed = true; if (frame) cancelAnimationFrame(frame); frame = 0;
    reset(); intersection?.disconnect(); mutation.disconnect(); abort.abort(); reduced.removeEventListener('change', visibility);
  } };
  refresh();
})();
