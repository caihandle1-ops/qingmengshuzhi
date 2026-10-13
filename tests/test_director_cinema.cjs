'use strict';
// Uses the shipped GSAP, Flip and Draggable in a real DOM implementation.
// Layout rectangles are deterministic fixtures, not a browser visual/FPS test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '../app/director_frontend');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const dom = new JSDOM(html, {url: 'https://local.test/component/', runScripts: 'outside-only', pretendToBeVisual: true});
const win = dom.window, doc = win.document, byId = id => doc.getElementById(id), messages = [], observers = [];
const parent = {postMessage: data => messages.push(data)};
Object.defineProperty(win, 'parent', {value: parent});
let hidden = false;
Object.defineProperty(doc, 'hidden', {get: () => hidden});
const media = new win.EventTarget();media.matches = false;win.matchMedia = () => media;
win.scrollTo = () => {};
win.IntersectionObserver = class {constructor(callback) {this.callback = callback;observers.push(this);}observe() {}disconnect() {this.disconnected = true;}};
win.ResizeObserver = class {observe() {}disconnect() {}};
Object.defineProperty(win.HTMLElement.prototype, 'offsetWidth', {get() {return this.id === 'cinema-playhead' ? 17 : this.id === 'cinema-track' ? 600 : 240;}});
Object.defineProperty(win.HTMLElement.prototype, 'clientWidth', {get() {return this.offsetWidth;}});
Object.defineProperty(win.HTMLElement.prototype, 'offsetHeight', {get() {return this.id === 'director' ? 860 : 70;}});
win.HTMLElement.prototype.getBoundingClientRect = function () {
  const kind = this.closest('[data-fact-slot]')?.dataset.factSlot;
  const left = kind === 'metrics' ? 250 : kind === 'annual' ? 670 : kind === 'sources' ? 570 : 0;
  const top = kind === 'metrics' ? 320 : kind === 'annual' ? 420 : kind === 'sources' ? 260 : 0;
  return {left, top, x: left, y: top, right: left + this.offsetWidth, bottom: top + this.offsetHeight, width: this.offsetWidth, height: this.offsetHeight};
};
for (const file of ['vendor/gsap.min.js', 'vendor/Draggable.min.js', 'vendor/Flip.min.js', 'director-model.js', 'director-cinema.js', 'director.js']) {
  win.eval(fs.readFileSync(path.join(root, file), 'utf8'));
}
const source = {file: '真实资料.csv', location: 'B3', identity: '用户导入', recorded: true};
const metrics = (value, location = 'B3') => [{id: 'revenue', label: '营业收入', value, unit: '亿元', source: {...source, location}},
  {id: 'profit', label: '归母净利润', value: -3.25, unit: '亿元', source: {...source, location: 'C3'}}];
const rows = [{year: 2021, metrics: metrics(0, 'B2')}, {year: 2023, metrics: metrics(null, '独立定位待补充'), ambiguous: true}, {year: 2024, metrics: metrics(123.45)}];
const identity = {label: '用户导入'};
const payload = {version: 1, revision: 'fixture-1', brand: '擎梦数智', focus: {metrics: metrics(0).map(({id, label, unit}) => ({id, label, unit})), rows}, chapters: [
  {id: 'overview', kind: 'overview', title: '企业概览', heading: '真实企业', body: '原始记录', year_count: 3, period: '2021—2024', identity},
  {id: 'metrics', kind: 'metrics', title: '经营量级', heading: '经营量级', year: 2024, metrics: metrics(123.45), identity},
  {id: 'annual', kind: 'annual', title: '年度记录', heading: '年度记录', rows, identity},
  {id: 'sources', kind: 'sources', title: '来源定位', heading: '来源定位', sources: [], identity},
  {id: 'report', kind: 'report', title: '完整报告', heading: '已有报告', body: '<b>原样保存</b>完整记录', identity}
]};
const render = (data = payload, mode = 'presentation') => win.dispatchEvent(new win.MessageEvent('message', {source: parent,
  data: {type: 'streamlit:render', args: {payload: data, motion: {version: 1, mode}}}}));
