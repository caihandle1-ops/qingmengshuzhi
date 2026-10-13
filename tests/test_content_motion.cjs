'use strict';
// Actual pinned GSAP + jsdom. Geometry/visibility and scheduled DOM refreshes
// are deterministic; production timelines are inspected and advanced directly.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM, VirtualConsole} = require('jsdom');
const read = name => fs.readFileSync(path.join(__dirname, '../app', name), 'utf8');

function fixture(engine = true) {
  const errors = [], bridge = new VirtualConsole();
  bridge.on('jsdomError', error => errors.push(String(error)));
  bridge.on('warn', message => errors.push(String(message)));
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: bridge
  });
  const win = dom.window, doc = win.document, mediaListeners = new Set(), frames = new Map();
  let hidden = false, frameId = 0;
  Object.defineProperty(doc, 'hidden', {get: () => hidden});
  const media = {matches: false, addEventListener: (name, fn) => mediaListeners.add(fn), removeEventListener: (name, fn) => mediaListeners.delete(fn)};
  win.matchMedia = () => media;
  win.HTMLElement.prototype.getBoundingClientRect = function () {
    return this._rect || {x: 20, y: 60, left: 20, top: 60, right: 620, bottom: 120, width: 600, height: 60};
  };
  const observers = [];
  win.IntersectionObserver = class {
    constructor(callback) { this.callback = callback; this.nodes = new Set(); this.disconnected = false; observers.push(this); }
    observe(node) { this.nodes.add(node); }
    unobserve(node) { this.nodes.delete(node); }
    disconnect() { this.nodes.clear(); this.disconnected = true; }
    emit(node, isIntersecting) { this.callback([{target: node, isIntersecting}]); }
  };
  const timelines = [], tweens = [];
  if (engine) {
    win.eval(read('vendor/gsap/gsap.min.js'));
    const timeline = win.gsap.timeline, to = win.gsap.to;
    win.gsap.timeline = function (...args) { const result = timeline.apply(this, args); timelines.push(result); return result; };
    win.gsap.to = function (...args) { const result = to.apply(this, args); tweens.push(result); return result; };
  }
  // GSAP retains its own real clock. Only the controller's DOM scheduling is
  // controlled here, so no stubbed tween can make a broken animation pass.
  win.requestAnimationFrame = callback => { frames.set(++frameId, callback); return frameId; };
  win.cancelAnimationFrame = id => frames.delete(id);
  win.eval(read('content_motion.js'));
  const api = win.QMContentMotion;
  async function flush() {
    for (let pass = 0; pass < 3; pass++) {
      await Promise.resolve();
      const batch = [...frames.values()]; frames.clear(); batch.forEach(callback => callback(0));
      timelines.forEach(item => item.pause()); tweens.forEach(item => item.pause());
    }
  }
  function root(kind, key, html = '<p data-qm-content-part="body">确认内容 123.45</p>') {
    const node = doc.createElement('section');
    node.dataset.qmContent = kind; node.dataset.qmContentKey = key;
    node.innerHTML = html; doc.body.append(node); return node;
  }
  function quiet(value) { doc.documentElement.dataset.qmMotionMode = value; win.dispatchEvent(new win.Event('qm-motion-preference-change')); }
  function visibility(value) { hidden = value; doc.dispatchEvent(new win.Event('visibilitychange')); }
  function reduced(value) { media.matches = value; for (const callback of mediaListeners) callback(); }
  function cleanup() { api.dispose(); win.gsap?.globalTimeline.clear(); win.gsap?.ticker.sleep(); win.close(); }
  return {win, doc, api, root, flush, quiet, visibility, reduced, timelines, tweens, observers, errors, frames, mediaListeners, cleanup};
}

