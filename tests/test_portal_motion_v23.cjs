'use strict';
// Real local GSAP / real JSDOM events. Only screen geometry and app scan timing
// are deterministic; neither routing nor native business DOM is replaced.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const source=read('portal_motion.js');
function fixture({engine=true,bodyless=false}={}){
  const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(String(e)));
  const dom=new JSDOM('<!doctype html><html><body><main data-testid="stMainBlockContainer"><h1>比亚迪 · 2024</h1><p>营业收入 7,771.02 亿元</p><input value="财报问题"><button>开始分析</button></main></body></html>',
    {url:'http://127.0.0.1:8504/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
  const win=dom.window,doc=win.document,queue=new Map(),timelines=[],listeners=new Set();let number=0,hidden=false;
  Object.defineProperty(doc,'hidden',{get:()=>hidden});
  win.innerWidth=1366;win.innerHeight=768;
  const media={matches:false,addEventListener:(_,f)=>listeners.add(f),removeEventListener:(_,f)=>listeners.delete(f)};win.matchMedia=()=>media;
  win.HTMLElement.prototype.getBoundingClientRect=function(){return this._rect||{left:270,top:90,right:1325,bottom:740,width:1055,height:650};};
  if(engine){win.eval(read('vendor/gsap/gsap.min.js'));const real=win.gsap.timeline;win.gsap.timeline=function(...args){const tl=real.apply(this,args);timelines.push(tl);return tl;};}
  win.requestAnimationFrame=cb=>{queue.set(++number,cb);return number;};win.cancelAnimationFrame=id=>queue.delete(id);
  if(bodyless)doc.body.remove();
  win.eval(source);const api=win.QMPortalMotion;
  function hero(src='/component/app.hero_visual.qm_immersive_hero/index.html?streamlitUrl=http%3A%2F%2F127.0.0.1%3A8504%2F'){
    const node=doc.createElement('iframe');
    // Preserve the actual browser URL, including index.html and its query.
    node.src=src;node._rect={left:780,top:170,right:1320,bottom:750,width:540,height:580};doc.body.append(node);
    return node;
  }
  function context(token='context-2024'){const node=doc.createElement('span');node.hidden=true;node.dataset.portalContext=token;doc.body.append(node);return node;}
  function emit(iframe,overrides={},eventOverrides={}){
    const data={type:'qm:portal-intent',action:'annual_reports',nonce:'intent-1',context_token:'context-2024',
      rect:{left:55,top:110,width:310,height:360},label:'untrusted <img onerror="x">',...overrides};
    win.dispatchEvent(new win.MessageEvent('message',{data,source:iframe.contentWindow,origin:'http://127.0.0.1:8504',...eventOverrides}));
  }
  function arrival(nonce='intent-1',action='annual_reports'){
    const marker=doc.createElement('span');marker.hidden=true;Object.assign(marker.dataset,{portalArrival:'',portalNonce:nonce,portalAction:action});doc.body.append(marker);return marker;
  }
  async function flush(){for(let i=0;i<3;i++){await Promise.resolve();const calls=[...queue.values()];queue.clear();calls.forEach(f=>f(0));timelines.forEach(tl=>tl.pause());}}
  function reduced(value){media.matches=value;listeners.forEach(f=>f());}
  function mode(value){doc.documentElement.dataset.qmMotionMode=value;win.dispatchEvent(new win.Event('qm-motion-preference-change'));}
  function visibility(value){hidden=value;doc.dispatchEvent(new win.Event('visibilitychange'));}
  function cleanup(){api.dispose();win.QMPortalMotion?.dispose();win.gsap?.globalTimeline.clear();win.gsap?.ticker.sleep();win.close();}
  return {win,doc,api,hero,context,emit,arrival,flush,reduced,mode,visibility,timelines,listeners,errors,cleanup};
}
const tests=[];function test(name,fn){tests.push({name,fn});}
test('legacy component-name URLs remain accepted with the same origin and source checks',async()=>{
  for(const src of ['/component/app.hero_visual.qm_immersive_hero','/component/app.hero_visual.qm_immersive_hero/?streamlitUrl=http%3A%2F%2F127.0.0.1%3A8504']){
    const f=fixture();try{
      const h=f.hero(src);f.context();await f.flush();assert.equal(f.api.getState().frames,1);
      f.emit(h,{}, {origin:'https://evil.example'});f.emit(h,{}, {source:f.win});assert.equal(f.api.getState().starts,0);
      f.emit(h);assert.equal(f.api.getState().starts,1);
    }finally{f.cleanup();}
  }
});
test('component lookalikes, unrelated prefixes and extra path suffixes remain rejected',async()=>{
  const f=fixture();try{
    f.context();const paths=[
      '/component/app.hero_visual.qm_immersive_hero_fake/index.html',
      '/component/app.hero_visual.qm_immersive_hero/index.html.bak',
      '/component/app.hero_visual.qm_immersive_hero/index.html/extra',
      '/component/app.hero_visual.qm_immersive_hero/extra',
      '/fake/component/app.hero_visual.qm_immersive_hero/index.html',
      '/component/app.hero_visual.not_qm_immersive_hero/index.html?streamlitUrl=http%3A%2F%2F127.0.0.1%3A8504'];
    for(const src of paths){const h=f.hero(src);await f.flush();f.emit(h);}
    assert.equal(f.api.getState().frames,0);assert.equal(f.api.getState().starts,0);assert.equal(f.api.getState().rejected,paths.length);
  }finally{f.cleanup();}
});
test('authenticated hero flight lands only on its real arrival marker without touching native values',async()=>{
  const f=fixture();try{
    const h=f.hero();f.context();await f.flush();const native=f.doc.querySelector('main'),html=native.innerHTML,input=native.querySelector('input');input.focus();
    f.emit(h);await f.flush();assert.equal(f.api.getState().starts,1);const overlay=f.doc.querySelector('.qm-portal-flight');
    assert.ok(overlay);assert.equal(overlay.getAttribute('aria-hidden'),'true');assert.ok(overlay.hasAttribute('inert'));assert.equal(overlay.querySelector('img'),null);
    assert.equal(overlay.querySelector('strong').textContent,'年度报告');const paper=overlay.querySelector('.qm-portal-sheet:not(.qm-portal-underlay)');
    f.timelines[0].progress(.5);assert.match(paper.style.transform,/translate/);assert.equal(f.api.getState().arrivals,0);
    f.arrival('wrong');f.timelines[0].progress(1);await f.flush();assert.equal(f.api.getState().running,1);assert.equal(f.api.getState().arrivals,0);
    f.arrival();await f.flush();assert.equal(f.api.getState().arrivals,1);f.timelines.at(-1).progress(1);assert.equal(f.api.getState().running,0);assert.equal(f.doc.querySelector('.qm-portal-flight'),null);
    assert.equal(native.innerHTML,html);assert.equal(f.doc.activeElement,input);assert.equal(input.value,'财报问题');
    for(const el of [native,...native.querySelectorAll('*')]){assert.equal(el.style.transform,'');assert.equal(el.style.opacity,'');assert.equal(f.win.gsap.getTweensOf(el).length,0);}
    f.emit(h);await f.flush();assert.equal(f.api.getState().starts,1,'Repeated component value cannot replay flight.');assert.deepEqual(f.errors,[]);
  }finally{f.cleanup();}
});

test('landing entry survives iframe removal and keeps both GSAP paths behind ready content',async()=>{
  const f=fixture();try{
    const h=f.hero(),context=f.context('landing-visit-25');await f.flush();
    const native=f.doc.querySelector('main'),original=native.innerHTML,input=native.querySelector('input');input.focus();
    f.emit(h,{action:'enter_workspace',nonce:'landing-enter-25',context_token:'landing-visit-25'});await f.flush();
    const overlay=f.doc.querySelector('.qm-portal-flight'),paper=overlay.querySelector('.qm-portal-sheet:not(.qm-portal-underlay)'),opening=f.timelines[0];
    assert.equal(overlay.querySelector('strong').textContent,'进入研究空间');assert.equal(opening.duration(),.4);
    opening.progress(.1);const transform=paper.style.transform;
    // The native rerun removes its outgoing iframe before publishing arrival.
    h.remove();context.remove();await f.flush();assert.equal(f.api.getState().frames,0);assert.equal(f.api.getState().running,1);
    f.arrival('landing-enter-25','annual_reports');await f.flush();assert.equal(f.api.getState().arrivals,0,'nonce alone cannot match a different business action');
    const marker=f.arrival('landing-enter-25','enter_workspace');await f.flush();
    assert.equal(f.api.getState().arrivals,1,'ready content is recognized before the opening has finished');
    assert.equal(overlay.dataset.ready,'true');assert.equal(Number(overlay.style.opacity),.18,'ready text is not covered by the .68-opacity full-size paper');
    assert.equal(f.timelines.length,1,'fast arrival preserves the remaining physical opening');
    marker.remove();f.win.eval(source);await f.flush();assert.equal(f.win.QMPortalMotion,f.api);
    opening.progress(.6);assert.notEqual(paper.style.transform,transform,'the original paper trajectory continues after readiness and iframe removal');
    opening.progress(1);await f.flush();assert.equal(f.api.getState().arrivals,1);assert.equal(f.timelines.at(-1).duration(),.42,'the original landing also remains');
    f.timelines.at(-1).progress(1);assert.equal(f.api.getState().running,0);assert.equal(f.doc.querySelector('.qm-portal-flight'),null);
    assert.equal(native.innerHTML,original);assert.equal(f.doc.activeElement,input);assert.equal(f.win.gsap.getTweensOf(input).length,0);
    assert.deepEqual(f.errors,[]);
  }finally{f.cleanup();}
});

test('every fast destination lowers overlay opacity without skipping opening or accepting stale arrivals',async()=>{
  for(const action of ['annual_reports','annual_data','answer_evidence','enter_workspace']){
    const f=fixture();try{
      const h=f.hero();f.context();await f.flush();f.emit(h,{action});await f.flush();
      f.timelines[0].progress(.05);f.arrival('old-nonce',action);await f.flush();
      assert.equal(f.api.getState().arrivals,0);assert.equal(f.doc.querySelector('.qm-portal-flight').dataset.ready,undefined);
      f.arrival('intent-1',action);await f.flush();assert.equal(f.api.getState().arrivals,1);
      const overlay=f.doc.querySelector('.qm-portal-flight');assert.equal(Number(overlay.style.opacity),.18);assert.equal(f.timelines.length,1);
      f.timelines[0].progress(1);await f.flush();f.timelines.at(-1).progress(1);assert.equal(f.api.getState().running,0);
    }finally{f.cleanup();}
  }
});

test('landing visit context and detached frame identity remain required for a new visual intent',async()=>{
  const f=fixture();try{
    const previous=f.hero();f.context('landing-visit-old');await f.flush();
    const oldSource=previous.contentWindow;previous.remove();const current=f.hero();f.context('landing-visit-new');await f.flush();
    const request={action:'enter_workspace',nonce:'landing-new',context_token:'landing-visit-new'};
    f.emit(current,request,{source:oldSource});f.emit(current,{...request,context_token:'landing-visit-old'});
    assert.equal(f.api.getState().starts,0);assert.equal(f.api.getState().rejected,2);
    f.emit(current,request);await f.flush();assert.equal(f.api.getState().starts,1);
    f.arrival('landing-old','enter_workspace');await f.flush();assert.equal(f.api.getState().arrivals,0);
    f.emit(current,request);assert.equal(f.api.getState().starts,1,'a duplicate landing request cannot replay');
  }finally{f.cleanup();}
});
test('untrusted origin/source/path/context/action/nonce and nonfinite or out-of-frame rectangles are rejected',async()=>{
  const f=fixture();try{
    const h=f.hero(),other=f.hero('/component/other.qm_immersive_hero_fake');f.context();await f.flush();
    f.emit(h,{}, {origin:'https://evil.example'});f.emit(h,{}, {source:f.win});f.emit(other);
    f.emit(h,{context_token:'wrong'});f.emit(h,{action:'delete_data'});f.emit(h,{action:'__proto__'});f.emit(h,{nonce:'<img>'});
    f.emit(h,{rect:{left:0,top:0,width:Infinity,height:200}});f.emit(h,{rect:{left:-1,top:0,width:300,height:200}});
    f.emit(h,{rect:{left:0,top:0,width:900,height:200}});f.emit(h,{rect:{left:400,top:0,width:200,height:200}});
    f.emit(h,{rect:{left:0,top:500,width:200,height:200}});await f.flush();assert.equal(f.api.getState().starts,0);assert.equal(f.api.getState().rejected,12);
    h.src='https://evil.example/component/app.hero_visual.qm_immersive_hero';await f.flush();f.emit(h);assert.equal(f.api.getState().starts,0);
  }finally{f.cleanup();}
});
test('rapid next selection cancels only owned artwork and stale arrivals cannot finish the next route',async()=>{
  const f=fixture();try{
    const h=f.hero();f.context();await f.flush();f.emit(h);f.timelines[0].pause().progress(.4);
    f.emit(h,{nonce:'intent-2',action:'annual_data'});await f.flush();assert.equal(f.doc.querySelectorAll('.qm-portal-flight').length,1);assert.equal(f.api.getState().cancelled,1);
    assert.equal(f.doc.querySelector('.qm-portal-flight').dataset.action,'annual_data');f.arrival();f.timelines.at(-1).progress(1);await f.flush();assert.equal(f.api.getState().arrivals,0);
    f.arrival('intent-2','annual_data');await f.flush();assert.equal(f.api.getState().arrivals,1);f.timelines.at(-1).progress(1);assert.equal(f.api.getState().running,0);
  }finally{f.cleanup();}
});
test('visibility, reduced preference and research mode cancel and do not replay later',async()=>{
  for(const ready of [false,true])for(const cancel of [f=>f.visibility(true),f=>f.reduced(true),f=>f.mode('research')]){
    const f=fixture();try{
      const h=f.hero();f.context();await f.flush();f.emit(h);if(ready){f.arrival();await f.flush();}cancel(f);assert.equal(f.api.getState().running,0);assert.equal(f.doc.querySelector('.qm-portal-flight'),null);
      f.visibility(false);f.reduced(false);f.mode('presentation');await f.flush();assert.equal(f.api.getState().starts,1);f.emit(h);assert.equal(f.api.getState().starts,1);
    }finally{f.cleanup();}
  }
});
test('initial quiet modes and missing engine keep native navigation independent',async()=>{
  for(const action of ['annual_reports','enter_workspace'])for(const [engine,quiet] of [[true,f=>f.reduced(true)],[true,f=>f.mode('research')],[true,f=>f.visibility(true)],[false,()=>{}]]){
    const f=fixture({engine});try{const h=f.hero();f.context();await f.flush();quiet(f);f.emit(h,{action});assert.equal(f.api.getState().starts,0);assert.equal(f.doc.querySelector('.qm-portal-flight'),null);}finally{f.cleanup();}
  }
});
test('slow or unsuccessful navigation times out and never invents an arrival',async()=>{
  const f=fixture();try{const h=f.hero();f.context();await f.flush();f.emit(h);await new Promise(r=>setTimeout(r,1850));assert.equal(f.api.getState().running,0);assert.equal(f.api.getState().arrivals,0);assert.equal(f.doc.querySelector('.qm-portal-flight'),null);}finally{f.cleanup();}
});
test('remount and duplicate bootstrap reuse one controller; disposal cleans listeners and overlay',async()=>{
  const f=fixture({bodyless:true});try{
    await f.flush();assert.equal(f.api.getState().frames,0);const body=f.doc.createElement('body');f.doc.documentElement.append(body);const h=f.hero();f.context();await f.flush();
    f.win.eval(source);await f.flush();assert.equal(f.win.QMPortalMotion,f.api);assert.equal(f.listeners.size,1);f.emit(h);assert.equal(f.api.getState().running,1);
    f.api.dispose();assert.equal(f.api.getState().running,0);assert.equal(f.listeners.size,0);assert.equal(f.doc.querySelector('.qm-portal-flight'),null);
    f.emit(h,{nonce:'later'});assert.equal(f.api.getState().starts,1);assert.deepEqual(f.errors,[]);
  }finally{f.cleanup();}
});
(async()=>{for(const {name,fn} of tests){await fn();process.stdout.write('PASS '+name+'\n');}process.stdout.write(JSON.stringify({passed:tests.length,failed:0})+'\n');})().catch(e=>{console.error(e);process.exitCode=1;});
