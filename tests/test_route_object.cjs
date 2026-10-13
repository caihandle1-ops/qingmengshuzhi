'use strict';
// Exercise real route-controller callbacks with deterministic DOM geometry.
// These assertions prove object ownership and lifecycle, not rendered pixels.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
class Events{
  constructor(){this.listeners=new Map();}
  addEventListener(type,fn,options={}){if(options.signal?.aborted)return;if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(fn);options.signal?.addEventListener('abort',()=>this.removeEventListener(type,fn),{once:true});}
  removeEventListener(type,fn){this.listeners.get(type)?.delete(fn);}
  emit(type){for(const fn of [...this.listeners.get(type)||[]])fn({type});}
  count(){return [...this.listeners.values()].reduce((sum,list)=>sum+list.size,0);}
}
const motions=[];
class Node{
  constructor(tag='div'){this.tag=tag;this.attrs={};this.dataset={};this.style={setProperty(){}};this.children=[];this.classList=[];this.className='';this.textContent='';this.isConnected=true;this.rect={left:330,top:150,width:230,height:80};}
  setAttribute(key,value){this.attrs[key]=String(value);}
  getAttribute(key){return this.attrs[key]??null;}
  appendChild(node){node.parent=this;this.children.push(node);}
  remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}
  getBoundingClientRect(){return {...this.rect};}
  closest(){return this.owner||null;}
  matches(selector){return selector==='[data-feature-inline]'&&'data-feature-inline'in this.attrs;}
  querySelector(selector){if(selector==='[data-feature-inline]')return this.host||null;if(selector==='[data-qm-route-report-target]')return this.target||null;return null;}
  querySelectorAll(){return[];}
  animate(frames,options){const motion={node:this,frames,options,cancelled:false,settled:false};motion.finished=new Promise((resolve,reject)=>{motion.finish=()=>{if(!motion.settled){motion.settled=true;resolve();}};motion.cancel=()=>{motion.cancelled=true;if(!motion.settled){motion.settled=true;reject(Error('cancelled'));}};});motions.push(motion);return motion;}
}
const root=new Node('html'),main=new Node('main'),body=new Node('body');main.rect={left:240,top:55,width:1200,height:860};main.scrollTop=190;
const doc=new Events();Object.assign(doc,{documentElement:root,body,hidden:false,createElement:tag=>new Node(tag)});
const entries=new Map(),currentHosts=new Map();
doc.querySelector=selector=>selector==='[data-testid="stMain"]'?main:entries.get(selector)||currentHosts.get(selector)||null;
const media=new Events();media.matches=false;const timers=new Map();let timerId=0,now=100;
const win=new Events();Object.assign(win,{document:doc,matchMedia:()=>media,AbortController,performance:{now:()=>now},innerWidth:1440,innerHeight:960,CSS:{escape:value=>value},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)});win.window=win;
const source=fs.readFileSync(path.join(__dirname,'../app/route_transition.js'),'utf8');
assert.doesNotMatch(source,/<[/\w!]/,'raw route st.html script must not trigger Streamlit DOMPurify SAFE_FOR_XML removal');
vm.createContext(win);vm.runInContext(source,win);const route=win.__qmRouteStage;
const owner=new Node();owner.classList=['st-key-open_scope'];const button=new Node('button');button.owner=owner;button.textContent='口径核验';button.rect={left:40,top:330,width:170,height:64};entries.set('.st-key-open_scope button',button);
function scene(name){const view=new Node(),host=new Node(),target=new Node();host.setAttribute('data-feature-inline',name);host.rect={left:310,top:160,width:1090,height:580};target.rect={left:930,top:330,width:200,height:310};host.target=target;view.host=host;currentHosts.set('[data-feature-inline="'+name+'"]',host);return{view,host,target};}
const allNodes=node=>[node,...node.children.flatMap(allNodes)];
const landing=()=>motions.findLast(m=>m.node.attrs['data-qm-route-report']!==undefined&&m.options.fill==='forwards');
async function flush(){for(let i=0;i<5;i++)await Promise.resolve();}
async function run(){
  let {view,host,target}=scene('scope'),reveals=0,cancels=0;
  assert.equal(route.begin(button,{scene:'home'}),true);
  const plane=body.children[0],report=allNodes(plane).find(node=>'data-qm-route-report'in node.attrs);
  assert.equal(plane.style.left,'252px','the overlay begins inside the native main; sidebar remains outside');
  assert.ok(report);assert.ok(allNodes(report).some(node=>node.className==='qm-route-report-fold'));
  assert.ok(allNodes(report).some(node=>node.className==='qm-route-report-spine'));
  assert.equal(allNodes(plane).filter(node=>node.tag==='button'||node.tag==='input').length,0,'shared object has no player controls');
  assert.equal(route.arrive(view,{location:'scope',previous:'home',onReveal:()=>{reveals++;assert.equal(body.children.length,1,'the decorative flight continues after content release');assert.equal(host.dataset.qmRouteArrival,'report');},onCancel:()=>cancels++}),true);
  const motion=landing(),endFrame=motion.frames.at(-1),numbers=[...endFrame.transform.matchAll(/-?\d+(?:\.\d+)?/g)].map(match=>Number(match[0]));
  assert.equal(endFrame.opacity,1,'a successful forward report stays solid until the inline folded paper takes over');
  const landedLeft=parseFloat(plane.style.left)+parseFloat(report.style.left)+numbers[0],landedTop=parseFloat(plane.style.top)+parseFloat(report.style.top)+numbers[1];
  assert.ok(landedLeft>=target.rect.left&&landedLeft<=target.rect.left+target.rect.width,'report uses the explicit destination object geometry');
  assert.ok(landedTop>=target.rect.top&&landedTop<=target.rect.top+target.rect.height);
  assert.equal(numbers[2],numbers[3],'paper keeps its proportions while crossing scenes');
  assert.ok(motions.every(m=>m.node!==button&&m.node!==view&&m.node!==host&&m.node!==target&&m.node!==main),'only transient overlay nodes animate');
  assert.equal(reveals,1,'ready content releases synchronously');assert.equal(motion.options.delay,510,'the full decorative expansion remains');assert.equal(motion.options.duration,690);motion.finish();await flush();assert.equal(reveals,1);assert.equal(cancels,0);assert.equal(timers.size,0);

  // A native React remount cannot receive a late marker from an already-released flight.
  ({view,host}=scene('counter'));route.begin(button,{scene:'scope'});route.arrive(view,{location:'counter',onReveal:()=>reveals++});
  const remountLanding=landing(),oldHost=host;oldHost.isConnected=false;({host}=scene('counter'));remountLanding.finish();await flush();
  assert.equal(oldHost.dataset.qmRouteArrival,'report');assert.equal(host.dataset.qmRouteArrival,undefined);

  for(const kind of ['resize','hidden','research','reduced']){
    ({view,host}=scene('replay'));route.begin(button,{scene:'scope'});let released=0,cancelled=0;
    route.arrive(view,{location:'replay',onReveal:()=>released++,onCancel:()=>cancelled++});const pending=landing();
    if(kind==='resize')win.emit('resize');
    if(kind==='hidden'){doc.hidden=true;doc.emit('visibilitychange');}
    if(kind==='research'){root.dataset.qmMotionMode='research';win.emit('qm-motion-preference-change');}
    if(kind==='reduced'){media.matches=true;media.emit('change');}
    pending.finish();await flush();assert.equal(released,1,kind+' cannot release the ready scene twice');assert.equal(cancelled,0);assert.equal(host.dataset.qmRouteArrival,'report');assert.equal(body.children.length,0);assert.equal(timers.size,0);
    doc.hidden=false;root.dataset.qmMotionMode='presentation';media.matches=false;
  }
  ({view}=scene('qa'));route.begin(button,{scene:'qa'});assert.equal(route.arrive(view,{location:'qa'}),false,'same scene never replays');assert.equal(body.children.length,0);

  const old=scene('scope'),next=scene('assets');let stale=0,fresh=0,aborted=0;
  route.begin(button,{scene:'home'});route.arrive(old.view,{location:'scope',onReveal:()=>stale++,onCancel:()=>aborted++});const prior=landing();
  route.begin(button,{scene:'scope'});route.arrive(next.view,{location:'assets',onReveal:()=>fresh++});const latest=landing();prior.finish();await flush();assert.equal(stale,1);assert.equal(fresh,1);assert.equal(aborted,0);latest.finish();await flush();assert.equal(fresh,1);

  // Parent entry/scroll is remembered independently of report appearance.
  main.scrollTop=700;route.begin(button,{scene:'scope',back:true});route.arrive(new Node(),{location:'home',previous:'scope'});assert.equal(main.scrollTop,190);assert.equal(root.dataset.qmRouteStage,'returning');landing().finish();await flush();

  route.begin(button,{scene:'home'});for(const [id,fn]of[...timers]){timers.delete(id);fn();}motions.at(-1).finish();await flush();assert.equal(body.children.length,0,'a view that never becomes ready cannot strand its paper');
  route.dispose();assert.equal(doc.count()+win.count()+media.count(),0);assert.equal(timers.size,0);assert.equal(body.children.length,0);
  console.log('route report: explicit paper target, overlay-only transforms, handoff/remount, interruption, rapid routes, same scene, anchors and cleanup passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
