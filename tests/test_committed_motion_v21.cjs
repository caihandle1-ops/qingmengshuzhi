'use strict';
// Real pinned GSAP + JSDOM MutationObserver. Only controller RAF scheduling,
// viewport geometry and user preferences are deterministic fixture inputs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM, VirtualConsole} = require('jsdom');
const read = name => fs.readFileSync(path.join(__dirname, '../app', name), 'utf8');
const controller = read('committed_motion.js');

function fixture({bodyless = false, engine = true} = {}) {
  const errors = [], console = new VirtualConsole();
  console.on('jsdomError', error => errors.push(String(error)));
  console.on('warn', warning => errors.push(String(warning)));
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: console
  });
  const win = dom.window, doc = win.document, frames = new Map(), listeners = new Set(), timelines = [];
  let hidden = false, nextFrame = 0;
  Object.defineProperty(doc, 'hidden', {get: () => hidden});
  const media = {matches: false, addEventListener: (_, fn) => listeners.add(fn), removeEventListener: (_, fn) => listeners.delete(fn)};
  win.matchMedia = () => media;
  win.HTMLElement.prototype.getBoundingClientRect = function () {
    return this._rect || {x: 20, y: 60, left: 20, top: 60, right: 620, bottom: 160, width: 600, height: 100};
  };
  if (engine) {
    win.eval(read('vendor/gsap/gsap.min.js'));
    const timeline = win.gsap.timeline;
    win.gsap.timeline = function (...args) { const value = timeline.apply(this, args); timelines.push(value); return value; };
  }
  // GSAP has already retained its real clock, so these callbacks only schedule
  // the app's DOM scans; production tween objects are never substituted.
  win.requestAnimationFrame = callback => { frames.set(++nextFrame, callback); return nextFrame; };
  win.cancelAnimationFrame = id => frames.delete(id);
  if (bodyless) doc.body.remove();
  win.eval(controller);
  const api = win.QMCommittedMotion;
  async function flush() {
    for (let pass = 0; pass < 3; pass++) {
      await Promise.resolve();
      const batch = [...frames.values()]; frames.clear(); batch.forEach(callback => callback(0));
      timelines.forEach(timeline => timeline.pause());
    }
  }
  function annual(scope = 'company-a', year = '2024') {
    const node = doc.createElement('aside');
    node.dataset.commitScope = scope; node.dataset.commitYear = year;
    node.innerHTML = '<div aria-hidden="true"><i data-commit-art style="opacity:.35;transform:rotate(2deg)"></i>' +
      '<i data-commit-art></i><i data-commit-art></i></div><p>真实财务数据 <strong>7,771.02</strong> 亿元</p>' +
      '<label>年份<input value="2024"></label><button>确认年度</button>';
    doc.body.append(node); return node;
  }
  function visibility(value) { hidden = value; doc.dispatchEvent(new win.Event('visibilitychange')); }
  function reduced(value) { media.matches = value; for (const callback of listeners) callback(); }
  function mode(value) { doc.documentElement.dataset.qmMotionMode = value; win.dispatchEvent(new win.Event('qm-motion-preference-change')); }
  function scroll() { doc.dispatchEvent(new win.Event('scroll')); }
  function cleanup() { win.QMCommittedMotion?.dispose(); api.dispose(); win.gsap?.globalTimeline.clear(); win.gsap?.ticker.sleep(); win.close(); }
  return {win, doc, api, annual, flush, visibility, reduced, mode, scroll, timelines, frames, listeners, errors, cleanup};
}

function assertNativeSafe(f, node, input, text) {
  assert.equal(node.textContent, text, 'Financial text is never rewritten by motion.');
  assert.equal(input.value, '2024'); assert.equal(f.doc.activeElement, input);
  for (const target of [node, ...node.querySelectorAll('p,strong,input,button,label')]) {
    assert.equal(target.style.transform, '', 'Native and financial elements never receive transforms.');
    assert.equal(target.style.opacity, '', 'Native and financial elements never disappear.');
    assert.equal(f.win.gsap.getTweensOf(target).length, 0);
  }
}

const cases = [];
function test(name, fn) { cases.push({name, fn}); }

