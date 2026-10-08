const assert = require('node:assert/strict');
const {createReadingPosition} = require('../app/reading_position.js');
function fixture() {
  let route='enterprise', tick, expiry, disconnected=0;
  const events=new Map(), handles=new Map();
  const listen=(name, fn, options) => { if (!events.has(name)) events.set(name, new Set()); events.get(name).add(fn); options?.signal?.addEventListener('abort',()=>events.get(name).delete(fn)); };
  const main={scrollTop:400,scrollHeight:2000,clientHeight:600,contains:n=>n===anchor};
  const anchor={classList:['st-key-source_button_sample'],parentElement:null,closest:()=>null,getBoundingClientRect:()=>({top:500-main.scrollTop})};
  const button={classList:[],parentElement:anchor,closest:()=>null};
  const doc={hidden:false,body:{},addEventListener:listen,querySelector:s=>s.includes('data-studio-location')?{getAttribute:()=>route}:s==='[data-testid="stMain"]'?main:s.startsWith('.st-key-')?anchor:null};
  const win={innerHeight:900,addEventListener:listen};
  const controller=createReadingPosition({document:doc,window:win,AbortController,
    MutationObserver:class {constructor(cb){tick=cb;}observe(){}disconnect(){disconnected++;}},
    requestAnimationFrame:fn=>{handles.set(1,fn);return 1;},cancelAnimationFrame:id=>handles.delete(id),
    setTimeout:fn=>{expiry=fn;return 1;},clearTimeout:()=>{},escape:v=>v});
  return {controller,main,doc,emit:(type,values={})=>{for(const fn of events.get(type)||[])fn({type,target:button,...values});},
    flush:()=>{tick();for(const [id,fn] of [...handles]){handles.delete(id);fn();}},
    scene:v=>route=v,expire:()=>expiry(),disconnected:()=>disconnected};
}
{
  const f=fixture();f.emit('pointerdown');f.main.scrollTop=150;f.flush();
  assert.equal(f.main.scrollTop,400,'restore clicked control after rerender clamps the scroller');
  f.emit('wheel');f.main.scrollTop=80;f.flush();assert.equal(f.main.scrollTop,80,'manual scrolling wins');
  f.controller.dispose();assert.equal(f.disconnected(),1);f.emit('pointerdown');f.flush();assert.equal(f.main.scrollTop,80);
}
{
  const f=fixture();f.emit('keydown',{key:'Enter'});f.main.scrollTop=170;f.scene('assets');f.flush();
  assert.equal(f.main.scrollTop,170,'navigation cancels old reading anchor');f.controller.dispose();
}
{
  const f=fixture();f.emit('pointerdown');f.main.scrollTop=200;f.emit('pointerdown');f.main.scrollTop=100;f.flush();
  assert.equal(f.main.scrollTop,200,'second intent supersedes first');f.expire();f.main.scrollTop=70;f.flush();assert.equal(f.main.scrollTop,70);
  f.emit('pointerdown');f.doc.hidden=true;f.emit('visibilitychange');f.main.scrollTop=0;f.flush();assert.equal(f.main.scrollTop,0);f.controller.dispose();
}
console.log('Reading position: rerender, user scroll, navigation, rapid interaction, timeout and disposal passed');
for (const event of [{key:'Tab'}, {key:'Tab',shiftKey:true}, {key:'Enter',target:{classList:[],parentElement:null}}]) {
  const f=fixture();f.emit('pointerdown');f.emit('keydown',event);f.main.scrollTop=60;f.flush();
  assert.equal(f.main.scrollTop,60,'keyboard focus movement wins over previous reading anchor');f.controller.dispose();
}