(async () => {
  const fallback = fixture(false);
  try {
    const node = fallback.root('answer', 'fallback'); await fallback.flush();
    assert.equal(node.querySelector('p').style.opacity, '', 'Missing GSAP leaves native content readable.');
    assert.equal(fallback.api.getState().running, 0);
    assert.equal(node.textContent, '确认内容 123.45');
  } finally { fallback.cleanup(); }

  const f = fixture(), {win, doc, api} = f;
  try {
    assert.equal(api.version, '2026-10-11.17-body-ready20');
    let answer = f.root('answer', 'answer-a', '<header data-qm-content-part="heading"><i data-qm-content-accent aria-hidden="true" style="opacity:.8;transform:rotate(2deg)"></i>真实回答</header>' +
      '<p data-qm-content-part="conclusion" style="opacity:.9">真实数值 <strong>-123.45</strong> 万元</p>' +
      '<div data-qm-content-part="native"><input value="draft"><button>继续</button></div>' +
      '<div data-qm-content-part="prior-owner"><i data-result-piece="proof"></i>原场景</div>');
    const input = answer.querySelector('input'); input.focus();
    const part = answer.querySelector('p'), accent = answer.querySelector('[data-qm-content-accent]');
    const content = answer.textContent;
    await f.flush();
    assert.equal(api.getState().starts, 1);
    const entry = f.timelines.at(-1);
    assert.ok(entry.duration() >= .45 && entry.duration() <= .65, 'Entrance remains within the intended duration.');
    assert.ok(Number(part.style.opacity) >= .7, 'Text never starts as a blank or hidden surface.');
    assert.equal(accent.style.transform, 'rotate(2deg)', 'Authored decorative transforms remain intact.');
    assert.equal(answer.style.transform, ''); assert.equal(part.style.transform, '');
    assert.equal(answer.querySelector('button').getAttribute('style'), null);
    assert.equal(answer.querySelector('[data-result-piece]').getAttribute('style'), null);
    assert.equal(input.value, 'draft'); assert.equal(doc.activeElement, input);
    entry.progress(.5);
    assert.ok(Number(part.style.opacity) > .7 && Number(part.style.opacity) <= .9);
    assert.equal(answer.textContent, content, 'GSAP never counts up or rewrites real numbers.');
    assert.equal(input.value, 'draft'); assert.equal(doc.activeElement, input);
    assert.equal(win.gsap.getTweensOf(input).length, 0);

    win.eval(read('content_motion.js')); await f.flush();
    assert.equal(win.QMContentMotion, api, 'Same-version bootstrap preserves the singleton.');
    assert.equal(api.getState().starts, 1, 'An ordinary rerun cannot replay content.');
    answer.remove();
    answer = f.root('answer', 'answer-a'); await f.flush();
    assert.equal(api.getState().starts, 1, 'Same stable key survives DOM replacement.');
    assert.equal(entry.parent, null, 'Unmount kills the real GSAP timeline.');
    assert.equal(part.style.opacity, '0.9', 'Unmount restores exact authored opacity.');
    assert.equal(accent.style.transform, 'rotate(2deg)'); assert.equal(accent.style.scale, '');
    answer.dataset.qmContentKey = 'answer-b'; await f.flush();
    assert.equal(api.getState().starts, 2, 'A confirmed different content key can enter.');
    f.timelines.at(-1).progress(1);
    assert.equal(answer.querySelector('p').style.opacity, '');
    assert.equal(api.getState().running, 0);

    const below = f.root('import', 'import-offscreen');
    below._rect = {x: 20, y: 1500, left: 20, top: 1500, right: 620, bottom: 1600, width: 600, height: 100};
    await f.flush(); const beforeVisible = api.getState().starts;
    assert.equal(below.querySelector('p').style.opacity, '', 'Offscreen initial content is never hidden.');
    below._rect = undefined; f.observers[0].emit(below, true);
    assert.equal(api.getState().starts, beforeVisible + 1, 'First actual viewport appearance enters once.');
    f.observers[0].emit(below, false);
    assert.equal(below.querySelector('p').style.opacity, '');
    f.observers[0].emit(below, true);
    assert.equal(api.getState().starts, beforeVisible + 1, 'Returning after an interrupted reveal never replays it.');

    const archive = f.root('archive', 'frozen-archive', '<p data-qm-content-part="title">已保存快照</p><i data-qm-content-accent aria-hidden="true"></i>');
    await f.flush();
    assert.ok(Number(archive.querySelector('p').style.opacity) >= .7);
    f.timelines.at(-1).progress(1);
    const archiveStarts = api.getState().starts;
    archive.remove(); f.root('archive', 'frozen-archive'); await f.flush();
    assert.equal(api.getState().starts, archiveStarts, 'Closing and reopening the same archive cannot replay its entry.');
    const interrupted = f.root('feedback', 'feedback-a'); await f.flush();
    f.quiet('research');
    assert.equal(interrupted.querySelector('p').style.opacity, ''); assert.equal(api.getState().running, 0);
    const researchRoot = f.root('answer', 'research-new'); await f.flush();
    const researchStarts = api.getState().starts; f.quiet('presentation'); await f.flush();
    assert.equal(api.getState().starts, researchStarts, 'Leaving research mode cannot replay static results.');
    assert.equal(researchRoot.querySelector('p').style.opacity, '');
    const reducedRoot = f.root('import', 'reduced-a'); await f.flush(); f.reduced(true);
    assert.equal(reducedRoot.querySelector('p').style.opacity, '');
    const reducedStarts = api.getState().starts; f.reduced(false); await f.flush();
    assert.equal(api.getState().starts, reducedStarts, 'OS preference reversal cannot restart consumed results.');
    f.visibility(true); const background = f.root('feedback', 'background-new'); await f.flush();
    const backgroundStarts = api.getState().starts; f.visibility(false); await f.flush();
    assert.equal(api.getState().starts, backgroundStarts);
    assert.equal(background.querySelector('p').style.opacity, '');

    const comparison = f.root('comparison', 'compare-a', '<h3 data-qm-content-part="heading"><i data-qm-content-accent aria-hidden="true"></i>比较已生成</h3>' +
      '<p data-qm-content-part="reasoning">逐项核对两个期间</p><table data-qm-content-part="table"><tbody>' +
      '<tr data-qm-comparison-row><th><i data-qm-content-accent aria-hidden="true" style="opacity:.8"></i>收入</th>' +
      '<td><button>原文</button><span>123.45</span></td></tr></tbody></table>');
    await f.flush(); f.timelines.at(-1).progress(1);
    const row = comparison.querySelector('tr'), rowAccent = row.querySelector('i'), button = row.querySelector('button');
    assert.equal(api.getState().rows, 1);
    const baselineScale = rowAccent.style.scale; let clicked = 0;
    button.addEventListener('click', () => clicked++);
    button.dispatchEvent(new win.MouseEvent('click', {bubbles: true})); assert.equal(clicked, 1);
    row.dispatchEvent(new win.MouseEvent('pointerover', {bubbles: true}));
    let hover = f.tweens.at(-1); hover.pause().progress(.6);
    const halfwayScale = Number.parseFloat(rowAccent.style.scale);
    assert.ok(halfwayScale > Number.parseFloat(baselineScale) && halfwayScale < 1);
    row.dispatchEvent(new win.MouseEvent('pointerout', {bubbles: true}));
    let outward = f.tweens.at(-1); outward.pause().progress(.3);
    assert.equal(hover.parent, null, 'Rapid reversal kills the previous tween.');
    assert.ok(Number.parseFloat(rowAccent.style.scale) <= halfwayScale, 'Reversal has no overshoot.');
    row.dispatchEvent(new win.MouseEvent('pointerover', {bubbles: true}));
    f.tweens.at(-1).pause().progress(1);
    row.dispatchEvent(new win.MouseEvent('pointercancel', {bubbles: true}));
    f.tweens.at(-1).pause().progress(1);
    assert.equal(rowAccent.style.scale, baselineScale, 'Pointer cancellation returns decoration to its idle state.');
    button.focus(); f.tweens.at(-1).pause().progress(1);
    assert.equal(rowAccent.style.scale, '1 1', 'Keyboard focus uses the same decorative emphasis.');
    assert.equal(doc.activeElement, button); assert.equal(row.style.transform, ''); assert.equal(button.style.transform, '');
    f.visibility(true);
    assert.equal(rowAccent.style.opacity, '0.8'); assert.equal(rowAccent.style.scale, '');
    f.visibility(false); await f.flush();
    comparison.remove(); await f.flush();
    assert.equal(api.getState().rows, 0); assert.equal(rowAccent.style.opacity, '0.8');
    assert.equal(rowAccent.style.scale, '');

    // Real imports may deliver many distinct keys during a long-lived session.
    // Cache storage stays bounded and controls are never used as cache keys.
    f.quiet('research');
    const many = [];
    for (let index = 0; index < 205; index++) many.push(f.root('feedback', 'bounded-' + index));
    await f.flush(); assert.equal(api.getState().remembered, 192);
    many.forEach(node => node.remove()); await f.flush();
    f.quiet('presentation'); const pending = f.root('answer', 'dispose-pending');
    api.dispose(); await f.flush();
    assert.equal(pending.querySelector('p').style.opacity, '');
    assert.deepEqual({...api.getState()}, {roots: 0, rows: 0, remembered: 0, starts: api.getState().starts, running: 0, pending: false, disposed: true});
    assert.equal(f.frames.size, 0); assert.equal(f.mediaListeners.size, 0);
    assert.ok(f.observers.every(observer => observer.disconnected && observer.nodes.size === 0));
    assert.ok(f.timelines.every(timeline => timeline.parent === null), 'Every owned real timeline is released.');
    assert.ok(f.tweens.every(tween => tween.parent === null), 'Every owned row tween is released.');
    assert.deepEqual(f.errors, []);
    console.log('content motion: real GSAP, first visibility, stable keys, value/focus safety, rapid row reversal, quiet modes, bounded cache and complete cleanup passed');
  } finally { f.cleanup(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
