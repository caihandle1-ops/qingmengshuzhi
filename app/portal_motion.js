/* A sculpture intent can animate paper; only Python can authorize navigation. */
(function(win){
  'use strict';
  const VERSION='portal-motion-20261011-25-ready',doc=win.document;
  if(win.QMPortalMotion?.version===VERSION){win.QMPortalMotion.refresh();return;}
  win.QMPortalMotion?.dispose();
  const labels={annual_reports:'年度报告',annual_data:'结构化数据',answer_evidence:'答案与依据',enter_workspace:'进入研究空间'};
  const tokenPattern=/^[A-Za-z0-9_-]{1,160}$/;
  const abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
  const frames=new Map(),seen=new Set();
  let disposed=false,frame=0,current=null,starts=0,rejected=0,arrivals=0,cancelled=0;
  const quiet=()=>disposed||doc.hidden||media.matches||doc.documentElement.dataset.qmMotionMode==='research';
  const engineReady=()=>!quiet()&&typeof win.gsap?.timeline==='function'&&typeof win.gsap?.context==='function';
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  function remember(nonce){seen.add(nonce);if(seen.size>100)seen.delete(seen.values().next().value);}
  function finish(reason){
    const record=current;if(!record)return;
    current=null;win.clearTimeout(record.timeout);record.context.revert();record.node.remove();
    if(reason!=='arrived')cancelled++;
  }
  function identifyFrames(){
    for(const [node] of frames)if(!node.isConnected)frames.delete(node);
    for(const node of doc.querySelectorAll('iframe[src]')){
      try{
        const url=new win.URL(node.getAttribute('src'),win.location.href);
        if(url.origin===win.location.origin&&/^\/component\/(?:[A-Za-z0-9_]+\.)*qm_immersive_hero(?:\/index\.html|\/)?$/.test(url.pathname))
          frames.set(node,{source:node.contentWindow,origin:url.origin});
        else frames.delete(node);
      }catch(_){frames.delete(node);}
    }
  }
  function contextMatches(token){
    if(typeof token!=='string'||!tokenPattern.test(token))return false;
    const markers=[...doc.querySelectorAll('[data-portal-context]')];
    return markers.length>0&&markers.at(-1).dataset.portalContext===token;
  }
  function readIntent(event){
    const message=event.data;
    if(!message||message.type!=='qm:portal-intent')return null;
    const found=[...frames].find(([node,identity])=>node.isConnected&&event.source===identity.source&&event.origin===identity.origin);
    if(!found||!Object.prototype.hasOwnProperty.call(labels,message.action)||
       typeof message.nonce!=='string'||!tokenPattern.test(message.nonce)||!contextMatches(message.context_token))return false;
    const rect=message.rect,iframe=found[0],bounds=iframe.getBoundingClientRect();
    if(!rect||!['left','top','width','height'].every(key=>finite(rect[key]))||
       rect.width<4||rect.height<4||rect.left<0||rect.top<0||rect.width>bounds.width+2||rect.height>bounds.height+2||
       rect.left+rect.width>bounds.width+2||rect.top+rect.height>bounds.height+2||bounds.width<4||bounds.height<4)return false;
    const from={left:bounds.left+rect.left,top:bounds.top+rect.top,width:rect.width,height:rect.height};
    if(from.left+from.width<=0||from.left>=win.innerWidth||from.top+from.height<=0||from.top>=win.innerHeight)return false;
    return {action:message.action,nonce:message.nonce,contextToken:message.context_token,from};
  }
  function readingRect(marker){
    // A target is an authored DOM id, never an arbitrary selector supplied by a message.
    const id=marker?.dataset.portalTarget;
    const target=(id?doc.getElementById(id):null)||doc.querySelector('[data-testid="stMainBlockContainer"]')||doc.querySelector('main');
    const bounds=target?.getBoundingClientRect();
    const left=Math.max(16,Math.min(bounds?.left||win.innerWidth*.18,win.innerWidth-120));
    const top=Math.max(85,Math.min(bounds?.top||110,win.innerHeight-120));
    const right=Math.min(win.innerWidth-20,Math.max(left+100,bounds?.right||win.innerWidth-24));
    return {left,top,width:Math.max(100,right-left),height:Math.max(100,Math.min(win.innerHeight-top-24,bounds?.height||win.innerHeight*.72))};
  }
  function element(tag,className,parent){const node=doc.createElement(tag);node.className=className;parent.append(node);return node;}
  function flight(intent){
    finish('replaced');remember(intent.nonce);if(!engineReady()||!doc.body)return;
    const to=readingRect(),node=element('div','qm-portal-flight',doc.body);
    node.setAttribute('aria-hidden','true');node.setAttribute('inert','');node.dataset.action=intent.action;
    const underlay=element('div','qm-portal-sheet qm-portal-underlay',node),paper=element('div','qm-portal-sheet',node);
    for(const item of [underlay,paper]){item.style.width=to.width+'px';item.style.height=to.height+'px';}
    const copy=element('div','qm-portal-copy',paper);
    element('small','',copy).textContent='QINGMENG / RESEARCH';element('strong','',copy).textContent=labels[intent.action];
    const line=element('i','qm-portal-rule',paper);
    const context=win.gsap.context(()=>{},node),record={...intent,node,paper,underlay,context,to,stage:'depart',arrival:null,timeout:0};
    current=record;starts++;
    context.add(()=>{
      const tl=win.gsap.timeline({paused:true,defaults:{ease:'power3.inOut'},onComplete:()=>{
        if(current===record){record.stage='waiting';scanArrival();}
      }});record.timeline=tl;
      const start={x:intent.from.left,y:intent.from.top,scaleX:intent.from.width/to.width,scaleY:intent.from.height/to.height,
        transformOrigin:'0 0',rotation:0,rotationY:0,opacity:.88};
      tl.set([underlay,paper],start,0)
        .to(underlay,{x:to.left+16,y:to.top+13,scaleX:.95,scaleY:.96,rotation:-4,opacity:.32,duration:.38},0)
        .to(paper,{x:to.left,y:to.top,scaleX:.99,scaleY:.99,rotation:0,rotationY:-9,opacity:.68,duration:.4},0)
        .from(line,{scaleX:0,duration:.3,ease:'power2.out'},.1);
      tl.play();
    });
    // A slow/failed navigation can never leave a covering surface behind.
    record.timeout=win.setTimeout(()=>{if(current===record)finish('timeout');},1800);
  }
  function settle(marker){
    const record=current;if(!record||record.stage==='arriving')return;
    record.stage='arriving';win.clearTimeout(record.timeout);record.timeline.kill();
    const to=readingRect(marker),xScale=to.width/record.to.width,yScale=to.height/record.to.height;
    record.context.add(()=>{
      const tl=win.gsap.timeline({paused:true,defaults:{ease:'power3.out'},onComplete:()=>{if(current===record)finish('arrived');}});
      record.timeline=tl;
      tl.to(record.paper,{x:to.left,y:to.top,scaleX:xScale,scaleY:yScale,rotationY:0,opacity:0,duration:.42},0)
        .to(record.underlay,{x:to.left-22,y:to.top-10,scaleX:xScale,scaleY:yScale,rotation:0,opacity:0,duration:.34},0);
      tl.play();
    });
    record.timeout=win.setTimeout(()=>{if(current===record)finish('timeout');},700);
  }
  function scanArrival(){
    if(!current||current.stage==='arriving')return;
    const record=current;
    if(!record.arrival){
      const marker=[...doc.querySelectorAll('[data-portal-arrival]')].find(node=>
        node.dataset.portalNonce===record.nonce&&node.dataset.portalAction===record.action);
      if(!marker)return;
      // Only a matching Python-rendered arrival makes the destination ready.
      // Retain that fact across iframe/marker replacement, without retaining
      // the old DOM. The parent-owned paper can finish both original paths.
      record.arrival={dataset:{portalTarget:marker.dataset.portalTarget}};arrivals++;
      record.node.dataset.ready='true';record.node.style.opacity='.18';
    }
    // Geometry keeps its full opening and landing, at low opacity as soon as
    // content is ready. Native input and reading never wait for this artwork.
    if(record.stage==='waiting')settle(record.arrival);
  }
  function scan(){
    frame=0;if(disposed)return;
    identifyFrames();if(current&&(quiet()||!current.node.isConnected)){finish('inactive');return;}
    scanArrival();
  }
  function schedule(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
  function message(event){
    if(disposed)return;
    identifyFrames();const intent=readIntent(event);if(intent===null)return;
    if(intent===false){rejected++;return;}
    if(seen.has(intent.nonce))return;
    flight(intent);
  }
  const observer=new win.MutationObserver(schedule);
  observer.observe(doc,{childList:true,subtree:true,attributes:true,
    attributeFilter:['src','data-portal-context','data-portal-arrival','data-portal-nonce','data-portal-action','data-qm-motion-mode']});
  win.addEventListener('message',message,{signal:abort.signal});
  doc.addEventListener('visibilitychange',()=>{if(quiet())finish('hidden');else schedule();},{signal:abort.signal});
  win.addEventListener('qm-motion-preference-change',()=>{if(quiet())finish('preference');},{signal:abort.signal});
  win.addEventListener('resize',()=>finish('resize'),{signal:abort.signal});
  win.addEventListener('pagehide',()=>finish('pagehide'),{signal:abort.signal});
  doc.addEventListener('keydown',event=>{if(event.key==='Escape')finish('escape');},{signal:abort.signal});
  const preference=()=>{if(quiet())finish('reduced');};media.addEventListener?.('change',preference);
  const api={version:VERSION,refresh:schedule,getState:()=>({starts,rejected,arrivals,cancelled,running:current?1:0,frames:frames.size}),
    dispose(){if(disposed)return;disposed=true;finish('dispose');abort.abort();observer.disconnect();
      media.removeEventListener?.('change',preference);if(frame)win.cancelAnimationFrame(frame);frame=0;frames.clear();seen.clear();}};
  win.QMPortalMotion=api;schedule();
})(window);
