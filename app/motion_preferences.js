/* Small, explicit preference protocol. No prototype patches or cross-frame messages. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.QMMotionPreferences = api;
})(typeof window === 'undefined' ? globalThis : window, function () {
  'use strict';
  const VERSION = '2026-10-09.2', EVENT = 'qm-motion-preference-change';
  const normalize = value => value?.version === 1 && value.mode === 'research' ? 'research' : 'presentation';
  function createPreferenceRuntime(env, initial) {
    let mode = normalize(initial), disposed = false, last = '';
    function sync() {
      if (disposed) return;
      const reduced = Boolean(env.reduced()), level = reduced ? 'reduced' : mode === 'presentation' ? 'enhanced' : 'light';
      const key = mode + ':' + level;
      env.apply({version: 1, mode, level, reduced});
      if (key !== last) { last = key; env.notify({version: 1, mode, level, reduced}); }
    }
    const stop = env.listenReduced(sync);
    sync();
    return {version: VERSION, set(value) { if (disposed) return; mode = normalize(value); sync(); },
      snapshot() { return {version: 1, mode, reduced: Boolean(env.reduced())}; },
      dispose() { if (disposed) return; disposed = true; stop(); }};
  }
  function install(win, doc, value) {
    if (win.__qmMotionPreferences?.version === VERSION) { win.__qmMotionPreferences.set(value); return win.__qmMotionPreferences; }
    win.__qmMotionPreferences?.dispose();
    const media = win.matchMedia('(prefers-reduced-motion: reduce)');
    const api = createPreferenceRuntime({reduced: () => media.matches,
      apply: state => { doc.documentElement.dataset.qmMotionMode = state.mode; doc.documentElement.dataset.qmMotionLevel = state.level; },
      notify: state => win.dispatchEvent(new win.CustomEvent(EVENT, {detail: state})),
      listenReduced: sync => { media.addEventListener('change', sync); return () => media.removeEventListener('change', sync); }
    }, value);
    const finish = () => { api.dispose(); win.removeEventListener('pagehide', finish); };
    win.addEventListener('pagehide', finish, {once: true});
    const dispose = api.dispose;
    api.dispose = () => { dispose(); win.removeEventListener('pagehide', finish); };
    win.__qmMotionPreferences = api;
    return api;
  }
  return {VERSION, EVENT, normalize, createPreferenceRuntime, install};
});
