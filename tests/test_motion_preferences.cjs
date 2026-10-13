'use strict';
const assert = require('node:assert/strict');
const {createPreferenceRuntime, install} = require('../app/motion_preferences.js');
const seen = [], applied = [];
let reduced = false, listener, stops = 0;
const policy = createPreferenceRuntime({reduced: () => reduced, apply: value => applied.push(value),
  notify: value => seen.push(value), listenReduced: callback => {listener = callback; return () => {stops++; listener = null;};}
}, {});
assert.equal(seen[0].mode, 'presentation'); assert.equal(seen[0].level, 'enhanced');
policy.set({version: 1, mode: 'research'});assert.equal(seen.at(-1).level, 'light');
policy.set({version: 1, mode: 'presentation'});assert.equal(seen.at(-1).level, 'enhanced');
const stable = seen.length;policy.set({version: 1, mode: 'presentation'});assert.equal(seen.length, stable, 'ordinary rerun must not dispatch a new animation request');
reduced = true;listener();assert.equal(seen.at(-1).mode, 'presentation');assert.equal(seen.at(-1).level, 'reduced');
policy.set({version: 1, mode: 'research'});assert.equal(seen.at(-1).level, 'reduced', 'system preference always wins');
reduced = false;listener();assert.equal(seen.at(-1).level, 'light');
policy.set({version: 900, mode: 'research'});assert.equal(policy.snapshot().mode, 'presentation', 'only an explicit supported research choice disables the original motion');
for (let i = 0; i < 80; i++) policy.set({version: 1, mode: i % 2 ? 'presentation' : 'research'});
policy.dispose();policy.dispose();assert.equal(stops, 1);const finished = seen.length;policy.set({version:1,mode:'presentation'});assert.equal(seen.length, finished);

// Execute the actual DOM installer twice: persistent document, zero duplicate listeners.
class Events {
  constructor() {this.events = new Map();}
  addEventListener(type, callback) {if (!this.events.has(type)) this.events.set(type, new Set()); this.events.get(type).add(callback);}
  removeEventListener(type, callback) {this.events.get(type)?.delete(callback);}
  dispatchEvent(event) {for (const callback of [...this.events.get(event.type) || []]) callback(event);}
  count() {return [...this.events.values()].reduce((n, callbacks) => n + callbacks.size, 0);}
}
const win = new Events(), media = new Events(), doc = {documentElement:{dataset:{}}};
media.matches = false;win.matchMedia = () => media;win.CustomEvent = class {constructor(type, options) {this.type = type;this.detail = options.detail;}};
let changes = 0;win.addEventListener('qm-motion-preference-change', () => changes++);
const first = install(win, doc, {version: 1, mode: 'research'}), count = win.count() + media.count();
assert.equal(doc.documentElement.dataset.qmMotionLevel, 'light');
assert.equal(install(win, doc, {version: 1, mode: 'research'}), first);
assert.equal(win.count() + media.count(), count);assert.equal(changes, 1);
install(win, doc, {version: 1, mode: 'presentation'});assert.equal(changes, 2);assert.equal(doc.documentElement.dataset.qmMotionLevel, 'enhanced');
media.matches = true;media.dispatchEvent({type:'change'});assert.equal(doc.documentElement.dataset.qmMotionLevel, 'reduced');
win.dispatchEvent({type:'pagehide'});assert.equal(media.count(), 0);assert.equal(win.count(), 1, 'installer releases both lifecycle and media listeners');
console.log('global preference runtime: defaults, OS priority, stable reruns, rapid changes and cleanup passed');
