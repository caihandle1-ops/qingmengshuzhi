'use strict';
// Real local GSAP, deterministic native-widget geometry. This is not a pixel/FPS test.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const source=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const markup=`<main data-testid="stMain">
  <section class="st-key-qa_composer" data-rect="10,10,1000,250">
    <label for="question">自然语言问题</label><input id="question" value="2024年净利润 -123.45 与 0" />
    <div class="st-key-qa_submit" data-testid="stButton"><button data-testid="stBaseButton-primary" aria-label="开始分析">开始分析<span data-testid="stIconMaterial" aria-hidden="true">arrow_outward</span></button></div>
  </section>
  <section class="st-key-qa_suggestions" data-rect="10,300,900,90">
    <div class="st-key-recommended_0" data-testid="stButton"><button data-rect="10,300,400,80" data-testid="stBaseButton-secondary">营收趋势</button></div>
    <div class="st-key-recommended_1" data-testid="stButton"><button data-rect="430,300,480,80" data-testid="stBaseButton-secondary" disabled>利润变化</button></div>
  </section>
  <section class="st-key-guided_picker_scope" data-rect="10,420,900,90">
    <div class="st-key-guided_card_scope_0" data-testid="stButton"><button data-rect="10,420,400,80" kind="primary">核验结果</button></div>
    <div class="st-key-guided_card_scope_1" data-testid="stButton"><button data-rect="430,420,480,80" kind="secondary">来源明细</button></div>
  </section>
  <div data-testid="stButton"><button id="ordinary" data-rect="10,650,400,80">普通操作</button></div>
