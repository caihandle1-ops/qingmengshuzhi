/* Isolated illustration clock. No Streamlit values or financial inputs. */
(function (global) {
  'use strict';
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const ease=t=>1-Math.pow(1-clamp(t,0,1),4);
  const ACT_MS=4200, DURATION=ACT_MS*3, LAYERS=9;
  const blend=(from,to,amount)=>from.map((value,index)=>value+(to[index]-value)*amount);
  const smooth=t=>{const value=clamp(t,0,1);return value*value*(3-2*value);};
  // Distance multiplier, target x/y/z, yaw, pitch, roll and vertical lens.
  // Camera cues share the illustration clock; there is no second RAF or timer.
  const FULL_CAMERA=[1.04,0,-.06,0,-.06,.08,0,.62];
  const MACRO_CAMERA=[.43,-.35,.38,.12,-.48,.13,-.07,.53];
  const CAMERA_CUES=[
    [0,'paper-edge',[.68,-.14,.18,.12,-.22,.10,-.025,.59]],
    [1800,'report-wide',[1.02,0,-.04,0,-.17,.08,-.012,.62]],
    [3400,'report-wide',[1.02,0,-.04,0,-.17,.08,-.012,.62]],
    [4700,'structure-orbit',[.93,.18,-.04,.22,.24,.11,.035,.62]],
    [6400,'structure-close',[.74,.20,-.08,.66,.20,.065,.02,.58]],
    [7550,'structure-close',[.74,.20,-.08,.66,.20,.065,.02,.58]],
    [8450,'evidence-approach',[.86,.53,-.04,.50,.09,.085,.015,.59]],
    [10000,'evidence-close',[.59,.91,-.06,.90,-.045,.055,.005,.55]],
    [11000,'evidence-close',[.59,.91,-.06,.90,-.045,.055,.005,.55]],
    [DURATION,'evidence-wide',FULL_CAMERA],
  ];
  function cameraAt(time,opening){
    for(let index=1;index<CAMERA_CUES.length;index++){
      const next=CAMERA_CUES[index],previous=CAMERA_CUES[index-1];
      if(time<=next[0])return {values:blend(index===1?opening:previous[2],next[2],smooth((time-previous[0])/(next[0]-previous[0]))),shot:previous[1]};
    }
    return {values:FULL_CAMERA.slice(),shot:'evidence-wide'};
  }
  function createRuntime(env, draw, notify) {
    let frame=0,disposed=false,visible=true,healthy=true,reduced=!!env.reduced;
    let stage=1,expanded=true,from=1,target=1,value=1,open=0,openFrom=0,openTarget=1;
    let layers=Array(LAYERS).fill(1),spreads=Array(LAYERS).fill(0),layerFrom=layers.slice(),spreadFrom=spreads.slice();
    let activeTime=0,start=0,clock=0,last=env.now(),dirty=true,px=0,py=0,tx=0,ty=0;
    let playback='idle',showTime=0,act=0,autoplayStarted=false;
    let score=null,choreography=null,selection=null;
    let camera=(env.autoplay&&!reduced?MACRO_CAMERA:FULL_CAMERA).slice(),cameraFrom=camera.slice(),cameraStart=0;
    let showCameraFrom=CAMERA_CUES[0][2].slice(),shot=reduced?'settled':'paper-edge';
    const flex=Array.from({length:LAYERS},()=>[0,0]),flexVelocity=Array.from({length:LAYERS},()=>[0,0]);
    function bendPapers(delta,previousLayers,previousSpreads){
      if(reduced){flex.forEach((value,index)=>{value.fill(0);flexVelocity[index].fill(0);});return;}
      const elapsed=Math.min(40,delta)/1000,steps=Math.ceil(elapsed/.008),step=steps?elapsed/steps:0;
      flex.forEach((value,index)=>{
        // Body follows the existing unfolding pose. The free corner responds
        // later, then makes one restrained rebound; it never owns a new clock.
        const seconds=Math.max(delta/1000,.001);
        const drive=clamp((spreads[index]-previousSpreads[index])*.28/seconds+(layers[index]-previousLayers[index])*.12/seconds,-.42,.48);
        const targets=[drive,drive*.20+value[0]*.32];
        for(let tick=0;tick<steps;tick++)for(let axis=0;axis<2;axis++){
          const frequency=axis?8.5:13,damping=axis?.68:.76;
          flexVelocity[index][axis]+=((targets[axis]-value[axis])*frequency*frequency-2*damping*frequency*flexVelocity[index][axis])*step;
          value[axis]+=flexVelocity[index][axis]*step;
          value[axis]=clamp(value[axis],axis?-.19:-.52,axis?.19:.52);
          if(Math.abs(value[axis])<1e-7&&Math.abs(flexVelocity[index][axis])<1e-7)value[axis]=flexVelocity[index][axis]=0;
        }
      });
    }
    const running=()=>!disposed&&visible&&healthy&&!env.hidden();
    const animated=()=>!reduced&&(selection?!selection.complete:playback!=='paused');
    const state=()=>({stage,expanded,reduced,visible,healthy,disposed,frame,playback,showTime,act,camera:camera.slice(),shot,choreography:choreography?{...choreography}:null,score:score?.getState(),paperFlex:flex.map(value=>value.slice()),
      selection:selection?{action:selection.action,...selection.pose,complete:selection.complete}:null,
      currentPose:{stage:value,open,layers:layers.slice(),spreads:spreads.slice()}});
    const announce=()=>notify(state());
    function paint(now) {
      frame=0;
      if(!running()){if(env.onPause)env.onPause();return;}
      const raw=last===null?0:Math.max(0,now-last);last=now;
      const delta=animated()?raw:0;
      if(!selection)activeTime+=delta;
      if(env.onFrame)env.onFrame(now,animated());
      if(animated()&&!selection)clock+=Math.min(40,delta);
      if(playback==='playing'&&!selection){
        showTime=Math.min(DURATION,showTime+delta);
        const nextAct=Math.min(2,Math.floor(showTime/ACT_MS));
        if(nextAct!==act){act=nextAct;change(act,true,true);}
        if(showTime===DURATION){playback='complete';announce();}
      }
      const progress=reduced?1:clamp((activeTime-start)/1450,0,1),motion=ease(progress);
      value=from+(target-from)*motion;open=openFrom+(openTarget-openFrom)*motion;
      const previousLayers=layers.slice(),previousSpreads=spreads.slice();
      layers=layers.map((_,index)=>{
        const delay=index*.035,amount=reduced?1:ease((progress-delay)/(1-delay));
        spreads[index]=spreadFrom[index]+(openTarget-spreadFrom[index])*amount;
        return layerFrom[index]+(target-layerFrom[index])*amount;
      });
      const scored=!reduced&&score&&playback!=='idle'?score.sample(showTime):null;
      if(scored){
        layers=scored.layers;spreads=scored.spreads;value=layers[0];open=spreads[0];choreography=scored.choreography;
      }
      bendPapers(delta,previousLayers,previousSpreads);
      const pointerBlend=selection?0:reduced?1:1-Math.exp(-Math.min(40,delta)/135);
      px+=(tx-px)*pointerBlend;py+=(ty-py)*pointerBlend;
      if(reduced){camera=FULL_CAMERA.slice();shot='settled';}
      else if(scored){camera=scored.camera;shot=scored.shot;}
      else if(playback!=='idle'){
        const cue=cameraAt(showTime,showCameraFrom);camera=cue.values;shot=showTime===DURATION?'evidence-wide':cue.shot;
      }else if(env.autoplay&&!autoplayStarted){
        camera=blend(MACRO_CAMERA,CAMERA_CUES[0][2],smooth(progress));shot='paper-edge';
      }else{camera=blend(cameraFrom,FULL_CAMERA,ease((activeTime-cameraStart)/1100));shot='settled';}
      if(selection&&!selection.complete){
        selection.elapsed=Math.min(430,selection.elapsed+delta);
        const amount=ease(selection.elapsed/430);
        selection.pose=selection.timeline?.sample(selection.elapsed)||{lift:.8*amount,turn:-.09*amount,scale:1+.12*amount,glow:amount};
      }
      draw({stage:value,open,layers:layers.slice(),spreads:spreads.slice(),pointer:[reduced?0:px,reduced?0:py],
        selection:selection?{action:selection.action,...selection.pose}:null,
        time:reduced?0:clock/1000,reduced,playback,showTime,act,camera:camera.slice(),shot,choreography:choreography?{...choreography}:null,paperFlex:flex.map(value=>value.slice())});
      dirty=false;
      if(selection&&!selection.complete&&selection.elapsed===430)finishSelection();
      // One automatic sequence follows the original unfolding entrance.
      // The same clock owns it; rerenders and offscreen time cannot restart it.
      if(env.autoplay && !autoplayStarted && !reduced && !selection && progress===1 && playback==='idle'){
        autoplayStarted=true;api.toggleShow();
      }
      if(animated()&&running()&&!frame)frame=env.raf(paint);
    }
    function request(){if(running()&&!frame&&(dirty||animated()))frame=env.raf(paint);}
    function stop(){if(frame)env.cancel(frame);frame=0;last=null;if(env.onPause)env.onPause();}
    function finishSelection(){
      if(!selection||selection.complete)return;
      selection.complete=true;selection.timeline?.dispose();selection.timeline=null;
      const done=selection.done;selection.done=null;done?.();
    }
    function cancelShow(){if(playback!=='idle'){playback='idle';showTime=0;last=env.now();score?.dispose();score=null;}}
    function change(nextStage,nextOpen,fromShow=false){
      if(disposed)return;
      const bounded=clamp(Math.round(nextStage),0,2);
      if(!fromShow){cameraFrom=camera.slice();cameraStart=activeTime;autoplayStarted=true;cancelShow();}
      if(bounded!==stage||nextOpen!==expanded){
        from=value;openFrom=open;layerFrom=layers.slice();spreadFrom=spreads.slice();
        stage=bounded;target=stage;expanded=nextOpen;openTarget=expanded?1:0;start=activeTime;
      }
      dirty=true;announce();if(!fromShow)request();
    }
    const api={
      selectObject(action,done){
        if(disposed||selection||!['annual_reports','annual_data','answer_evidence'].includes(action))return false;
        if(reduced||!healthy||env.hidden()){done?.();return true;}
        selection={action,elapsed:0,complete:false,done,pose:{lift:0,turn:0,scale:1,glow:0},timeline:global.QMHeroChoreography?.createSelection(global.gsap)};
        last=env.now();dirty=true;request();return true;
      },
      cancelSelection(){if(!selection)return;selection.timeline?.dispose();selection.done=null;selection=null;last=env.now();dirty=true;request();},
      setStage(next){if(Number.isFinite(next))change(next,true);},
      toggle(){change(stage,!expanded);},
      toggleShow(){
        if(disposed||reduced||!healthy)return;
        if(playback==='playing'){playback='paused';stop();dirty=true;announce();request();return;}
        if(playback==='paused'){playback='playing';last=env.now();dirty=true;announce();request();return;}
        showCameraFrom=camera.slice();score?.dispose();
        score=global.QMHeroChoreography?.createScore(global.gsap,{layers:layers.slice(),spreads:spreads.slice(),camera:camera.slice()})||null;
        playback='playing';showTime=0;act=0;last=env.now();change(0,true,true);request();
      },
      pointer(x,y){if(disposed||reduced||playback==='paused')return;tx=clamp(x,-1,1);ty=clamp(y,-1,1);dirty=true;request();},
      setVisible(next){visible=!!next;if(!visible)stop();else{dirty=true;request();}},
      setHealthy(next){healthy=!!next;if(!healthy){finishSelection();stop();}else{dirty=true;request();}announce();},
      setReduced(next){
        if(disposed||reduced===!!next)return;
        reduced=!!next;stop();if(reduced){autoplayStarted=true;cancelShow();}
        if(reduced)finishSelection();
        value=from=target;open=openFrom=openTarget;
        layers=layerFrom=Array(LAYERS).fill(target);spreads=spreadFrom=Array(LAYERS).fill(openTarget);
        camera=cameraFrom=FULL_CAMERA.slice();cameraStart=activeTime;shot='settled';
        choreography=null;
        flex.forEach((value,index)=>{value.fill(0);flexVelocity[index].fill(0);});
        start=activeTime;px=py=tx=ty=0;dirty=true;announce();request();
      },
      invalidate(){if(disposed)return;dirty=true;request();},
      syncVisibility(){if(!running())stop();else{dirty=true;request();}},
      getState:state,
      dispose(){disposed=true;stop();score?.dispose();score=null;selection?.timeline?.dispose();selection=null;},
    };
    announce();request();return api;
  }
  global.QMHeroRuntime={createRuntime,clamp,ACT_MS,DURATION};
})(typeof window!=='undefined'?window:globalThis);
