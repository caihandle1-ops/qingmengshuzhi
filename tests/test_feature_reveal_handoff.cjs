'use strict';
// Exercise the production cover + studio owners with deferred native animation
// promises. The feature controller's hold/release contract has real-GSAP tests.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const code=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
class Events {
  constructor(){this.listeners=new Map();}
  addEventListener(type,fn,options={}){if(options.signal?.aborted)return;if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(fn);options.signal?.addEventListener('abort',()=>this.removeEventListener(type,fn),{once:true});}
  removeEventListener(type,fn){this.listeners.get(type)?.delete(fn);}
  emit(type){for(const fn of [...this.listeners.get(type)||[]])fn({type});}
}
const motions=[];
class Animation {
  constructor(node,frames,options){Object.assign(this,{node,frames,options,cancelled:false,settled:false});this.finished=new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;});motions.push(this);}
  cancel(){this.cancelled=true;if(!this.settled){this.settled=true;this.reject(Error('cancelled'));}}
  finish(){if(!this.settled){this.settled=true;this.resolve();}}
  pause(){} play(){}
}
class Node extends Events {
  constructor(tag='div'){super();this.nodeType=1;this.tag=tag;this.isConnected=true;this.attrs={};this.dataset={};this.className='';this.children=[];this.style={setProperty(){}};this.classList={toggle(){}};this.rect={left:260,top:180,width:950,height:300,bottom:480};this.textContent='';}
  setAttribute(key,value){this.attrs[key]=String(value);}
  getAttribute(key){return this.attrs[key]??null;}
  removeAttribute(key){delete this.attrs[key];}
  getBoundingClientRect(){return {...this.rect};}
  appendChild(node){this.children.push(node);node.parent=this;node.isConnected=true;}
  prepend(node){this.children.unshift(node);node.parent=this;}
  remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}
  contains(node){return this===node||this.children.some(child=>child.contains(node));}
  closest(){return null;}
  matches(){return false;}
  querySelector(key){return key==='[data-feature-scene]'?this.feature||null:null;}
  querySelectorAll(key){return key==='.qm-route-stage-piece'?this.children.filter(child=>child.className.startsWith('qm-route-stage-piece')):[];}
  animate(frames,options){return new Animation(this,frames,options);}
}
const root=new Node('html'),header=new Node(),marker=new Node(),main=new Node('main');
root.dataset.qmMotionMode='presentation';main.scrollTop=0;main.rect={left:230,top:50,width:1100,height:850,bottom:900};
header.attrs={'data-studio-location':'home','data-studio-scene':'home','data-studio-view-required':'true'};
marker.attrs={'data-studio-view':'home','data-studio-view-scene':'home'};
let intro=new Node(),feature=null,rafId=0,timerId=0;
const frames=new Map(),timers=new Map(),log=[],records=new Map();
const doc=new Events();Object.assign(doc,{documentElement:root,body:new Node('body'),hidden:false,defaultView:{innerHeight:960}});
doc.createElement=tag=>new Node(tag);
doc.querySelector=key=>key==='[data-studio-location]'?header:key==='[data-studio-view]'?marker:key==='[data-testid="stMain"]'?main:key.startsWith('.st-key-workspace_hero,')?intro:null;
doc.querySelectorAll=key=>key==='[data-feature-scene]'&&feature?[feature]:[];
const media=new Events();media.matches=false;
class Observer {observe(){}unobserve(){}disconnect(){}}
const featureOwner={
  setRoute(route){log.push({type:'route',route});records.clear();},
  enter(node,options={}){if(records.has(node)&&records.get(node).entered)return;records.set(node,{entered:true,held:!!options.hold});log.push({type:'enter',node,hold:!!options.hold});},
  release(node,{settle=false}={}){if(!records.has(node))return;records.get(node).held=false;log.push({type:'release',node,settle,coverPresent:doc.body.children.some(child=>child.className==='qm-route-stage')});},
  sync(nodes){const live=new Set(nodes);for(const node of records.keys())if(!live.has(node))records.delete(node);for(const node of live)if(!records.has(node))records.set(node,{entered:false,held:false});},
  refresh(){},getState(){return [...records.values()];},dispose(){records.clear();log.push({type:'dispose'});}
};
const host=new Events();Object.assign(host,{document:doc,AbortController,IntersectionObserver:Observer,MutationObserver:Observer,ResizeObserver:Observer,performance:{now:()=>100},innerWidth:1440,innerHeight:960,
  matchMedia:()=>media,CSS:{escape:value=>value},console,
  requestAnimationFrame:fn=>{frames.set(++rafId,fn);return rafId;},cancelAnimationFrame:id=>frames.delete(id),
  setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),
  QMFeatureSceneMotion:{create:()=>featureOwner}});host.window=host;
