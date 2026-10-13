'use strict';
// Actual GSAP + ScrollTrigger and native MutationObserver. Controlled geometry
// verifies ownership and lifecycle; desktop pixel acceptance is a separate step.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function runViewport(width,height){
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',error=>errors.push(error.message));vc.on('warn',message=>errors.push(String(message)));
 const dom=new JSDOM('<!doctype html><html><head></head><body></body></html>',{runScripts:'dangerously',pretendToBeVisual:true,url:'http://127.0.0.1:8504/',virtualConsole:vc});
 const win=dom.window,doc=win.document,queries=new Map();let main=null;
 win.matchMedia=query=>{if(!queries.has(query)){const events=new win.EventTarget();events.matches=false;events.addListener=fn=>events.addEventListener('change',fn);events.removeListener=fn=>events.removeEventListener('change',fn);queries.set(query,events);}return queries.get(query);};
 Object.defineProperty(win,'innerWidth',{configurable:true,value:width});Object.defineProperty(win,'innerHeight',{configurable:true,value:height});
 win.scrollTo=()=>{};
 for(const node of [doc.documentElement,doc.body]){
  Object.defineProperty(node,'clientHeight',{configurable:true,value:height});Object.defineProperty(node,'scrollHeight',{configurable:true,value:2400});Object.defineProperty(node,'clientWidth',{configurable:true,value:width});
 }
 const spreadHeight=height<900?340:432;
 win.Element.prototype.getBoundingClientRect=function(){
  if(this===doc.body||this===doc.documentElement||this===main)return{x:280,y:0,left:280,top:0,width:width-280,height,right:width,bottom:height};
  const top=150-(main?.scrollTop||0);return{x:312,y:top,left:312,top,width:width-344,height:spreadHeight,right:width-32,bottom:top+spreadHeight};
 };
 win.IntersectionObserver=class{observe(){}unobserve(){}disconnect(){}};
 win.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};
 const matrix=()=>({a:1,b:0,c:0,d:1,e:0,f:0,inverse(){return matrix();},multiply(){return matrix();}});
 win.SVGElement.prototype.getBBox=()=>({x:0,y:0,width:160,height:160});win.SVGElement.prototype.getCTM=matrix;win.SVGElement.prototype.getScreenCTM=matrix;win.SVGSVGElement.prototype.createSVGMatrix=matrix;
 Object.defineProperty(win.SVGElement.prototype,'transform',{get(){return{baseVal:{numberOfItems:0,consolidate(){return{matrix:matrix()};}}};}});
 doc.body.remove();win.eval(read('feature_theater.js'));await wait(35);assert.deepEqual(errors,[],'Controller boots against Document before body');
 const body=doc.createElement('body');doc.documentElement.append(body);
 main=doc.createElement('main');main.dataset.testid='stMain';main.style.cssText='overflow-y:auto;height:'+height+'px';body.append(main);
 for(const [key,value] of Object.entries({clientHeight:height,scrollHeight:2400,clientWidth:width-280}))Object.defineProperty(main,key,{configurable:true,value});
 const input=doc.createElement('input');input.value='原生草稿 0';input.id='real-input';main.append(input);
 for(const file of ['vendor/gsap/gsap.min.js','vendor/gsap/ScrollTrigger.min.js'])win.eval(read(file));
 const engine=win.QMFeatureTheater,gsap=win.gsap,ST=win.ScrollTrigger;
 function render(scene){
  const spread=doc.createElement('section');spread.dataset.featureSpread=scene;
  spread.innerHTML='<header><div class="feature-title-mask" data-feature-title-mask><h2>当前真实功能</h2></div><div><span data-feature-work-context>真实企业 A</span><span data-feature-work-context>2025 年度</span></div><a data-feature-work-link href="#qm-action-'+scene+'"><span>进入实际操作</span><i>↘</i></a></header><div data-feature-scene="'+scene+'" data-feature-inline="'+scene+'"></div>';
  main.prepend(spread);const target=doc.createElement('div');target.id='qm-action-'+scene;main.append(target);
  const host=spread.querySelector('[data-feature-inline]');engine.syncInline([host]);ST.refresh();return{spread,host,target};
 }
 function scroll(top){main.scrollTop=top;main.dispatchEvent(new win.Event('scroll'));ST.update();}
 try{
  for(const scene of ['qa','scope','counter','replay','assets']){
   input.blur();scroll(0);engine.setRoute(scene);let {spread,host,target}=render(scene);
   const entrance=gsap.getById('qm-feature-entrance-'+scene);assert.ok(entrance,'Original large entrance retained');entrance.progress(1);
   const art=host.querySelector('[data-ft-scroll]'),nativeStyle=input.getAttribute('style'),header=spread.querySelector('header');
   assert.equal(host.querySelector('button,input,output,[role="slider"],progress'),null,'No stage/player controls');
   assert.equal(doc.querySelectorAll('[data-qm-feature-reading]').length,1);
   let strip=doc.querySelector('[data-qm-feature-reading]');assert.equal(strip.hidden,true);
   scroll(150+spreadHeight+100);await wait(90);
   for(const trigger of ST.getAll())trigger.getTween?.()?.progress(1);
   assert.equal(strip.hidden,false,'Read-only context follows the passed introduction');
   assert.match(strip.textContent,/真实企业 A.*2025 年度/);assert.equal(strip.querySelector('a').getAttribute('href'),'#'+target.id);
   assert.equal(parseFloat(strip.style.width),width-344);assert.equal(parseFloat(strip.style.left),312);
   assert.ok(Number(gsap.getProperty(art,'xPercent'))>15,'Actual ScrollTrigger retreats artwork to the side');
   assert.equal(input.value,'原生草稿 0');assert.equal(input.getAttribute('style'),nativeStyle);assert.equal(gsap.getTweensOf(input).length,0);
   assert.equal(header.style.transform,'');assert.ok(ST.getAll().every(trigger=>!trigger.vars.pin));
   assert.equal(ST.getAll().filter(trigger=>trigger.animation).length,1,'Exactly one scroll transform owner');
   input.focus();await wait(530);assert.ok(engine.getInlineState()[0].ambientTimeScale<=.32,'Focused native input retains calm existing attention mode');
   const originalTime=engine.getInlineState()[0].ambientTime;win.eval(read('feature_theater.js'));engine.syncInline([host]);
   assert.equal(win.QMFeatureTheater,engine);assert.equal(doc.querySelectorAll('[data-qm-feature-reading]').length,1);assert.equal(engine.getInlineState()[0].progress,1);
   spread.remove();const next=render(scene);spread=next.spread;host=next.host;target.remove();target=next.target;
   assert.equal(engine.getInlineState()[0].progress,1,'Equal-route remount does not repeat entrance');assert.ok(engine.getInlineState()[0].ambientTime>=originalTime);
   assert.equal(doc.querySelectorAll('[data-qm-feature-reading]').length,1);assert.equal(ST.getAll().length,2,'Remount clears both old triggers');
   strip=doc.querySelector('[data-qm-feature-reading]');
   doc.documentElement.dataset.qmMotionMode='research';win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));scroll(150+spreadHeight+100);ST.refresh();ST.update();
   assert.equal(strip.hidden,false,'Context remains available in reduced decorative mode');assert.equal(engine.getInlineState()[0].ambientRunning,false);
   assert.equal(Number(gsap.getProperty(host.querySelector('[data-ft-scroll]'),'xPercent')),0,'Reduced motion settles scroll decoration');
   delete doc.documentElement.dataset.qmMotionMode;win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));
   const reduced=queries.get('(prefers-reduced-motion: reduce)');reduced.matches=true;reduced.dispatchEvent(new win.Event('change'));assert.equal(engine.getInlineState()[0].ambientRunning,false);reduced.matches=false;reduced.dispatchEvent(new win.Event('change'));
   engine.setRoute('leaving-'+scene);spread.remove();target.remove();assert.equal(doc.querySelectorAll('[data-qm-feature-reading]').length,0);assert.equal(ST.getAll().length,0);
  }
  engine.dispose();assert.equal(ST.getAll().length,0);assert.equal(doc.querySelectorAll('[data-qm-feature-reading]').length,0);
  win.eval(read('feature_theater.js'));assert.notEqual(win.QMFeatureTheater,engine,'Disposed same-document owner can initialize again');win.QMFeatureTheater.dispose();
  assert.deepEqual(errors,[]);
  return{viewport:[width,height],scenes:5,real_scrolltrigger:true,readonly_context:true,single_scroll_owner:true,remount_preserves_phase:true};
 }finally{win.QMFeatureTheater?.dispose();ST.killAll();gsap.ticker.sleep();dom.window.close();}
}
(async()=>{const results=[];for(const viewport of [[1366,768],[1920,1080]])results.push(await runViewport(...viewport));console.log(JSON.stringify({passed:true,results}));})().catch(error=>{console.error(error);process.exitCode=1;});
