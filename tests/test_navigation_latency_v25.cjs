'use strict';
// Real production GSAP/component clocks plus deterministic native animation
// promises: measure dispatch/readiness, preserve motion, and exercise teardown.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {component}=require('./test_hero_initial_render.cjs');
const gsap=require('../app/hero_frontend/gsap.min.js').gsap;gsap.ticker.sleep();
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const initial={token:'company-2025-v25',company:'导航测试',year:'2025'};
const events=hero=>hero.posts.filter(post=>post.type==='streamlit:setComponentValue');
const click=(hero,id)=>hero.get(id).emit('click',{preventDefault(){},button:0});
const state=hero=>hero.context.__qmImmersiveHero.getState();
function setup(landing){
  const hero=component({navigation:true,gsap});
  if(landing){
    vm.runInContext(read('hero_frontend/landing-cinema.js'),hero.context);
    for(const id of ['landing-line-one','landing-line-two','landing-copy-detail'])hero.get(id).style={};
  }
  hero.renderValue=(value=initial)=>hero.context.emit('message',{source:hero.context.parent,data:{type:'streamlit:render',args:{landing,context:value,motion:{version:1,mode:'presentation'}}}});
  hero.renderValue();hero.paintAt(0);return hero;
}
const measurements=[];
for(const landing of [false,true]){
  const hero=setup(landing),id=landing?'landing-enter':'hero-link-annual_data',duration=landing?620:430;
  hero.paintAt(2700);const before=state(hero).showTime;
  click(hero,id);
  assert.equal(events(hero).length,1,'dispatch happens in the click call before the next RAF');
  assert.equal(state(hero).selection.complete,false,'the original physical exit is still pending');
  assert.ok(hero.posts.findIndex(post=>post.type==='qm:portal-intent')<hero.posts.findIndex(post=>post.type==='streamlit:setComponentValue'),'the parent portal receives the handoff before native rerun can remove this iframe');
  hero.paintAt(2700+duration/2);
  assert.ok(state(hero).selection.lift>.1,'the real production motion continues after dispatch');
  assert.equal(state(hero).showTime,before,'the committed exit holds the existing choreography');
  assert.equal(state(hero).selection.complete,false);
  for(let i=0;i<8;i++){hero.renderValue();click(hero,id);}
  hero.paintAt(2700+duration-1);assert.equal(state(hero).selection.complete,false,'do not shorten the original exit');
  hero.paintAt(2700+duration);assert.equal(state(hero).selection.complete,true);
  assert.equal(events(hero).length,1,'visual completion and same-context reruns do not dispatch again');
  hero.doc.hidden=true;hero.doc.emit('visibilitychange');hero.get('sculpture').emit('webglcontextlost',{preventDefault(){}});
  assert.equal(events(hero).length,1);hero.dispose();
  measurements.push({landing,dispatch_wait_frames:0,retained_exit_ms:duration});

  // Removal during the exit leaves no clock or event to leak into a replacement iframe.
  const outgoing=setup(landing);click(outgoing,id);outgoing.paintAt(100);outgoing.dispose();outgoing.paintAt(5000);
  assert.equal(events(outgoing).length,1);
  const replacement=setup(landing);replacement.paintAt(5000);assert.equal(events(replacement).length,0,'a new iframe never restores a previously sent navigation');
  click(replacement,id);assert.equal(events(replacement).length,1);replacement.dispose();
}

// Exercise reentrant host reruns and stale visual completions using real DOM.
const dom=new JSDOM(read('hero_frontend/index.html'),{runScripts:'outside-only',url:'http://localhost:8504/component/hero'});
dom.window.eval(read('hero_frontend/hero-navigation.js'));
const callbacks=[],sent=[],listeners=[];let nav,reentrant=null,begins=0,cancels=0;
const env={document:dom.window.document,shell:dom.window.document.getElementById('hero'),onHover(){},intent(){},
  listen(node,event,fn){node.addEventListener(event,fn);listeners.push(()=>node.removeEventListener(event,fn));},
  cancel(){cancels++;},begin(action,done){begins++;callbacks.push(done);},emit(event){sent.push(event);reentrant?.();}};
