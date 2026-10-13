'use strict';
// Real production GSAP and MutationObserver; deterministic document geometry only.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const wait=()=>new Promise(resolve=>setTimeout(resolve,35));
async function run({engine=true,reduced=false}={}){
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));vc.on('warn',e=>errors.push(String(e)));
 const dom=new JSDOM('<!doctype html><html><body></body></html>',{runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
 const w=dom.window,d=w.document,timelines=[];
 const media=new w.EventTarget();media.matches=reduced;w.matchMedia=()=>media;
 w.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};
 w.HTMLElement.prototype.getBoundingClientRect=function(){return this._rect||{top:100,bottom:400,left:0,right:600,width:600,height:300};};
 w.HTMLElement.prototype.scrollIntoView=function(){};
 if(engine){w.eval(read('vendor/gsap/gsap.min.js'));const create=w.gsap.timeline;w.gsap.timeline=function(...args){const tl=create.apply(this,args);timelines.push(tl);return tl;};}
 const markup='<article data-report-reader="report-revision-a"><header class="rr-cover"><div class="rr-cover-art" aria-hidden="true"><em></em></div><h2>比亚迪 2025</h2></header>'+
  '<section data-report-chapter="0"><div class="rr-chapter-art" aria-hidden="true"><b></b></div><p data-report-original>原文营业收入 8,039.65 亿元，完整原文。</p><a data-report-source-id="exact_2025">实际来源</a></section></article><input value="原有问题"><button>确认</button>';
 function mount(){d.body.innerHTML=markup;return d.querySelector('article');}
 let root=mount();const input=d.querySelector('input');input.focus();
 const texts=root.textContent;w.eval(read('report_reader.js'));await wait();timelines.forEach(tl=>tl.pause());
 try{
  const api=w.__qmReportReader;assert.ok(api);
  if(!engine||reduced){assert.equal(timelines.length,0);assert.equal(root.textContent,texts);api.dispose();return;}
  assert.equal(timelines.length,2,'Cover and visible chapter each enter once');
  timelines.forEach(tl=>tl.progress(.4));
  const targets=timelines.flatMap(tl=>tl.getChildren(true,true,false).flatMap(t=>t.targets()));
  assert.ok(targets.length&&targets.every(t=>t.matches('.rr-cover-art>em,.rr-chapter-art>b')),'Only inert artwork can be a GSAP target');
  assert.equal(root.textContent,texts);assert.equal(input.value,'原有问题');assert.equal(d.activeElement,input);
  assert.equal(root.querySelector('a').dataset.reportSourceId,'exact_2025');
  root=mount();await wait();assert.equal(timelines.length,2,'Same report remount is not a new entry');
  assert.ok(timelines.every(t=>t.parent===null),'Detached paper timelines are reverted');
  root.dataset.reportReader='report-revision-b';api.refresh();await wait();timelines.forEach(t=>t.pause());
  assert.equal(timelines.length,4,'A newly generated report has its own entry');
  const chapter=root.querySelector('[data-report-chapter]');chapter._rect={top:2000,bottom:2300,left:0,right:600,width:600,height:300};
  d.dispatchEvent(new w.Event('scroll'));await wait();assert.equal(timelines.at(-1).parent,null,'Offscreen paper is stopped');
  media.matches=true;media.dispatchEvent(new w.Event('change'));await wait();
  assert.ok(timelines.every(t=>t.parent===null),'Reduced motion clears existing GSAP work');
  assert.equal(root.textContent,texts);api.dispose();api.dispose();await wait();
  assert.equal(w.gsap.globalTimeline.getChildren(true,true,true).length,0);assert.deepEqual(errors,[]);
 }finally{w.__qmReportReader?.dispose();w.gsap?.ticker.sleep();w.close();}
}
(async()=>{await run();await run({reduced:true});await run({engine:false});console.log('PASS report v22: real GSAP decorative-only, exact text/source, rerun, revision, offscreen, reduced, fallback, disposal');})().catch(e=>{console.error(e);process.exitCode=1;});