test('initial state, uncommitted input, same value and native remount never replay', async () => {
  const f = fixture();
  try {
    let node = f.annual(); await f.flush();
    assert.deepEqual({...f.api.getState()}, {starts: 0, running: 0, pending: 0});
    const input = node.querySelector('input'); input.value = '2025';
    input.dispatchEvent(new f.win.Event('input', {bubbles: true})); await f.flush();
    assert.equal(f.api.getState().starts, 0, 'Draft widget input is not a confirmed business state.');
    node.dataset.commitYear = '2024'; await f.flush(); assert.equal(f.api.getState().starts, 0);
    node.remove(); node = f.annual(); await f.flush(); assert.equal(f.api.getState().starts, 0);
    f.win.eval(controller); await f.flush();
    assert.equal(f.win.QMCommittedMotion, f.api); assert.equal(f.listeners.size, 1);
    assert.equal(f.api.getState().starts, 0); assert.equal(f.timelines.length, 0);
    assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

test('confirmed annual change animates only authored strips and restores their styles', async () => {
  const f = fixture();
  try {
    const node = f.annual(), input = node.querySelector('input'), art = [...node.querySelectorAll('[data-commit-art]')];
    const styles = art.map(piece => piece.style.cssText), text = node.textContent;
    input.focus(); await f.flush(); node.dataset.commitYear = '2025'; await f.flush();
    assert.equal(f.api.getState().starts, 1); assert.equal(f.api.getState().running, 1);
    const timeline = f.timelines.at(-1); timeline.progress(.32);
    assert.ok(art.some((piece, index) => piece.style.cssText !== styles[index]), 'Real GSAP moves paper strips.');
    const targets = new Set(timeline.getChildren(true, true, false).flatMap(tween => tween.targets()));
    assert.ok([...targets].every(target => art.includes(target)), 'Annual ownership contains artwork only.');
    assertNativeSafe(f, node, input, text);
    node.dataset.commitYear = '2025'; f.api.refresh(); await f.flush();
    assert.equal(f.api.getState().starts, 1, 'Confirmed same value does not rebuild an active timeline.');
    timeline.progress(1);
    assert.equal(f.api.getState().running, 0); assert.equal(timeline.parent, null);
    art.forEach((piece, index) => assert.equal(piece.style.cssText, styles[index]));
    assertNativeSafe(f, node, input, text); assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

test('offscreen changes wait, survive a native remount and enter once', async () => {
  const f = fixture();
  try {
    let node = f.annual();
    const below = {left: 20, top: 1500, right: 620, bottom: 1600, width: 600, height: 100};
    node._rect = below; await f.flush(); node.dataset.commitYear = '2025'; await f.flush();
    assert.deepEqual({...f.api.getState()}, {starts: 0, running: 0, pending: 1});
    assert.equal(node.querySelector('[data-commit-art]').style.transform, 'rotate(2deg)');
    node.remove(); node = f.annual('company-a', '2025'); node._rect = below; await f.flush();
    assert.equal(f.api.getState().pending, 1); assert.equal(f.api.getState().starts, 0);
    node._rect = undefined; f.scroll(); await f.flush();
    assert.deepEqual({...f.api.getState()}, {starts: 1, running: 1, pending: 0});
    f.timelines.at(-1).progress(1); f.scroll(); await f.flush(); assert.equal(f.api.getState().starts, 1);
    node.remove(); f.annual('company-a', '2025'); await f.flush(); assert.equal(f.api.getState().starts, 1);
    assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

test('hidden, reduced and research modes restore interrupted styles without replay', async () => {
  const f = fixture();
  try {
    const node = f.annual(), art = [...node.querySelectorAll('[data-commit-art]')], styles = art.map(piece => piece.style.cssText);
    await f.flush(); let year = 2024;
    for (const toggle of [value => f.visibility(value), value => f.reduced(value), value => f.mode(value ? 'research' : 'presentation')]) {
      node.dataset.commitYear = String(++year); await f.flush(); f.timelines.at(-1).progress(.4);
      const starts = f.api.getState().starts; toggle(true); await f.flush();
      assert.equal(f.api.getState().running, 0);
      art.forEach((piece, index) => assert.equal(piece.style.cssText, styles[index]));
      node.dataset.commitYear = String(++year); await f.flush();
      assert.equal(f.api.getState().pending, 0); assert.equal(f.api.getState().starts, starts);
      toggle(false); await f.flush(); assert.equal(f.api.getState().starts, starts, 'Restoring a preference does not replay consumed changes.');
    }
    assert.ok(f.timelines.every(timeline => timeline.parent === null)); assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

test('Document bootstrap accepts a late body and disposal before body leaves no work', async () => {
  const f = fixture({bodyless: true});
  try {
    await f.flush(); assert.equal(f.api.getState().starts, 0); assert.equal(f.frames.size, 0);
    const body = f.doc.createElement('body'); f.doc.documentElement.append(body);
    const node = f.annual(); await f.flush(); assert.equal(f.api.getState().starts, 0);
    node.dataset.commitYear = '2025'; await f.flush(); assert.equal(f.api.getState().starts, 1);
    f.api.dispose(); f.api.dispose(); await f.flush();
    assert.equal(f.win.QMCommittedMotion, undefined); assert.equal(f.listeners.size, 0); assert.equal(f.frames.size, 0);
    assert.equal(f.api.getState().running, 0); assert.ok(f.timelines.every(timeline => timeline.parent === null));
    node.dataset.commitYear = '2026'; f.scroll(); await f.flush(); assert.equal(f.api.getState().starts, 1);
    assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
  const disposed = fixture({bodyless: true});
  try {
    disposed.api.dispose(); disposed.doc.documentElement.append(disposed.doc.createElement('body'));
    disposed.annual(); await disposed.flush();
    assert.equal(disposed.timelines.length, 0); assert.equal(disposed.frames.size, 0); assert.equal(disposed.listeners.size, 0);
    assert.deepEqual(disposed.errors, []);
  } finally { disposed.cleanup(); }
});

test('report assembly owns paper artwork only and restores exact style on unmount', async () => {
  const f = fixture();
  try {
    const stage = f.doc.createElement('section'); stage.dataset.resultScene = 'report'; stage.dataset.resultId = 'report-a';
    stage.innerHTML = '<div class="deep-report-paper" aria-hidden="true"><i data-result-piece style="transform:rotate(5deg)"></i>' +
      '<i data-result-piece></i><div class="deep-report-paper-front" style="opacity:.8"><b></b><b></b></div></div>' +
      '<p>营业收入 <strong>7,771.02</strong> 亿元</p><label>年度<input value="2024"></label><button>下载真实报告</button>';
    f.doc.body.append(stage); const input = stage.querySelector('input'); input.focus();
    const text = stage.textContent, art = [...stage.querySelectorAll('[data-result-piece],.deep-report-paper-front,.deep-report-paper-front b')];
    const styles = art.map(piece => piece.style.cssText);
    assert.equal(f.api.report(stage), true); await f.flush();
    const timeline = f.timelines.at(-1); timeline.progress(.38);
    const targets = timeline.getChildren(true, true, false).flatMap(tween => tween.targets());
    assert.ok(targets.length > 0 && targets.every(target => art.includes(target)));
    assert.ok(art.some((piece, index) => piece.style.cssText !== styles[index]));
    assertNativeSafe(f, stage, input, text);
    stage.remove(); await f.flush();
    assert.equal(f.api.getState().running, 0); assert.equal(timeline.parent, null);
    art.forEach((piece, index) => assert.equal(piece.style.cssText, styles[index]));
    assert.equal(f.api.report(stage), false, 'Disconnected results cannot animate.');
    const invalid = f.doc.createElement('section'); f.doc.body.append(invalid);
    assert.equal(f.api.report(invalid), false);
    f.reduced(true); f.doc.body.append(stage); assert.equal(f.api.report(stage), false);
    assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

function paper(f) {
  const node = f.doc.createElement('div'); node.setAttribute('aria-hidden', 'true'); node.inert = true;
  node.style.opacity = '.3'; node.innerHTML = '<i style="transform:scaleX(.7)"></i>';
  f.doc.body.append(node); return node;
}
const origin = {left: 70, top: 110, width: 180, height: 90}, destination = {left: 400, top: 70, width: 410, height: 680};

test('source close cancels opening, completes once and removes owned GSAP work', async () => {
  const f = fixture();
  try {
    const opening = paper(f), oldStyle = opening.style.cssText, ruleStyle = opening.querySelector('i').style.cssText;
    let opened = 0, closed = 0;
    const openHandle = f.api.source(opening, origin, destination, false, () => { opened++; opening.remove(); });
    await f.flush(); const openTimeline = f.timelines.at(-1); openTimeline.progress(.35);
    assert.ok(openHandle && opening.style.transform); assert.equal(opened, 0);
    assert.equal(Number(f.win.gsap.getProperty(opening,'rotation')),0,
      'An interrupted flight must stay axis-aligned so the close can continue from its exact bounding rectangle without a bulge.');
    openHandle.cancel(); openHandle.cancel(); await f.flush();
    assert.equal(opened, 1); assert.equal(openTimeline.parent, null); assert.equal(opening.style.cssText, oldStyle);
    assert.equal(opening.querySelector('i').style.cssText, ruleStyle);
    const closing = paper(f), closeHandle = f.api.source(closing, destination, origin, true, () => { closed++; closing.remove(); });
    await f.flush(); const closeTimeline = f.timelines.at(-1);
    assert.equal(closeTimeline.duration(), .5); closeTimeline.progress(.5);
    openHandle.cancel(); assert.equal(f.api.getState().running, 1, 'Stale opening handle cannot affect a new closing paper.');
    closeTimeline.progress(1); closeHandle.cancel(); await f.flush();
    assert.equal(closed, 1); assert.equal(f.api.getState().running, 0); assert.equal(closeTimeline.parent, null);
    const disposePaper = paper(f); let disposed = 0;
    const disposeHandle = f.api.source(disposePaper, origin, destination, false, () => { disposed++; disposePaper.remove(); });
    await f.flush(); f.api.dispose(); disposeHandle.cancel();
    assert.equal(disposed, 1); assert.equal(f.api.getState().running, 0);
    assert.ok(f.timelines.every(timeline => timeline.parent === null)); assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

test('source handle cancellation remains scoped to its own run when a paper is reused', async () => {
  const f = fixture();
  try {
    const reused = paper(f); let openingDone = 0, closingDone = 0;
    const opening = f.api.source(reused, origin, destination, false, () => openingDone++); await f.flush();
    const first = f.timelines.at(-1); first.progress(.25);
    const closing = f.api.source(reused, destination, origin, true, () => closingDone++); await f.flush();
    assert.equal(openingDone, 1); assert.equal(first.parent, null); assert.equal(closingDone, 0);
    opening.cancel();
    assert.equal(closingDone, 0, 'An obsolete opening handle must not invoke the active closing completion.');
    assert.equal(f.api.getState().running, 1, 'Cancellation must target its original record, not any run with the same DOM node.');
    f.timelines.at(-1).progress(1); closing.cancel(); assert.equal(closingDone, 1);
    assert.equal(f.api.getState().running, 0); assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

test('missing GSAP remains readable and native remount cleanup never accumulates work', async () => {
  const fallback = fixture({engine: false});
  try {
    const node = fallback.annual(); await fallback.flush(); node.dataset.commitYear = '2025'; await fallback.flush();
    assert.equal(fallback.api.getState().starts, 0); assert.equal(fallback.api.getState().running, 0);
    assert.equal(node.querySelector('[data-commit-art]').style.transform, 'rotate(2deg)');
    assert.equal(fallback.api.source(paper(fallback), origin, destination, false, () => assert.fail('No engine has no completion callback.')), null);
    assert.deepEqual(fallback.errors, []);
  } finally { fallback.cleanup(); }
  const f = fixture();
  try {
    let node = f.annual(); await f.flush(); node.dataset.commitYear = '2025'; await f.flush();
    const timeline = f.timelines.at(-1); timeline.progress(.25);
    for (let pass = 0; pass < 4; pass++) {
      node.remove(); node = f.annual('company-a', '2025'); f.win.eval(controller); await f.flush();
    }
    assert.equal(f.api.getState().starts, 1); assert.equal(f.api.getState().running, 0); assert.equal(f.listeners.size, 1);
    assert.equal(timeline.parent, null); f.api.dispose(); await f.flush();
    assert.equal(f.frames.size, 0); assert.equal(f.listeners.size, 0); assert.deepEqual(f.errors, []);
  } finally { f.cleanup(); }
});

(async () => {
  let failed = 0;
  for (const {name, fn} of cases) {
    try { await fn(); console.log('PASS ' + name); }
    catch (error) { failed++; console.error('FAIL ' + name + '\n' + (error.stack || error)); }
  }
  console.log(`committed motion v21: ${cases.length - failed}/${cases.length} scenarios passed with real GSAP`);
  if (failed) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
