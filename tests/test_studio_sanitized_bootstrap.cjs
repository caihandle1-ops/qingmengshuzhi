'use strict';
// Called by test_gsap_assets.py with real Python-rendered HTML. jsdom is a
// diagnostics-only dependency supplied through NODE_PATH, never a runtime one.
// This validates DOM/script integration, not browser visuals or performance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM, VirtualConsole} = require('jsdom');
assert.ok(process.argv[2], 'Run through test_gsap_assets.py to generate production fixtures.');
const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const errors = [], warnings = [], virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', error => errors.push(error.stack || String(error)));
virtualConsole.on('warn', (...items) => warnings.push(items.map(String).join(' ')));
const dom = new JSDOM('<!doctype html><html><head></head><body><main data-testid="stMain"></main><div id="bootstrap"></div></body></html>', {
  url:'http://127.0.0.1:8504/', runScripts:'dangerously', pretendToBeVisual:true, virtualConsole,
});
const win = dom.window, doc = win.document;
const mediaQueries=new Map();
win.matchMedia = query => {
  if(!mediaQueries.has(query)) {
    const listeners=new Set();
    mediaQueries.set(query,{matches:false,media:query,listeners,
      addEventListener(type,listener){if(type==='change')listeners.add(listener);},
      removeEventListener(type,listener){if(type==='change')listeners.delete(listener);},
      addListener(listener){listeners.add(listener);},removeListener(listener){listeners.delete(listener);}});
  }
  return mediaQueries.get(query);
};
const intersections = [];
win.IntersectionObserver = class {
  constructor(callback){this.callback=callback;this.targets=new Set();intersections.push(this);}
  observe(target){this.targets.add(target);} unobserve(target){this.targets.delete(target);} disconnect(){this.targets.clear();}
};
win.ResizeObserver = class {observe(){} unobserve(){} disconnect(){}};
// ScrollTrigger remains the shipped GSAP plugin. JSDOM lacks document layout,
// so supply measurable viewport/scroll geometry rather than mocking the plugin.
const mainScroller=doc.querySelector('main');
mainScroller.style.cssText='overflow-y:auto;height:900px;position:relative';
Object.defineProperty(win,'innerHeight',{configurable:true,value:900});
for(const element of [doc.documentElement,doc.body,mainScroller]) {
  Object.defineProperty(element,'clientHeight',{configurable:true,value:900});
  Object.defineProperty(element,'scrollHeight',{configurable:true,value:2400});
  Object.defineProperty(element,'clientWidth',{configurable:true,value:1280});
}
win.scrollTo=(x,y)=>{
  const top=typeof x==='object'?Number(x.top)||0:Number(y)||0;
  doc.documentElement.scrollTop=top;doc.body.scrollTop=top;
  Object.defineProperty(win,'pageYOffset',{configurable:true,value:top});
  Object.defineProperty(win,'scrollY',{configurable:true,value:top});
};
win.Element.prototype.getBoundingClientRect = function(){
  if(this===mainScroller||this===doc.documentElement||this===doc.body)
    return {x:0,y:0,left:0,top:0,right:1280,bottom:900,width:1280,height:900};
  const top=160-mainScroller.scrollTop;
  return {x:0,y:top,left:0,top,right:1080,bottom:top+470,width:1080,height:470};
};
// JSDOM has no SVG layout or browser top layer. Supply only deterministic
// geometry/dialog primitives; real GSAP plugins, DOM mutation and all of the
// production controls still execute. These checks are not pixel acceptance.
const identityMatrix = () => ({a:1,b:0,c:0,d:1,e:0,f:0,
  inverse(){return identityMatrix();}, multiply(){return identityMatrix();}});
win.SVGElement.prototype.getBBox = function(){
  return {x:Number(this.getAttribute('x'))||0,y:Number(this.getAttribute('y'))||0,
    width:Number(this.getAttribute('width'))||160,height:Number(this.getAttribute('height'))||160};
};
win.SVGElement.prototype.getCTM = identityMatrix;
win.SVGElement.prototype.getScreenCTM = identityMatrix;
win.SVGSVGElement.prototype.createSVGMatrix = identityMatrix;
win.SVGSVGElement.prototype.createSVGPoint = () => ({x:0,y:0,matrixTransform(){return {x:this.x,y:this.y};}});
Object.defineProperty(win.SVGElement.prototype, 'transform', {configurable:true,
  get(){return {baseVal:{numberOfItems:0,consolidate(){return {matrix:identityMatrix()};}}};}});
win.HTMLDialogElement.prototype.showModal = function(){this.open=true;};
win.HTMLDialogElement.prototype.close = function(){
  if(!this.open)return;this.open=false;this.dispatchEvent(new win.Event('close'));
};

