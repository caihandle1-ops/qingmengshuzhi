/* Fullscreen landing direction. One native RAF owns both GSAP and WebGL. */
(function(global){
  'use strict';
  const INTRO_MS=2600,EXIT_MS=620;
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  const ease=value=>1-Math.pow(1-clamp(value,0,1),4);
  const lerp=(a,b,t)=>a+(b-a)*t;
  function createRuntime(env,draw,notify){
    let disposed=false,visible=true,healthy=true,reduced=!!env.reduced,frame=0,last=null,elapsed=0;
    let tx=0,ty=0,px=0,py=0,selection=null,dirty=true;
    const entrance={spread:.12,travel:1,camera:.67,lineOne:110,lineTwo:110,tilt:12};
    const current={fan:0,turn:0,lift:0,detail:0};
    const gsap=global.gsap;
    const intro=gsap?.timeline({paused:true,defaults:{ease:'power3.out'}})
      .to(entrance,{spread:1,travel:0,camera:1,duration:2.6,ease:'expo.out'},0)
      .to(entrance,{lineOne:0,tilt:0,duration:1.22,ease:'expo.out'},.08)
      .to(entrance,{lineTwo:0,duration:1.36,ease:'expo.out'},.20);
    const flowScore=gsap?.timeline({paused:true,defaults:{ease:'sine.inOut'}})
      .to(current,{fan:1,turn:1,lift:.35,duration:4.5},0)
      .to(current,{detail:1,fan:.45,turn:.25,lift:1,duration:4.5},4.5)
      .to(current,{detail:.2,fan:.8,turn:-.7,lift:.15,duration:4.5},9)
      .to(current,{detail:0,fan:0,turn:0,lift:0,duration:4.5},13.5);
    gsap?.ticker.sleep();
    const nodes=env.document?{
      one:env.document.getElementById('landing-line-one'),two:env.document.getElementById('landing-line-two'),
      detail:env.document.getElementById('landing-copy-detail'),
    }:{};
    function paintType(exit=0){
      if(nodes.one?.style){nodes.one.style.transform=`translate3d(0,${entrance.lineOne-exit*70}%,0) rotate(${entrance.tilt}deg)`;nodes.one.style.opacity=String(1-exit);}
      if(nodes.two?.style){nodes.two.style.transform=`translate3d(0,${entrance.lineTwo-exit*50}%,0)`;nodes.two.style.opacity=String(1-exit);}
      if(nodes.detail?.style){nodes.detail.style.transform=`translate3d(${-exit*50}px,0,0)`;nodes.detail.style.opacity=String(1-exit);}
    }
    function sampleEntrance(){
      const time=reduced?INTRO_MS:elapsed;
      if(intro){intro.time(Math.min(INTRO_MS,time)/1000,true);gsap.ticker.sleep();}
      else{const amount=ease(time/INTRO_MS);entrance.spread=lerp(.12,1,amount);entrance.travel=1-amount;entrance.camera=lerp(.67,1,amount);entrance.lineOne=110*(1-ease(time/1200));entrance.lineTwo=110*(1-ease((time-150)/1300));entrance.tilt=12*(1-amount);}
      if(reduced)Object.assign(entrance,{spread:1,travel:0,camera:1,lineOne:0,lineTwo:0,tilt:0});
      if(flowScore){flowScore.time(reduced?0:Math.max(0,elapsed-INTRO_MS)/1000%18,true);gsap.ticker.sleep();}
    }
    function snapshot(){
      const seconds=reduced?0:elapsed/1000,exit=selection?ease(selection.elapsed/EXIT_MS):0;
      const flow=reduced?0:Math.sin(seconds*.22)*.5+Math.sin(seconds*.097)*.3;
      // Wide asymmetric framing deliberately gives type the left half. The
      // renderer composes all physical objects in the right half of this lens.
      const camera=[entrance.camera*(1-exit*.31),-.18+Math.sin(seconds*.11)*.15,-.02+Math.sin(seconds*.15)*.07,.04,
        -.13+Math.sin(seconds*.19)*.13+current.turn*.08,.07+Math.sin(seconds*.14)*.045,-.025+Math.sin(seconds*.10)*.025,.66];
      return {landing:true,stage:1,expanded:true,open:entrance.spread,layers:Array(9).fill(1),spreads:Array(9).fill(entrance.spread),
        pointer:reduced?[0,0]:[px,py],time:seconds,reduced,visible,healthy,disposed,frame,
        playback:selection?'exiting':elapsed<INTRO_MS&&!reduced?'opening':'flow',showTime:elapsed,act:0,camera,
        shot:selection?'landing-enter':elapsed<INTRO_MS&&!reduced?'landing-reveal':'landing-flow',
        landingPose:{spread:entrance.spread,travel:entrance.travel,camera:entrance.camera,lineOne:entrance.lineOne,lineTwo:entrance.lineTwo,tilt:entrance.tilt,flow,exit,fan:current.fan,turn:current.turn,lift:current.lift,detail:current.detail},choreography:{fan:entrance.spread,passage:0,gather:0,archive:0,energy:.6},
        paperFlex:Array.from({length:9},(_,i)=>reduced?[0,0]:[Math.sin(seconds*.65+i*.57)*.052,Math.sin(seconds*.43+i*.8)*.022]),
        selection:selection?{action:selection.action,lift:exit*.7,turn:exit*.1,scale:1+exit*.16,glow:exit,complete:selection.complete}:null,
        currentPose:{stage:1,open:entrance.spread,layers:Array(9).fill(1),spreads:Array(9).fill(entrance.spread)},
        score:intro?{paused:intro.paused(),duration:intro.duration(),time:Math.min(elapsed,INTRO_MS)/1000}:null};
    }
    const running=()=>!disposed&&visible&&healthy&&!env.hidden();
    const animated=()=>!reduced&&(!selection||!selection.complete);
    function stop(){if(frame)env.cancel(frame);frame=0;last=null;env.onPause?.();}
    function finish(){if(!selection||selection.complete)return;selection.complete=true;const done=selection.done;selection.done=null;done?.();}
    function paint(now){
      frame=0;if(!running())return;
      const delta=last===null?0:Math.max(0,now-last);last=now;
      if(animated()){
        if(selection)selection.elapsed=Math.min(EXIT_MS,selection.elapsed+delta);
        else elapsed+=delta;
        const blend=1-Math.exp(-Math.min(delta,64)/180);px+=(tx-px)*blend;py+=(ty-py)*blend;
      }
      sampleEntrance();const state=snapshot();paintType(state.landingPose.exit);
      env.onFrame?.(now,animated());draw(state);notify(state);dirty=false;
      if(selection&&selection.elapsed===EXIT_MS)finish();
      if(running()&&animated())frame=env.raf(paint);
    }
    function request(){if(running()&&!frame&&(dirty||animated()))frame=env.raf(paint);}
    const api={
      pointer(x,y){if(disposed||reduced||selection)return;tx=clamp(x,-1,1);ty=clamp(y,-1,1);dirty=true;request();},
      selectObject(action,done){
        if(disposed||selection||!['enter_workspace','annual_reports','annual_data','answer_evidence'].includes(action))return false;
        if(reduced||!healthy||env.hidden()){done?.();return true;}
        selection={action,done,elapsed:0,complete:false};last=env.now();env.shell&&(env.shell.dataset.exiting='true');dirty=true;request();return true;
      },
      cancelSelection(){if(!selection)return;selection.done=null;selection=null;last=null;env.shell&&(env.shell.dataset.exiting='false');paintType();dirty=true;request();},
      setVisible(value){visible=!!value;if(!visible)stop();else{dirty=true;request();}},
      setHealthy(value){healthy=!!value;if(!healthy){elapsed=Math.max(elapsed,INTRO_MS);sampleEntrance();paintType();finish();stop();}else{dirty=true;request();}},
      setReduced(value){if(disposed||reduced===!!value)return;reduced=!!value;stop();if(reduced){elapsed=Math.max(elapsed,INTRO_MS);finish();}sampleEntrance();paintType();dirty=true;notify(snapshot());request();},
      invalidate(){if(disposed)return;dirty=true;request();},
      syncVisibility(){if(!running()){if(env.hidden())finish();stop();}else{dirty=true;request();}},
      getState:snapshot,
      dispose(){if(disposed)return;disposed=true;stop();selection=null;intro?.kill();flowScore?.kill();gsap?.ticker.sleep();[nodes.one,nodes.two,nodes.detail].forEach(node=>{if(node?.style){node.style.transform='';node.style.opacity='';}});env.shell&&(env.shell.dataset.exiting='false');},
    };
    sampleEntrance();paintType();notify(snapshot());request();return api;
  }
  function setLayout(document,shell,landing,brand){
    shell.dataset.landing=String(landing);document.documentElement.dataset.landing=String(landing);
    document.querySelectorAll('.landing-only').forEach(node=>{node.hidden=!landing;});
    if(!landing)return;
    const name=document.getElementById('landing-brand-name');
    if(name)name.textContent=typeof brand?.name==='string'?brand.name.slice(0,32):'擎梦数智';
    const mark=document.getElementById('landing-brand-mark');
    if(mark&&typeof brand?.mark==='string'&&/^data:image\/(?:svg\+xml|png|webp);(?:base64,|utf8,|charset=utf-8,)/.test(brand.mark)&&brand.mark.length<180000){
      if(mark.dataset.source!==brand.mark){const image=document.createElement('img');image.alt='';image.src=brand.mark;mark.replaceChildren(image);mark.dataset.source=brand.mark;}
    }
  }
  global.QMLandingCinema={createRuntime,setLayout,INTRO_MS,EXIT_MS};
})(typeof window!=='undefined'?window:globalThis);
