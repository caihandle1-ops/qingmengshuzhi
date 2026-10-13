/* Confirmed business state triggers inert artwork. No value or native widget moves. */
(function(win){
  'use strict';
  const VERSION='committed-motion-20261011-22',doc=win.document;
  if(win.QMCommittedMotion?.version===VERSION){win.QMCommittedMotion.refresh();return;}
  win.QMCommittedMotion?.dispose();
  const abort=new win.AbortController(),media=win.matchMedia('(prefers-reduced-motion: reduce)');
  const running=new Map(),years=new Map(),pending=new Map();
  let frame=0,disposed=false,starts=0;
  const quiet=()=>disposed||doc.hidden||media.matches||doc.documentElement.dataset.qmMotionMode==='research';
  const ready=()=>!quiet()&&typeof win.gsap?.timeline==='function';
  const visible=node=>{const r=node.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<win.innerHeight;};
  function finish(node){const record=running.get(node);if(!record)return;running.delete(node);record.context.revert();record.done?.();}
  function run(node,build,done){
    if(!ready()||!node?.isConnected)return null;
    finish(node);
    const context=win.gsap.context(()=>{},node),record={context,done};running.set(node,record);
    context.add(()=>{record.timeline=win.gsap.timeline({paused:true,defaults:{ease:'power3.out'},onComplete:()=>finish(node)});build(record.timeline);});
    starts++;record.timeline.play();return {cancel:()=>{if(running.get(node)===record)finish(node);}};
  }
  function annual(node){
    const sheets=[...node.querySelectorAll('[data-commit-art]')];
    if(!sheets.length)return;
    // These strips sit behind the opaque financial panel: no data is hidden.
    run(node,tl=>{
      tl.addLabel('turn').fromTo(sheets,{xPercent:-120,rotation:-12,opacity:0},
        {xPercent:0,rotation:0,opacity:1,duration:.72,stagger:.09},'turn');
      tl.to(sheets,{xPercent:135,opacity:0,duration:.64,stagger:.06,ease:'power2.inOut'},'turn+=.62');
    });
  }
  function report(stage){
    if(!stage?.matches('[data-result-scene="report"][data-result-id]'))return false;
    const pieces=[...stage.querySelectorAll('.deep-report-paper > [data-result-piece]')];
    const front=stage.querySelector('.deep-report-paper-front');
    if(!front||!pieces.length||!ready())return false;
    return Boolean(run(stage,tl=>{
      tl.addLabel('gather').from(pieces,{x:i=>i?130:-115,y:i=>i?-75:110,rotation:i=>i?32:-28,
        scale:.72,opacity:0,duration:.95,stagger:.13},'gather');
      tl.from(front,{y:105,x:45,rotation:-16,scale:.74,opacity:0,duration:1.1},'gather+=.2');
      const rules=[...front.querySelectorAll('b')];
      if(rules.length)tl.from(rules,{scaleX:0,transformOrigin:'left',duration:.45,stagger:.08},'gather+=.8');
    }));
  }
  function source(paper,from,to,closing,done){
    if(!ready())return null;
    return run(paper,tl=>{
      const x=from.left-to.left,y=from.top-to.top;
      tl.set(paper,{x,y,scaleX:from.width/to.width,scaleY:from.height/to.height,opacity:.92,rotation:0});
      if(closing){
        tl.to(paper,{x:0,y:0,scaleX:1,scaleY:1,rotation:0,opacity:0,duration:.5,ease:'power3.inOut'},0);
      }else{
        // Only a blank paper and source tab travel; the authorized viewer stays fixed.
        tl.addLabel('lift').to(paper,{x:x*.35,y:y*.35-44,scaleX:.76,scaleY:.82,
          rotation:0,opacity:.94,duration:.48,ease:'power2.in'},'lift')
          .addLabel('register').to(paper,{x:0,y:0,scaleX:1,scaleY:1,rotation:0,
          opacity:0,duration:.48,ease:'power3.out'},'register');
      }
      const line=paper.querySelector('i');
      if(line&&!closing)tl.from(line,{scaleX:0,transformOrigin:'left',duration:.48},.2);
    },done);
  }
  function scan(){
    frame=0;if(disposed||!doc.body)return;
    for(const node of [...running.keys()])if(!node.isConnected||quiet())finish(node);
    const nodes=[...doc.querySelectorAll('[data-commit-scope][data-commit-year]')];
    for(const node of nodes){
      const scope=node.dataset.commitScope,value=node.dataset.commitYear;
      if(!scope||!value)continue;
      const previous=years.get(scope);years.delete(scope);years.set(scope,value);
      if(previous!==undefined&&previous!==value)pending.set(scope,{node,value});
      // Reconcile a native remount without interpreting it as another action.
      if(pending.get(scope)?.value===value)pending.get(scope).node=node;
    }
    while(years.size>32)years.delete(years.keys().next().value);
    for(const [scope,change] of pending){
      if(!change.node.isConnected||years.get(scope)!==change.value||quiet()){pending.delete(scope);continue;}
      if(visible(change.node)){pending.delete(scope);annual(change.node);}
    }
  }
  function refresh(){if(!disposed&&!frame)frame=win.requestAnimationFrame(scan);}
  function settle(){pending.clear();for(const node of [...running.keys()])finish(node);refresh();}
  const mutations=new win.MutationObserver(changes=>{
    if(changes.some(change=>change.type==='attributes'||[...change.addedNodes,...change.removedNodes]
      .some(node=>node instanceof win.Element&&(node.matches('[data-commit-scope]')||node.querySelector('[data-commit-scope]')))))refresh();
    for(const node of [...running.keys()])if(!node.isConnected)finish(node);
  });
  mutations.observe(doc,{childList:true,subtree:true,attributes:true,attributeFilter:['data-commit-year','data-commit-scope']});
  doc.addEventListener('scroll',refresh,{capture:true,passive:true,signal:abort.signal});
  doc.addEventListener('visibilitychange',settle,{signal:abort.signal});
  win.addEventListener('qm-motion-preference-change',settle,{signal:abort.signal});
  win.addEventListener('resize',settle,{passive:true,signal:abort.signal});
  media.addEventListener('change',settle);
  const api={version:VERSION,refresh,report,source,getState:()=>({starts,running:running.size,pending:pending.size}),dispose(){
    if(disposed)return;disposed=true;abort.abort();mutations.disconnect();media.removeEventListener('change',settle);
    if(frame)win.cancelAnimationFrame(frame);frame=0;pending.clear();for(const node of [...running.keys()])finish(node);years.clear();
    if(win.QMCommittedMotion===api)delete win.QMCommittedMotion;
  }};
  win.QMCommittedMotion=api;refresh();
})(window);
