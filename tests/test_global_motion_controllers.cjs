'use strict';
// Production clocks/controllers with deterministic events and geometry. No CSS claims.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = name => fs.readFileSync(path.join(__dirname, '../app', name), 'utf8');

const clockContext = {};vm.createContext(clockContext);vm.runInContext(code('hero_frontend/hero-runtime.js'), clockContext);
let now = 0, ticket = 0;const frames = new Map(), painted = [], notified = [];
const runtime = clockContext.QMHeroRuntime.createRuntime({now: () => now, reduced: true, hidden: () => false,
  raf: fn => {frames.set(++ticket, fn);return ticket;}, cancel: id => frames.delete(id)},
  frame => painted.push(frame), state => notified.push(state));
function paintAt(value) {now = value;const scheduled = [...frames.values()];frames.clear();scheduled.forEach(fn => fn(now));}
paintAt(0);assert.equal(painted.at(-1).open, 1);assert.equal(frames.size, 0, 'research hero has no idle animation loop');
runtime.setReduced(false);paintAt(16);assert.equal(painted.at(-1).open, 1, 'enable presentation without replaying initial assembly');
runtime.setStage(2);paintAt(300);assert.ok(painted.at(-1).stage > 1 && painted.at(-1).stage < 2);
runtime.setReduced(true);runtime.setReduced(false);paintAt(310);
assert.equal(painted.at(-1).stage, 2, 'rapid mode reversal cannot return to an old interpolation');
runtime.toggle();paintAt(400);runtime.setReduced(true);paintAt(401);assert.equal(painted.at(-1).open, 0);
runtime.setReduced(false);paintAt(402);assert.equal(painted.at(-1).open, 0, 'collapsed assembly stays collapsed after mode changes');
runtime.setVisible(false);assert.equal(frames.size, 0);runtime.dispose();runtime.setReduced(true);assert.equal(frames.size, 0);

class Events {
  constructor() {this.listeners = new Map();}
  addEventListener(type, fn, options = {}) {if (options.signal?.aborted) return; if (!this.listeners.has(type)) this.listeners.set(type, new Set());this.listeners.get(type).add(fn);options.signal?.addEventListener('abort', () => this.removeEventListener(type, fn), {once:true});}
  removeEventListener(type, fn) {this.listeners.get(type)?.delete(fn);}
  emit(type) {for (const fn of [...this.listeners.get(type) || []]) fn({type});}
  count() {return [...this.listeners.values()].reduce((n, set) => n + set.size, 0);}
}
const motions = [], timers = new Map();let timerId = 0;
class Element {
  constructor(tag) {this.tag = tag;this.dataset = {};this.className = '';this.children = [];this.style = {setProperty(){}};this.rect = {left:0,top:0,width:100,height:45};this.textContent = '';}
  setAttribute() {}
  appendChild(node) {this.children.push(node);node.parent = this;}
  remove() {if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this);this.parent = null;}
  getBoundingClientRect() {return this.rect;}
  querySelectorAll(selector) {return selector === '.qm-route-stage-piece' ? this.children.filter(child => child.className.startsWith('qm-route-stage-piece')) : [];}
  closest() {return null;}
  animate(keyframes, options) {const result = {keyframes, options, cancelled:false, finished:new Promise(() => {}), cancel(){this.cancelled = true;}};motions.push(result);return result;}
}
const main = new Element('main');main.rect = {left:220,top:50,width:1150,height:850};main.scrollTop = 77;
const doc = new Events();doc.documentElement = new Element('html');doc.body = new Element('body');doc.hidden = false;
doc.createElement = tag => new Element(tag);doc.querySelector = selector => selector === '[data-testid="stMain"]' ? main : null;
const media = new Events();media.matches = false;
const context = new Events();Object.assign(context, {document:doc, matchMedia:() => media, AbortController, performance:{now:() => now}, innerWidth:1440, innerHeight:960,
  setTimeout:fn => {timers.set(++timerId,fn);return timerId;},clearTimeout:id => timers.delete(id),CSS:{escape:value => value},console});context.window = context;
vm.createContext(context);vm.runInContext(code('route_transition.js'), context);
const route = context.__qmRouteStage, button = new Element('button');button.textContent = '核验工具';button.rect = {left:340,top:220,width:410,height:100};
assert.equal(route.begin(button, {scene:'home'}), true, 'a pending preference bootstrap preserves the original full route transition');
const defaultMotions = [...motions];
assert.ok(defaultMotions.length > 0);
doc.documentElement.dataset.qmMotionMode = 'research';context.emit('qm-motion-preference-change');
assert.ok(defaultMotions.every(animation => animation.cancelled), 'an explicit research preference cancels the running default transition');
assert.equal(doc.body.children.length, 0);assert.equal(timers.size, 0);assert.equal(main.scrollTop, 77);
assert.equal(route.begin(button, {scene:'home'}), false);assert.equal(doc.body.children.length, 0);
doc.documentElement.dataset.qmMotionMode = 'presentation';context.emit('qm-motion-preference-change');
assert.equal(route.begin(button, {scene:'home'}), true);assert.equal(doc.documentElement.dataset.qmRouteStage, 'expanding');
assert.ok(motions.length >= 5, 'presentation connects the stage and its independent decorative layers');
const original = [...motions];doc.documentElement.dataset.qmMotionMode = 'research';context.emit('qm-motion-preference-change');
assert.ok(original.every(animation => animation.cancelled));assert.equal(doc.body.children.length, 0);assert.equal(timers.size, 0);assert.equal(main.scrollTop, 77, 'preference changes preserve reading position');
doc.documentElement.dataset.qmMotionMode = 'presentation';context.emit('qm-motion-preference-change');const prior = motions.length;
vm.runInContext(code('route_transition.js'), context);assert.equal(motions.length, prior, 'ordinary same-version rerun has no entrance animation');
for (let index = 0; index < 30; index++) {assert.equal(route.begin(button, {scene:'home'}), true);route.arrive(main, {location:'tool',previous:'home'});route.cancel();}
assert.equal(doc.body.children.length, 0);assert.ok(motions.every(animation => animation.cancelled));
media.matches = true;media.emit('change');assert.equal(route.begin(button), false, 'OS reduced-motion wins over presentation mode');
route.dispose();assert.equal(context.count() + doc.count() + media.count(), 0);assert.equal(timers.size, 0);
console.log('global motion controllers: rapid hero reversal, route staging, research/same-scene stability, OS priority and cleanup passed');
