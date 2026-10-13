'use strict';
// Exercise the production landing runtime, GSAP, WebGL draw path and component
// protocol with a deterministic graphics adapter. Browser review owns pixels.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {component}=require('./test_hero_initial_render.cjs');
const gsap=require('../app/hero_frontend/gsap.min.js').gsap;gsap.ticker.sleep();
const source=fs.readFileSync(path.join(__dirname,'../app/hero_frontend/landing-cinema.js'),'utf8');
const context={token:'landing-company-year-v24',company:'测试企业',year:'2025',has_reports:false,has_data:false,has_answer:false};
const events=hero=>hero.posts.filter(post=>post.type==='streamlit:setComponentValue');
const state=hero=>hero.context.__qmImmersiveHero.getState();
function setup(options={}){
  const hero=component({navigation:true,gsap,captureGeometry:true,...options});
  vm.runInContext(source,hero.context);
  hero.context.innerWidth=options.width||1366;hero.context.innerHeight=options.height||768;
  for(const id of ['sculpture','sculpture-stage'])hero.get(id).getBoundingClientRect=()=>({left:0,top:0,width:hero.context.innerWidth,height:hero.context.innerHeight});
  for(const id of ['landing-line-one','landing-line-two','landing-copy-detail'])hero.get(id).style={};
  hero.renderLanding=(value=context,landing=true)=>hero.context.emit('message',{source:hero.context.parent,data:{type:'streamlit:render',args:{landing,context:value,brand:{name:'擎梦数智'},motion:{version:1,mode:'presentation'}}}});
  hero.renderLanding();hero.paintAt(0);return hero;
}
const click=hero=>hero.get('landing-enter').emit('click',{preventDefault(){},button:0});
const productionMatrices=hero=>hero.geometryDraws.filter(draw=>draw.indexed).map(draw=>draw.model);
const checks=[];
for(const [width,height] of [[1366,768],[1920,1080]]){
  const hero=setup({width,height});
  assert.equal(state(hero).landing,true);assert.equal(state(hero).score.paused,true);
  assert.equal(hero.get('landing-enter').attributes['aria-disabled'],'false','main entry is actionable on the first frame');
  assert.equal(hero.posts.at(-1).height,height,'component requests its actual viewport height');
  assert.equal(hero.geometryDraws.filter(draw=>draw.indexed).length,8,'the real paper ensemble is rendered');
  const first=JSON.stringify(productionMatrices(hero));hero.paintAt(1300);
  assert.notEqual(JSON.stringify(productionMatrices(hero)),first,'entrance changes actual model matrices');
  hero.paintAt(2600);assert.equal(state(hero).landingPose.travel,0);assert.equal(state(hero).landingPose.spread,1);
  assert.equal(hero.get('landing-line-one').style.opacity,'1');assert.equal(hero.get('landing-line-two').style.opacity,'1');
  const composed=JSON.stringify(productionMatrices(hero)),camera=JSON.stringify(state(hero).cameraRig);
  hero.paintAt(10600);assert.notEqual(JSON.stringify(productionMatrices(hero)),composed,'flow keeps transforming the physical papers');
  assert.notEqual(JSON.stringify(state(hero).cameraRig),camera,'flow keeps the real camera alive');
  const before=JSON.stringify(state(hero).landingPose);hero.renderLanding();hero.paintAt(10600);
  assert.equal(JSON.stringify(state(hero).landingPose),before,'same-context rerenders do not restart entrance');
  assert.equal(events(hero).length,0,'presentation never requests business work or navigation');
  const beforeHidden=state(hero).showTime;hero.doc.hidden=true;hero.doc.emit('visibilitychange');assert.equal(hero.frames.size,0);
  hero.paintAt(45000);hero.doc.hidden=false;hero.doc.emit('visibilitychange');hero.paintAt(45001);
  assert.equal(state(hero).showTime,beforeHidden,'hidden time does not advance GSAP or camera');
  assert.equal(hero.frames.size,1,'there is one RAF after resume');
  assert.doesNotThrow(()=>JSON.stringify(state(hero)),'diagnostic state stays serializable');
  hero.dispose();checks.push({width,height,physical_entrance:true,ongoing_camera:true,one_clock:true});
}
// Fast initial clicks do not wait for the 2.6-second title/geometry entrance.
const fast=setup();click(fast);assert.equal(events(fast).length,1,'the click dispatches without waiting for any animation frame');click(fast);fast.paintAt(300);
assert.equal(events(fast).length,1);assert.equal(state(fast).playback,'exiting');assert.equal(state(fast).selection.complete,false);
fast.paintAt(620);assert.equal(events(fast).length,1);assert.equal(events(fast)[0].value.action,'enter_workspace');
assert.equal(events(fast)[0].value.context_token,context.token);assert.ok(events(fast)[0].value.nonce);
fast.paintAt(900);click(fast);assert.equal(events(fast).length,1,'a committed entry is idempotent');fast.dispose();
// The three secondary links stay bound to the same validated context.
for(const action of ['annual_reports','annual_data','answer_evidence']){
  const hero=setup();hero.get('hero-link-'+action).emit('click',{preventDefault(){},button:0});hero.paintAt(620);
  assert.equal(events(hero).length,1);assert.equal(events(hero)[0].value.action,action);hero.dispose();
}
const stale=setup();click(stale);stale.paintAt(300);stale.renderLanding({...context,token:'new-company'});stale.paintAt(700);
assert.equal(events(stale).length,1,'a changed context cancels visuals without replaying the already-sent action');assert.equal(state(stale).navigation.pending,null);stale.dispose();
for(const options of [{osReduced:true},{webgl:false}]){
  const hero=setup(options);assert.equal(hero.get('landing-line-one').style.opacity,'1');
  assert.equal(hero.frames.size,0,'static/fallback mode does not run a hidden animation');click(hero);
  assert.equal(events(hero).length,1);assert.equal(events(hero)[0].value.action,'enter_workspace');hero.dispose();
}
const missing=setup();missing.renderLanding({});click(missing);missing.paintAt(1000);assert.equal(events(missing).length,0);missing.dispose();
const lost=setup();click(lost);lost.paintAt(200);lost.get('sculpture').emit('webglcontextlost',{preventDefault(){}});
assert.equal(events(lost).length,1,'graphics loss does not strand an explicit entry');lost.dispose();
const switching=setup();switching.paintAt(700);switching.renderLanding(context,false);switching.paintAt(720);
assert.equal(state(switching).landing,false);assert.equal(state(switching).shot,'paper-edge');
click(switching);switching.paintAt(2000);assert.equal(events(switching).length,0,'the hidden landing CTA cannot enter from a workspace hero');
switching.renderLanding();switching.paintAt(2000);assert.equal(state(switching).landing,true);assert.equal(switching.frames.size,1);switching.dispose();
assert.equal(gsap.globalTimeline.getChildren(true,true,true).length,0,'all landing and legacy GSAP timelines are released');
console.log(JSON.stringify({passed:true,checks,immediate_cta:true,exit_ms:620,idempotent:true,context_validation:true,reduced_and_fallback:true,mode_switch_cleanup:true}));