const click = id => byId(id).click();
const input = progress => {byId('cinema-seek').value = String(progress);byId('cinema-seek').dispatchEvent(new win.Event('input', {bubbles: true}));};
const go = id => win.__qmDirector.deck.go(id);
const tick = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

(async () => {
  try {
    render();const cinema = win.__qmDirector.cinema, fact = byId('focus-fact'), valueNode = byId('focus-value');
    assert.ok(cinema.getState().available && cinema.getState().draggable);
    assert.equal(byId('cinema-controls').hidden, false);
    go('metrics');assert.equal(cinema.getState().factParent, 'metrics');assert.equal(valueNode.textContent, '123.45');
    assert.equal(doc.querySelectorAll('#focus-value').length, 1);
    assert.equal(doc.querySelector('.metric-sheet.is-focused').querySelectorAll('.metric-value').length, 0, 'active card uses the original value element once');
    assert.equal(cinema.getState().identity, JSON.stringify(['fixture-1', 'revenue', 2024]));
    assert.equal(doc.querySelector('[data-fact-slot="metrics"] #focus-value'), valueNode);
    const satellite = [...doc.querySelectorAll('.metric-sheet')].find(item => !item.contains(fact));
    input(600);const middleMetrics = satellite.style.transform;assert.match(middleMetrics, /scale\(0\.9/, 'middle shot fans surrounding metric cards backward');
    input(1000);assert.notEqual(satellite.style.transform, middleMetrics);assert.equal(Number(win.gsap.getProperty(satellite, 'scale')), 1);
    input(500);assert.ok(Math.abs(cinema.getState().time - 3.2) < .01);assert.equal(cinema.getState().playing, false);
    assert.equal(cinema.getState().phase, 'inspect');assert.match(byId('cinema-seek').getAttribute('aria-valuetext'), /3.2 秒/);
    const before = cinema.getState().time;render();assert.equal(cinema.getState().time, before, 'same payload preserves playhead');
    byId('cinema-seek').dispatchEvent(new win.KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
    assert.equal(win.__qmDirector.deck.snapshot().active, 'metrics', 'range arrows do not navigate chapters');
    click('cinema-play');await tick(90);assert.ok(cinema.getState().time > before);click('cinema-play');
    const paused = cinema.getState().time;await tick(70);assert.equal(cinema.getState().time, paused);
    click('cinema-reverse');await tick(80);assert.ok(cinema.getState().time < paused);assert.equal(cinema.getState().reversed, true);click('cinema-play');
    click('cinema-replay');await tick(35);assert.ok(cinema.getState().time < .3);click('cinema-play');
    doc.querySelector('[data-cinema-phase="trace"]').click();assert.equal(cinema.getState().time, 4.45);
    const drag = win.Draggable.get(byId('cinema-playhead'));assert.ok(drag);
    drag.vars.onPress.call(drag);drag.x = 291.5;drag.vars.onDrag.call(drag);drag.vars.onRelease.call(drag);
    assert.ok(Math.abs(cinema.getState().time - 3.2) < .01, 'real Draggable callbacks control the real timeline');
    go('annual');assert.equal(cinema.getState().factParent, 'annual');assert.equal(byId('focus-fact'), fact);assert.equal(byId('focus-value'), valueNode);
    assert.equal(cinema.getState().flipping, true, 'same fact uses an actual Flip transition');
    input(600);const otherRow = [...doc.querySelectorAll('.annual-row')].find(item => !item.contains(fact));
    assert.ok(Number(win.gsap.getProperty(otherRow, 'opacity')) < .5, 'middle annual shot isolates the selected row');
    input(1000);assert.equal(Number(win.gsap.getProperty(otherRow, 'opacity')), 1);
    go('sources');assert.equal(cinema.getState().factParent, 'sources');assert.equal(doc.querySelector('.source-locator').textContent, 'B3');
    input(600);assert.ok(Number(win.gsap.getProperty(doc.querySelector('.source-locator'), 'x')) > 20, 'middle source shot reframes the exact locator');
    input(1000);assert.equal(Number(win.gsap.getProperty(doc.querySelector('.source-locator'), 'x')), 0);
    assert.equal(valueNode.textContent, '123.45');input(150);assert.equal(valueNode.textContent, '123.45');assert.equal(doc.querySelector('.source-locator').textContent, 'B3');
    win.__qmDirector.deck.setFocus('profit', 2024);assert.equal(valueNode.textContent, '-3.25');assert.equal(cinema.getState().flipping, false, 'different fact never borrows an old fact position');
    assert.equal(doc.querySelector('.source-locator').textContent, 'C3');
    win.__qmDirector.deck.setFocus('revenue', 2021);assert.equal(valueNode.textContent, '0.00');assert.equal(doc.querySelector('.source-locator').textContent, 'B2');
    win.__qmDirector.deck.setFocus('revenue', 2023);assert.equal(valueNode.textContent, '暂无数据');assert.equal(doc.querySelector('.source-locator').textContent, '独立定位待补充');
    assert.match(byId('stage').textContent, /同年度多条记录待核对/);
    for (let i = 0; i < 5; i++) {go('annual');go('metrics');go('sources');}
    assert.equal(doc.querySelectorAll('#focus-fact').length, 1);assert.equal(valueNode.textContent, '暂无数据');
    input(350);click('cinema-play');hidden = true;doc.dispatchEvent(new win.Event('visibilitychange'));
    const hiddenTime = cinema.getState().time;await tick(75);assert.equal(cinema.getState().time, hiddenTime, 'hidden pauses without resetting');
    hidden = false;doc.dispatchEvent(new win.Event('visibilitychange'));await tick(60);assert.ok(cinema.getState().time > hiddenTime);
    click('configure');const editorTime = cinema.getState().time;await tick(60);assert.equal(cinema.getState().time, editorTime);click('close-editor');
    render(payload, 'research');assert.equal(cinema.getState().time, 6.4);assert.equal(byId('cinema-seek').disabled, true);
    assert.equal(byId('focus-value'), valueNode);assert.equal(valueNode.textContent, '暂无数据');
    go('annual');assert.equal(cinema.getState().paused, true);assert.equal(cinema.getState().factParent, 'annual');
    render(payload, 'presentation');assert.equal(cinema.getState().time, 6.4, 'mode changes do not replay');
    media.matches = true;media.dispatchEvent(new win.Event('change'));assert.equal(byId('cinema-play').disabled, true);
    media.matches = false;media.dispatchEvent(new win.Event('change'));go('report');assert.match(byId('stage').textContent, /<b>原样保存<\/b>/);
    assert.equal(byId('stage').querySelectorAll('b').length, 0, 'stored text is never interpreted as HTML');
    assert.equal(messages.filter(message => message.type === 'streamlit:setComponentValue').length, 0, 'playback and focus stay local');
    render({...payload, revision: 'fixture-2'});go('metrics');assert.equal(cinema.getState().identity, JSON.stringify(['fixture-2', 'revenue', 2024]));
    assert.equal(cinema.getState().flipping, false);
    click('exit');assert.equal(messages.filter(message => message.type === 'streamlit:setComponentValue').length, 1);
    win.__qmDirector.dispose();assert.equal(cinema.getState().disposed, true);assert.equal(win.Draggable.get(byId('cinema-playhead')), undefined);
    assert.equal(win.gsap.globalTimeline.getChildren(true, true, true).filter(item => item.isActive()).length, 0, 'dispose stops all owned animation');
    assert.equal(byId('focus-home').contains(fact), true);
    console.log('director cinema: actual GSAP/Flip/Draggable, seek/play/reverse/replay/phases, exact fact/source continuity, hidden/quiet/reduced/editor state and cleanup passed');
  } finally {win.gsap.ticker.sleep();win.close();}
})().catch(error => {console.error(error);process.exitCode = 1;});
