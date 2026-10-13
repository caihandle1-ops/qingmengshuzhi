'use strict';
// Exercise the shipped component and clock together, including the first
// Streamlit render. A deterministic graphics adapter cannot certify pixels.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = name => fs.readFileSync(path.join(__dirname, '../app/hero_frontend', name), 'utf8');

class Events {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, fn) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(fn); }
  removeEventListener(type, fn) { this.listeners.get(type)?.delete(fn); }
  emit(type, event = {}) { for (const fn of [...this.listeners.get(type) || []]) fn({type, ...event}); }
  count() { return [...this.listeners.values()].reduce((total, set) => total + set.size, 0); }
}

function component({osReduced = false, devicePixelRatio = 1, captureGeometry = false, navigation = false, gsap = null, webgl = true} = {}) {
  let now = 0, ticket = 0, draws = 0, clock;
  let enumIndex=0,boundArray=null,boundIndex=null,currentModel=null,currentNormal=null;
  const frames = new Map(), painted = [], posts = [], observers = [], matrices = [], vectors = [], allocated = new Set(), released = new Set();
  const geometryDraws=[];
  const recordDraw=(indexed,count)=>{
    draws++;
    if(captureGeometry)geometryDraws.push({indexed,count,vertices:boundArray.data.slice(),indices:indexed?boundIndex.data.slice():null,model:currentModel.slice(),normal:currentNormal.slice()});
  };
  const gl = new Proxy({}, {get(target, key) {
    if (!(key in target)) target[key] = key === 'drawArrays' ? (_,first,count) => recordDraw(false,count)
      : key === 'drawElements' ? (_,count) => recordDraw(true,count)
      : key === 'bindBuffer' ? (target,buffer) => { if(captureGeometry){if(target===gl.ARRAY_BUFFER)boundArray=buffer;else if(target===gl.ELEMENT_ARRAY_BUFFER)boundIndex=buffer;} }
      : key === 'bufferData' ? (target,data) => { if(captureGeometry)(target===gl.ARRAY_BUFFER?boundArray:boundIndex).data=data.slice(); }
      : key === 'bufferSubData' ? (_,offset,data) => { if(captureGeometry)boundArray.data.set(data,offset/data.BYTES_PER_ELEMENT); }
      : key === 'getShaderParameter' || key === 'getProgramParameter' ? () => true
      : key === 'getAttribLocation' ? () => 0
      : key === 'getUniformLocation' ? (_, name) => name
      : key === 'uniformMatrix4fv' ? (name, transpose, value) => {
        assert.equal(transpose, false); assert.equal(value.length, 16);
        assert.ok([...value].every(Number.isFinite), 'every camera/object matrix must remain finite');
        matrices.push({name, value: [...value]});
        if(name==='uModel')currentModel=[...value];
      }
      : key === 'uniformMatrix3fv' ? (name,transpose,value) => {assert.equal(name,'uNormal');assert.equal(transpose,false);assert.equal(value.length,9);assert.ok([...value].every(Number.isFinite),'normal matrix must remain finite');currentNormal=[...value];}
      : key === 'uniform1f' ? (_, value) => assert.ok(Number.isFinite(value), 'shader scalar remains finite')
      : key === 'uniform3fv' ? (name, value) => { assert.ok([...value].every(Number.isFinite), 'shader vector remains finite'); vectors.push({name,value:[...value]}); }
      : key.startsWith('create') ? () => { const resource = {kind: key}; allocated.add(resource); return resource; }
      : key.startsWith('delete') ? resource => { assert.ok(allocated.has(resource)); assert.ok(!released.has(resource), 'GPU resources are released once'); released.add(resource); }
      : /^[A-Z_0-9]+$/.test(key) ? ++enumIndex : () => {};
    return target[key];
  }});
  const texture = new Proxy({}, {get(target, key) {
    if (!(key in target)) target[key] = key === 'createLinearGradient' ? () => ({addColorStop() {}}) : () => {};
    return target[key];
  }});
  class Element extends Events {
    constructor() { super(); this.dataset = {}; this.children = []; this.attributes = {}; this.textContent = ''; }
    setAttribute(key, value) { this.attributes[key] = value; }
    replaceChildren(...children) { this.children = children; }
    appendChild(child) { this.children.push(child); }
    getBoundingClientRect() { return {left: 0, top: 0, width: 800, height: 500}; }
    getContext(kind) { return kind === 'webgl' ? webgl ? gl : null : texture; }
  }
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const buttons = [0, 1, 2].map(phase => { const element = new Element(); element.dataset.phase = String(phase); return element; });
  const doc = new Events();
  Object.assign(doc, {hidden: false, referrer:'http://localhost:8504/', documentElement: new Element(), getElementById: get,
    querySelectorAll: () => buttons, createElement: () => new Element(), createTextNode: text => ({textContent: text})});
  const media = new Map();
  const query = text => { if (!media.has(text)) { const value = new Events(); value.matches = text.includes('prefers-reduced') && osReduced; media.set(text, value); } return media.get(text); };
  class Observer {
    constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
    observe() {}
    disconnect() { this.disconnected = true; }
  }
  const context = new Events(), parent = {postMessage: value => posts.push(value)};
  Object.assign(context, {document: doc, parent, matchMedia: query, performance: {now: () => now}, devicePixelRatio,URL,
    location:{origin:'http://localhost:8504'},innerWidth:800,innerHeight:580,
    IntersectionObserver: Observer, ResizeObserver: Observer,
    requestAnimationFrame: callback => { frames.set(++ticket, callback); return ticket; }, cancelAnimationFrame: id => frames.delete(id)});
  context.window = context;
  vm.createContext(context);
  vm.runInContext(script('hero-quality.js'), context);
  vm.runInContext(script('hero-runtime.js'), context);
  vm.runInContext(script('hero-paper.js'), context);
  if(navigation){context.gsap=gsap;vm.runInContext(script('hero-choreography.js'),context);vm.runInContext(script('hero-navigation.js'),context);}
  const original = context.QMHeroRuntime.createRuntime;
  context.QMHeroRuntime.createRuntime = (env, draw, notify) => (clock = original(env, frame => { painted.push(frame); draw(frame); }, notify));
  vm.runInContext(script('hero.js'), context);
  return {context, doc, get, buttons, frames, painted, posts, observers, matrices, vectors,geometryDraws,
    get clock(){return clock;},
    get draws() { return draws; },
    get liveResources() { return allocated.size - released.size; },
    render(mode, source = parent) { context.emit('message', {source, data: {type: 'streamlit:render', args: mode === undefined ? {} : {motion: {version: 1, mode}}}}); },
    renderContext(value, mode='presentation') { context.emit('message',{source:parent,data:{type:'streamlit:render',args:{motion:{version:1,mode},context:value}}}); },
    paintAt(time) { now = time; const pending = [...frames.values()]; frames.clear(); if(pending.length)geometryDraws.length=0; pending.forEach(callback => callback(time)); },
    reduced(value) { const match = query('(prefers-reduced-motion: reduce)'); match.matches = value; match.emit('change'); },
    forced(value) { const match = query('(forced-colors: active)'); match.matches = value; match.emit('change'); },
    dispose() { context.emit('pagehide'); assert.equal(frames.size, 0); assert.equal(context.count() + doc.count() + [...nodes.values(), ...buttons, ...media.values()].reduce((total, node) => total + node.count(), 0), 0); assert.ok(observers.every(observer => observer.disconnected)); assert.equal(released.size, allocated.size, 'all graphics allocations are released on disposal'); }
  };
}

