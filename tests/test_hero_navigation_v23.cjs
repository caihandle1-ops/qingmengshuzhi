'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {component}=require('./test_hero_initial_render.cjs');
const gsap=require('../app/hero_frontend/gsap.min.js').gsap;gsap.ticker.sleep();
const context={token:'company-year-answer-v23',company:'真实测试企业',year:'2025',has_reports:true,has_data:true,has_answer:true};
const events=hero=>hero.posts.filter(message=>message.type==='streamlit:setComponentValue');
const state=hero=>hero.context.__qmImmersiveHero.getState();
function setup(options={}){
  const hero=component({navigation:true,gsap,...options});
  hero.context.innerWidth=480;
  hero.get('sculpture').getBoundingClientRect=()=>({width:480,height:370,left:0,top:78});
  hero.renderContext(context);hero.paintAt(0);return hero;
}
function pointFor(hero,action){
  const api=hero.context.__qmImmersiveHero;
  for(const item of api.getNavigationTargets().filter(item=>item.action===action)){
    const r=item.rect;
    for(let fy=.02;fy<1;fy+=.07)for(let fx=.02;fx<1;fx+=.07){
      const x=r.left+r.width*fx,y=r.top+r.height*fy;
      if(api.hitTest(x,y)===action)return {x,y};
    }
  }
  throw new Error('No exposed hit surface for '+action);
}
const results=[];
for(const action of ['annual_reports','annual_data','answer_evidence']){
  const hero=setup({captureGeometry:true});hero.paintAt(1450);hero.paintAt(7350);
  assert.equal(events(hero).length,0,'autoplay never emits navigation');
  const position=pointFor(hero,action),api=hero.context.__qmImmersiveHero;
  assert.equal(api.hitTest(1,79),null,'empty canvas space is not a hit');
  hero.get('sculpture-stage').emit('pointermove',{clientX:position.x,clientY:position.y});
  assert.equal(state(hero).navigation.hovered,action);
  assert.equal(hero.get('hero-object-label').hidden,false);
  assert.match(hero.get('hero-object-label').textContent,/查阅|查看|打开/);
  const before=state(hero).showTime;
  const modelsBefore=hero.geometryDraws.filter(item=>item.indexed).map(item=>item.model);
  hero.get('sculpture-stage').emit('click',{clientX:position.x,clientY:position.y,button:0});
  assert.equal(events(hero).length,1,'navigation dispatches before the parallel selection animation');
  assert.equal(hero.posts.filter(message=>message.type==='qm:portal-intent').length,1);
  hero.paintAt(7540);
  assert.ok(state(hero).selection.lift>.2&&state(hero).selection.scale>1.04,'real GSAP brings the selected physical object forward');
  assert.equal(state(hero).showTime,before,'paper choreography and camera hold during committed selection');
  const modelsAfter=hero.geometryDraws.filter(item=>item.indexed).map(item=>item.model);
  const physicallyMoved=modelsAfter.filter((model,index)=>model.some((value,axis)=>Math.abs(value-modelsBefore[index][axis])>1e-6));
  assert.equal(physicallyMoved.length,{annual_reports:2,annual_data:5,answer_evidence:1}[action],
    'only the selected object group changes its actual WebGL model transform');
  hero.get('sculpture-stage').emit('click',{clientX:position.x,clientY:position.y,button:0});
  hero.paintAt(7800);
  assert.equal(events(hero).length,1,'rapid repeat clicks send exactly one intent');
  assert.equal(events(hero)[0].value.action,action);assert.equal(events(hero)[0].value.context_token,context.token);
  const portal=hero.posts.find(message=>message.type==='qm:portal-intent');
  assert.equal(portal.nonce,events(hero)[0].value.nonce);assert.equal(portal.context_token,context.token);
  assert.ok(portal.rect.left>=0&&portal.rect.top>=0&&portal.rect.left+portal.rect.width<=480&&portal.rect.top+portal.rect.height<=580);
  hero.renderContext(context);hero.paintAt(8000);assert.equal(events(hero).length,1,'same-context rerender does not replay navigation');
  hero.dispose();results.push({action,projected_deformed_hit:true,actual_gsap_selection:true,exactly_one_event:true});
}
// Data changed during the short animation: cancel visuals without replaying the sent intent.
const stale=setup();stale.paintAt(1450);stale.paintAt(7350);const point=pointFor(stale,'annual_reports');
stale.get('sculpture-stage').emit('click',{clientX:point.x,clientY:point.y});stale.paintAt(7510);
stale.renderContext({...context,token:'other-company'});stale.paintAt(8000);assert.equal(events(stale).length,1);assert.equal(events(stale)[0].value.context_token,context.token);assert.equal(state(stale).navigation.pending,null);stale.dispose();
for(const options of [{osReduced:true},{webgl:false}]){
  const hero=setup(options),link=hero.get('hero-link-annual_data');
  link.emit('focus');assert.equal(state(hero).navigation.focused,'annual_data');
  link.emit('click',{preventDefault(){},button:0});assert.equal(events(hero).length,1);
  assert.equal(events(hero)[0].value.action,'annual_data');hero.dispose();
}
const missing=component({navigation:true,gsap});missing.render('presentation');missing.paintAt(0);
missing.get('hero-link-annual_reports').emit('click',{preventDefault(){}});assert.equal(events(missing).length,0);missing.dispose();
// Hidden time pauses the decorative movement; navigation was already sent once.
const hidden=setup();hidden.paintAt(1450);hidden.paintAt(7350);
hidden.get('hero-link-annual_reports').emit('click',{preventDefault(){},button:0});hidden.paintAt(7500);
hidden.doc.hidden=true;hidden.doc.emit('visibilitychange');hidden.paintAt(20000);
assert.equal(events(hidden).length,1);assert.equal(hidden.frames.size,0);
hidden.doc.hidden=false;hidden.doc.emit('visibilitychange');hidden.paintAt(20001);
assert.equal(events(hidden).length,1);hidden.paintAt(20431);assert.equal(events(hidden).length,1);hidden.dispose();
// A lost graphics context still honors the already-explicit action exactly once.
const lost=setup();lost.paintAt(1450);lost.paintAt(7350);
lost.get('hero-link-answer_evidence').emit('click',{preventDefault(){},button:0});lost.paintAt(7400);
lost.get('sculpture').emit('webglcontextlost',{preventDefault(){}});
assert.equal(events(lost).length,1);lost.get('sculpture').emit('webglcontextlost',{preventDefault(){}});
assert.equal(events(lost).length,1);lost.dispose();
// Real DOM anchor semantics, focus, Space activation and safe label handling.
const html=fs.readFileSync(path.join(__dirname,'../app/hero_frontend/index.html'),'utf8');
const dom=new JSDOM(html,{url:'http://localhost:8504/component/app.hero_visual.qm_immersive_hero/index.html',runScripts:'outside-only'});
dom.window.eval(fs.readFileSync(path.join(__dirname,'../app/hero_frontend/hero-navigation.js'),'utf8'));
const cleanups=[],received=[];
const nav=dom.window.QMHeroNavigation.createNavigation({document:dom.window.document,shell:dom.window.document.getElementById('hero'),
  listen(node,event,callback){node.addEventListener(event,callback);cleanups.push(()=>node.removeEventListener(event,callback));},
  cancel(){},onHover(){},intent(){},begin(action,done){done();},emit(event){received.push(event);}});
nav.setContext({...context,company:'<img src=x onerror=alert(1)>',has_answer:false});
const link=dom.window.document.getElementById('hero-link-answer_evidence');link.focus();
assert.equal(dom.window.document.activeElement,link);assert.equal(nav.getState().focused,'answer_evidence');
assert.match(link.getAttribute('aria-label'),/从一个财务问题开始/);assert.equal(dom.window.document.querySelectorAll('img').length,0);
link.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true}));
assert.equal(received.length,1);assert.equal(received[0].action,'answer_evidence');
nav.dispose();cleanups.forEach(fn=>fn());dom.window.close();
assert.equal(gsap.globalTimeline.getChildren(true,true,true).length,0);
console.log(JSON.stringify({passed:true,results,stale_context_canceled:true,reduced_and_webgl_fallback:true,hidden_selection:true,graphics_loss_selection:true,real_dom_keyboard:true,cleanup:true}));
