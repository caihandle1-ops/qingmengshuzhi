/* Keyboard enhancement for the mounted native search surface. No cloned UI. */
(function(win) {
  'use strict';
  const VERSION = '2026-10-11.17.2-body-ready20', doc = win.document;
  if (win.QMCommandPalette?.version === VERSION) return;
  win.QMCommandPalette?.dispose();
  const abort = new win.AbortController(), signal = abort.signal;
  const media = win.matchMedia('(prefers-reduced-motion: reduce)');
  const panelSelector = '.st-key-workspace_search_results';
  const triggerSelector = '.st-key-workspace_search_open_button button';
  const inputSelector = '.st-key-workspace_palette_query input';
  const resultSelector = '[class*="st-key-workspace_search_item_"] button';
  let panel = null, selected = null, origin = null, pendingOpen = false;
  let pendingClose = false, composing = false, frame = 0, disposed = false, context = null;
  let openFrame = 0, openRequested = false;
  let focusReturn = null, focusFrame = 0, settleFrame = 0, returnTimer = 0;
  const triggers = new Map();
  const quiet = () => media.matches || doc.hidden || doc.documentElement.dataset.qmMotionMode === 'research';
  function visible(node) {
    if (!node?.isConnected || node.closest('[hidden],[inert],[aria-hidden="true"]')) return false;
    const style = win.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    // Tabs often hide a parent instead of their individual result buttons.
    for (let parent = node.parentElement; parent; parent = parent.parentElement) {
      const css = win.getComputedStyle(parent);
      if (css.display === 'none' || css.visibility === 'hidden') return false;
    }
    const box = node.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }
  const enabled = node => node && !node.disabled && node.getAttribute('aria-disabled') !== 'true';
  const results = () => panel ? [...panel.querySelectorAll(resultSelector)].filter(node => enabled(node) && visible(node)) : [];
  const input = () => panel?.querySelector(inputSelector);
  function foreignPopup(target) {
    if (target?.closest('[data-testid="stDialog"],[role="dialog"],[role="listbox"],[data-baseweb="popover"]')) return true;
    return [...doc.querySelectorAll('[data-testid="stDialog"],[role="dialog"][aria-modal="true"],[role="listbox"]')]
      .some(node => !panel?.contains(node) && visible(node));
  }
  function rememberOrigin(node) {
    if (!node || node === doc.body || panel?.contains(node)) return;
    const keyed = node.closest('[class*="st-key-"]');
    const key = keyed && [...keyed.classList].find(name => name.startsWith('st-key-'));
    const type = node.matches('input,textarea,button,a,select') ? node.tagName.toLowerCase() : null;
    const main = scrollRoot();
    origin = {node, key, type, index: keyed && type ? [...keyed.querySelectorAll(type)].indexOf(node) : -1,
      start: node.selectionStart, end: node.selectionEnd, route: route(),
      scrollTop: main?.scrollTop || 0, scrollLeft: main?.scrollLeft || 0};
  }
  const route = () => doc.querySelector('[data-studio-location]')?.getAttribute('data-studio-location') || '';
  const scrollRoot = () => doc.querySelector('[data-testid="stMain"]') || doc.scrollingElement || doc.documentElement;
  function originalControl(record) {
    let target = record.node;
    if (!target?.isConnected && record.key && record.type) {
      const keyed = doc.getElementsByClassName(record.key)[0];
      target = keyed?.querySelectorAll(record.type)[record.index];
    }
    return target && !target.closest('[data-stale="true"]') && visible(target) && enabled(target) ? target : null;
  }
  function cancelReturn() {
    if (focusFrame) win.cancelAnimationFrame(focusFrame);
    if (settleFrame) win.cancelAnimationFrame(settleFrame);
    if (returnTimer) win.clearTimeout(returnTimer);
    focusFrame = 0; settleFrame = 0; returnTimer = 0; focusReturn = null;
  }
  function fallbackFocus() {
    const target = [...doc.querySelectorAll(triggerSelector)].find(visible) ||
      doc.querySelector('.st-key-header_search_desktop input');
    if (visible(target) && enabled(target)) target.focus({preventScroll: true});
  }
  function restoreFocus() {
    const record = focusReturn;
    if (!record || disposed || focusFrame || settleFrame || doc.querySelector(panelSelector)) return;
    if (doc.hidden || foreignPopup(doc.activeElement) || (record.route && route() && record.route !== route())) {
      cancelReturn(); return;
    }
    const initial = originalControl(record);
    if (!initial || (initial === record.lastTarget && doc.activeElement === initial)) return;
    // A Streamlit close can remove search before the original widget mounts.
    // Resolve a non-stale native control across two paints, and retain a short
    // recovery record for a subsequent replacement in the same native rerun.
    focusFrame = win.requestAnimationFrame(() => {
      focusFrame = 0;
      if (focusReturn !== record) return;
      const candidate = originalControl(record);
      settleFrame = win.requestAnimationFrame(() => {
        settleFrame = 0;
        if (focusReturn !== record || disposed || doc.hidden || doc.querySelector(panelSelector)) return;
        if ((record.route && route() && record.route !== route()) || foreignPopup(doc.activeElement)) { cancelReturn(); return; }
        const target = originalControl(record);
        if (!target) return;
        if (target !== candidate) { schedule(); return; }
        const main = scrollRoot();
        const maxScroll = main ? Math.max(0, main.scrollHeight - main.clientHeight) : 0;
        // Wait for enough native content to restore the old position instead of
        // clamping to a short partial page and bouncing on its next render.
        if (!record.scrollRestored && main && maxScroll + 2 < record.scrollTop) return;
        if (!record.scrollRestored && main) {
          if (typeof main.scrollTo === 'function') main.scrollTo({top:record.scrollTop, left:record.scrollLeft, behavior:'instant'});
          else { main.scrollTop = record.scrollTop; main.scrollLeft = record.scrollLeft; }
          record.scrollRestored = true;
        }
        target.focus({preventScroll:true});
        try { if (Number.isInteger(record.start)) target.setSelectionRange(record.start, record.end); } catch (_) { /* non-text input */ }
        record.lastTarget = target; record.attempts++;
        if (record.attempts >= 4) cancelReturn();
      });
    });
  }
  function beginReturn() {
    cancelReturn();
    if (!origin) { fallbackFocus(); return; }
    const record = focusReturn = {...origin, lastTarget:null, attempts:0, scrollRestored:false};
    origin = null;
    returnTimer = win.setTimeout(() => {
      if (focusReturn !== record) return;
      const fallback = !record.lastTarget && !doc.hidden && !doc.querySelector(panelSelector) &&
        !foreignPopup(doc.activeElement) && (!record.route || !route() || record.route === route());
      cancelReturn(); if (fallback) fallbackFocus();
    }, 1800);
    restoreFocus();
  }
  function mark(node) {
    if (selected === node) return;
    selected?.removeAttribute('data-qm-command-active');
    selected = node;
    selected?.setAttribute('data-qm-command-active', 'true');
  }
  function focusInput(scroll = false) {
    const field = input();
    if (!field || !enabled(field)) return false;
    mark(null); field.focus({preventScroll: true});
    if (scroll) panel.scrollIntoView?.({block: 'start', behavior: 'instant'});
    return true;
  }
  function stopMotion() { context?.revert(); context = null; }
  function entrance() {
    stopMotion();
    const rule = panel?.querySelector('.qm-command-rule');
    if (!rule || quiet() || !win.gsap) return;
    // Only a decorative rule animates. Native inputs and hit areas stay still.
    context = win.gsap.context(() => {
      win.gsap.fromTo(rule, {scaleX: .08}, {scaleX: 1, duration: .42, ease: 'power3.out'});
    }, panel);
  }
  function queueNativeOpen() {
    if (openFrame || !openRequested || disposed) return;
    openFrame = win.requestAnimationFrame(() => {
      openFrame = 0;
      if (disposed || !openRequested) return;
      if (foreignPopup(doc.activeElement)) { openRequested = false; pendingOpen = false; return; }
      if (doc.querySelector(panelSelector)) { openRequested = false; schedule(); return; }
      // Blur may have caused a native rerun. Resolve its current real button,
      // never hold a detached React control or write to any input/React state.
      const target = [...doc.querySelectorAll(triggerSelector)].find(enabled);
      if (!target) return; // A later DOM mount retries through refresh().
      openRequested = false;
      target.click();
    });
  }
  function refresh() {
    frame = 0; if (disposed) return;
    for (const node of doc.querySelectorAll(triggerSelector)) {
      if (!triggers.has(node)) {
        triggers.set(node, node.getAttribute('aria-keyshortcuts'));
        node.setAttribute('aria-keyshortcuts', 'Control+k Meta+k');
      }
    }
    for (const [node] of triggers) if (!node.isConnected) triggers.delete(node);
    const next = doc.querySelector(panelSelector);
    if (next !== panel) {
      const wasOpen = !!panel; stopMotion(); mark(null); panel = next;
      if (panel) { cancelReturn(); entrance(); if (pendingOpen) focusInput(true); }
      else if (wasOpen && pendingClose) { beginReturn(); pendingClose = false; }
    }
    if (panel && pendingOpen && focusInput(true)) pendingOpen = false;
    if (selected && (!selected.isConnected || !panel?.contains(selected) || !visible(selected))) mark(null);
    if (openRequested) queueNativeOpen();
    restoreFocus();
  }
  function schedule() { if (!frame && !disposed) frame = win.requestAnimationFrame(refresh); }
  function dirtyInput() {
    const field = input(), marker = panel?.querySelector('[data-qm-command-query]');
    return !!field && !!marker && field.value.trim() !== marker.dataset.qmCommandQuery;
  }
  function keydown(event) {
    if (focusReturn) cancelReturn(); // Any new keyboard action takes precedence.
    if (disposed || event.defaultPrevented || event.isComposing || composing || event.keyCode === 229 || event.repeat) return;
    const target = event.target;
    if (foreignPopup(target)) return;
    const shortcut = (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k';
    if (shortcut) {
      const trigger = [...doc.querySelectorAll(triggerSelector)].find(enabled);
      if (!panel && !trigger) return;
      event.preventDefault(); event.stopPropagation();
      if (panel) focusInput(true);
      else {
        if (openRequested) return;
        const active = doc.activeElement;
        rememberOrigin(active); pendingOpen = true; pendingClose = false; openRequested = true;
        // A programmatic click does not blur the focused Streamlit input.
        // Move focus just as a real pointer click would, so its native onBlur
        // commits a draft before preserve_inputs() runs on the server.
        trigger.focus({preventScroll: true});
        if (doc.activeElement === active) active?.blur?.(); // collapsed sidebar
        queueNativeOpen();
      }
      return;
    }
    if (!panel || !panel.contains(target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'Escape') {
      const close = panel.querySelector('.st-key-workspace_search_close button');
      if (!enabled(close)) return;
      event.preventDefault(); event.stopPropagation(); pendingClose = true; pendingOpen = false; close.click(); return;
    }
    if (!['ArrowDown', 'ArrowUp'].includes(event.key) || dirtyInput()) return;
    // Preserve arrow behavior in native tabs and any future selects/textareas.
    if (target !== input() && !target.matches(resultSelector)) return;
    const items = results(); if (!items.length) return;
    event.preventDefault(); event.stopPropagation();
    const current = items.indexOf(target);
    if (event.key === 'ArrowUp' && current === 0) { focusInput(); return; }
    const next = event.key === 'ArrowDown' ? (current + 1) % items.length : current < 0 ? items.length - 1 : current - 1;
    mark(items[next]); items[next].focus({preventScroll: true});
    items[next].scrollIntoView?.({block: 'nearest', behavior: 'instant'});
    // Enter deliberately remains native: one real button activation/callback.
  }
  function click(event) {
    if (focusReturn) cancelReturn();
    const trigger = event.target.closest?.(triggerSelector);
    if (trigger && !panel) {
      if (!pendingOpen) rememberOrigin(trigger);
      pendingOpen = true; pendingClose = false;
    }
    if (panel?.contains(event.target)) {
      if (event.target.closest('.st-key-workspace_search_close')) { pendingClose = true; pendingOpen = false; }
      else if (event.target.closest(resultSelector)) { pendingClose = false; origin = null; }
    }
  }
  doc.addEventListener('keydown', keydown, {capture: true, signal});
  doc.addEventListener('click', click, {capture: true, signal});
  doc.addEventListener('compositionstart', () => { composing = true; }, {capture: true, signal});
  doc.addEventListener('compositionend', () => { composing = false; }, {capture: true, signal});
  doc.addEventListener('focusin', event => {
    if (panel?.contains(event.target)) mark(event.target.matches(resultSelector) ? event.target : null);
  }, {signal});
  const observer = new win.MutationObserver(schedule);
  observer.observe(doc, {childList: true, subtree: true, attributes:true, attributeFilter:['data-stale']});
  doc.addEventListener('pointerdown', cancelReturn, {capture:true, signal});
  doc.addEventListener('wheel', cancelReturn, {capture:true, passive:true, signal});
  doc.addEventListener('touchmove', cancelReturn, {capture:true, passive:true, signal});
  media.addEventListener('change', stopMotion, {signal});
  doc.addEventListener('visibilitychange', stopMotion, {signal});
  doc.addEventListener('visibilitychange', cancelReturn, {signal});
  win.addEventListener('qm-motion-preference-change', stopMotion, {signal});
  function dispose() {
    if (disposed) return; disposed = true; abort.abort(); observer.disconnect();
    if (frame) win.cancelAnimationFrame(frame); frame = 0;
    if (openFrame) win.cancelAnimationFrame(openFrame); openFrame = 0; openRequested = false;
    stopMotion(); mark(null); cancelReturn();
    for (const [node, value] of triggers) {
      if (value === null) node.removeAttribute('aria-keyshortcuts'); else node.setAttribute('aria-keyshortcuts', value);
    }
    triggers.clear(); origin = null; panel = null;
  }
  win.QMCommandPalette = {version: VERSION, dispose};
  refresh();
})(window);
