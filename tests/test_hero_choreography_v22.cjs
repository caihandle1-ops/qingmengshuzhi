'use strict';
// Actual shipped GSAP, actual illustration clock and production WebGL matrices.
// The graphics adapter checks geometry/state, not visual appearance or GPU FPS.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const gsap=require('../app/hero_frontend/gsap.min.js').gsap;
const {component}=require('./test_hero_initial_render.cjs');
gsap.ticker.sleep();
const source=fs.readFileSync(path.join(__dirname,'../app/hero_frontend/hero-choreography.js'),'utf8');
function realHero(options={},scoreSource=source){
  const hero=component(options);hero.context.gsap=gsap;vm.runInContext(scoreSource,hero.context);return hero;
}
const state=hero=>hero.context.__qmImmersiveHero.getState();
const snapshot=hero=>JSON.stringify({pose:state(hero).currentPose,camera:state(hero).camera,choreography:state(hero).choreography});
const matrices=hero=>hero.matrices.slice(hero.matrices.map(item=>item.name).lastIndexOf('uVP'));
const transform=(matrix,vector)=>[0,1,2,3].map(row=>vector.reduce((sum,value,column)=>sum+matrix[column*4+row]*value,0));
function visiblePapers(hero){
  const records=matrices(hero);
  for(const object of records.slice(1,9))for(const x of [-.5,.5])for(const y of [-.5,.5])for(const z of [-.5,.5]){
    const point=transform(records[0].value,transform(object.value,[x,y,z,1]));
    assert.ok(point[3]>0&&Math.abs(point[0]/point[3])<1&&Math.abs(point[1]/point[3])<1,'the full paper ensemble is framed in a held wide shot');
  }
}
const results=[];
for(const [viewport,width] of [[1366,480],[1920,760]]){
  const hero=realHero();
  hero.get('sculpture').getBoundingClientRect=()=>({width,height:370,left:0,top:78});
  hero.render('presentation');hero.paintAt(0);hero.paintAt(1450);
  assert.equal(state(hero).score.duration,12.6);assert.equal(state(hero).score.paused,true);
  hero.paintAt(1450);const opening=snapshot(hero);
  hero.paintAt(1850);const anticipation=state(hero);
  assert.ok(anticipation.currentPose.open<.80,'anticipation compresses the real assembly before release');
  assert.ok(anticipation.choreography.fan<0,'the score changes the physical fan, not just a label');
  hero.paintAt(2700);const flight=state(hero);
  assert.ok(flight.currentPose.open>.99&&flight.choreography.fan>.97,'fast fanout opens decisively');
  assert.notEqual(flight.currentPose.layers[0],flight.currentPose.layers[8],'sheets have staggered physical phases');
  hero.paintAt(3250);const reveal=state(hero);
  visiblePapers(hero);const revealMatrices=JSON.stringify(matrices(hero));
  hero.paintAt(6200);const passage=state(hero);
  assert.ok(passage.choreography.passage>.9);
  assert.ok(passage.camera[4]-reveal.camera[4]>.35,'camera turns through the opening');
  hero.paintAt(7800);const corridor=state(hero);
  assert.ok(corridor.cameraRig.distance<reveal.cameraRig.distance*.7,'camera advances between sheets');
  assert.notEqual(JSON.stringify(matrices(hero)),revealMatrices,'GSAP updates the production shader matrices, not a detached preview object');
  assert.ok(corridor.paperGeometry.vertices>800,'deformed closed paper meshes remain');
  const before=snapshot(hero),beforeTime=state(hero).showTime;
  hero.render('presentation');hero.paintAt(7800);
  assert.equal(snapshot(hero),before,'ordinary rerender does not replay GSAP');
  hero.observers[0].callback([{isIntersecting:false}]);assert.equal(hero.frames.size,0);
  hero.paintAt(80000);hero.observers[0].callback([{isIntersecting:true}]);hero.paintAt(80000);
  assert.equal(state(hero).showTime,beforeTime);assert.equal(snapshot(hero),before,'offscreen time cannot advance either animation owner');
  hero.paintAt(83000);const evidence=state(hero);
  assert.ok(evidence.choreography.gather>.99&&evidence.currentPose.layers.every(value=>value===2));
  assert.ok(evidence.choreography.fan<.01&&evidence.choreography.passage<.01,'same sheets gather, with the corridor closed');
  assert.ok(evidence.paperFlex.every(pair=>pair.every(Number.isFinite)));
  hero.paintAt(86250);assert.equal(state(hero).showTime,12600);
  assert.equal(state(hero).playback,'complete');assert.equal(state(hero).choreography.archive,1);
  visiblePapers(hero);
  assert.equal(state(hero).score.time,12.6);assert.equal(hero.frames.size,1,'only the native illustration RAF remains');
  const completed=snapshot(hero);hero.render('presentation');hero.paintAt(96250);
  assert.equal(snapshot(hero),completed,'completed composition never restarts after a rerun');
  assert.notEqual(completed,opening);
  assert.ok(hero.posts.every(message=>message.type!=='streamlit:setComponentValue'));
  hero.dispose();assert.equal(gsap.globalTimeline.getChildren(true,true,true).length,0,'disposal releases the paused score and every child tween');
  results.push({viewport,actual_gsap:true,paused_score:true,one_clock:true,fanout_camera_filament_archive:true});
}
// Render deformed paper vertices, not only undeformed bounding boxes. These
// are the actual 480/708px desktop panel widths observed in browser review.
const framing=[];
const oldWide=source.replace('[1.02,-.06,-.04,0,-.17,.08,-.012,.48]',
  '[1.02,-.06,-.04,0,-.17,.08,-.012,.62]').replace('[1.04,0,-.06,0,-.06,.08,0,.46]',
  '[1.04,0,-.06,0,-.06,.08,0,.62]');
