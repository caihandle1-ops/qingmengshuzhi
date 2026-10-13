/* Content-only enhancement. Native state, values, focus and hit areas remain
   authored by Streamlit; a content key identifies a confirmed rendered state. */
(function (win) {
  'use strict';
  const VERSION = '2026-10-11.17-body-ready20', doc = win.document;
  if (win.QMContentMotion?.version === VERSION) { win.QMContentMotion.refresh(); return; }
  win.QMContentMotion?.dispose();
  const ROOT = '[data-qm-content][data-qm-content-key]';
  const KINDS = new Set(['answer', 'comparison', 'import', 'feedback', 'archive']);
  const CONTROL = 'input,button,select,textarea,a,summary,[contenteditable],[role="button"],[role="link"],[role="combobox"],[role="slider"],[tabindex]';
  const OWNED = '[data-result-piece],[data-result-sweep],[data-feature-piece],[data-feature-ambient]';
  const ROW = '[data-qm-comparison-row]', ACCENT = '[data-qm-content-accent]';
  const LIMIT = 192, records = new Map(), seen = new Map(), rows = new Map();
  const media = win.matchMedia?.('(prefers-reduced-motion: reduce)');
  const abort = new win.AbortController();
  let disposed = false, frame = 0, starts = 0;
  const quiet = () => Boolean(media?.matches || doc.hidden || doc.documentElement.dataset.qmMotionMode === 'research');
  const ready = () => typeof win.gsap?.timeline === 'function' && typeof win.gsap?.to === 'function';
  const keyOf = node => node.dataset.qmContent + ':' + node.dataset.qmContentKey;
  const valid = node => KINDS.has(node.dataset.qmContent) && Boolean(node.dataset.qmContentKey);
  const owned = (node, root) => node.closest(ROOT) === root && !node.closest('[data-qm-visual-exit]');
  const remember = key => {
    seen.delete(key); seen.set(key, true);
    while (seen.size > LIMIT) seen.delete(seen.keys().next().value);
  };
  function visible(node) {
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 &&
      rect.top < (win.innerHeight || 900) && rect.left < (win.innerWidth || 1440);
  }
  function save(node, names) {
    return names.map(name => ({name, value: node.style.getPropertyValue(name), priority: node.style.getPropertyPriority(name)}));
  }
  function authoredOpacity(node) {
    const opacity = Number.parseFloat(win.getComputedStyle(node).opacity);
    return Number.isFinite(opacity) ? opacity : 1;
  }
  function restore(node, saved) {
    for (const {name, value, priority} of saved) {
      if (value) node.style.setProperty(name, value, priority); else node.style.removeProperty(name);
    }
  }
  function finish(record, consume = true) {
    record.timeline?.kill(); record.timeline = null;
    for (const item of record.items) restore(item.node, item.saved);
    record.items = [];
    if (consume) { record.entered = true; remember(record.key); }
  }
  function paintEntry(record) {
    for (const item of record.items) {
      item.node.style.opacity = String(item.opacity * item.pose.alpha);
      // Independent scale leaves the authored transform and the content layout alone.
      if (item.accent) item.node.style.scale = item.pose.scale + ' 1';
    }
  }
  function reveal(record) {
    if (record.entered || disposed) return;
    if (seen.has(record.key) || quiet() || !ready()) { finish(record); return; }
    // Offscreen content stays fully readable. It is eligible on its first actual
    // appearance; an entrance interrupted by leaving the viewport is consumed.
    if (!record.visible) return;
    record.entered = true; remember(record.key);
    const root = record.node;
    const accents = [...root.querySelectorAll(ACCENT)].filter(node => owned(node, root) &&
      node.getAttribute('aria-hidden') === 'true' && !node.closest(ROW) &&
      !node.closest(CONTROL) && !node.querySelector(CONTROL) && !node.matches(OWNED));
    const parts = [...root.querySelectorAll('[data-qm-content-part]')].filter(node => owned(node, root) &&
      !node.closest(CONTROL) && !node.querySelector(CONTROL) && !node.matches(OWNED) && !node.querySelector(OWNED) &&
      !node.querySelector('[data-qm-content-part]') && !node.querySelector(ACCENT) && !node.matches(ACCENT));
    // Bound the work for long answer/table content. No text, number or progress
    // value is rewritten, and no control or whole content root is animated.
    const targets = [...accents.slice(0, 8).map(node => ({node, accent: true})),
      ...parts.slice(0, 10).map(node => ({node, accent: false}))];
    if (!targets.length) return;
    record.items = targets.map(({node, accent}) => ({node, accent,
      opacity: authoredOpacity(node),
      saved: save(node, ['opacity', 'scale', 'will-change']),
      pose: {alpha: accent ? .35 : .78, scale: accent ? .08 : 1}}));
    // All style reads above precede all writes. Stagger is bounded at 140ms so
    // even a long answer reaches its authored final state within 620ms.
    for (const item of record.items) item.node.style.willChange = item.accent ? 'opacity, scale' : 'opacity';
    paintEntry(record); starts++;
    record.timeline = win.gsap.timeline({paused: true, defaults: {ease: 'power2.out', overwrite: true},
      onUpdate: () => paintEntry(record), onComplete: () => finish(record)});
    record.timeline.to(record.items.map(item => item.pose), {alpha: 1, scale: 1, duration: .48,
      stagger: {amount: record.items.length > 1 ? .14 : 0}}, 0);
    record.timeline.play();
  }
  function stopRow(row) { row.tween?.kill(); row.tween = null; }
  function paintRow(row) {
    for (const item of row.items) {
      item.node.style.scale = (.55 + .45 * row.pose.amount) + ' 1';
      item.node.style.opacity = String(item.opacity + (1 - item.opacity) * row.pose.amount);
    }
  }
  function updateRow(row, animate = true) {
    const staticMode = quiet() || !ready() || !row.owner.visible;
    const target = !staticMode && (row.hovered || row.focused) ? 1 : 0;
    if (staticMode) {
      stopRow(row); row.target = null; row.pose.amount = 0;
      for (const item of row.items) restore(item.node, item.saved);
      return;
    }
    if (row.target === target) return;
    row.target = target; stopRow(row);
    if (!animate) { row.pose.amount = target; paintRow(row); return; }
    // Reversals always start at the current pose, with no overshoot or queued
    // reversal. This single owned tween never changes native event behavior.
    for (const item of row.items) item.node.style.willChange = 'opacity, scale';
    row.tween = win.gsap.to(row.pose, {amount: target, duration: .2, ease: 'power2.out', overwrite: true,
      onUpdate: () => paintRow(row), onComplete: () => {
        stopRow(row);
        for (const item of row.items) restore(item.node, item.saved.filter(style => style.name === 'will-change'));
      }});
  }
  function forgetRow(row) {
    stopRow(row);
    for (const item of row.items) restore(item.node, item.saved);
    rows.delete(row.node);
  }
  function mountRows(record) {
    if (record.node.dataset.qmContent !== 'comparison') return;
    for (const node of record.node.querySelectorAll(ROW)) {
      if (!owned(node, record.node) || rows.has(node)) continue;
      const accents = [...node.querySelectorAll(ACCENT)].filter(item => owned(item, record.node) &&
        item.closest(ROW) === node && item.getAttribute('aria-hidden') === 'true' && !item.closest(CONTROL) && !item.querySelector(CONTROL));
      if (!accents.length) continue;
      const row = {node, owner: record, tween: null, target: null, pose: {amount: 0}, hovered: false,
        focused: node.contains(doc.activeElement), items: accents.slice(0, 2).map(item => ({node: item,
          opacity: authoredOpacity(item),
          saved: save(item, ['opacity', 'scale', 'will-change'])}))};
      rows.set(node, row); updateRow(row, false);
    }
  }
  function forget(record) {
    finish(record, record.entered);
    for (const row of [...rows.values()]) if (row.owner === record) forgetRow(row);
    intersection?.unobserve(record.node); records.delete(record.node);
  }
  function scan() {
    frame = 0; if (disposed || !doc.body) return;
    for (const record of [...records.values()]) {
      if (!record.node.isConnected || !record.node.matches(ROOT) || !valid(record.node) ||
          keyOf(record.node) !== record.key || record.node.closest('[data-qm-visual-exit]')) forget(record);
    }
    for (const row of [...rows.values()]) if (!row.node.isConnected || !row.node.matches(ROW) ||
      row.items.some(item => !row.node.contains(item.node) || !item.node.matches(ACCENT))) forgetRow(row);
    // Geometry is read once per refresh, never from a GSAP update/ticker.
    const roots = [...doc.body.querySelectorAll(ROOT)].filter(node => valid(node) && !node.closest('[data-qm-visual-exit]'));
    const measurements = roots.map(node => ({node, visible: visible(node)}));
    for (const item of measurements) {
      let record = records.get(item.node);
      if (!record) {
        record = {node: item.node, key: keyOf(item.node), visible: item.visible, entered: false, items: [], timeline: null};
        records.set(item.node, record); intersection?.observe(item.node);
      } else {
        record.visible = item.visible;
        if (!item.visible && record.timeline) finish(record);
        if (record.items.some(target => !record.node.contains(target.node))) finish(record);
      }
      reveal(record); mountRows(record);
    }
    for (const row of rows.values()) updateRow(row, false);
  }
  function schedule() { if (!disposed && !frame) frame = win.requestAnimationFrame(scan); }
  const intersection = typeof win.IntersectionObserver === 'function' ? new win.IntersectionObserver(entries => {
    for (const entry of entries) {
      const record = records.get(entry.target); if (!record) continue;
      record.visible = entry.isIntersecting;
      if (record.visible) reveal(record); else if (record.timeline) finish(record);
      for (const row of rows.values()) if (row.owner === record) {
        if (!record.visible) row.hovered = false;
        updateRow(row, false);
      }
    }
  }, {threshold: 0}) : null;
  const mutations = new win.MutationObserver(changes => {
    if (changes.some(change => change.type === 'attributes' ||
      change.target instanceof win.Element && change.target.closest(ROOT) ||
      [...change.addedNodes, ...change.removedNodes].some(node => node instanceof win.Element && (node.matches(ROOT) || node.querySelector(ROOT))))) schedule();
  });
  mutations.observe(doc, {childList: true, subtree: true, attributes: true,
    attributeFilter: ['data-qm-content', 'data-qm-content-key', 'data-qm-content-part', 'data-qm-content-accent', 'data-qm-comparison-row']});
  function point(event, enter) {
    if (!(event.target instanceof win.Element) || event.pointerType === 'touch') return;
    const row = rows.get(event.target.closest(ROW));
    if (!row || event.relatedTarget instanceof win.Node && row.node.contains(event.relatedTarget)) return;
    row.hovered = enter; updateRow(row);
  }
  function focus(event, enter) {
    if (!(event.target instanceof win.Element)) return;
    const row = rows.get(event.target.closest(ROW));
    if (!row || event.relatedTarget instanceof win.Node && row.node.contains(event.relatedTarget)) return;
    row.focused = enter; updateRow(row);
  }
  function mode() {
    if (quiet()) for (const record of records.values()) finish(record);
    for (const row of rows.values()) { if (doc.hidden) row.hovered = false; updateRow(row, false); }
    schedule();
  }
  function cancelPointer(event) {
    if (!(event.target instanceof win.Element)) return;
    const row = rows.get(event.target.closest(ROW));
    if (row) { row.hovered = false; updateRow(row); }
  }
  function dispose() {
    if (disposed) return;
    disposed = true; if (frame) win.cancelAnimationFrame(frame); frame = 0;
    mutations.disconnect(); intersection?.disconnect();
    for (const record of [...records.values()]) forget(record);
    seen.clear(); abort.abort(); media?.removeEventListener?.('change', mode);
  }
  const options = {signal: abort.signal};
  doc.addEventListener('visibilitychange', mode, options);
  win.addEventListener('qm-motion-preference-change', mode, options);
  win.addEventListener('pagehide', dispose, options);
  win.addEventListener('resize', schedule, {...options, passive: true});
  if (!intersection) doc.addEventListener('scroll', schedule, {...options, capture: true, passive: true});
  doc.addEventListener('pointerover', event => point(event, true), {...options, passive: true});
  doc.addEventListener('pointerout', event => point(event, false), {...options, passive: true});
  doc.addEventListener('pointercancel', cancelPointer, {...options, passive: true});
  doc.addEventListener('focusin', event => focus(event, true), options);
  doc.addEventListener('focusout', event => focus(event, false), options);
  media?.addEventListener?.('change', mode);
  win.QMContentMotion = {version: VERSION, refresh: schedule, dispose,
    getState: () => ({roots: records.size, rows: rows.size, remembered: seen.size, starts,
      running: [...records.values()].filter(record => record.timeline).length + [...rows.values()].filter(row => row.tween).length,
      pending: Boolean(frame), disposed})};
  schedule();
})(window);