// Execute the exact bundled sanitizer as a scoped script; only the ESM export
// is adapted. No substitute DOMPurify package or relaxed security flag is used.
const purifierSource = fs.readFileSync(fixture.purifier, 'utf8');
const exported = /export\s*\{\s*([\w$]+)\s+as\s+t\s*\};?\s*$/;
assert.match(purifierSource, exported, 'Streamlit purifier export shape changed.');
win.eval('(function(){' + purifierSource.replace(exported, 'window.__testPurifier = $1;') + '\n})();');
const purifier = win.__testPurifier;
assert.equal(typeof purifier.sanitize, 'function');
const frontend = fs.readFileSync(fixture.frontend, 'utf8');
assert.match(frontend, /USE_PROFILES:\{html:!0\},FORCE_BODY:!0/);
assert.match(frontend, /ADD_TAGS:\[`script`,`style`\]/);
assert.match(frontend, /ADD_ATTR:\[`src`,`type`,`async`,`defer`,`nonce`,`crossorigin`,`referrerpolicy`,`integrity`\]/);
const plainConfig = {USE_PROFILES:{html:true}, FORCE_BODY:true};
const scriptConfig = {...plainConfig, ADD_TAGS:['script','style'],
  ADD_ATTR:['src','type','async','defer','nonce','crossorigin','referrerpolicy','integrity']};
const raw = doc.createElement('div');
raw.innerHTML = purifier.sanitize('<script>' + fixture.vendor + '</script>', scriptConfig);
assert.equal(raw.querySelectorAll('script').length, 0,
  'Control must reproduce Streamlit removing the raw minified vendor payload.');