for(const width of [480,708])for(const [px,py] of [[-1,-1],[-1,1],[1,-1],[1,1]]){
  const hero=realHero({captureGeometry:true});
  const baseline=realHero({captureGeometry:true},oldWide);
  const rect=()=>({width,height:370,left:0,top:78});
  for(const scene of [hero,baseline]){
    scene.get('sculpture').getBoundingClientRect=rect;
    scene.get('sculpture-stage').getBoundingClientRect=rect;
    scene.render('presentation');scene.paintAt(0);
  }
  let time=0;
  const boundsAt=(target,label)=>{
    for(;time<target;time+=20){
      for(const scene of [hero,baseline]){
        if(time===3200)scene.get('sculpture-stage').emit('pointermove',{clientX:px<0?0:width,clientY:py<0?78:448});
        scene.paintAt(time+20);
      }
    }
    const measure=scene=>{
    const vp=matrices(scene)[0].value;
    let left=Infinity,right=-Infinity,bottom=Infinity,top=-Infinity;
    const sheets=scene.geometryDraws.filter(draw=>draw.indexed);
    assert.equal(sheets.length,8,'all physical paper surfaces stay present');
    for(const draw of sheets)for(let index=0;index<draw.vertices.length;index+=9){
      const point=transform(vp,transform(draw.model,[draw.vertices[index],draw.vertices[index+1],draw.vertices[index+2],1]));
      assert.ok(point[3]>0,'paper vertices stay in front of the lens');
      const x=point[0]/point[3],y=point[1]/point[3];
      left=Math.min(left,x);right=Math.max(right,x);bottom=Math.min(bottom,y);top=Math.max(top,y);
    }
    return {left,right,bottom,top};
    };
    const {left,right,bottom,top}=measure(hero),old=measure(baseline);
    const margins=[(left+1)*width/2,(1-right)*width/2,(1-top)*185,(bottom+1)*185];
    assert.ok(margins.every(value=>value>4),`${label} has a safe paper margin at width ${width}, pointer ${px}/${py}: ${margins}`);
    const size=[(right-left)*width/2,(top-bottom)*185];
    const gain=(right-left)/(old.right-old.left);
    assert.ok(gain>1.30&&gain<1.45,'same production paper geometry enlarges 1.3–1.45x against the former wide lens');
    framing.push({width,pointer:[px,py],shot:label,gain:Math.round(gain*1000)/1000,size:size.map(Math.round),margins:margins.map(Math.round)});
  };
  boundsAt(4000,'report');boundsAt(15100,'archive');hero.dispose();baseline.dispose();
}
const quiet=realHero({osReduced:true});quiet.render('presentation');quiet.paintAt(0);
assert.equal(state(quiet).score,undefined);assert.equal(quiet.frames.size,0);assert.equal(state(quiet).shot,'settled');quiet.dispose();
const recovery=realHero();recovery.render('presentation');recovery.paintAt(0);recovery.paintAt(1450);recovery.paintAt(6300);
const preserved=snapshot(recovery);recovery.get('sculpture').emit('webglcontextlost',{preventDefault(){}});
recovery.paintAt(30000);recovery.get('sculpture').emit('webglcontextrestored');recovery.paintAt(30000);
assert.equal(snapshot(recovery),preserved,'graphics context recovery preserves the shared score');
recovery.render('research');recovery.paintAt(30001);assert.equal(recovery.frames.size,0);assert.equal(state(recovery).choreography,null);
recovery.render('presentation');recovery.paintAt(30002);assert.equal(state(recovery).playback,'idle');recovery.dispose();
assert.equal(gsap.globalTimeline.getChildren(true,true,true).length,0);
console.log(JSON.stringify({passed:true,results,framing,reduced_motion:true,context_recovery:true,cleanup:true}));
