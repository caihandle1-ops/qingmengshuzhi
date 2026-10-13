'use strict';
// Real local GSAP/MorphSVG in a deterministic DOM. This does not claim pixels/FPS.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
let JSDOM,VirtualConsole;
try{({JSDOM,VirtualConsole}=require('jsdom'));}catch{console.log('report fold: skipped; set NODE_PATH to the offline jsdom diagnostics package');process.exit(0);}
const errors=[],warnings=[],consoleBridge=new VirtualConsole();consoleBridge.on('jsdomError',error=>errors.push(String(error)));consoleBridge.on('warn',(...args)=>warnings.push(args.join(' ')));
const dom=new JSDOM('<!doctype html><html><body><main data-testid="stMain"><input value="保留真实输入 0 / 缺失" id="native"></main></body></html>',{url:'http://127.0.0.1:8504/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:consoleBridge});
const win=dom.window,doc=win.document,main=doc.querySelector('main'),native=doc.querySelector('#native'),queries=new Map(),intersections=[];
win.matchMedia=query=>{if(!queries.has(query))queries.set(query,{matches:false,listeners:new Set(),addEventListener(type,fn){this.listeners.add(fn);},removeEventListener(type,fn){this.listeners.delete(fn);}});return queries.get(query);};
win.IntersectionObserver=class{constructor(callback){this.callback=callback;this.targets=new Set();intersections.push(this);}observe(node){this.targets.add(node);}unobserve(node){this.targets.delete(node);}disconnect(){this.targets.clear();}};
win.Element.prototype.getBoundingClientRect=function(){return{x:260,y:140,left:260,top:140,right:1360,bottom:720,width:1100,height:580};};
const matrix=()=>({a:1,b:0,c:0,d:1,e:0,f:0,inverse(){return matrix();},multiply(){return matrix();}});
win.SVGElement.prototype.getBBox=function(){return{x:Number(this.getAttribute('x'))||0,y:Number(this.getAttribute('y'))||0,width:Number(this.getAttribute('width'))||160,height:Number(this.getAttribute('height'))||160};};
win.SVGElement.prototype.getCTM=matrix;win.SVGElement.prototype.getScreenCTM=matrix;win.SVGSVGElement.prototype.createSVGMatrix=matrix;
Object.defineProperty(win.SVGElement.prototype,'transform',{get(){return{baseVal:{numberOfItems:0,consolidate(){return{matrix:matrix()};}}};}});
for(const file of ['vendor/gsap/gsap.min.js','vendor/gsap/MorphSVGPlugin.min.js','feature_theater.js'])win.eval(fs.readFileSync(path.join(__dirname,'../app',file),'utf8'));
const engine=win.QMFeatureTheater,gsap=win.gsap,state=()=>engine.getInlineState()[0],sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let serial=0;
function hostFor(scene,{newRoute=true}={}){if(newRoute)engine.setRoute(scene+'-'+(++serial));const host=doc.createElement('div');host.setAttribute('data-feature-inline',scene);host.setAttribute('data-feature-scene',scene);main.appendChild(host);engine.syncInline([host],{hold:true});return host;}
function land(host){host.dataset.qmRouteArrival='report';engine.releaseInline(host);return gsap.getById('qm-feature-handoff-'+host.getAttribute('data-feature-inline'));}
const response=node=>[...node.querySelectorAll('[data-ft-response]')].map(item=>item.getAttribute('transform')+'|'+item.style.opacity).join(';');
function hidden(value){Object.defineProperty(doc,'hidden',{configurable:true,value});doc.dispatchEvent(new win.Event('visibilitychange'));}
function mode(value){doc.documentElement.dataset.qmMotionMode=value;win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));}
function intersect(host,value){const node=host.querySelector('[data-qm-feature-inline]');for(const observer of intersections)if(observer.targets.has(node))observer.callback([{target:node,isIntersecting:value}]);}
const selection={qa:{v:1,category:'source',source:2},scope:{v:1,dimension:'period'},counter:{v:1,category:'source',source:1},replay:{v:1,category:'source'},assets:{v:1,type:'pdf'}};
async function run(){
  native.focus();const summaries={};
  for(const scene of ['qa','scope','counter','replay','assets']){
    const host=hostFor(scene);engine.setContext(scene,selection[scene]);const currentResponse=response(host);
    const panels=[...host.querySelectorAll('[data-ft-fold-panel]')],initial=panels.map(node=>node.getAttribute('d')).join('|');
    const fold=land(host);assert.ok(fold,scene+': real report arrival owns a bounded fold timeline');
    assert.equal(state().handoffRunning,true);assert.equal(state().ambientRunning,false,'ambient cannot compete with the folded paper');assert.equal(state().progress,1,'the entry camera remains complete');
    assert.equal(host.hasAttribute('data-qm-route-arrival'),false);assert.equal(host.querySelector('button,input,output,nav,[role="slider"]'),null);
    const camera=host.querySelector('[data-ft-camera]'),pose=camera.getAttribute('transform'),paper=host.querySelector('[data-ft-handoff-paper]');
    assert.equal(Number(gsap.getProperty(paper,'opacity')),1);
    fold.time(.31);const crease=panels.map(node=>node.getAttribute('d')).join('|');assert.notEqual(crease,initial,'MorphSVG creates a visible intermediate crease');
    fold.time(.89);const expanded=panels.map(node=>node.getAttribute('d')).join('|');assert.notEqual(expanded,crease,'paper contours continuously become scene geometry');
    if(scene==='counter')assert.ok(Number(host.querySelector('[data-ft-fold-aperture]').getAttribute('r'))>20,'a real mask opens the inspection aperture');
    assert.equal(camera.getAttribute('transform'),pose,'fold does not replay camera motion');assert.equal(response(host),currentResponse,'confirmed business selection is retained through the fold');
    assert.equal(doc.activeElement,native);assert.equal(native.value,'保留真实输入 0 / 缺失');assert.equal(gsap.getTweensOf(native).length,0);
    summaries[scene]={panels:panels.length,duration:fold.duration(),target:panels.map(node=>node.getAttribute('data-ft-fold-target')).join('|')};
    fold.progress(1);assert.equal(state().handoffRunning,false);assert.equal(state().handoffProgress,1);assert.equal(state().ambientRunning,true);assert.equal(Number(gsap.getProperty(paper,'opacity')),0);
    // Exercise the actual quickTo reset path after landing, including its
    // pinned GSAP console warnings. The first held context is static and alone
    // cannot detect an unsupported quickTo('scale') alias.
    const responseTargets=[...host.querySelectorAll('[data-ft-response]')];
    engine.setContext(scene,{v:1});
    assert.equal(state().responseRunning,true);
    for(const target of responseTargets){
      const tweens=gsap.getTweensOf(target);
      assert.ok(tweens.some(tween=>Object.hasOwn(tween.vars,'scaleX')));
      assert.ok(tweens.some(tween=>Object.hasOwn(tween.vars,'scaleY')));
      tweens.forEach(tween=>tween.progress(1));
      assert.equal(Number(gsap.getProperty(target,'scaleX')),1);
      assert.equal(Number(gsap.getProperty(target,'scaleY')),1);
    }
    engine.setContext(scene,selection[scene]);
    for(const target of responseTargets)gsap.getTweensOf(target).forEach(tween=>tween.progress(1));
    assert.ok(responseTargets.some(target=>Number(gsap.getProperty(target,'scaleX'))!==1),scene+': selected emphasis still scales');
    for(const target of responseTargets)assert.equal(gsap.getProperty(target,'scaleX'),gsap.getProperty(target,'scaleY'));
    assert.deepEqual(warnings,[],scene+': real response resets must emit no GSAP warnings');
    engine.releaseInline(host);assert.equal(gsap.getById('qm-feature-handoff-'+scene),undefined,'an ordinary repeated release cannot start another fold');
    host.remove();
  }
  assert.equal(new Set(Object.values(summaries).map(item=>item.target)).size,5,'all five final shapes are distinct');
  for(const interruption of ['hidden','research','reduced','offscreen']){
    const host=hostFor('scope'),fold=land(host);fold.time(.44);const camera=host.querySelector('[data-ft-camera]'),pose=camera.getAttribute('transform');
    if(interruption==='hidden')hidden(true);
    if(interruption==='research')mode('research');
    if(interruption==='reduced'){const media=win.matchMedia('(prefers-reduced-motion: reduce)');media.matches=true;media.listeners.forEach(fn=>fn({matches:true}));}
    if(interruption==='offscreen')intersect(host,false);
    assert.equal(state().handoffRunning,false);assert.equal(state().handoffProgress,1);assert.equal(state().ambientRunning,false);
    assert.equal(Number(gsap.getProperty(host.querySelector('[data-ft-handoff-art]'),'opacity')),1,'interruption preserves complete authored content');
    hidden(false);mode('presentation');const media=win.matchMedia('(prefers-reduced-motion: reduce)');media.matches=false;media.listeners.forEach(fn=>fn({matches:false}));intersect(host,true);
    assert.equal(state().handoffRunning,false);assert.equal(state().ambientRunning,true);assert.equal(camera.getAttribute('transform'),pose);assert.equal(gsap.getById('qm-feature-handoff-scope'),undefined);
    host.remove();
  }
  // A Streamlit remount in the middle of a fold settles and retains business state.
  let host=hostFor('counter');engine.setContext('counter',selection.counter);const fold=land(host);fold.time(.4);const revision=state().contextRevision,oldTargets=[...host.querySelectorAll('*')];host.remove();
  host=hostFor('counter',{newRoute:false});engine.releaseInline(host);assert.equal(state().progress,1);assert.equal(state().contextRevision,revision);assert.equal(state().handoffRunning,false);assert.equal(state().ambientRunning,true);assert.equal(gsap.getTweensOf(oldTargets).length,0);
  const rapid=land(hostFor('qa'));rapid.time(.3);const next=hostFor('assets');assert.equal(gsap.getById('qm-feature-handoff-qa'),undefined);assert.equal(state().scene,'assets');assert.equal(state().held,true);land(next).progress(1);
  // Plugin absence falls back to the complete scene with a live ambient clock.
  const plugin=win.MorphSVGPlugin;win.MorphSVGPlugin=null;host=hostFor('qa');assert.equal(land(host),undefined);assert.equal(state().progress,1);assert.equal(state().handoffRunning,false);assert.equal(state().ambientRunning,true);win.MorphSVGPlugin=plugin;
  await sleep(35);assert.deepEqual(errors,[]);assert.deepEqual(warnings,[]);engine.dispose();assert.equal(gsap.getById('qm-feature-handoff-assets'),undefined);assert.equal(doc.querySelectorAll('[data-qm-feature-inline]').length,0);
  console.log(JSON.stringify({passed:true,report_fold_scenes:Object.fromEntries(Object.entries(summaries).map(([scene,{panels,duration}])=>[scene,{panels,duration}])),real_morphsvg:true,distinct_geometry:true,interrupted_settle:true,remount_context_retained:true,camera_not_replayed:true,no_player_or_input_mutation:true}));
}
run().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{engine.dispose();gsap.ticker.sleep();dom.window.close();});
