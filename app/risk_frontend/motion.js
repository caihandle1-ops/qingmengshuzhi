/* A reversible camera clock; it never receives financial values or source data. */
(function (global) {
  'use strict';
  function createCamera(env, draw, count = 6) {
    let current = [0, 0, 1, ...Array(count).fill(1)], from = current.slice(), target = current.slice();
    let start = env.now(), frame = 0, selected = null, reduced = !!env.reduced, visible = true, disposed = false;
    const enabled = () => !disposed && visible && !env.hidden();
    const moving = () => current.some((value, index) => value !== target[index]);
    function sample(now) {
      const time = reduced ? 1 : Math.max(0, Math.min(1, (now - start) / 900));
      const eased = 1 - Math.pow(1 - time, 3);
      current = from.map((value, index) => time === 1 ? target[index] : value + (target[index] - value) * eased);
    }
    function emit() { draw({x: current[0], y: current[1], zoom: current[2], weights: current.slice(3), selected,
      phase: moving() ? (selected === null ? 'returning' : 'focusing') : selected === null ? 'overview' : 'focused'}); }
    function stop() { if (frame) env.cancel(frame); frame = 0; }
    function settle() { stop(); current = target.slice(); from = current.slice(); start = env.now(); }
    function paint(now) { frame = 0; if (!enabled()) return; sample(now); emit(); if (moving()) frame = env.raf(paint); }
    function request() { if (enabled() && !frame) frame = env.raf(paint); }
    function change(next, index) {
      if (disposed || (selected === index && next.every((value, position) => value === target[position]))) return;
      sample(env.now()); from = current.slice(); target = next; selected = index; start = env.now();
      if (reduced || !enabled()) settle();
      if (enabled()) { emit(); request(); }
    }
    const api = {
      focus(index, x, y, zoom = 1.32) {
        if (!Number.isInteger(index) || index < 0 || index >= count || ![x, y, zoom].every(Number.isFinite) || zoom < 1 || zoom > 2) return;
        change([x, y, zoom, ...Array.from({length: count}, (_, position) => position === index ? 1 : 0)], index);
      },
      reset() { change([0, 0, 1, ...Array(count).fill(1)], null); },
      setVisible(next) { if (disposed) return; visible = !!next; if (!visible) settle(); else { emit(); request(); } },
      syncVisibility() { if (disposed) return; if (!enabled()) settle(); else { emit(); request(); } },
      setReduced(next) { if (disposed) return; reduced = !!next; if (reduced) settle(); if (enabled()) { emit(); request(); } },
      invalidate() { if (enabled()) { emit(); request(); } },
      getState() { return {x: current[0], y: current[1], zoom: current[2], selected, frame, visible, reduced, disposed}; },
      dispose() { disposed = true; stop(); },
    };
    emit(); request(); return api;
  }
  global.QMRiskCamera = {createCamera};
})(typeof window !== 'undefined' ? window : globalThis);