</main>`;
const dom=new JSDOM(`<!doctype html><html><body>${markup}</body></html>`,{runScripts:'outside-only',pretendToBeVisual:true});
const win=dom.window,doc=win.document,listeners=new Set(),observers=[],errors=[];
const media={matches:false,addEventListener:(_,fn)=>listeners.add(fn),removeEventListener:(_,fn)=>listeners.delete(fn)};
const fine={matches:true,addEventListener(){},removeEventListener(){}};
win.matchMedia=query=>query.includes('prefers-reduced-motion')?media:fine;
win.addEventListener('error',event=>errors.push(event.error));
win.IntersectionObserver=class{constructor(fn){this.callback=fn;this.nodes=new Set();observers.push(this);}observe(node){this.nodes.add(node);}unobserve(node){this.nodes.delete(node);}disconnect(){this.nodes.clear();}};
win.HTMLElement.prototype.getBoundingClientRect=function(){
  const [left,top,width,height]=String(this.dataset.rect||'10,10,180,52').split(',').map(Number);
  return {x:left,y:top,left,top,width,height,right:left+width,bottom:top+height,toJSON(){return this;}};
};
const oldAnimations=[];
win.HTMLElement.prototype.animate=function(frames,options){
  let resolve;const animation={node:this,frames,options,finished:new Promise(done=>{resolve=done;}),cancel(){resolve();}};
  oldAnimations.push(animation);win.setTimeout(()=>resolve(),options.duration||0);return animation;
};
const pointer=(node,name,relatedTarget=null)=>node.dispatchEvent(new win.MouseEvent(name,{bubbles:true,button:0,clientX:100,clientY:100,relatedTarget}));
const readLine=node=>{
  const line=node.querySelector('.qm-ui-active-line'),match=line.style.transform.match(/translate\(([-.\d]+)px, ([-.\d]+)px\) scaleX\(([-.\d]+)\)/);
  return {line,x:Number(match?.[1]||0),y:Number(match?.[2]||0),width:Number(match?.[3]||1),opacity:Number(line.style.opacity||0)};
};
win.eval(source('vendor/gsap/gsap.min.js'));win.eval(source('feature_workflow.js'));
(async()=>{
  await delay(60);
  const api=win.QMFeatureWorkflow,composer=doc.querySelector('.st-key-qa_composer'),input=doc.querySelector('input'),submit=doc.querySelector('.st-key-qa_submit button');
  let shortcuts=doc.querySelector('.st-key-qa_suggestions'),[revenue,profit]=shortcuts.querySelectorAll('button');
  const guided=doc.querySelector('.st-key-guided_picker_scope'),[summary,sourceButton]=guided.querySelectorAll('button');
  assert.equal(api.getState().hosts,3);assert.equal(api.getState().buttons,5);assert.equal(api.getState().rules,2);
  assert.equal(composer.dataset.qmUiReady,'true');assert.equal(readLine(guided).width,400,'Installed Streamlit kind=primary is recognized.');
  assert.equal(readLine(shortcuts).opacity,0,'No native selection means no invented active state.');
  const content=input.value,label=submit.getAttribute('aria-label');input.focus();await delay(340);
  assert.equal(Number(composer.style.getPropertyValue('--qm-ui-focus')),1);assert.equal(doc.activeElement,input);
  assert.equal(input.value,content);assert.equal(input.style.cssText,'');assert.equal(composer.style.transform,'');
  pointer(submit,'pointerover');await delay(65);const rising=Number(submit.style.getPropertyValue('--qm-ui-hover'));
  assert.ok(rising>0&&rising<1);pointer(submit,'pointerout');await delay(350);
  assert.equal(Number(submit.style.getPropertyValue('--qm-ui-hover')),0,'Rapid leave reverses from the current pose and settles.');
  assert.equal(submit.style.transform,'');assert.equal(submit.getAttribute('aria-label'),label);assert.equal(win.gsap.getTweensOf(input).length,0);
  pointer(profit,'pointerover');await delay(45);assert.equal(Number(profit.style.getPropertyValue('--qm-ui-hover')||0),0,'Disabled controls never gain hover feedback.');
  let clicks=0;submit.addEventListener('click',()=>clicks++);submit.click();assert.equal(clicks,1);assert.equal(input.value,content);

  revenue.click();await delay(45);assert.equal(readLine(shortcuts).opacity,0,'Clicks alone never guess business selection.');
  revenue.dataset.testid='stBaseButton-primary';await delay(520);assert.equal(readLine(shortcuts).width,400);assert.equal(readLine(shortcuts).opacity,1);
  profit.disabled=false;revenue.dataset.testid='stBaseButton-secondary';profit.dataset.testid='baseButton-primary';await delay(110);
  const moving=readLine(shortcuts);assert.ok(moving.x>0&&moving.x<420,'Confirmed native selection drives the moving underline.');
  const movingX=moving.x;
  shortcuts.remove();
  const replacement=doc.createElement('section');replacement.className='st-key-qa_suggestions';replacement.dataset.rect='10,300,900,90';
  replacement.innerHTML='<div class="st-key-recommended_0" data-testid="stButton"><button data-rect="10,300,400,80" data-testid="stBaseButton-primary">营收趋势</button></div><div class="st-key-recommended_1" data-testid="stButton"><button data-rect="430,300,480,80" data-testid="stBaseButton-secondary">利润变化</button></div>';
  guided.before(replacement);shortcuts=replacement;[revenue,profit]=shortcuts.querySelectorAll('button');await delay(45);
  assert.ok(readLine(shortcuts).x>=0&&readLine(shortcuts).x<=movingX+30,'A rapid replacement starts from the rendered pose, not the discarded target.');
  await delay(520);assert.equal(readLine(shortcuts).x,0);assert.equal(doc.querySelectorAll('.qm-ui-active-line').length,2);
  const same=shortcuts.cloneNode(true);same.querySelector('.qm-ui-active-line').remove();shortcuts.replaceWith(same);shortcuts=same;[revenue,profit]=same.querySelectorAll('button');await delay(70);
  assert.equal(api.getState().running,0,'Same-selection native rerun cannot replay an entrance.');assert.equal(doc.querySelectorAll('.qm-ui-active-line').length,2);
  const originalApi=api;win.eval(source('feature_workflow.js'));assert.equal(win.QMFeatureWorkflow,originalApi);

  summary.setAttribute('kind','secondary');sourceButton.setAttribute('kind','primary');await delay(80);
  media.matches=true;listeners.forEach(fn=>fn());assert.equal(api.getState().running,0);assert.equal(readLine(guided).x,420);
  pointer(submit,'pointerover');assert.equal(Number(submit.style.getPropertyValue('--qm-ui-hover')),1,'Reduced motion keeps readable immediate interaction state.');
  assert.equal(api.getState().running,0);media.matches=false;listeners.forEach(fn=>fn());
  pointer(submit,'pointerout');await delay(60);Object.defineProperty(doc,'hidden',{value:true,configurable:true});doc.dispatchEvent(new win.Event('visibilitychange'));
  assert.equal(api.getState().running,0);assert.equal(Number(submit.style.getPropertyValue('--qm-ui-hover')),0);assert.equal(input.value,content);
  Object.defineProperty(doc,'hidden',{value:false,configurable:true});doc.dispatchEvent(new win.Event('visibilitychange'));
  pointer(submit,'pointerover');await delay(40);observers[0].callback([{target:composer,isIntersecting:false}]);
  assert.equal(Number(submit.style.getPropertyValue('--qm-ui-hover')),0);assert.equal(api.getState().running,0,'Offscreen interaction tweens settle.');
  observers[0].callback([{target:composer,isIntersecting:true}]);

  win.eval(source('motion.js'));await delay(45);
  pointer(submit,'pointerdown');pointer(sourceButton,'pointermove');submit.click();await delay(25);
  assert.equal(doc.querySelectorAll('.qm-motion-ripple,.qm-motion-sheen').length,0,'New controls have one decorative owner.');assert.equal(clicks,2);
  assert.equal(input.value,content);assert.equal(doc.activeElement,input,'Interaction never steals input focus.');
  pointer(doc.querySelector('#ordinary'),'pointerdown');assert.equal(doc.querySelectorAll('.qm-motion-ripple').length,1,'Unrelated native controls retain their existing feedback.');
  win.__qingmengMotion.dispose();
  doc.querySelector('main').remove();await delay(60);assert.equal(api.getState().hosts,0);assert.equal(api.getState().buttons,0);assert.equal(api.getState().running,0);
  api.dispose();assert.equal(listeners.size,0);assert.equal(composer.dataset.qmUiReady,undefined);assert.equal(submit.dataset.qmUiButton,undefined);
  assert.equal(submit.style.getPropertyValue('--qm-ui-hover'),'');assert.equal(composer.style.getPropertyValue('--qm-ui-focus'),'');assert.deepEqual(errors,[]);
  win.gsap.ticker.sleep();dom.window.close();

  const fallback=new JSDOM(`<!doctype html><body>${markup}</body>`,{runScripts:'outside-only',pretendToBeVisual:true});
  fallback.window.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
  fallback.window.eval(source('feature_workflow.js'));await delay(35);
  assert.equal(fallback.window.document.querySelectorAll('[data-qm-ui-ready],[data-qm-ui-button],.qm-ui-active-line').length,0,'Missing GSAP leaves authored native controls intact.');
  assert.equal(fallback.window.document.querySelector('input').value,content);fallback.window.QMFeatureWorkflow.dispose();fallback.window.close();
  console.log('editorial controls: real GSAP focus/hover, native confirmed selections, continuous rerenders, single decoration owner, reduced/hidden/offscreen state and cleanup passed');
})().catch(error=>{win.QMFeatureWorkflow?.dispose();win.__qingmengMotion?.dispose();win.gsap?.ticker.sleep();dom.window.close();console.error(error);process.exitCode=1;});