nav=dom.window.QMHeroNavigation.createNavigation(env);nav.setContext(initial);
const press=id=>dom.window.document.getElementById(id).dispatchEvent(new dom.window.MouseEvent('click',{bubbles:true,cancelable:true,button:0}));
press('hero-link-annual_reports');assert.equal(sent.length,1);assert.equal(begins,1);
nav.setContext({...initial,token:'new-company'});press('hero-link-answer_evidence');
callbacks[0]();assert.equal(sent.length,2);assert.equal(nav.getState().pending.context_token,'new-company');
callbacks[1]();nav.settlePending();nav.settlePending();press('hero-link-annual_data');assert.equal(sent.length,2,'late completion, fallback settlement and repeats retain the committed lock');
nav.setContext({...initial,token:'sync-rerun'});reentrant=()=>nav.setContext({...initial,token:'after-sync-rerun'});
press('hero-link-annual_data');assert.equal(sent.length,3);assert.equal(begins,2,'synchronous native context replacement cannot start an orphaned exit');assert.equal(nav.getState().pending,null);
reentrant=null;nav.setContext({token:'<invalid>'});press('hero-link-annual_data');assert.equal(sent.length,3,'invalid context cannot authorize navigation');
nav.setContext(initial);press('landing-enter');assert.equal(sent.length,3,'the hidden landing action is not authorized from a workspace');
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
nav.setScene([{action:'run_business_job',matrix:identity,vertices:[-1,-1,0,0,0,0,0,0,0,1,-1,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],indices:[0,1,2]}],identity,{left:0,top:0,width:100,height:100});
assert.equal(nav.selectAt(50,50),false);assert.equal(sent.length,3,'projected geometry cannot authorize a new action');
reentrant=()=>nav.dispose();press('hero-link-annual_reports');assert.equal(sent.length,4);assert.equal(begins,2,'synchronous iframe destruction cannot create a new timeline');
callbacks.forEach(done=>done());nav.settlePending();press('hero-link-annual_data');assert.equal(sent.length,4);
listeners.forEach(remove=>remove());dom.window.close();assert.ok(cancels>0);

async function routeChecks(){
  const dom=new JSDOM('<main data-testid="stMain"></main><button>核验工具</button><section data-feature-inline="scope"><i data-qm-route-report-target></i></section>',{runScripts:'outside-only',pretendToBeVisual:true,url:'http://localhost:8504/'});
  const win=dom.window,doc=win.document,root=doc.documentElement,animations=[],timers=new Map();let timerId=0,now=0;
  const media={matches:false,addEventListener(){},removeEventListener(){}};
  win.matchMedia=()=>media;win.CSS={escape:value=>value};Object.defineProperty(win.performance,'now',{value:()=>now});
  win.setTimeout=(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;};win.clearTimeout=id=>timers.delete(id);
  win.Element.prototype.getBoundingClientRect=function(){return this.tagName==='BUTTON'?{left:300,top:180,width:260,height:70}:{left:250,top:80,width:1100,height:680};};
  win.Element.prototype.animate=function(frames,options){
    const animation={node:this,frames,options,cancelled:false};
    animation.finished=new Promise((resolve,reject)=>{animation.finish=resolve;animation.cancel=()=>{animation.cancelled=true;reject(Error('cancelled'));};});
    animations.push(animation);return animation;
  };
  win.eval(read('route_transition.js'));const route=win.__qmRouteStage,button=doc.querySelector('button'),target=doc.querySelector('section');
  const flush=async()=>{for(let i=0;i<6;i++)await Promise.resolve();};
  let ready=0,cancelled=0;
  route.begin(button,{scene:'home'});now=25;
  route.arrive(target,{location:'scope',onReveal:()=>ready++,onCancel:()=>cancelled++});
  assert.equal(ready,1,'a 25ms backend releases native content at 25ms, not 1200ms');
  assert.ok(doc.querySelector('.qm-route-stage'),'paper artwork continues after readiness');
  const flight=animations.findLast(a=>a.node.hasAttribute('data-qm-route-report')&&a.options.fill==='forwards');
  assert.equal(flight.options.delay,485);assert.equal(flight.options.duration,690);
  const veil=animations.findLast(a=>a.node.className==='qm-route-stage-veil');assert.equal(veil.options.duration,120);assert.equal(veil.options.delay,undefined);
  const retained=animations.length;win.eval(read('route_transition.js'));assert.equal(animations.length,retained,'same-version SSR cannot restart a transition');
  for(const [id,timer]of [...timers]){timers.delete(id);timer.fn();}await flush();
  assert.equal(doc.querySelector('.qm-route-stage'),null,'arrival timeout bounds a dropped native animation promise');
  flight.finish();await flush();assert.equal(ready,1);assert.equal(cancelled,0,'timeout cleanup cannot emit another reveal or cancellation');
  route.begin(button,{scene:'home'});route.arrive(target,{location:'scope',onReveal:()=>ready++});const old=animations.at(-1);
  route.cancel();old.finish();await flush();assert.equal(ready,2);
  route.begin(button,{scene:'home'});route.dispose();for(const animation of animations)animation.finish();await flush();
  assert.equal(ready,2);assert.equal(timers.size,0);assert.equal(doc.querySelector('.qm-route-stage'),null);
  assert.ok(animations.every(animation=>animation.cancelled),'all native decorative animations are released');dom.window.close();
}
routeChecks().then(()=>{assert.equal(gsap.globalTimeline.getChildren(true,true,true).length,0);gsap.ticker.sleep();console.log(JSON.stringify({passed:true,measurements,ready_release_ms:25,real_gsap:true,reentrant_rerun:true,iframe_remount:true,unauthorized_actions:true,timeout_cleanup:true}));}).catch(error=>{console.error(error);process.exitCode=1;});
