'use strict';
// Real pinned GSAP/MorphSVG; geometry and visibility are controlled, not tweens.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));vc.on('warn',e=>errors.push(String(e)));
const dom=new JSDOM('<!doctype html><html><body><main data-testid="stMain"><input value="原生草稿 / 0"><button>真实操作</button><p id="value">真实值 7,771.02 亿元</p></main></body></html>',{runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
const win=dom.window,doc=win.document,main=doc.querySelector('main'),input=doc.querySelector('input'),button=doc.querySelector('button'),queries=new Map(),intersections=[];
win.matchMedia=q=>{if(!queries.has(q))queries.set(q,{matches:false,listeners:new Set(),addEventListener(_,fn){this.listeners.add(fn);},removeEventListener(_,fn){this.listeners.delete(fn);}});return queries.get(q);};
win.IntersectionObserver=class{constructor(fn){this.fn=fn;this.nodes=new Set();intersections.push(this);}observe(node){this.nodes.add(node);}unobserve(node){this.nodes.delete(node);}disconnect(){this.nodes.clear();}};
win.Element.prototype.getBoundingClientRect=()=>({x:312,y:130,left:312,top:130,width:1020,height:430,right:1332,bottom:560});
const matrix=()=>({a:1,b:0,c:0,d:1,e:0,f:0,inverse(){return matrix();},multiply(){return matrix();}});
win.SVGElement.prototype.getBBox=()=>({x:0,y:0,width:160,height:160});win.SVGElement.prototype.getCTM=matrix;win.SVGElement.prototype.getScreenCTM=matrix;win.SVGSVGElement.prototype.createSVGMatrix=matrix;
Object.defineProperty(win.SVGElement.prototype,'transform',{get(){return{baseVal:{numberOfItems:0,consolidate(){return{matrix:matrix()};}}};}});
for(const name of ['vendor/gsap/gsap.min.js','vendor/gsap/MorphSVGPlugin.min.js','feature_theater.js'])win.eval(read(name));
const api=win.QMFeatureTheater,gsap=win.gsap;
function render(scene){const spread=doc.createElement('section');spread.dataset.featureSpread=scene;spread.innerHTML='<div data-feature-field><i></i><i></i><i></i></div><header><div data-feature-title-mask><h2>真实功能标题</h2></div><span data-feature-work-context>当前企业 · 2025</span><a data-feature-work-link href="#real">开始实际操作</a></header><div data-feature-type>EDITION</div><div data-feature-inline="'+scene+'" data-feature-scene="'+scene+'"></div>';main.prepend(spread);const host=spread.querySelector('[data-feature-inline]');api.syncInline([host],{hold:true});return{spread,host};}
function assertNative(){assert.equal(input.value,'原生草稿 / 0');assert.equal(doc.activeElement,input);assert.equal(doc.querySelector('#value').textContent,'真实值 7,771.02 亿元');for(const node of [input,button,doc.querySelector('#value')]){assert.equal(node.getAttribute('style'),null);assert.equal(gsap.getTweensOf(node).length,0);}}
const selection={qa:{v:1,category:'source',source:2},scope:{v:1,dimension:'period'},counter:{v:1,category:'source',source:1},replay:{v:1,category:'source'},assets:{v:1,type:'pdf'}};
const finalAttr=node=>node.tagName.toLowerCase()==='circle'?['r'].map(n=>node.getAttribute(n)):['x','y','width','height'].map(n=>node.getAttribute(n));
try{
  input.focus();let clicks=0;button.addEventListener('click',()=>clicks++);
  const directions=[];
  for(const scene of Object.keys(selection)){
    api.setRoute(scene);let {spread,host}=render(scene);
    const entrance=gsap.getById('qm-feature-entrance-'+scene),aperture=host.querySelector('[data-ft-aperture]');
    assert.ok(entrance&&aperture,scene+': original entrance owns a real SVG aperture');
    entrance.time(0,true);const initial=finalAttr(aperture);entrance.time(.8,true);const mid=finalAttr(aperture);
    assert.notDeepEqual(mid,initial,scene+': GSAP changes the geometric aperture between authored states');
    entrance.progress(1,true);const complete=finalAttr(aperture);assert.notDeepEqual(mid,complete);
    if(scene==='counter')assert.deepEqual(complete,['900']);else assert.deepEqual(complete,['-75','-130','1250','720']);
    directions.push(initial.join(','));
    assert.equal(spread.querySelector('header').style.transform,'');assert.equal(spread.style.transform,'');
    assert.equal(host.querySelector('button,input,output,[role="slider"],progress'),null);
    api.releaseInline(host,{settle:true});api.setContext(scene,selection[scene]);
    const revision=api.getInlineState()[0].contextRevision;assert.ok(revision>0);
    const state=api.getInlineState()[0];assert.equal(state.progress,1);assert.equal(state.arrived,true);
    const ambient=gsap.getById('qm-feature-ambient-'+scene);ambient.pause().time(4.5,true);
    const time=api.getInlineState()[0].ambientTime;
    assertNative();spread.remove();({spread,host}=render(scene));
    assert.equal(api.getInlineState()[0].progress,1,'Same-route native remount cannot replay title or aperture.');
    assert.equal(api.getInlineState()[0].ambientTime,time);assert.equal(api.getInlineState()[0].contextRevision,revision);
    assert.deepEqual(finalAttr(host.querySelector('[data-ft-aperture]')),complete);
    // A route-paper arrival retains the original fold and resolves its new
    // aperture before performing handoff; a mask must never clip the fold.
    api.setRoute(scene+'-arrived');spread.remove();({spread,host}=render(scene));
    host.dataset.qmRouteArrival='report';api.releaseInline(host);const handoff=gsap.getById('qm-feature-handoff-'+scene);
    assert.ok(handoff);assert.deepEqual(finalAttr(host.querySelector('[data-ft-aperture]')),complete);
    handoff.progress(1);assert.equal(api.getInlineState()[0].handoffProgress,1);
    doc.documentElement.dataset.qmMotionMode='research';win.dispatchEvent(new win.Event('qm-motion-preference-change'));
    assert.equal(api.getInlineState()[0].ambientRunning,false);assert.deepEqual(finalAttr(host.querySelector('[data-ft-aperture]')),complete);assertNative();
    delete doc.documentElement.dataset.qmMotionMode;win.dispatchEvent(new win.Event('qm-motion-preference-change'));
    for(const io of intersections)if(io.nodes.has(host.firstElementChild))io.fn([{target:host.firstElementChild,isIntersecting:false}]);
    assert.equal(api.getInlineState()[0].ambientRunning,false);
    api.setRoute('end-'+scene);spread.remove();assert.equal(api.getInlineState().length,0);
  }
  assert.equal(new Set(directions).size,5,'All five editions open in different authored directions.');
  button.click();assert.equal(clicks,1);api.dispose();assert.ok(intersections.every(io=>io.nodes.size===0));
  assert.equal(gsap.globalTimeline.getChildren(true,true,true).filter(t=>String(t.vars.id||'').startsWith('qm-feature-')).length,0);
  assert.deepEqual(errors,[]);console.log('feature editions v22: five real GSAP apertures, existing artwork/context/handoff, remount continuity, quiet/offscreen, native stability and disposal passed');
}catch(error){console.error(error);process.exitCode=1;}finally{api.dispose();gsap.ticker.sleep();win.close();}
