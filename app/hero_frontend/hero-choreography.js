/* A paused GSAP score, sampled exclusively by the existing illustration clock. */
(function (global) {
  'use strict';
  if(global.gsap)global.gsap.ticker.sleep();
  const DURATION=12.6;
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  function createScore(gsap, opening) {
    if(!gsap || typeof gsap.timeline!=='function')return null;
    const papers=opening.layers.map((phase,index)=>({phase,spread:opening.spreads[index]}));
    const camera={};opening.camera.forEach((value,index)=>{camera['c'+index]=value;});
    const body={fan:0,passage:0,gather:0,archive:0,energy:0};
    const timeline=gsap.timeline({paused:true,defaults:{ease:'power3.inOut'}});
    const cameraTo=(values,at,duration,ease='power3.inOut')=>{
      const vars={duration,ease};values.forEach((value,index)=>{vars['c'+index]=value;});timeline.to(camera,vars,at);
    };
    timeline.addLabel('anticipation',0).addLabel('fanout',.48)
      .addLabel('paper-gap',3.2).addLabel('evidence',7.75).addLabel('archive',11.15);
    // The sequence begins at the painted pose, including an internal replay.
    timeline.to(papers,{spread:.68,duration:.46,ease:'power2.in'},'anticipation');
    timeline.to(body,{fan:-.12,energy:.18,duration:.46,ease:'power2.in'},0);
    timeline.to(papers,{phase:0,spread:1,duration:.84,stagger:.046,ease:'expo.out'},'fanout');
    timeline.to(body,{fan:1,energy:1,duration:1.02,ease:'expo.out'},'fanout');
    cameraTo([1.02,-.06,-.04,0,-.17,.08,-.012,.48],.46,1.34,'power3.out');
    timeline.to(papers,{phase:1,duration:1.12,stagger:.04,ease:'power3.inOut'},'paper-gap');
    timeline.to(body,{passage:1,fan:.58,duration:1.22},'paper-gap');
    cameraTo([.93,.18,-.04,.22,.27,.11,.035,.62],3.4,1.3);
    cameraTo([.64,.14,-.05,.70,.20,.065,.02,.58],4.7,1.65);
    timeline.to(body,{passage:.28,energy:.65,duration:1.35},6.35);
    timeline.to(papers,{phase:2,duration:1.18,stagger:.044,ease:'power3.inOut'},'evidence');
    timeline.to(body,{fan:0,passage:0,gather:1,energy:.32,duration:1.56},'evidence');
    cameraTo([.86,.53,-.04,.50,.09,.085,.015,.59],7.75,.70);
    cameraTo([.59,.91,-.06,.90,-.045,.055,.005,.55],8.45,1.55);
    timeline.to(body,{archive:1,energy:.12,duration:1.45,ease:'power3.inOut'},'archive');
    cameraTo([1.04,0,-.06,0,-.06,.08,0,.46],11.15,1.45);
    // This iframe contains no independently ticking GSAP work. Its only owner
    // is hero-runtime's RAF; even GSAP's otherwise idle ticker stays asleep.
    gsap.ticker.sleep();
    let disposed=false;
    function sample(milliseconds){
      if(disposed)return null;
      const seconds=clamp(milliseconds/1000,0,DURATION);
      timeline.time(seconds,true);gsap.ticker.sleep();
      return {layers:papers.map(paper=>paper.phase),spreads:papers.map(paper=>paper.spread),
        camera:Array.from({length:8},(_,index)=>camera['c'+index]),
        choreography:{fan:body.fan,passage:body.passage,gather:body.gather,archive:body.archive,energy:body.energy},shot:seconds<3.2?'report-wide':seconds<6.35?'paper-gap':seconds<7.75?'structure-close':seconds<10?'evidence-approach':seconds<11.15?'evidence-close':'evidence-wide'};
    }
    return {sample,dispose(){if(disposed)return;disposed=true;timeline.kill();gsap.ticker.sleep();},
      getState:()=>({disposed,paused:timeline.paused(),duration:timeline.duration(),time:timeline.time()})};
  }
  function createSelection(gsap){
    if(!gsap)return null;
    const pose={lift:0,turn:0,scale:1,glow:0};
    const timeline=gsap.timeline({paused:true,defaults:{ease:'power3.out'}})
      .to(pose,{lift:-.065,glow:.5,duration:.08,ease:'power2.in'},0)
      .to(pose,{lift:.80,turn:-.09,scale:1.12,glow:1,duration:.35},.08);
    gsap.ticker.sleep();
    return {sample(milliseconds){timeline.time(Math.min(.43,milliseconds/1000),true);gsap.ticker.sleep();return {lift:pose.lift,turn:pose.turn,scale:pose.scale,glow:pose.glow};},
      dispose(){timeline.kill();gsap.ticker.sleep();}};
  }
  global.QMHeroChoreography={createScore,createSelection,DURATION};
})(typeof window!=='undefined'?window:globalThis);
