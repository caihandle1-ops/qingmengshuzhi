'use strict';
// Real production adaptive-quality controller, deterministic RAF timestamps.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/hero_frontend/hero-quality.js'), 'utf8'), context);
function clock() {
  let now = 0;
  const changes = [];
  const quality = context.QMHeroQuality.createQuality(state => changes.push({now, tier: state.tier}));
  quality.ratio(2);
  quality.sample(now);
  return {quality, changes,
    advance(duration, interval = 16.67, eligible = true) {
      const end = now + duration;
      while (now < end) { now += interval; quality.sample(now, eligible); }
    },
    sample(interval, eligible = true) { now += interval; quality.sample(now, eligible); },
  };
}

const adaptive = clock();
assert.equal(adaptive.quality.ratio(2), 2, 'start at the existing full pixel density');
adaptive.advance(1700, 40);
assert.equal(adaptive.changes.length, 0, 'shader warmup cannot trigger a downgrade');
adaptive.advance(4500, 40);
assert.equal(adaptive.quality.getState().tier, 1, 'two sustained slow windows select one lower pixel-density tier');
assert.equal(adaptive.quality.ratio(2), 1.64);
adaptive.advance(8000, 40);
assert.equal(adaptive.quality.getState().tier, 2);
assert.equal(adaptive.quality.ratio(2), 1.34);
adaptive.advance(20000, 40);
assert.equal(adaptive.changes.length, 2, 'bounded tiers never remove scene geometry or reduce RAF frequency');
adaptive.advance(23000);
assert.equal(adaptive.quality.getState().tier, 0, 'four stable windows per level recover full clarity');
assert.deepEqual(adaptive.changes.map(item => item.tier), [1, 2, 1, 0]);
assert.ok(adaptive.changes.slice(1).every((entry, index) => entry.now - adaptive.changes[index].now >= 6000), 'hysteresis prevents quality oscillation');

const spikes = clock();
for (let n = 0; n < 25; n++) { spikes.advance(1800); spikes.sample(450); }
assert.equal(spikes.quality.getState().tier, 0, 'isolated long task spikes do not masquerade as sustained slow rendering');
spikes.sample(30000); spikes.advance(1700, 40);
assert.equal(spikes.quality.getState().tier, 0, 'sleep/wake discontinuity requires fresh warmup');
const unstable = clock();
for (let n = 0; n < 7; n++) { unstable.advance(1800, 40); unstable.advance(2000, 16.67); }
assert.ok(unstable.changes.length <= 1, 'mixed rendering windows cannot repeatedly bounce tiers');

for (const reason of ['hidden', 'offscreen', 'research', 'OS reduced', 'context loss']) {
  const paused = clock(); paused.advance(5800, 40);
  const previous = paused.quality.getState().tier;
  paused.quality.pause();
  assert.equal(paused.quality.getState().sampling, false, reason + ' clears stale sampling');
  paused.advance(15000, 40, false);
  assert.equal(paused.quality.getState().tier, previous, reason + ' does not train the quality controller');
  paused.advance(1700, 40);
  assert.equal(paused.quality.getState().tier, previous, reason + ' resume begins with warmup');
  paused.advance(23000);
  assert.equal(paused.quality.getState().tier, 0, reason + ' eventually recovers with a fresh stable run');
}

const zoom = clock(); zoom.advance(15000, 40);
assert.equal(zoom.quality.getState().tier, 2);
assert.equal(zoom.quality.ratio(1), .75, 'low-resolution displays retain a readable density floor');
assert.equal(zoom.quality.getState().sampling, false, 'display DPR changes discard old samples');
assert.equal(zoom.quality.ratio(10), 1.34, 'high-DPR displays keep the original two-times pixel cap');
assert.equal(zoom.quality.ratio(NaN), .75, 'invalid DPR falls back safely');
for (const deviceRatio of [.5, .625]) {
  const scaled = clock();
  assert.equal(scaled.quality.ratio(deviceRatio), deviceRatio, 'browser zoom below the floor preserves the original default pixel count');
  scaled.advance(15000, 40);
  assert.equal(scaled.quality.getState().tier, 2);
  const pixelRatio = scaled.quality.ratio(deviceRatio);
  assert.ok(Number.isFinite(pixelRatio) && pixelRatio > 0 && pixelRatio <= deviceRatio, 'lower tiers never increase pixel cost at a low native DPR');
  scaled.advance(24000);
  assert.equal(scaled.quality.getState().tier, 0);
  assert.equal(scaled.quality.ratio(deviceRatio), deviceRatio, 'stable recovery also respects low browser-zoom DPR');
}
zoom.quality.dispose();
const frozen = JSON.stringify(zoom.quality.getState()), count = zoom.changes.length;
zoom.advance(50000); zoom.quality.pause(); zoom.quality.ratio(2);
assert.equal(JSON.stringify(zoom.quality.getState()), frozen, 'disposed controller cannot revive or mutate');
assert.equal(zoom.changes.length, count);
assert.equal(zoom.quality.getState().samples, 0);
console.log('hero quality: warmup, sustained slowdown/recovery, hysteresis, isolated spikes, paused sampling, DPR bounds and cleanup passed');
