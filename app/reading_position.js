/* Keep a reading control in place during its own native rerender. No text/data storage. */
(function (host) {
  'use strict';
  function createReadingPosition(env) {
    const doc = env.document, win = env.window, abort = new env.AbortController();
    let pending = null, frame = 0, timer = 0, disposed = false;
    const prefix = /^st-key-(?:source_(?:button|table_button|docx_button|page|docx_location)_|enterprise_chart_(?:type|metrics)$)/;
    const allowed = key => prefix.test(key) || /^st-key-\w+_report_reader_toggle$/.test(key);
    const scene = () => doc.querySelector('[data-studio-location]')?.getAttribute('data-studio-scene') || '';
    const owner = node => {
      for (let item = node; item && item !== doc.body; item = item.parentElement) {
        const key = Array.from(item.classList || []).find(allowed);
        if (key) return {node: item, key};
      }
      return null;
    };
    function cancel() {
      pending = null;
      if (frame) env.cancelAnimationFrame(frame);
      if (timer) env.clearTimeout(timer);
      frame = 0; timer = 0;
    }
    function capture(event) {
      if (disposed || doc.hidden || (event.type === 'keydown' && !['Enter', ' '].includes(event.key))) return;
      const selected = owner(event.target);
      if (!selected) { if (event.type === 'keydown' || !event.target.closest?.('[role="listbox"]')) cancel(); return; }
      const main = doc.querySelector('[data-testid="stMain"]');
      if (!main || !main.contains(selected.node)) return;
      cancel();
      pending = {key: selected.key, scene: scene(), top: selected.node.getBoundingClientRect().top, main};
      timer = env.setTimeout(cancel, 2200);
    }
    function restore() {
      frame = 0;
      if (!pending || disposed) return;
      if (doc.hidden || scene() !== pending.scene || doc.querySelector('[data-testid="stMain"]') !== pending.main) { cancel(); return; }
      const node = doc.querySelector('.' + env.escape(pending.key));
      if (!node || node.closest?.('[data-stale="true"]')) return;
      const delta = node.getBoundingClientRect().top - pending.top;
      if (!Number.isFinite(delta) || Math.abs(delta) < 1 || Math.abs(delta) > win.innerHeight) return;
      const main = pending.main, before = main.scrollTop;
      main.scrollTop = Math.max(0, Math.min(main.scrollHeight - main.clientHeight, before + delta));
      // Native clamping at document boundaries has priority; never force height.
    }
    function refresh() { if (pending && !frame && !disposed) frame = env.requestAnimationFrame(restore); }
    const options = {capture: true, signal: abort.signal};
    doc.addEventListener('pointerdown', capture, options);
    doc.addEventListener('keydown', event => {
      if (['Tab', 'PageDown', 'PageUp', 'Home', 'End', 'ArrowDown', 'ArrowUp', 'Escape'].includes(event.key)) cancel();
      else capture(event);
    }, options);
    // Manual scrolling or navigation always wins over automatic preservation.
    doc.addEventListener('wheel', cancel, {passive: true, capture: true, signal: abort.signal});
    doc.addEventListener('touchmove', cancel, {passive: true, capture: true, signal: abort.signal});
    doc.addEventListener('visibilitychange', cancel, {signal: abort.signal});
    win.addEventListener('resize', cancel, {signal: abort.signal});
    const mutations = new env.MutationObserver(refresh);
    mutations.observe(doc, {subtree: true, childList: true, attributes: true,
      attributeFilter: ['class', 'style', 'data-stale', 'data-studio-scene']});
    const resize = env.ResizeObserver ? new env.ResizeObserver(refresh) : null;
    const content = doc.querySelector('[data-testid="stMainBlockContainer"]');
    if (content) resize?.observe(content);
    const dispose = () => { if (disposed) return; disposed = true; cancel(); abort.abort(); mutations.disconnect(); resize?.disconnect(); };
    win.addEventListener('pagehide', dispose, {signal: abort.signal});
    return {refresh, cancel, dispose, version: '20261008.1-body-ready20'};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {createReadingPosition};
  if (host.document && host.MutationObserver) {
    if (host.__qmReadingPosition?.version === '20261008.1-body-ready20') { host.__qmReadingPosition.refresh(); return; }
    host.__qmReadingPosition?.dispose();
    host.__qmReadingPosition = createReadingPosition({document: host.document, window: host,
      AbortController: host.AbortController, MutationObserver: host.MutationObserver, ResizeObserver: host.ResizeObserver,
      requestAnimationFrame: host.requestAnimationFrame.bind(host), cancelAnimationFrame: host.cancelAnimationFrame.bind(host),
      setTimeout: host.setTimeout.bind(host), clearTimeout: host.clearTimeout.bind(host), escape: host.CSS.escape});
  }
})(typeof window === 'undefined' ? globalThis : window);