function injectBootstrap(){
  const host = doc.getElementById('bootstrap');
  // Follow Streamlit Html exactly: innerHTML, then recreate script elements so
  // their textContent executes synchronously in the current document.
  host.innerHTML = purifier.sanitize('<script>' + fixture.bootstrap + '</script>', scriptConfig);
  const scripts = [...host.querySelectorAll('script')];
  assert.equal(scripts.length, 1, 'Production bootstrap must survive the real sanitizer.');
  assert.equal(scripts[0].textContent, fixture.bootstrap, 'Sanitization must preserve the complete script.');
  for (const previous of scripts) {
    const script = doc.createElement('script');
    for (const {name,value} of [...previous.attributes]) script.setAttribute(name,value);
    if (!previous.src) script.textContent = previous.textContent;
    previous.parentNode.replaceChild(script, previous);
  }
  assert.equal(win.gsap?.version, '3.15.0', 'The pinned engine actually executes.');
  assert.ok(win.__qmStudioMotion, 'The complete studio bootstrap actually executes.');
  assert.equal(win.MorphSVGPlugin?.version, '3.15.0', 'MorphSVG survives the exact sanitizer transport.');
  assert.equal(win.MotionPathPlugin?.version, '3.15.0', 'MotionPath survives the exact sanitizer transport.');
  assert.equal(win.ScrollTrigger?.version, '3.15.0', 'ScrollTrigger survives the exact sanitizer transport.');
  assert.ok(win.QMFeatureTheater, 'The theater is initialized in the real main-page bootstrap.');
  assert.deepEqual(errors, [], 'No swallowed script or DOM errors.');
}
const businessStates=new Map();
const emptyBusinessState=()=>({v:1,company:null,dimension:null,source:null,category:null,asset:null,type:null});
function contextMarker(scene,state){
  const holder=doc.createElement('div'),marker=doc.createElement('span');
  marker.hidden=true;marker.setAttribute('aria-hidden','true');
  marker.setAttribute('data-feature-context',scene.name);
  marker.setAttribute('data-feature-state',JSON.stringify(state));
  // Hidden native-selection metadata travels through the same HTML-only
  // sanitizer as the Python-rendered view, never through an executable script.
  holder.innerHTML=purifier.sanitize(marker.outerHTML,plainConfig);
  const safe=holder.firstElementChild;
  assert.equal(safe.getAttribute('data-feature-state'),JSON.stringify(state));
  return safe;
}
function mountScene(scene){
  const main = doc.querySelector('main');
  const header = doc.createElement('div');
  header.setAttribute('data-studio-location', scene.title);
  header.setAttribute('data-studio-scene', scene.route);
  header.setAttribute('data-studio-view-required', 'true');
  const intro = doc.createElement('section');
  intro.className = 'st-key-guided_intro_' + scene.name;
  intro.innerHTML = purifier.sanitize(scene.html, plainConfig);
  const marker = doc.createElement('span');
  marker.hidden = true;
  marker.setAttribute('data-studio-view', scene.title);
  marker.setAttribute('data-studio-view-scene', scene.route);
  const workflow=doc.createElement('section');
  workflow.setAttribute('aria-label','真实研究操作区');
  const input=doc.createElement('textarea');
  input.setAttribute('data-regression-business-input','');
  input.setAttribute('aria-label','研究问题');
  input.value='0 / -123.45 / 保留用户研究问题';
  workflow.append(input);
  const fact=doc.createElement('p');fact.setAttribute('data-regression-frozen-fact','');
  fact.textContent='冻结数值 0 · -123.45 · 缺失数据保持空缺';workflow.append(fact);
  const state=businessStates.get(scene.name)||emptyBusinessState();businessStates.set(scene.name,state);
  main.replaceChildren(header,intro,workflow,contextMarker(scene,state),marker);
  return intro.querySelector('[data-feature-scene]');
}
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
const styles = node => [...node.querySelectorAll('[data-feature-piece]')].map(piece => piece.style.cssText).join('|');
const inlineState = () => win.QMFeatureTheater.getInlineState()[0];
const clocks = () => ({entrance:inlineState().entranceTime,ambient:inlineState().ambientTime});
const compositions={qa:'question-weave',scope:'precision-rails',counter:'evidence-peel',replay:'archive-depth',assets:'spatial-index'};
const sceneTimings=new Map();
const geometry=node=>[node.getAttribute('transform'),node.getAttribute('d'),node.getAttribute('style')].join('|');
const responseGeometry=node=>[...node.querySelectorAll('[data-ft-response]')].map(geometry).join('|');
const businessPatches={
  qa:{company:'0123456789abcdef',category:'source',source:0},
  scope:{dimension:'period',category:'sources',source:0},
  counter:{category:'source',source:0},
  replay:{category:'source'},
  assets:{category:'library',asset:'catalog',type:'pdf'},
};
function updateBusinessContext(scene,patch){
  const state={...businessStates.get(scene.name),...patch};businessStates.set(scene.name,state);
  const previous=mainScroller.querySelector('[data-feature-context]');
  assert.ok(previous,'The native completed page has one business-state marker.');
  previous.replaceWith(contextMarker(scene,state));
  return state;
}
async function checkBusinessContext(node,scene){
  const theater=win.QMFeatureTheater,targets=[...node.querySelectorAll('[data-ft-response]')];
  const input=mainScroller.querySelector('[data-regression-business-input]');
  const fact=mainScroller.querySelector('[data-regression-frozen-fact]');
  const inputValue=input.value,frozenText=fact.textContent,entranceTime=inlineState().entranceTime;
  assert.equal(typeof theater.setContext,'function','Production exposes a read-only visual selection API.');
  assert.ok(targets.length,'Business response owns wrappers separate from entrance, ambient and native controls.');
  assert.equal(inlineState().contextRevision,1,'The first confirmed native state is applied exactly once.');
  assert.equal(inlineState().responseRunning,false,'Initial selection is applied statically behind the entrance.');
  const initial=responseGeometry(node);
  updateBusinessContext(scene,businessPatches[scene.name]);await delay(90);
  assert.equal(inlineState().contextRevision,2,'A native marker update is consumed by the actual studio observer.');
  assert.equal(inlineState().responseRunning,true,'A confirmed changed selection animates its decorative response layer.');
  assert.deepEqual(warnings.filter(message=>/not eligible for reset/.test(message)),[],
    'The pinned GSAP response quickTo/resetTo path must not warn about alias properties.');
  assert.notEqual(responseGeometry(node),initial,scene.name+': confirmed selection changes actual SVG geometry.');
  assert.equal(inlineState().entranceTime,entranceTime,'Business selection never replays the entrance.');
  const activeTweens=win.gsap.getTweensOf(targets,true);
  assert.ok(activeTweens.length,'Real GSAP, not a mocked progress flag, drives the business response.');
  updateBusinessContext(scene,{});await delay(35);
  assert.equal(inlineState().contextRevision,2,'Equal Streamlit rerenders do not increment the context revision.');
  assert.ok(win.gsap.getTweensOf(targets,true).every(tween=>activeTweens.includes(tween)),
    'Repeated state does not create a second set of response tweens.');
  assert.equal(input.value,inputValue);assert.equal(fact.textContent,frozenText);
  assert.equal(win.gsap.getTweensOf([input,fact]).length,0,'Original inputs, zero values and missing-value text never become animation targets.');

  Object.defineProperty(doc,'hidden',{configurable:true,value:true});
  doc.dispatchEvent(new win.Event('visibilitychange'));
  assert.equal(inlineState().responseRunning,false,'Hiding a tab immediately settles an in-flight response.');
  assert.equal(win.gsap.getTweensOf(targets,true).length,0);
  const visiblePose=responseGeometry(node);
  const reset={...emptyBusinessState()};delete reset.v;
  updateBusinessContext(scene,reset);await delay(40);
  assert.equal(inlineState().contextRevision,3);
  assert.notEqual(responseGeometry(node),visiblePose,'A changed hidden selection is applied immediately.');
  assert.equal(inlineState().responseRunning,false);
  Object.defineProperty(doc,'hidden',{configurable:true,value:false});
  doc.dispatchEvent(new win.Event('visibilitychange'));await delay(40);
  assert.equal(inlineState().responseRunning,false,'Returning to the tab never queues an old selection response.');

  doc.documentElement.dataset.qmMotionMode='research';
  win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));
  const quietPose=responseGeometry(node);
  updateBusinessContext(scene,businessPatches[scene.name]);await delay(40);
  assert.equal(inlineState().contextRevision,4);
  assert.notEqual(responseGeometry(node),quietPose,'Reduced-motion users still receive the selected emphasis statically.');
  assert.equal(inlineState().responseRunning,false);
  assert.equal(win.gsap.getTweensOf(node.querySelectorAll('[data-ft-response]'),true).length,0);
  updateBusinessContext(scene,{});await delay(35);
  assert.equal(inlineState().contextRevision,4,'Equal quiet-state rerenders are also a no-op.');
  delete doc.documentElement.dataset.qmMotionMode;
  win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));await delay(45);
  assert.equal(inlineState().contextRevision,4);
  assert.equal(inlineState().responseRunning,false,'Leaving quiet mode does not animate a stale business event.');
  assert.equal(inlineState().entranceTime,entranceTime);
  assert.equal(input.value,inputValue);assert.equal(fact.textContent,frozenText);
  assert.equal(doc.activeElement,nativeInput,'Selection-driven artwork never steals focus.');
}
let covered = null;
// Hold only the route cover's asynchronous completion. The production studio
// owns the real hold/release wiring; real GSAP clocks must wait for this event.
win.__qmRouteStage = {arrive(target,options){covered={target,options};return true;}};
const nativeInput=doc.createElement('input');nativeInput.value='保留业务输入 123.45';
nativeInput.setAttribute('aria-label','业务输入');doc.body.append(nativeInput);
function observeInline(node, visible){
  let notified=0;
  for(const observer of intersections){
    for(const target of observer.targets){
      if(target===node||node.contains(target)){
        observer.callback([{target,isIntersecting:visible,intersectionRatio:visible?1:0}]);notified++;
      }
    }
  }
  assert.ok(notified,'A real production observer owns the scene visibility.');
}
async function releaseCover(scene){
  if(!covered)return;
  const current=covered;covered=null;
  assert.equal(inlineState().held,true,scene.name+': inline entrance waits behind the route cover');
  const held=clocks();
  await delay(65);
  assert.deepEqual(clocks(),held,'Neither entrance nor ambient clocks run behind an opaque transition.');
  current.options.onReveal();
  await delay(35);
  assert.equal(inlineState().held,false,'The actual studio reveal callback releases the stage.');
}
async function checkInline(node,scene){
  const theater=win.QMFeatureTheater;
  assert.ok(node.hasAttribute('data-feature-inline'),scene.name+': inline opt-in survives HTML sanitization');
  assert.equal(node.querySelector('[data-feature-theater-open]'),null,'Viewing the animation requires no opening button.');
  assert.equal(doc.querySelector('[data-qm-feature-theater]'),null,'Page entry creates no modal.');
  assert.equal(node.getAttribute('data-feature-inline-mounted'),'true');
  assert.equal(theater.getInlineState().length,1,'Only the visible native scene is owned.');
  assert.equal(inlineState().scene,scene.name);
  assert.equal(inlineState().static,false,'Production plugin setup must not fallback: '+warnings.join('\n'));
  assert.equal(inlineState().held,false);
  assert.equal(node.querySelector('button,input,output,footer,nav,[role="slider"],[data-ft-scrub],[data-ft-time],[data-ft-pause],[data-ft-replay],[data-ft-chapter],[data-ft-status]'),null,
    'A feature illustration is part of the page, with no player controls or playback status.');
  assert.equal(doc.activeElement,nativeInput,'Autoplay never steals focus from a native control.');
  assert.equal(nativeInput.value,'保留业务输入 123.45');
  const svg=node.querySelector('svg'),witness=node.querySelector('[data-ft-ambient-witness]');
  assert.equal(svg?.namespaceURI,'http://www.w3.org/2000/svg');
  assert.ok(witness,'Trusted runtime constructs authored SVG after the HTML-only sanitizer.');
  assert.equal(svg.getAttribute('data-ft-composition'),compositions[scene.name],
    'Each function owns the distinct composition appropriate to its research action.');
  assert.equal(inlineState().motionProfile,compositions[scene.name]);
  assert.equal(node.querySelector('[data-ft-core],[data-ft-orbit]'),null,
    'Distinct inline compositions do not retain the shared morphing core and orbit motif.');
  assert.doesNotMatch(svg.textContent,/已通过|100%|入库成功|核验成功/,
    'Concept artwork cannot report invented analysis results or processing progress.');
  const heading=doc.querySelector('[data-studio-scene]');
  const headingStyle=heading.getAttribute('style');
  const originalArt=node.querySelector('.feature-scene-art'),originalText=originalArt.textContent;
  const camera=node.querySelector('[data-ft-camera]');
  const clock=inlineState().entranceTime,initialTransform=camera.getAttribute('transform');
  await delay(90);
  assert.ok(inlineState().entranceTime>clock,scene.name+': entering the page starts the real GSAP clock without any click');
  assert.notEqual(camera.getAttribute('transform'),initialTransform,'The live clock changes visible SVG geometry.');
  const entrance=win.gsap.getById('qm-feature-entrance-'+scene.name);
  assert.ok(entrance,'A scene-specific production timeline owns the entrance.');
  entrance.progress(1);
  assert.equal(inlineState().arrived,true,'The entrance hands over to a living ambient illustration.');
  const ambient=win.gsap.getById('qm-feature-ambient-'+scene.name);
  assert.ok(ambient,'A scene-specific production timeline owns the ongoing choreography.');
  assert.equal(ambient.duration(),inlineState().ambientDuration);
  sceneTimings.set(scene.name,ambient.duration());
  ambient.progress(.18);const first=geometry(witness);
  ambient.progress(.63);const later=geometry(witness);
  assert.notEqual(first,later,scene.name+': its authored ambient choreography changes visible SVG geometry.');
  if(scene.name==='counter'){
    const fold=node.querySelector('path[data-ft-fold]');
    assert.ok(fold,'The evidence scene includes an authored paper fold.');
    ambient.time(2.5);const closedFold=fold.getAttribute('d');
    ambient.time(10);const peeledFold=fold.getAttribute('d');
    assert.notEqual(closedFold,peeledFold,'The real MorphSVG plugin reshapes the paper fold as evidence is exposed.');
    const clips=[...svg.querySelectorAll('clipPath[id]')];
    assert.ok(clips.length>=2,'Separate masks expose the source and inspection lens.');
    assert.equal(new Set(clips.map(item=>item.id)).size,clips.length,'SVG masks have unique local identities.');
    for(const clipped of svg.querySelectorAll('[clip-path]')){
      const id=/url\(#([^)]+)\)/.exec(clipped.getAttribute('clip-path'))?.[1];
      assert.ok(id && clips.some(item=>item.id===id),'Each evidence mask resolves inside the current scene.');
    }
  }
  const ambientTime=inlineState().ambientTime;
  await delay(90);
  assert.ok(inlineState().ambientTime>ambientTime,'Finishing the entrance does not leave a static finished player.');
  assert.equal(inlineState().ambientRunning,true);
  assert.equal(ambient.repeat(),-1,'The ambient illustration continues without a replay button.');

  // Attending to real research controls reduces the illustration's tempo while
  // preserving its current phase; it never changes the input or interrupts work.
  const workflowInput=mainScroller.querySelector('[data-regression-business-input]');
  const inputValue=workflowInput.value,attentionTime=inlineState().ambientTime;
  workflowInput.focus();
  await delay(620);
  assert.equal(inlineState().attentive,true,'A focused native work control receives visual priority.');
  assert.ok(inlineState().ambientTimeScale<=.32,'Working attention lowers the ambient tempo.');
  assert.ok(inlineState().ambientTime>attentionTime,'Working attention attenuates rather than freezing the illustration.');
  assert.equal(inlineState().ambientRunning,true);
  assert.equal(workflowInput.value,inputValue);
  assert.equal(win.gsap.getTweensOf(workflowInput).length,0,'Business inputs are never animation targets.');
  const slowedTime=inlineState().ambientTime;
  nativeInput.focus();await delay(620);
  assert.equal(inlineState().attentive,false);
  assert.ok(inlineState().ambientTimeScale>=.96,'Leaving the work control restores the original visual tempo.');
  assert.ok(inlineState().ambientTime>slowedTime,'Attention changes retain the authored phase.');
  assert.equal(heading.getAttribute('style'),headingStyle,'Artwork animation never moves the native page heading.');
  assert.equal(win.gsap.getTweensOf(heading).length,0);
  await checkBusinessContext(node,scene);
  observeInline(node,false);
  const retainedClocks=clocks(),studio=win.__qmStudioMotion;
  injectBootstrap();await delay(35);
  assert.equal(win.QMFeatureTheater,theater,'A rerun retains the inline singleton.');
  assert.equal(win.__qmStudioMotion,studio,'A rerun retains the studio controller.');
  assert.equal(node.querySelector('svg'),svg);
  assert.deepEqual(clocks(),retainedClocks,'A widget rerun does not replay or unpause an offscreen illustration.');
  const offscreen=clocks();await delay(65);
  assert.deepEqual(clocks(),offscreen,'Offscreen scenes stop both animation clocks.');
  observeInline(node,true);await delay(60);
  assert.ok(inlineState().ambientTime>offscreen.ambient,'A visible illustration resumes its prior position.');
  assert.equal(originalArt.textContent,originalText,'The original compact fallback artwork is preserved.');

  const trigger=win.ScrollTrigger.getAll().find(item=>item.trigger && node.contains(item.trigger));
  assert.ok(trigger,scene.name+': the real official ScrollTrigger owns a local scene transform.');
  assert.equal(Boolean(trigger.vars.pin),false,'Normal page scrolling never becomes a pinned presentation.');
  assert.equal(inlineState().scrollActive,true);
  const scrollLayer=node.querySelector('[data-ft-scroll]');
  assert.ok(scrollLayer,'Scroll motion has a transform owner separate from entrance and pointer motion.');
  const scrollBefore=scrollLayer.style.transform;
  mainScroller.scrollTop=330;mainScroller.dispatchEvent(new win.Event('scroll'));
  win.ScrollTrigger.update();await delay(120);
  assert.notEqual(scrollLayer.style.transform,scrollBefore,'Actual scroll position updates the artwork transform.');
  mainScroller.scrollTop=0;win.ScrollTrigger.update();
  const stage=node.querySelector('.ft-stage'),front=node.querySelector('[data-ft-parallax="front"]');
  stage.dispatchEvent(new win.MouseEvent('pointerenter',{clientX:540,clientY:330,bubbles:true}));
  const pointerBefore=front.getAttribute('transform');
  stage.dispatchEvent(new win.MouseEvent('pointermove',{clientX:970,clientY:450,bubbles:true}));
  await delay(90);
  assert.notEqual(front.getAttribute('transform'),pointerBefore,'Pointer movement adds live parallax without a play control.');
  assert.equal(doc.activeElement,nativeInput);
  assert.equal(workflowInput.value,inputValue);
  assert.equal(heading.getAttribute('style'),headingStyle);

  // Simulate Streamlit replacing an equal-route HTML element. This is distinct
  // from a new route; the ambient position must transfer instead of restarting.
  observeInline(node,false);const remountTime=inlineState().ambientTime;
  const remountContext=inlineState().contextRevision,remountPose=responseGeometry(node);
  const oldTargets=[...svg.querySelectorAll('*')],next=mountScene(scene);
  injectBootstrap();await delay(90);
  assert.equal(covered,null,'A same-route remount cannot begin another route entrance.');
  assert.equal(inlineState().scene,scene.name);
  assert.equal(inlineState().arrived,true,'Same-route replacement never repeats the large entrance.');
  assert.equal(inlineState().contextRevision,remountContext,'Same-route replacement retains its confirmed business revision.');
  assert.equal(responseGeometry(next),remountPose,'Same-route replacement restores the confirmed decorative pose.');
  assert.equal(inlineState().responseRunning,false,'Same-route remount cannot replay a settled business interaction.');
  assert.ok(inlineState().ambientTime>=remountTime && inlineState().ambientTime<remountTime+.6,
    'Same-route replacement retains the ambient position.');
  assert.equal(win.gsap.getTweensOf(oldTargets).length,0,'Detached SVG nodes retain no tweens.');
  assert.equal(doc.querySelectorAll('svg.ft-svg').length,1,'A remount leaves exactly one visual owner.');
  assert.equal(next.querySelector('.feature-scene-art').textContent,originalText);
  assert.equal(win.ScrollTrigger.getAll().filter(item=>item.trigger && next.contains(item.trigger)).length,1,'A remount retains one scroll controller.');
  assert.equal(win.ScrollTrigger.getAll().includes(trigger),false,'The detached scene scroll controller is killed.');
}
async function run(){
  let engine,index=0;
  for(const scene of fixture.scenes){
    nativeInput.focus();
    const node=mountScene(scene);
    assert.equal(node.querySelectorAll('svg').length,0,'SVG is not transported through unsafe HTML.');
    injectBootstrap();engine||=win.gsap;
    assert.equal(win.gsap,engine,'All routes retain one GSAP engine.');
    await delay(70);
    if(index++)assert.ok(covered,'A genuine route change passes through the cover handoff.');
    await releaseCover(scene);
    await checkInline(node,scene);
    const active={value:0},tween=engine.to(active,{value:100,duration:3,paused:true});
    tween.totalTime(.7);const value=active.value;
    injectBootstrap();
    assert.equal(engine.getTweensOf(active)[0],tween,'A native rerun cannot replace the engine or orphan unrelated live tweens.');
    assert.equal(active.value,value);tween.totalTime(1.2);assert.ok(active.value>value);tween.kill();
  }
  assert.equal(new Set(sceneTimings.values()).size,fixture.scenes.length,
    'All five compositions use distinct rhythms instead of one shared ambient loop.');
  let scene={...fixture.scenes.at(-1),route:'interrupted-cover-route'};
  let node=mountScene(scene);injectBootstrap();await delay(70);
  assert.ok(covered,'The interrupted route has a genuine held reveal request.');
  const interrupted=covered;covered=null;
  assert.equal(inlineState().held,true);
  // A tab can disappear while the opaque route transition is still running.
  // Studio settles that pending entrance; automatic ambient must resume when
  // the tab returns because the page intentionally has no replay control.
  Object.defineProperty(doc,'hidden',{configurable:true,value:true});
  doc.dispatchEvent(new win.Event('visibilitychange'));
  assert.equal(inlineState().held,false);
  assert.equal(inlineState().arrived,true);
  const interruptedClocks=clocks();await delay(55);assert.deepEqual(clocks(),interruptedClocks);
  Object.defineProperty(doc,'hidden',{configurable:true,value:false});
  doc.dispatchEvent(new win.Event('visibilitychange'));await delay(60);
  assert.equal(inlineState().ambientRunning,true,'Returning after a cancelled route cover must never leave a permanently frozen scene.');
  assert.ok(inlineState().ambientTime>interruptedClocks.ambient);
  interrupted.options.onCancel();
  assert.equal(inlineState().ambientRunning,true,'A stale cover callback cannot stop the already visible illustration.');
  // Background tabs pause both layers, then resume the retained ambient phase.
  await delay(45);
  Object.defineProperty(doc,'hidden',{configurable:true,value:true});
  doc.dispatchEvent(new win.Event('visibilitychange'));
  const hiddenTime=clocks();await delay(65);assert.deepEqual(clocks(),hiddenTime);
  Object.defineProperty(doc,'hidden',{configurable:true,value:false});
  doc.dispatchEvent(new win.Event('visibilitychange'));await delay(60);
  assert.ok(inlineState().ambientTime>hiddenTime.ambient);
  doc.documentElement.dataset.qmMotionMode='research';
  win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));
  assert.equal(inlineState().static,true);
  assert.equal(inlineState().ambientRunning,false);
  const quietTime=clocks();await delay(55);assert.deepEqual(clocks(),quietTime);
  assert.ok(node.querySelector('[data-ft-composition="'+compositions[scene.name]+'"] [data-ft-ambient-witness]'),
    'Quiet mode retains the complete authored composition.');
  assert.equal(node.querySelector('button,input,output,[role="slider"]'),null,'Quiet mode does not introduce player controls.');
  delete doc.documentElement.dataset.qmMotionMode;
  win.dispatchEvent(new win.CustomEvent('qm-motion-preference-change'));
  assert.equal(inlineState().static,false);
  assert.equal(inlineState().entranceTime,quietTime.entrance,'Changing mode does not unexpectedly replay the entrance.');
  await delay(60);
  assert.ok(inlineState().ambientTime>quietTime.ambient,'Leaving quiet mode restores the ambient illustration automatically.');
  const reduced=win.matchMedia('(prefers-reduced-motion: reduce)');
  reduced.matches=true;
  for(const listener of reduced.listeners)listener({matches:true,media:reduced.media});
  assert.equal(inlineState().static,true,'The operating-system motion preference also settles the scene.');
  const reducedTime=clocks();await delay(55);assert.deepEqual(clocks(),reducedTime);
  assert.equal(inlineState().scrollActive,false,'Reduced motion disables scroll response as well as the ambient loop.');
  reduced.matches=false;
  for(const listener of reduced.listeners)listener({matches:false,media:reduced.media});
  await delay(60);
  assert.equal(inlineState().static,false);
  assert.equal(inlineState().arrived,true,'Changing OS preference does not trigger another large entrance.');
  assert.equal(inlineState().ambientRunning,true);

  // A report that has already travelled into its destination completes the
  // visual entrance. The destination must not immediately fly away again.
  const reportScene={...fixture.scenes[0],route:'report-arrival-handoff'};
  node=mountScene(reportScene);injectBootstrap();await delay(70);
  assert.ok(covered,'The report arrival has a real held route handoff.');
  assert.equal(inlineState().held,true);
  node.dataset.qmRouteArrival='report';
  const reportCover=covered;covered=null;reportCover.options.onReveal();await delay(40);
  assert.equal(node.hasAttribute('data-qm-route-arrival'),false,'Report arrival is consumed once.');
  assert.equal(inlineState().held,false);
  assert.equal(inlineState().progress,1,'The report handoff settles the entrance rather than replaying it.');
  assert.equal(inlineState().arrived,true);
  assert.equal(inlineState().handoffRunning,true,'The landed report folds into the actual scene before the ambient sequence.');
  assert.equal(inlineState().ambientRunning,false,'The fold temporarily owns visible choreography.');
  const reportFold=win.gsap.getById('qm-feature-handoff-'+reportScene.name);
  assert.ok(reportFold,'The real production bootstrap constructs a report-fold timeline.');
  const reportFoldPanel=node.querySelector('[data-ft-fold-panel]'),reportFoldStart=reportFoldPanel.getAttribute('d');
  reportFold.time(.6);assert.notEqual(reportFoldPanel.getAttribute('d'),reportFoldStart,'The actual MorphSVG plugin changes the shared paper contour.');
  reportFold.progress(1);
  assert.equal(inlineState().handoffRunning,false);
  assert.equal(inlineState().ambientRunning,true,'The completed fold becomes a living inline illustration.');
  const reportCamera=node.querySelector('[data-ft-camera]'),reportCameraPose=geometry(reportCamera);
  const reportAmbient=inlineState().ambientTime;
  await delay(90);
  assert.equal(geometry(reportCamera),reportCameraPose,'The entrance camera remains settled after the report lands.');
  assert.equal(win.gsap.getTweensOf(reportCamera,true).length,0);
  assert.ok(inlineState().ambientTime>reportAmbient,'Only the intended ambient sequence continues after landing.');

  // If enhanced mounting is unavailable, legacy compact scenes still run.
  const fallback={...fixture.scenes[0],route:'fallback-route',
    html:fixture.scenes[0].html.replace(/\sdata-feature-inline="[^"]*"/g,'')};
  node=mountScene(fallback);injectBootstrap();await delay(70);
  if(covered){const request=covered;covered=null;request.options.onReveal();}
  await delay(70);
  assert.equal(win.QMFeatureTheater.getInlineState().length,0);
  const fallbackState=win.__qmStudioMotion.getFeatureState()[0];
  assert.equal(fallbackState.engine,'gsap');
  assert.ok(fallbackState.running>0,'The original compact animation remains a working fallback.');
  const before=styles(node);await delay(70);assert.notEqual(styles(node),before);
  assert.equal(node.querySelector('button,input,output,[role="slider"]'),null,'The compact fallback also remains part of the page, without a player.');
  assert.equal(win.ScrollTrigger.getAll().length,0,'Leaving enhanced scenes removes all scene ScrollTriggers.');
  assert.equal(nativeInput.value,'保留业务输入 123.45');
  assert.equal(win.gsap.getTweensOf(nativeInput).length,0,'Financial input controls never become animation targets.');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,scenes:fixture.scenes.map(item=>item.name),
    reproduced_raw_script_removal:true,production_script_survives:true,
    inline_autoplay_without_player_chrome:true,continuous_ambient_after_entrance:true,
    route_cover_handoff:true,distinct_scene_compositions_and_geometry:true,distinct_ambient_rhythms:Object.fromEntries(sceneTimings),
    actual_scrolltrigger_without_pinning:true,pointer_parallax:true,working_attention_attenuates_and_resumes:true,
    same_route_rerun_and_remount_preserve_phase:true,offscreen_and_hidden_pause:true,
    native_confirmed_context_drives_decorative_transforms:true,initial_and_repeated_context_do_not_replay:true,
    context_remount_and_quiet_hidden_settle:true,financial_zero_missing_and_inputs_preserved:true,
    report_handoff_consumed_without_second_entrance:true,landed_report_morphs_into_scene:true,
    quiet_mode_and_original_fallback:true,no_focus_or_business_input_change:true}));
}
run().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{
  win.QMFeatureTheater?.dispose();win.__qmStudioMotion?.dispose();win.gsap?.ticker.sleep();dom.window.close();
});
