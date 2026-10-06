/* Isolated animation clock. It has no access to Streamlit or financial data. */
(function (global) {
  'use strict';
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const ease=t=>1-Math.pow(1-clamp(t,0,1),4);
  function createRuntime(env, draw, notify) {
    let frame=0, disposed=false, visible=true, healthy=true, reduced=!!env.reduced;
    let stage=1, expanded=true, from=1, target=1, value=1, open=0, openFrom=0, openTarget=1;
    let start=env.now(), clock=0, last=0, dirty=true, px=0,py=0, tx=0,ty=0;
    const running=()=>!disposed&&visible&&healthy&&!env.hidden();
    function paint(now) {
      frame=0;
      if(!running())return;
      const delta=last?Math.min(40,Math.max(0,now-last)):16;last=now;
      if(!reduced)clock+=delta;
      const progress=reduced?1:ease((now-start)/1450);
      value=from+(target-from)*progress;open=openFrom+(openTarget-openFrom)*progress;
      const pointerBlend=reduced?1:1-Math.exp(-delta/135);
      px+=(tx-px)*pointerBlend;py+=(ty-py)*pointerBlend;
      draw({stage:value,open,pointer:[reduced?0:px,reduced?0:py],time:reduced?0:clock/1000,reduced});
      dirty=false;
      if(!reduced&&running())frame=env.raf(paint);
    }
    function request() {if(running()&&!frame&&(dirty||!reduced))frame=env.raf(paint);}
    function stop() {if(frame)env.cancel(frame);frame=0;last=0;}
    function change(nextStage,nextOpen) {
      if(disposed)return;
      const bounded=clamp(Math.round(nextStage),0,2);
      if(bounded===stage&&nextOpen===expanded)return;
      from=value;openFrom=open;stage=bounded;target=stage;expanded=nextOpen;openTarget=expanded?1:0;
      start=env.now();dirty=true;notify({stage,expanded,reduced});request();
    }
    const api={
      setStage(next){if(Number.isFinite(next))change(next,true);},
      toggle(){change(stage,!expanded);},
      pointer(x,y){if(disposed||reduced)return;tx=clamp(x,-1,1);ty=clamp(y,-1,1);dirty=true;request();},
      setVisible(next){visible=!!next;if(!visible)stop();else{dirty=true;request();}},
      setHealthy(next){healthy=!!next;if(!healthy)stop();else{dirty=true;request();}},
      setReduced(next){reduced=!!next;stop();dirty=true;notify({stage,expanded,reduced});request();},
      invalidate(){if(disposed)return;dirty=true;request();},
      syncVisibility(){if(!running())stop();else{dirty=true;request();}},
      getState(){return {stage,expanded,reduced,visible,healthy,disposed,frame};},
      dispose(){disposed=true;stop();},
    };
    notify({stage,expanded,reduced});request();return api;
  }
  global.QMHeroRuntime={createRuntime,clamp};
})(typeof window!=='undefined'?window:globalThis);
