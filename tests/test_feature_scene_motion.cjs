'use strict';
// Exercise production choreography with the actual vendored GSAP engine.
// The deterministic DOM adapters verify lifecycle logic, not pixels or FPS.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/feature_scene_motion.js'),'utf8');
const {gsap}=require('../app/vendor/gsap/gsap.min.js');
assert.equal(gsap.version,'3.15.0','exercise the exact vendored engine, not a GSAP imitation');
const timelines=[];
const originalTimeline=gsap.timeline;
gsap.timeline=function(options){const timeline=originalTimeline.call(gsap,options);timelines.push(timeline);return timeline;};
const animations=[];
class Animation {
  constructor(frames,options) {this.frames=frames;this.options=options;this.playState='running';this.currentTime=0;this.cancelled=false;this.finished=new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;});}
  pause(){this.playState='paused';}
  play(){this.playState='running';}
  cancel(){this.cancelled=true;this.playState='idle';this.reject(new Error('cancelled'));}
  finish(){this.playState='finished';this.resolve();}
}
function styleAdapter(initial={}){
  const values={...initial},writes=[];
  const camel=key=>key.replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase());
  const methods={getPropertyValue:key=>values[camel(key)]||'',getPropertyPriority:()=>'',
    setProperty(key,value){writes.push(camel(key));values[camel(key)]=String(value);},
    removeProperty(key){writes.push(camel(key));const previous=values[camel(key)]||'';delete values[camel(key)];return previous;}};
  const style=new Proxy(methods,{get(target,key){return key in target?target[key]:values[key]||'';},set(target,key,value){writes.push(key);values[key]=String(value);return true;}});
  return {style,writes,values};
}
class Piece {
  constructor(kind,ambient=false){this.kind=kind;this.ambient=ambient;this.inline=styleAdapter({transform:'rotate(7deg)',color:'#123456'});this.style=this.inline.style;}
  getAttribute(key){return key===(this.ambient?'data-feature-ambient':'data-feature-piece')?this.kind:null;}
  animate(frames,options){const animation=new Animation(frames,options);animations.push(animation);return animation;}
}
class ReplayControl {
  constructor(scene){this.scene=scene;this.attrs={'data-feature-replay':''};this.disabled=false;this.listeners=new Map();this.textContent='重播动效';this.title='';}
  getAttribute(key){return this.attrs[key]??null;}
  setAttribute(key,value){this.attrs[key]=String(value);}
  removeAttribute(key){delete this.attrs[key];}
  addEventListener(type,listener){if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(listener);}
  removeEventListener(type,listener){this.listeners.get(type)?.delete(listener);}
  closest(selector){return selector==='[data-feature-replay]'?this:selector==='[data-feature-scene]'?this.scene:null;}
  contains(node){return node===this;}
  click(){
    if(this.disabled)return;
    const event={type:'click',target:this,stopped:false,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;}};
    for(const listener of [...this.listeners.get('click')||[]])listener(event);
    if(!event.stopped)this.scene.dispatch(event);
  }
}
const sceneMarkup=fs.readFileSync(path.join(__dirname,'../app/feature_scenes.py'),'utf8');
const pieces={},loops={};
for(const scene of ['qa','scope','counter','replay','assets']){
  const markup=sceneMarkup.match(new RegExp("'"+scene+"': '''([\\s\\S]*?)'''"))[1];
  pieces[scene]=Array.from(markup.matchAll(/data-feature-piece="([^"]+)"/g),match=>match[1]);
  loops[scene]=Array.from(markup.matchAll(/data-feature-ambient="([^"]+)"/g),match=>match[1]);
  assert.ok(pieces[scene].length&&loops[scene].length,`${scene}: exercise every marker in the actual production concept markup`);
}
class Scene {
  constructor(name){this.name=name;this.attrs={'data-feature-scene':name};this.isConnected=true;this.pieces=pieces[name].map(kind=>new Piece(kind));this.loops=loops[name].map(kind=>new Piece(kind,true));this.curtain=new Piece('curtain');this.nativeControls=[new Piece('button'),new Piece('input'),new Piece('summary')];this.replayControl=new ReplayControl(this);this.status={textContent:''};this.listeners=new Map();this.inline=styleAdapter();this.style=this.inline.style;this.dataset={};this.rect={left:0,top:80,right:520,bottom:344,width:520,height:264};}
  getAttribute(key){return this.attrs[key]??null;}
  setAttribute(key,value){this.attrs[key]=String(value);}
  removeAttribute(key){delete this.attrs[key];}
  getBoundingClientRect(){return {...this.rect};}
  querySelectorAll(key){return key==='[data-feature-piece]'?this.pieces:key==='[data-feature-ambient]'?this.loops:key==='[data-feature-curtain]'?[this.curtain]:key==='[data-feature-replay]'?[this.replayControl]:[];}
  querySelector(key){return key==='[data-feature-curtain]'?this.curtain:key==='[data-feature-replay]'?this.replayControl:key==='[data-feature-status]'?this.status:null;}
  addEventListener(type,listener){if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(listener);}
  removeEventListener(type,listener){this.listeners.get(type)?.delete(listener);}
  contains(node){return node===this||node===this.replayControl||[...this.pieces,...this.loops,...this.nativeControls].includes(node);}
  dispatch(event){for(const listener of [...this.listeners.get(event.type)||[]])listener(event);}
}
const observers=[];
class Observer {
  constructor(callback){this.callback=callback;this.nodes=new Set();this.disconnected=false;observers.push(this);}
  observe(node){this.nodes.add(node);}
  unobserve(node){this.nodes.delete(node);}
  disconnect(){this.nodes.clear();this.disconnected=true;}
  visible(node,value){this.callback([{target:node,isIntersecting:value}]);}
}
const context={IntersectionObserver:Observer,gsap};vm.createContext(context);vm.runInContext(source,context);
let research=false,reduced=false;
const document={hidden:false,defaultView:{innerHeight:900}};
const controller=context.QMFeatureSceneMotion.create({document,quiet:()=>research||reduced});
const observer=observers[0];
async function run(){
  const unrelatedTarget={value:0};
  const unrelated=gsap.to(unrelatedTarget,{value:100,duration:100,paused:true});
  const nativeStyleProperties=new Set(['translate','rotate','scale','opacity','visibility','willChange']);
  const ambientTimeline=list=>list.find(timeline=>timeline.repeat()===-1);
  const entranceTimeline=list=>list.find(timeline=>timeline.repeat()!==-1);
  function assertScopedStyles(node){
    for(const piece of [...node.pieces,...node.loops,node.curtain]){
      assert.equal(piece.style.transform,'rotate(7deg)','static CSS/base transform is preserved');
      assert.ok(piece.inline.writes.every(key=>nativeStyleProperties.has(key)),`only compositor style properties are owned: ${piece.inline.writes}`);
    }
    assert.ok(node.nativeControls.every(control=>control.inline.writes.length===0),'buttons, input and summary hit targets are never animated');
    assert.equal(node.rect.height,264,'animation never changes layout geometry');
  }
  function assertRestored(node){
    assertScopedStyles(node);
    for(const piece of [...node.pieces,...node.loops,node.curtain])for(const property of nativeStyleProperties)assert.equal(piece.style[property],'',`${property} is restored after disposal`);
    assert.equal(node.getAttribute('data-feature-motion'),null,'disposing releases the CSS transition ownership marker');
  }
  for(const sceneName of Object.keys(pieces)){
    const node=new Scene(sceneName),start=timelines.length;
    controller.setRoute(sceneName);controller.enter(node);controller.sync([node]);
    gsap.ticker.sleep();
    const entered=timelines.slice(start),entry=entranceTimeline(entered),loop=ambientTimeline(entered);
    assert.equal(entered.length,2,`${sceneName}: exactly one coordinated entrance and one ambient owner`);
    assert.ok(entered.every(timeline=>timeline instanceof gsap.core.Timeline),'production uses real GSAP timeline objects');
    assert.equal(controller.getState()[0].engine,'gsap');
    assert.equal(node.getAttribute('data-feature-motion'),'gsap','live GSAP ownership disables competing CSS transition easing');
    assert.equal(controller.getState()[0].phase,'entering');
    assert.ok(entry.duration()>=1,'entrance has a staged duration');
    assert.ok(Object.keys(entry.labels).length>=3,'entrance has explicit choreography labels');
    for(let rerun=0;rerun<12;rerun++){controller.setRoute(sceneName);controller.sync([node]);controller.enter(node);}
    assert.equal(timelines.length,start+entered.length,'same scene and repeated arrival cannot replay');
    entry.totalTime(.73,true);loop.totalTime(.73,true);assertScopedStyles(node);
    assert.ok([...node.pieces,...node.loops].some(piece=>piece.style.translate!==''||piece.style.opacity!==''),'real engine interpolation writes visible motion styles');
    observer.visible(node,false);
    assert.equal(controller.getState()[0].running,0);assert.equal(controller.getState()[0].phase,'paused');
    observer.visible(node,true);
    assert.ok(entered.every(timeline=>timeline.totalTime()===.73&&!timeline.paused()),'offscreen resume preserves exact GSAP seconds');
    document.hidden=true;controller.refresh();assert.equal(controller.getState()[0].running,0);
    document.hidden=false;controller.refresh();assert.ok(entered.every(timeline=>timeline.totalTime()===.73));
    research=true;controller.refresh();
    assert.equal(controller.getState()[0].phase,'static');assert.equal(controller.getState()[0].running,0);
    assert.equal(loop.totalTime(),.73,'explicit research keeps paused ambient time');
    assert.equal(loop.paused(),true);
    assert.equal(entry.parent,null,'interrupting entrance removes its timeline');
    for(const piece of [...node.pieces,...node.loops])for(const property of ['translate','rotate','scale','opacity'])assert.equal(piece.style[property],'','research restores the complete static artwork while retaining internal phase');
    research=false;controller.refresh();
    assert.equal(loop.paused(),false);assert.equal(loop.totalTime(),.73);
    assert.equal(timelines.length,start+entered.length,'changing mode does not recreate or replay the timeline');
    reduced=true;controller.refresh();assert.equal(controller.getState()[0].running,0,'OS reduced overrides presentation');
    reduced=false;controller.refresh();
    node.isConnected=false;const remount=new Scene(sceneName),beforeRemount=timelines.length;controller.sync([remount]);
    assert.ok(entered.every(timeline=>timeline.parent===null));assert.equal(observer.nodes.size,1);assertRestored(node);
    assert.equal(timelines.length-beforeRemount,1,'native same-page remount gets ambient only, no entrance bounce');
    const remounted=timelines[beforeRemount];
    assert.equal(remounted.totalTime(),.73,'same-page remount preserves 730ms rather than restarting');
    controller.sync([remount]);assert.equal(timelines.length-beforeRemount,1);
    remounted.totalTime(13.767,true);
    research=true;controller.refresh();remount.isConnected=false;
    const quietRemount=new Scene(sceneName),beforeQuiet=timelines.length;controller.sync([quietRemount]);
    assert.equal(timelines.length,beforeQuiet,'quiet remount retains phase without starting timelines');assertRestored(remount);
    research=false;controller.refresh();
    assert.equal(timelines.length-beforeQuiet,1);
    assert.equal(timelines[beforeQuiet].totalTime(),13.767,'quiet remount preserves time across multiple repeated cycles');
    await Promise.resolve();
    assert.equal(controller.getState()[0].phase,'ambient');
    assert.ok(unrelated.parent,'scoped cleanup leaves unrelated engine animations alive');
  }
  const completedNode=new Scene('qa'),beforeCompleted=timelines.length;
  controller.setRoute('qa');controller.enter(completedNode);
  const completedEntry=entranceTimeline(timelines.slice(beforeCompleted));
  completedEntry.totalTime(completedEntry.duration(),false);
  assert.equal(controller.getState()[0].phase,'ambient','a normally completed entrance yields control to ambience');
  for(const piece of completedNode.pieces)assert.ok(piece.style.translate.includes('--scene-drift-x')&&piece.style.translate.includes('--piece-depth'),'ambient composition preserves existing pointer depth variables');
  const savedNode=new Scene('scope');savedNode.pieces[0].style.translate='3px 4px';savedNode.pieces[0].style.opacity='.82';savedNode.setAttribute('data-feature-motion','existing-owner');
  controller.setRoute('scope');controller.enter(savedNode);
  controller.setRoute('home');
  assert.equal(savedNode.pieces[0].style.translate,'3px 4px','context disposal preserves pre-existing inline translation');
  assert.equal(savedNode.pieces[0].style.opacity,'.82','context disposal preserves pre-existing inline opacity');
  assert.equal(savedNode.getAttribute('data-feature-motion'),'existing-owner','context disposal preserves a pre-existing ownership marker');
  for(let n=0;n<40;n++){
    const sceneName=Object.keys(pieces)[n%5],beforeVisit=timelines.length;controller.setRoute(sceneName);controller.enter(new Scene(sceneName));
    assert.ok(timelines.slice(beforeVisit).every(timeline=>timeline.totalTime()===0),'real route change clears prior visit time');
    assert.equal(controller.getState().length,1);assert.equal(observer.nodes.size,1,'rapid navigation releases all old observer targets');
    assert.ok(timelines.filter(timeline=>timeline.parent).length<=2,'route cycles cannot accumulate live top-level timelines');
  }
  controller.setRoute('home');controller.sync([]);assert.equal(controller.getState().length,0);assert.equal(observer.nodes.size,0);
  assert.ok(timelines.every(timeline=>timeline.parent===null),'leaving feature pages kills all owned timelines');
  reduced=true;const staticNode=new Scene('qa');const staticStart=timelines.length;controller.setRoute('qa');controller.enter(staticNode);controller.sync([staticNode]);
  assert.equal(timelines.length,staticStart,'initial OS reduced creates no decorative timelines');
  reduced=false;controller.refresh();assert.equal(timelines.length-staticStart,1,'enabling presentation starts ambience without replaying entry');
  const stale=new Scene('qa');stale.rect.top=1100;stale.rect.bottom=1364;staticNode.isConnected=false;controller.sync([stale]);
  assert.equal(controller.getState()[0].running,0,'below-fold mount starts paused before its first observer delivery');
  controller.dispose();controller.dispose();assert.ok(observer.disconnected);assert.equal(observer.nodes.size,0);assert.ok(timelines.every(timeline=>timeline.parent===null));assertRestored(stale);
  controller.enter(new Scene('scope'));controller.refresh();assert.equal(controller.getState().length,0,'disposed controller cannot resurrect');
  unrelated.totalTime(50,true);assert.equal(unrelatedTarget.value,75,'unrelated GSAP animation still interpolates after controller disposal');unrelated.kill();
  await Promise.resolve();
  testStaticFallback();
  testReplayControls();
  testStudioInterleavedDelivery();
  await testActualClock();
  console.log('feature scene motion: real GSAP 3.15.0 wall-clock playback, replay, late engine recovery, style ownership, native controls, remount phase, route races, reduced motion and scoped disposal passed');
}
function testStaticFallback(){
  const fallbackContext={IntersectionObserver:Observer};vm.createContext(fallbackContext);vm.runInContext(source,fallbackContext);
  const fallback=fallbackContext.QMFeatureSceneMotion.create({document,quiet:()=>false}),node=new Scene('qa');
  const count=timelines.length;fallback.setRoute('qa');fallback.enter(node);fallback.sync([node]);fallback.refresh();
  assert.equal(timelines.length,count,'a missing optional engine cannot create animations');
  assert.ok([...node.pieces,...node.loops,node.curtain].every(piece=>piece.inline.writes.length===0),'missing engine preserves complete static content');
  assert.ok(fallback.getState().every(state=>state.running===0));
  assert.equal(node.replayControl.disabled,true,'replay is unavailable while the engine is missing');
  fallbackContext.gsap=gsap;fallback.refresh();gsap.ticker.sleep();
  assert.equal(fallback.getState()[0].engine,'gsap','a late local engine becomes available without replacing the controller');
  assert.equal(fallback.getState()[0].phase,'ambient','late engine arrival does not unexpectedly replay a page entrance');
  assert.equal(timelines.length,count+1);assert.equal(timelines[count].repeat(),-1);
  assert.equal(node.replayControl.disabled,false);
  fallback.refresh();fallback.sync([node]);assert.equal(timelines.length,count+1,'refresh cannot bind another ambient owner');
  fallback.dispose();assert.equal(timelines[count].parent,null);
}
function listenerCount(node){return [...node.listeners.values(),...node.replayControl.listeners.values()].reduce((sum,set)=>sum+set.size,0);}
function testReplayControls(){
  let quiet=false,reduce=false;
  const playback=context.QMFeatureSceneMotion.create({document,quiet:()=>quiet||reduce});
  for(const name of Object.keys(pieces)){
    const node=new Scene(name);playback.setRoute(name);playback.enter(node);gsap.ticker.sleep();
    assert.equal(node.replayControl.disabled,false);assert.equal(listenerCount(node),1,'one scoped replay listener per live scene');
    const beforeNative=timelines.length;
    node.dispatch({type:'click',target:node.nativeControls[0]});
    assert.equal(timelines.length,beforeNative,'ordinary business control clicks cannot replay artwork');
    for(let click=0;click<12;click++){
      const before=timelines.filter(timeline=>timeline.repeat()!==-1).length;
      for(const timeline of timelines.filter(timeline=>timeline.parent))timeline.totalTime(.71,true);
      node.replayControl.click();gsap.ticker.sleep();
      assert.ok(timelines.filter(timeline=>timeline.repeat()!==-1).length<=before+1,'one explicit replay click cannot create duplicate entrances');
      assert.equal(playback.getState()[0].entranceTime,0);assert.equal(playback.getState()[0].ambientTime,0);
      assert.equal(playback.getState()[0].phase,'entering');
      assert.ok(timelines.filter(timeline=>timeline.parent).length<=2,'rapid replay leaves at most two live timelines');
      assert.equal(listenerCount(node),1,'replay cannot accumulate handlers');
    }
    quiet=true;playback.refresh();
    const beforeQuiet=timelines.length;
    assert.equal(node.replayControl.disabled,true);assert.ok(node.replayControl.title.length>0,'disabled replay explains the current motion preference');
    node.replayControl.click();playback.replay(node);
    assert.equal(timelines.length,beforeQuiet,'native and direct replay both respect research mode');
    quiet=false;playback.refresh();
    assert.equal(node.replayControl.disabled,false);assert.equal(playback.getState()[0].phase,'ambient','restoring presentation resumes ambience without an unwanted entrance');
    reduce=true;playback.refresh();assert.equal(node.replayControl.disabled,true);
    const beforeReduced=timelines.length;playback.replay(node);assert.equal(timelines.length,beforeReduced,'OS motion reduction cannot be bypassed through replay API');
    reduce=false;playback.refresh();
    assert.ok(node.nativeControls.every(control=>control.inline.writes.length===0));
    playback.setRoute('home');assert.equal(listenerCount(node),0,'leaving the page removes its replay listener');
    const beforeRemoved=timelines.length;node.replayControl.click();assert.equal(timelines.length,beforeRemoved,'a detached replay button cannot resurrect animation');
  }
  playback.dispose();
}
async function testActualClock(){
  // Real elapsed time drives the actual GSAP ticker here. No manual seek, mocked
  // ticker or browser/FPS claims: this catches a paused-but-seekable controller.
  const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const doc={hidden:false,defaultView:{innerHeight:900}},clockController=context.QMFeatureSceneMotion.create({document:doc,quiet:()=>false});
  for(const name of Object.keys(pieces)){
    const node=new Scene(name);clockController.setRoute(name);clockController.enter(node);
    const before=clockController.getState()[0],pose=JSON.stringify(node.pieces.map(piece=>[piece.style.translate,piece.style.rotate,piece.style.opacity]));
    gsap.ticker.wake();await delay(280);
    const after=clockController.getState()[0];
    assert.ok(after.entranceTime>before.entranceTime+.08,`${name}: the live GSAP ticker advances entrance time`);
    assert.ok(after.ambientTime>before.ambientTime+.08,`${name}: the live GSAP ticker advances repeated choreography`);
    assert.notEqual(JSON.stringify(node.pieces.map(piece=>[piece.style.translate,piece.style.rotate,piece.style.opacity])),pose,`${name}: elapsed time really updates visible artwork properties`);
    assert.ok(node.nativeControls.every(control=>control.inline.writes.length===0));
    node.isConnected=false;const remount=new Scene(name);clockController.sync([remount]);
    const ambientBefore=clockController.getState()[0],ambientPose=JSON.stringify(remount.pieces.map(piece=>[piece.style.translate,piece.style.rotate,piece.style.opacity]));
    assert.equal(ambientBefore.phase,'ambient','same-page remount contains no entrance tween');
    await delay(280);
    assert.ok(clockController.getState()[0].ambientTime>ambientBefore.ambientTime+.08);
    assert.notEqual(JSON.stringify(remount.pieces.map(piece=>[piece.style.translate,piece.style.rotate,piece.style.opacity])),ambientPose,`${name}: major artwork keeps moving under the real clock after the entrance is gone`);
  }
  doc.hidden=true;clockController.refresh();const frozen=clockController.getState()[0];
  await delay(180);assert.equal(clockController.getState()[0].ambientTime,frozen.ambientTime,'background time cannot advance paused GSAP choreography');
  doc.hidden=false;clockController.refresh();await delay(180);
  assert.ok(clockController.getState()[0].ambientTime>frozen.ambientTime+.05,'visibility restoration resumes actual ticking');
  clockController.setRoute('home');const held=new Scene('qa');clockController.setRoute('qa');clockController.enter(held,{hold:true});
  clockController.sync([held]);clockController.refresh();await delay(180);
  assert.equal(clockController.getState()[0].phase,'held');assert.equal(clockController.getState()[0].entranceTime,0);assert.equal(clockController.getState()[0].ambientTime,0,'sync cannot consume an entrance behind a route cover');
  clockController.release(held);await delay(180);
  assert.ok(clockController.getState()[0].entranceTime>.05,'route release starts real playback exactly when revealed');
  const handles=timelines.filter(timeline=>timeline.parent);clockController.dispose();const times=handles.map(timeline=>timeline.totalTime());
  await delay(120);assert.deepEqual(handles.map(timeline=>timeline.totalTime()),times,'disposed scenes receive no later engine updates');
  assert.ok(handles.every(timeline=>timeline.parent===null));gsap.ticker.sleep();
}
function testStudioInterleavedDelivery(){
  class Events {
    constructor(){this.listeners=new Map();}
    addEventListener(type,fn,options={}){if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(fn);options.signal?.addEventListener('abort',()=>this.removeEventListener(type,fn),{once:true});}
    removeEventListener(type,fn){this.listeners.get(type)?.delete(fn);}
    emit(type){for(const fn of [...this.listeners.get(type)||[]])fn({type});}
  }
  class TestAbort {constructor(){this.signal=new Events();}abort(){for(const fn of this.signal.listeners.get('abort')||[])fn();}}
  class Node extends Piece {
    constructor(){super('container');this.isConnected=true;this.dataset={};this.style={setProperty(){}};this.attrs={};this.classList={toggle(){}};}
    getAttribute(key){return this.attrs[key]??null;}
    getBoundingClientRect(){return {left:0,top:0,width:1100,height:360,bottom:360};}
    querySelector(key){return key==='[data-feature-scene]'?feature:null;}
    querySelectorAll(){return [];}
    closest(){return null;}
  }
  let feature=null,paint=0;
  const scheduled=new Map(),header=new Node(),marker=new Node(),intro=new Node(),root=new Node();
  header.attrs={'data-studio-scene':'home','data-studio-location':'home','data-studio-view-required':'true'};
  marker.attrs={'data-studio-view':'home','data-studio-view-scene':'home'};
  const doc=new Events();Object.assign(doc,{documentElement:root,body:new Node(),hidden:false,defaultView:{innerHeight:900}});
  doc.querySelector=key=>key==='[data-studio-location]'?header:key==='[data-studio-view]'?marker:key.startsWith('.st-key-workspace_hero,')?intro:null;
  doc.querySelectorAll=key=>key==='[data-feature-scene]'&&feature?[feature]:[];
  const media=new Events();media.matches=false;
  const host=new Events();Object.assign(host,{document:doc,gsap,IntersectionObserver:Observer,MutationObserver:class{observe(){}disconnect(){}},
    matchMedia:()=>media,AbortController:TestAbort,performance:{now:()=>0},CSS:{escape:value=>value},
    requestAnimationFrame:fn=>{scheduled.set(++paint,fn);return paint;},cancelAnimationFrame:id=>scheduled.delete(id)});host.window=host;
  vm.createContext(host);vm.runInContext(source,host);vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/studio_motion.js'),'utf8'),host);
  function flush(){for(let n=0;scheduled.size&&n<5;n++){const queue=[...scheduled.values()];scheduled.clear();queue.forEach(fn=>fn());}}
  function refresh(){host.__qmStudioMotion.refresh();flush();}
  flush();
  header.attrs['data-studio-scene']='qa';refresh();assert.equal(host.__qmStudioMotion.getFeatureState().length,0);
  feature=new Scene('qa');feature.closest=()=>null;refresh();
  assert.equal(host.__qmStudioMotion.getFeatureState().length,0,'new DOM also waits for the matching completed-view marker');
  marker.attrs['data-studio-view-scene']='qa';refresh();
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].scene,'qa');
  const previousCount=timelines.length,previousTimelines=timelines.slice(-2);
  header.attrs['data-studio-scene']='scope';refresh();
  assert.equal(host.__qmStudioMotion.getFeatureState().length,0,'header-first navigation does not rebind the outgoing QA artwork');
  assert.equal(timelines.length,previousCount,'old scene gets no new ambient timeline while waiting');
  assert.ok(previousTimelines.every(timeline=>timeline.parent===null));
  feature.isConnected=false;feature=new Scene('scope');feature.closest=()=>null;refresh();
  assert.equal(host.__qmStudioMotion.getFeatureState().length,0,'new scope DOM cannot animate under the previous QA completion marker');
  marker.attrs['data-studio-view-scene']='scope';refresh();
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].scene,'scope');
  const arrived=timelines.length;refresh();refresh();
  assert.equal(timelines.length,arrived,'same-route native reruns leave existing timelines intact');
  const studioIdentity=host.__qmStudioMotion,phaseTimeline=timelines[arrived-1];phaseTimeline.totalTime(.819,true);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/studio_motion.js'),'utf8'),host);flush();
  assert.equal(host.__qmStudioMotion,studioIdentity,'same-version reinjection retains the single studio owner');
  assert.equal(timelines.length,arrived);assert.equal(phaseTimeline.totalTime(),.819,'reinjection preserves current GSAP phase');
  header.attrs['data-studio-scene']='counter';refresh();
  doc.hidden=true;doc.emit('visibilitychange');flush();
  feature.isConnected=false;feature=new Scene('counter');feature.closest=()=>null;
  marker.attrs['data-studio-view-scene']='counter';refresh();
  assert.equal(root.dataset.qmStudioRoute,'counter','hidden interruption retains a route waiting for native completion');
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].running,0);
  doc.hidden=false;doc.emit('visibilitychange');flush();
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].phase,'ambient','a page completed in background resumes ambient without a late entrance');
  header.attrs['data-studio-scene']='replay';refresh();
  root.dataset.qmMotionMode='research';host.emit('qm-motion-preference-change');flush();
  feature.isConnected=false;feature=new Scene('replay');feature.closest=()=>null;
  marker.attrs['data-studio-view-scene']='replay';refresh();
  assert.equal(root.dataset.qmStudioRoute,'replay','preference interruption retains the pending route');
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].phase,'static');
  root.dataset.qmMotionMode='presentation';host.emit('qm-motion-preference-change');flush();
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].phase,'ambient','enabling presentation cannot replay the interrupted entrance');
  header.attrs['data-studio-scene']='assets';refresh();
  doc.hidden=true;doc.emit('visibilitychange');flush();
  doc.hidden=false;doc.emit('visibilitychange');flush();
  assert.equal(host.__qmStudioMotion.getFeatureState().length,0,'visibility reversal still waits for the new matching view marker');
  feature.isConnected=false;feature=new Scene('assets');feature.closest=()=>null;
  marker.attrs['data-studio-view-scene']='assets';refresh();
  assert.equal(host.__qmStudioMotion.getFeatureState()[0].phase,'entering','completion after visibility returns starts exactly one valid entrance');
  host.__qmStudioMotion.dispose();assert.equal(host.__qmStudioMotion.getFeatureState().length,0);
  assert.ok(timelines.every(timeline=>timeline.parent===null),'studio disposal releases every feature timeline');
}
run().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{gsap.timeline=originalTimeline;gsap.globalTimeline.clear();gsap.ticker.sleep();});
