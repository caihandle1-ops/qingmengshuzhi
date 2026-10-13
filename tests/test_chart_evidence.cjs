'use strict';
// Drive the production chart's DOM handlers and Streamlit event protocol.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
class Events {
  constructor() { this.handlers = new Map(); }
  addEventListener(type, fn, options={}) { if(options.signal?.aborted)return;if(!this.handlers.has(type))this.handlers.set(type,new Set());this.handlers.get(type).add(fn);options.signal?.addEventListener('abort',()=>this.handlers.get(type)?.delete(fn),{once:true}); }
  emit(type, event={}) { for(const fn of [...this.handlers.get(type)||[]])fn({type,...event}); }
  count() { return [...this.handlers.values()].reduce((n,values)=>n+values.size,0); }
}
class Element extends Events {
  constructor(tag='div') { super();this.tag=tag;this.children=[];this.dataset={};this.attrs={};this.style={};this.classes=new Set();this.hidden=false;this.clientWidth=800;this.scrollWidth=800;this.scrollLeft=0;this.classList={toggle:(name,yes)=>yes?this.classes.add(name):this.classes.delete(name)}; }
  setAttribute(name,value) {this.attrs[name]=String(value);if(name==='class')this.classes=new Set(String(value).split(' '));}
  getAttribute(name) {return this.attrs[name];}
  appendChild(node) {this.children.push(node);node.parent=this;return node;}
  replaceChildren(...nodes) {this.children=nodes;}
  querySelectorAll(selector) {const all=[];for(const node of this.children){if(selector.startsWith('.')&&node.classes.has(selector.slice(1)))all.push(node);all.push(...node.querySelectorAll(selector));}return all;}
  getBoundingClientRect() {return {left:20,top:20,width:80,height:40,right:100,bottom:60};}
  focus() {this.emit('focus');}
}
const ids=['chart-shell','marks','chart-viewport','chart','readout-year','readout-value','readout-source','source-button','readout-status','selection-line','grid','series-legend','chart-title','chart-mode','metric-tabs','line'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()])), document=new Events(), media=new Events(), window=new Events();
document.hidden=false;document.getElementById=id=>nodes[id];document.createElement=tag=>new Element(tag);document.createElementNS=(_,tag)=>new Element(tag);media.matches=false;
const sent=[],parent={postMessage:message=>sent.push(message)},frames=new Map();let frameId=0,now=0,resize;
Object.assign(window,{window,document,parent,matchMedia:()=>media,AbortController,performance:{now:()=>now},
  requestAnimationFrame:callback=>{frames.set(++frameId,callback);return frameId;},cancelAnimationFrame:id=>frames.delete(id),
  ResizeObserver:class {constructor(callback){this.callback=callback;resize=this;}observe(){}disconnect(){this.disconnected=true;}},
  innerWidth:1200,innerHeight:800,Date:{now:()=>7},console});
vm.createContext(window);vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/chart_frontend/chart.js'),'utf8'),window);
const points=[{id:'A|2024|revenue',company:'A',year:2024,metric:'revenue',value:0,source:'A.pdf',location:'PDF 第 2 页',source_index:0,source_id:'exact-source-a'},
  {id:'B|2024|revenue',company:'B',year:2024,metric:'revenue',value:-7,source:'B.pdf',location:'PDF 第 3 页',source_index:1,source_id:'exact-source-b'}];
const payload={revision:'frozen-revision',mode:'bar',metrics:[{id:'revenue',label:'营业收入',unit:'亿元'}],points};
function render(args) {window.emit('message',{source:parent,data:{type:'streamlit:render',args:{payload,motion:{version:1,mode:'presentation'},...args}}});}
function paint(time) {now=time;const callbacks=[...frames.values()];frames.clear();callbacks.forEach(callback=>callback(time));}
function values() {return sent.filter(message=>message.type==='streamlit:setComponentValue').map(message=>message.value);}
render();paint(1000);
assert.equal(Number(nodes.marks.querySelectorAll('.chart-bar')[0].getAttribute('height')),0,'a real zero is not drawn as a fabricated positive bar');
assert.ok(Number(nodes.marks.querySelectorAll('.mark')[0].getAttribute('height'))>=24,'the zero observation remains a real mouse/keyboard hit target');
assert.ok(Number(nodes.marks.querySelectorAll('.chart-bar')[1].getAttribute('height'))>0,'negative observations still have a visible extent below zero');
nodes.marks.querySelectorAll('.mark')[0].emit('click');
nodes['source-button'].emit('click');
const first=values().at(-1);
assert.deepEqual(JSON.parse(JSON.stringify(first)),{action:'source',index:0,point_id:'A|2024|revenue',source_id:'exact-source-a',revision:'frozen-revision',nonce:'7-1'});
assert.ok(sent.some(message=>message.type==='qm:evidence-anchor'),'existing source-to-paper presentation protocol is preserved');
assert.ok(nodes['readout-value'].textContent.startsWith('0.00'),'real zero remains a selectable data point');
nodes['source-button'].emit('click');assert.equal(values().at(-1).nonce,'7-2','same-millisecond clicks still carry distinct deliberate refocus tokens');
nodes.marks.querySelectorAll('.mark')[1].emit('keydown',{key:'Enter',preventDefault(){}});nodes['source-button'].emit('click');
assert.equal(values().at(-1).source_id,'exact-source-b');assert.equal(values().at(-1).point_id,'B|2024|revenue');
const eventsBefore=values().length;render({source_highlight:0});paint(2000);assert.equal(values().length,eventsBefore,'a parent rerun does not manufacture another source action');
assert.ok(nodes['readout-year'].textContent.startsWith('A'));
const settledMark=nodes.marks.querySelectorAll('.mark')[0];render();assert.equal(nodes.marks.querySelectorAll('.mark')[0],settledMark,'unchanged parent reruns do not remount or replay the chart');
const missing={...payload,revision:'missing-source',points:[{...points[0],source_index:null,source_id:null}]};
render({payload:missing});paint(3000);assert.equal(nodes['source-button'].hidden,true);nodes['source-button'].emit('click');assert.equal(values().length,eventsBefore);
render({payload,focus_events:true,focus_point:points[1].id});paint(4000);
nodes.marks.querySelectorAll('.mark')[0].emit('keydown',{key:'Enter',preventDefault(){}});assert.equal(values().at(-1).action,'focus');
media.matches=true;media.emit('change');paint(4100);assert.equal(nodes['chart-shell'].dataset.chartPhase,'settled');
nodes['chart-viewport'].clientWidth=1600;resize.callback();
assert.equal(nodes.chart.getAttribute('viewBox'),'0 0 1600 300','wide displays gain horizontal plotting space while the physical height stays bounded');
const linePayload={...payload,revision:'missing-year',mode:'line',points:[{...points[0],id:'A|2023|revenue',year:2023,value:2},{...points[0],id:'A|2025|revenue',year:2025,value:4}]};
render({payload:linePayload,focus_events:false});
assert.equal((nodes.line.getAttribute('d').match(/M/g)||[]).length,2,'a missing annual observation is never connected as continuous data');
const beforeHover=values().length;nodes.marks.querySelectorAll('.mark')[0].emit('pointerenter');nodes.marks.querySelectorAll('.mark')[1].emit('focus');assert.equal(values().length,beforeHover,'hover and keyboard focus never trigger a Python rerun');
window.__qmChart.dispose();assert.equal(frames.size,0);assert.ok(resize.disconnected);assert.equal(window.count()+document.count()+media.count(),0);
console.log('chart evidence: exact point/source events, zero/negative data, same-millisecond refocus, parent reruns, missing source and cleanup passed');