vm.createContext(host);vm.runInContext(code('route_transition.js'),host);vm.runInContext(code('studio_motion.js'),host);
function paint(){for(let count=0;frames.size&&count<12;count++){const jobs=[...frames.values()];frames.clear();jobs.forEach(fn=>fn());}assert.equal(frames.size,0,'bounded studio scan');}
function content(scene){if(feature)feature.isConnected=false;intro.isConnected=false;feature=new Node();feature.attrs['data-feature-scene']=scene;intro=new Node();intro.feature=feature;marker.attrs={'data-studio-view':scene,'data-studio-view-scene':scene};}
function navigate(scene,{cover=true}={}){if(cover){const button=new Node('button');button.textContent=scene;assert.equal(host.__qmRouteStage.begin(button,{scene:header.attrs['data-studio-scene']}),true);}header.attrs['data-studio-location']=scene;header.attrs['data-studio-scene']=scene;content(scene);host.__qmStudioMotion.refresh();paint();return motions.findLast(animation=>animation.node.attrs['data-qm-route-report']!==undefined&&animation.options.fill==='forwards'&&animation.options.duration===690&&!animation.cancelled);}
const released=node=>log.filter(event=>event.type==='release'&&event.node===node);
const entered=node=>log.filter(event=>event.type==='enter'&&event.node===node);
async function flush(){await Promise.resolve();await Promise.resolve();await Promise.resolve();}
async function run(){
  paint();
  let cover=navigate('qa'),node=feature;
  assert.ok(cover);assert.equal(records.get(node).held,false);assert.equal(entered(node).length,1);assert.equal(released(node).length,1,'ready content begins while the shared report keeps flying');
  for(let rerun=0;rerun<12;rerun++){host.__qmStudioMotion.refresh();paint();}
  assert.equal(entered(node).length,1);assert.equal(records.get(node).held,false,'same-page scans cannot re-hold the ready entrance');
  cover.finish();await flush();
  assert.equal(released(node).length,1);assert.equal(released(node)[0].settle,false);assert.equal(released(node)[0].coverPresent,true,'the decorative flight no longer blocks GSAP clock release');
  vm.runInContext(code('studio_motion.js'),host);paint();assert.equal(entered(node).length,1);assert.equal(released(node).length,1,'same-version bootstrap cannot replay');

  cover=navigate('scope');node=feature;const oldNode=node;
  content('scope');node=feature;host.__qmStudioMotion.refresh();paint();
  assert.equal(records.get(node).held,false,'native remount after readiness does not acquire a new hold');cover.finish();await flush();
  assert.equal(released(oldNode).length,1);assert.equal(released(node).length,0,'late overlay completion cannot replay a remounted DOM scene');

  for(const interruption of ['hidden','research','resize']){
    cover=navigate(interruption==='hidden'?'counter':interruption==='research'?'replay':'assets');node=feature;
    if(interruption==='hidden'){doc.hidden=true;doc.emit('visibilitychange');}
    if(interruption==='research'){root.dataset.qmMotionMode='research';host.emit('qm-motion-preference-change');}
    if(interruption==='resize')host.emit('resize');
    assert.equal(released(node).length,1,interruption+': interrupted decoration does not release again');assert.equal(released(node)[0].settle,false,'the scene had already begun while visible');
    cover.finish();await flush();assert.equal(released(node).length,1,'late completion cannot restart an interrupted scene');
    doc.hidden=false;root.dataset.qmMotionMode='presentation';doc.emit('visibilitychange');host.emit('qm-motion-preference-change');paint();
    assert.equal(entered(node).length,1,'restoring visibility/presentation does not replay');
  }

  const oldCover=navigate('counter'),oldFeature=feature;
  cover=navigate('replay');node=feature;
  assert.equal(released(oldFeature).length,1);assert.equal(released(oldFeature)[0].settle,false);
  oldCover.finish();await flush();assert.equal(released(node).length,1,'stale cover cannot release the next route twice');
  cover.finish();await flush();assert.equal(released(node).length,1);assert.equal(released(node)[0].settle,false);

  // A header may precede completed content, even while visibility cancels its cover.
  const button=new Node('button');button.textContent='scope';host.__qmRouteStage.begin(button,{scene:'replay'});
  header.attrs['data-studio-location']='scope';header.attrs['data-studio-scene']='scope';host.__qmStudioMotion.refresh();paint();
  assert.equal(root.dataset.qmStudioLast,'route-awaiting-content');
  doc.hidden=true;doc.emit('visibilitychange');doc.hidden=false;doc.emit('visibilitychange');paint();
  content('scope');host.__qmStudioMotion.refresh();paint();node=feature;
  assert.equal(entered(node).length,1,'cancelled visual cover does not discard a route awaiting its content');assert.equal(records.get(node).held,false);

  cover=navigate('qa');node=feature;host.__qmStudioMotion.dispose();cover.finish();await flush();
  assert.equal(released(node).length,1,'a disposed studio cannot receive a second late reveal');assert.equal(records.size,0);host.__qmRouteStage.dispose();
  assert.equal(doc.body.children.length,0);assert.equal(timers.size,0);
  console.log('feature reveal handoff: immediate content release, parallel paper flight, ready remount, same-page stability, hidden/research/resize cancellation, rapid routes and disposal passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
