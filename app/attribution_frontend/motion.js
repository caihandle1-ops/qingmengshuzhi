/* Numeric presentation state only; no financial data, network, or component events. */
(function (global) {
  'use strict';
  const clamp = value => Math.max(0, Math.min(1, value));
  function createMotion(env, draw, count) {
    let frame = 0, disposed = false, visible = true, reduced = !!env.reduced;
    let current = [0, ...Array.from({length: count}, (_, index) => index === 0 ? 1 : 0)];
    let from = current.slice(), target = current.slice(), start = env.now(), duration = 900;
    let active = 0, expanded = false;
    const enabled = () => !disposed && visible && !env.hidden();
    const moving = () => current.some((value, index) => value !== target[index]);
    function sample(now) {
      const t = reduced ? 1 : clamp((now - start) / duration), eased = 1 - Math.pow(1 - t, 3);
      current = from.map((value, index) => t === 1 ? target[index] : value + (target[index] - value) * eased);
    }
    function emit() {
      draw({open: current[0], focus: current.slice(1), active, expanded,
        phase: moving() ? (expanded ? 'expanding' : 'collapsing') : (expanded ? 'open' : 'closed')});
    }
    function stop() { if (frame) env.cancel(frame); frame = 0; }
    function paint(now) {
      frame = 0;
      if (!enabled()) return;
      sample(now); emit();
      if (moving()) frame = env.raf(paint);
    }
    function request() { if (enabled() && !frame) frame = env.raf(paint); }
    function settle() { stop(); current = target.slice(); from = current.slice(); start = env.now(); }
    function change(open, index) {
      if (disposed || !Number.isInteger(index) || index < 0 || index >= count) return;
      if (open === expanded && index === active) return;
      // Sample the live pose before reversing, including between RAF callbacks.
      sample(env.now()); from = current.slice(); expanded = !!open; active = index;
      target = [expanded ? 1 : 0, ...Array.from({length: count}, (_, position) => position === index ? 1 : 0)];
      start = env.now(); duration = from[0] !== target[0] ? 900 : 460;
      if (reduced || !enabled()) settle();
      if (enabled()) { emit(); request(); }
    }
    const api = {
      toggle() { change(!expanded, 0); },
      focus(index) { change(index > 0 ? true : expanded, index); },
      close() { change(false, 0); },
      setVisible(next) {
        if (disposed) return;
        visible = !!next;
        if (!visible) settle(); else { emit(); request(); }
      },
      syncVisibility() {
        if (disposed) return;
        if (!enabled()) settle(); else { emit(); request(); }
      },
      setReduced(next) {
        if (disposed) return;
        reduced = !!next;
        if (reduced) settle();
        if (enabled()) { emit(); request(); }
      },
      invalidate() { if (enabled()) { emit(); request(); } },
      getState() { return {open: current[0], focus: current.slice(1), active, expanded, frame, visible, reduced, disposed}; },
      dispose() { disposed = true; stop(); },
    };
    emit(); request(); return api;
  }
  global.QMAttributionMotion = {createMotion};
})(typeof window !== 'undefined' ? window : globalThis);