module.exports = {component};
if (require.main === module) {
const hero = component();
assert.equal(hero.frames.size, 0, 'do not consume the entrance before the authoritative first render');
hero.render('presentation', {});
assert.equal(hero.frames.size, 0, 'unrelated windows cannot start the component');
hero.paintAt(5000);
hero.render('presentation');
hero.paintAt(5000);
assert.equal(hero.painted.at(-1).open, 0, 'first real presentation frame starts assembled, even when the host was delayed');
assert.equal(hero.painted.at(-1).reduced, false);
assert.equal(hero.context.__qmImmersiveHero.getState().shot, 'paper-edge');
const firstCamera = JSON.stringify(hero.context.__qmImmersiveHero.getState().camera);
hero.paintAt(5400);
assert.ok(hero.painted.at(-1).open > 0 && hero.painted.at(-1).open < 1, 'original assembly entrance interpolates');
assert.notEqual(JSON.stringify(hero.context.__qmImmersiveHero.getState().camera), firstCamera, 'the initial camera actually leaves the paper-edge close shot');
hero.render('presentation');
hero.paintAt(5500);
assert.ok(hero.painted.at(-1).open > hero.painted.at(-2).open && hero.painted.at(-1).open < 1, 'ordinary rerender neither restarts nor skips the entrance');
hero.paintAt(6500);
assert.equal(hero.painted.at(-1).open, 1);
const priorTime = hero.painted.at(-1).time;
hero.get('sculpture-stage').emit('pointermove', {clientX: 750, clientY: 350});
hero.paintAt(6516);
assert.ok(hero.painted.at(-1).time > priorTime && hero.painted.at(-1).pointer[0] > 0, 'orbit clock and pointer exploration remain active');
assert.ok(hero.draws > 0, 'actual graphics draw path received the frames');
assert.ok(hero.matrices.some(entry => entry.name === 'uVP') && hero.matrices.some(entry => entry.name === 'uModel'), 'camera and every object matrix are checked');
hero.clock.toggle();
hero.paintAt(6916);
assert.ok(hero.painted.at(-1).open > 0 && hero.painted.at(-1).open < 1);
hero.render('research');
hero.paintAt(6917);
assert.equal(hero.painted.at(-1).open, 0);
assert.equal(hero.frames.size, 0);
hero.render('presentation');
hero.paintAt(6918);
assert.equal(hero.painted.at(-1).open, 0, 'mode switches keep the user-collapsed assembly, without replaying entrance');
hero.clock.toggle();
hero.paintAt(7318);
assert.ok(hero.painted.at(-1).open > 0 && hero.painted.at(-1).open < 1);
hero.paintAt(8500);
hero.clock.setStage(2);
hero.paintAt(8900);
assert.ok(hero.painted.at(-1).stage > 1 && hero.painted.at(-1).stage < 2);
hero.render('research'); hero.render('presentation'); hero.paintAt(8901);
assert.equal(hero.painted.at(-1).stage, 2, 'rapid mode reversal settles current chapter rather than bouncing to the preceding one');
hero.reduced(true); hero.paintAt(8902);
assert.equal(hero.painted.at(-1).reduced, true);
assert.equal(hero.frames.size, 0, 'OS reduced motion always wins over presentation');
hero.reduced(false); hero.paintAt(8903);
assert.equal(hero.painted.at(-1).open, 1);
assert.equal(hero.painted.at(-1).stage, 2);
hero.doc.hidden = true; hero.doc.emit('visibilitychange');
assert.equal(hero.frames.size, 0);
const beforeHidden = hero.painted.length, stoppedClock = hero.painted.at(-1).time;
hero.paintAt(12000);
assert.equal(hero.painted.length, beforeHidden, 'hidden pages do not paint or advance the orbit clock');
hero.doc.hidden = false; hero.doc.emit('visibilitychange'); hero.paintAt(12001);
assert.equal(hero.painted.at(-1).stage, 2);
assert.equal(hero.painted.at(-1).open, 1);
assert.ok(hero.painted.at(-1).time - stoppedClock < .05, 'resume does not apply the full hidden time to orbit or lighting');
assert.equal(hero.frames.size, 1, 'visible presentation resumes exactly one animation loop');
hero.dispose();

const reversed = component(); reversed.render('presentation'); reversed.paintAt(0); reversed.paintAt(1600);
let timestamp = 1600;
for (let index = 0; index < 16; index++) {
  reversed.clock.toggle();
  reversed.paintAt(timestamp += 110);
  const preceding = reversed.painted.at(-1);
  reversed.clock.toggle();
  reversed.paintAt(timestamp);
  assert.equal(reversed.painted.at(-1).open, preceding.open, 'reversing a click starts from the currently painted assembly');
  assert.equal(reversed.painted.at(-1).stage, preceding.stage);
  assert.ok(reversed.painted.every(frame => frame.open >= 0 && frame.open <= 1 && frame.stage >= 0 && frame.stage <= 2), 'rapid reversal stays inside valid pose ranges');
  reversed.clock.setStage(index % 3);
  reversed.paintAt(timestamp += 73);
}
reversed.clock.setStage(0); reversed.paintAt(timestamp += 1500);
assert.equal(reversed.painted.at(-1).stage, 0);
assert.equal(reversed.painted.at(-1).open, 1, 'latest chapter request survives interleaved assembly clicks');
reversed.clock.toggle(); reversed.paintAt(timestamp += 1500);
assert.equal(reversed.painted.at(-1).stage, 0);
assert.equal(reversed.painted.at(-1).open, 0, 'latest collapse request finishes at the exact assembled pose');
reversed.dispose();

const restored = component(); restored.render('presentation'); restored.paintAt(0); restored.paintAt(1600);
const graphicsResources = restored.liveResources;
assert.ok(graphicsResources > 0);
restored.forced(true);
assert.equal(restored.liveResources, 0, 'entering forced colors releases the previous WebGL scene');
assert.equal(restored.frames.size, 0);
assert.equal(restored.doc.documentElement.dataset.renderer, 'fallback');
restored.forced(false); restored.paintAt(1700);
assert.equal(restored.liveResources, graphicsResources, 'leaving forced colors creates one replacement graphics scene');
assert.equal(restored.frames.size, 1);
assert.equal(restored.painted.at(-1).open, 1, 'graphics recovery preserves the current assembly without replaying entrance');
let prevented = false;
restored.get('sculpture').emit('webglcontextlost', {preventDefault() { prevented = true; }});
assert.ok(prevented);
assert.equal(restored.frames.size, 0);
assert.equal(restored.context.__qmImmersiveHero.getState().healthy, false);
restored.get('sculpture').emit('webglcontextrestored'); restored.paintAt(1800);
assert.equal(restored.liveResources, graphicsResources, 'context restoration replaces resources without accumulating allocations');
assert.equal(restored.frames.size, 1);
assert.equal(restored.context.__qmImmersiveHero.getState().healthy, true);
assert.equal(restored.painted.at(-1).open, 1);
restored.dispose();

for (const options of [{mode: 'research'}, {mode: 'presentation', osReduced: true}]) {
  const quiet = component(options); quiet.render(options.mode); quiet.paintAt(0);
  assert.equal(quiet.painted.at(-1).reduced, true);
  assert.equal(quiet.painted.at(-1).open, 1);
  assert.equal(quiet.context.__qmImmersiveHero.getState().shot, 'settled');
  assert.equal(quiet.context.__qmImmersiveHero.getState().camera[0], 1.04, 'quiet entry uses the entire composition, never a frozen crop');
  assert.equal(quiet.frames.size, 0, 'explicit research and OS preference never run a transient entrance');
  quiet.dispose();
}
const legacy = component(); legacy.render(); legacy.paintAt(0);
assert.equal(legacy.painted.at(-1).reduced, false, 'a host without motion arguments preserves the original full animation');
assert.equal(legacy.painted.at(-1).open, 0);
legacy.dispose();
const abandoned = component(); abandoned.dispose();

const adaptive = component({devicePixelRatio: 2});
adaptive.render('presentation'); adaptive.paintAt(0); adaptive.paintAt(16);
assert.equal(adaptive.get('sculpture').width, 1600, 'full initial canvas density is preserved');
let adaptiveTime = 16;
for (let index = 0; index < 160; index++) adaptive.paintAt(adaptiveTime += 40);
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.tier, 1, 'actual runtime forwards unclamped RAF time to quality sampling');
assert.equal(adaptive.get('sculpture').width, 1312, 'only the actual canvas pixel dimensions change');
assert.equal(adaptive.context.__qmImmersiveHero.getState().stage, 1);
assert.equal(adaptive.context.__qmImmersiveHero.getState().expanded, true);
assert.equal(adaptive.frames.size, 1, 'adaptive sampling never creates an extra animation loop');
assert.equal(adaptive.painted.at(-1).reduced, false, 'lower pixel density keeps full motion');
const geometryCount = adaptive.draws;
adaptive.paintAt(adaptiveTime += 40);
const perFrameCount = adaptive.draws - geometryCount;
assert.ok(perFrameCount > 10, 'all original objects are still drawn at a lower tier');
adaptive.clock.toggle(); adaptive.paintAt(adaptiveTime += 40);
const adaptivePose = adaptive.painted.at(-1).open;
adaptive.clock.toggle(); adaptive.paintAt(adaptiveTime);
assert.equal(adaptive.painted.at(-1).open, adaptivePose, 'automatic quality preserves reversible assembly poses');
adaptive.doc.hidden = true; adaptive.doc.emit('visibilitychange');
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.sampling, false);
adaptive.doc.hidden = false; adaptive.doc.emit('visibilitychange'); adaptive.paintAt(adaptiveTime += 15000);
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.tier, 1, 'hidden time never downgrades quality');
adaptive.observers[0].callback([{isIntersecting: false}]);
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.sampling, false);
assert.equal(adaptive.frames.size, 0);
adaptive.observers[0].callback([{isIntersecting: true}]); adaptive.paintAt(adaptiveTime += 15000);
assert.equal(adaptive.frames.size, 1);
adaptive.render('research'); adaptive.paintAt(adaptiveTime += 16);
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.sampling, false);
adaptive.render('presentation'); adaptive.paintAt(adaptiveTime += 16);
adaptive.reduced(true); adaptive.paintAt(adaptiveTime += 16);
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.sampling, false);
adaptive.reduced(false); adaptive.paintAt(adaptiveTime += 16);
for (let index = 0; index < 630; index++) adaptive.paintAt(adaptiveTime += 16.67);
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.tier, 0, 'stable actual frames recover full clarity');
assert.equal(adaptive.get('sculpture').width, 1600);
const afterRecovery = adaptive.draws;
adaptive.paintAt(adaptiveTime += 16.67);
assert.equal(adaptive.draws - afterRecovery, perFrameCount, 'pixel density changes neither geometry count nor drawing passes');
assert.equal(adaptive.context.__qmImmersiveHero.getState().stage, 1);
assert.equal(adaptive.context.__qmImmersiveHero.getState().expanded, true);
adaptive.dispose();
assert.equal(adaptive.context.__qmImmersiveHero.getState().quality.disposed, true);
console.log('hero integration: first render, finite matrices, reversible poses, adaptive pixel density, one RAF, visibility, OS priority and resource cleanup passed');
}
