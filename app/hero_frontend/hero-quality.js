/* Pixel density only: every object, light and animation remains intact.
 * Samples come from the existing visible animation RAF; no timers or device
 * fingerprinting. Short spikes cannot qualify an entire observation window. */
(function (global) {
  'use strict';
  const scales = [1, .82, .67];
  const warmup = 1800, windowDuration = 1800, cooldown = 6000;
  function createQuality(onChange = () => {}) {
    let tier = 0, disposed = false, last = null, warmAt = null, windowAt = null;
    let samples = [], badWindows = 0, goodWindows = 0, changedAt = -Infinity;
    let nativeRatio = 1;
    function reset() {
      last = warmAt = windowAt = null;
      samples = []; badWindows = goodWindows = 0;
    }
    function getState() {
      return {tier, scale: scales[tier], ratio: Math.max(Math.min(.75, nativeRatio), nativeRatio * scales[tier]),
        sampling: !disposed && last !== null, samples: samples.length, disposed};
    }
    function setTier(next, now) {
      tier = next; changedAt = now; samples = []; badWindows = goodWindows = 0;
      windowAt = now; onChange(getState());
    }
    function sample(now, eligible = true) {
      if (disposed) return;
      if (!eligible || !Number.isFinite(now)) { reset(); return; }
      if (last === null) { last = warmAt = now; return; }
      const elapsed = now - last; last = now;
      if (elapsed <= 0) return;
      // A suspended main thread or sleep/wake is not a rendering benchmark.
      if (elapsed > 1000) { reset(); last = warmAt = now; return; }
      if (now - warmAt < warmup) return;
      if (windowAt === null) { windowAt = now; return; }
      samples.push(Math.min(elapsed, 100));
      if (now - windowAt < windowDuration || samples.length < 20) return;
      const sorted = samples.slice().sort((a, b) => a - b);
      const percentile = amount => sorted[Math.floor((sorted.length - 1) * amount)];
      const slow = percentile(.75) > 24;
      const smooth = percentile(.90) < 19;
      badWindows = slow ? badWindows + 1 : 0;
      goodWindows = smooth ? goodWindows + 1 : 0;
      samples = []; windowAt = now;
      if (now - changedAt < cooldown) return;
      if (badWindows >= 2 && tier < scales.length - 1) setTier(tier + 1, now);
      else if (goodWindows >= 4 && tier > 0) setTier(tier - 1, now);
    }
    return {
      sample,
      pause() { if (!disposed) reset(); },
      ratio(deviceRatio) {
        const next = Number.isFinite(deviceRatio) && deviceRatio > 0 ? Math.min(deviceRatio, 2) : 1;
        if (!disposed && next !== nativeRatio) { nativeRatio = next; reset(); }
        return getState().ratio;
      },
      getState,
      dispose() { disposed = true; reset(); },
    };
  }
  global.QMHeroQuality = {createQuality};
})(typeof window !== 'undefined' ? window : globalThis);
