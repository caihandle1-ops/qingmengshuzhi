'use strict';
// Execute automatic entry and internal reversible poses through the shipped clock + WebGL path.
// Deterministic graphics calls validate choreography, not rendered visual quality.
const assert = require('node:assert/strict');
const {component} = require('./test_hero_initial_render.cjs');
const fs=require('node:fs'),path=require('node:path');
const markup=fs.readFileSync(path.join(__dirname,'../app/hero_frontend/index.html'),'utf8');
const buttons=[...markup.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/gi)].map(match=>match[0]);
assert.equal(buttons.length,1,'the only button is the actual landing workspace entry');
assert.match(buttons[0],/\bid="landing-enter"/);
assert.match(buttons[0],/进入研究空间/);
assert.doesNotMatch(markup.replace(buttons[0],''),/<button\b/i,'no other player or stage buttons are exposed');
assert.doesNotMatch(markup,/\btype\s*=\s*["']?range\b|播放演出|聚合装置/i,'the spatial scene has no player or progress controls');
const state = hero => hero.context.__qmImmersiveHero.getState();
const click = hero => hero.clock.toggleShow();
const poses = hero => JSON.stringify(state(hero).currentPose);
const camera = hero => {const {shot,...rig}=state(hero).cameraRig;return JSON.stringify({camera:state(hero).camera,rig});};

const hero = component();
hero.render('presentation'); hero.paintAt(0); hero.paintAt(1500);
assert.equal(state(hero).playback, 'playing', 'original unfolding hands over to automatic choreography');
const before = poses(hero);
hero.paintAt(1500);
assert.equal(poses(hero), before, 'show begins from the exact current arrangement');
assert.equal(state(hero).playback, 'playing');
hero.paintAt(1800);
assert.equal(state(hero).act, 0);
assert.ok(state(hero).currentPose.layers[0] < state(hero).currentPose.layers[5], 'paper flights are staggered, not a single transform');
hero.render('presentation'); hero.paintAt(1900);
assert.equal(state(hero).showTime, 400, 'ordinary Streamlit rerenders retain the show clock');
click(hero); hero.paintAt(1900);
const pausedPose = poses(hero), pausedTime = hero.painted.at(-1).time, pausedCamera = camera(hero);
assert.equal(state(hero).playback, 'paused');
assert.equal(hero.frames.size, 0, 'explicit pause stops the single animation loop');
hero.paintAt(50000); hero.render('presentation'); hero.paintAt(50000);
assert.equal(poses(hero), pausedPose);
assert.equal(state(hero).showTime, 400);
assert.equal(hero.painted.at(-1).time, pausedTime);
assert.equal(camera(hero), pausedCamera, 'camera and its lighting eye are frozen by the same pause');
assert.equal(state(hero).quality.sampling, false, 'paused rendering is not sampled as poor performance');
click(hero); hero.paintAt(50000);
assert.equal(poses(hero), pausedPose, 'resume neither rewinds nor consumes paused time');
assert.equal(camera(hero), pausedCamera, 'resuming starts at the exact physical camera position');
assert.equal(hero.frames.size, 1);
hero.paintAt(53800); // first act boundary, visible show time 4200 ms
assert.equal(state(hero).act, 1);
assert.equal(state(hero).stage, 1);
hero.paintAt(55300);
assert.equal(hero.painted.at(-1).stage, 1);
const extractionPose = poses(hero), extractionCamera = camera(hero);
hero.doc.hidden = true; hero.doc.emit('visibilitychange');
assert.equal(hero.frames.size, 0);
const hiddenShowTime = state(hero).showTime;
hero.paintAt(99000); hero.doc.hidden = false; hero.doc.emit('visibilitychange'); hero.paintAt(99000);
assert.equal(state(hero).showTime, hiddenShowTime, 'hidden time never skips the evidence act');
assert.equal(poses(hero), extractionPose);
assert.equal(camera(hero), extractionCamera, 'hidden time does not advance the camera independently of its scene');
hero.observers[0].callback([{isIntersecting: false}]);
hero.paintAt(200000); hero.observers[0].callback([{isIntersecting: true}]); hero.paintAt(200000);
assert.equal(state(hero).showTime, hiddenShowTime, 'offscreen time also freezes choreography');
hero.paintAt(202700); // next boundary, total visible time 8400 ms
assert.equal(state(hero).act, 2);
hero.paintAt(204200);
assert.equal(hero.painted.at(-1).stage, 2);
assert.notEqual(poses(hero), extractionPose, 'the finale is a distinct geometry arrangement');
hero.paintAt(206900);
assert.equal(state(hero).playback, 'complete');
assert.equal(state(hero).showTime, 12600);
hero.paintAt(226900); hero.render('presentation'); hero.paintAt(227000);
assert.equal(state(hero).stage, 2);
assert.equal(state(hero).playback, 'complete', 'there is no automatic show loop or rerender replay');
assert.equal(state(hero).showTime, 12600);
assert.ok(hero.posts.every(post => post.type !== 'streamlit:setComponentValue'), 'illustration never emits a financial operation');
const finalPose = poses(hero), finalCamera = camera(hero); click(hero); hero.paintAt(227000);
assert.equal(poses(hero), finalPose, 'replay starts from the finale without a pose reset');
assert.equal(camera(hero), finalCamera, 'internal replay keeps the finale camera and approaches its first shot continuously');
hero.dispose();

const interrupted = component(); interrupted.render('presentation'); interrupted.paintAt(0); interrupted.paintAt(1500);
let now = 1500;
for (let i = 0; i < 30; i++) {
  click(interrupted); interrupted.paintAt(now += 91);
  const previous = poses(interrupted), previousCamera = camera(interrupted);
  interrupted.clock.setStage(i % 3); interrupted.paintAt(now);
  assert.equal(poses(interrupted), previous, 'manual chapter takes over every paper at its current pose');
  assert.equal(camera(interrupted), previousCamera, 'manual interruption continues from the actual camera rather than jumping wide');
  assert.equal(state(interrupted).playback, 'idle');
  interrupted.paintAt(now += 137);
  const stagePose = poses(interrupted);
  interrupted.clock.toggle(); interrupted.paintAt(now);
  assert.equal(poses(interrupted), stagePose, 'collapse reverses all staggered paper paths continuously');
  interrupted.paintAt(now += 113);
  const collapsedPose = poses(interrupted);
  interrupted.clock.toggle(); interrupted.paintAt(now);
  assert.equal(poses(interrupted), collapsedPose, 'immediate reopening never snaps a delayed paper back');
  assert.equal(interrupted.frames.size, 1, 'all rapid controls share a single RAF');
}
interrupted.clock.setStage(2); interrupted.paintAt(now += 1600);
assert.equal(state(interrupted).currentPose.stage, 2);
assert.ok(state(interrupted).currentPose.layers.every(value => value === 2));
click(interrupted); interrupted.paintAt(now += 250);
interrupted.reduced(true); interrupted.paintAt(now += 1);
assert.equal(state(interrupted).reduced, true);
assert.equal(state(interrupted).playback, 'idle');
assert.equal(interrupted.frames.size, 0);
click(interrupted); interrupted.paintAt(now += 1);
assert.equal(state(interrupted).playback, 'idle', 'OS reduction cannot be overridden by show controls');
interrupted.reduced(false); interrupted.paintAt(now += 1);
assert.equal(state(interrupted).playback, 'idle', 'returning to presentation does not restart an interrupted show');
click(interrupted); interrupted.paintAt(now += 300);
const recoveryPose = poses(interrupted), recoveryTime = state(interrupted).showTime;
interrupted.get('sculpture').emit('webglcontextlost', {preventDefault() {}});
assert.equal(interrupted.frames.size, 0);
interrupted.paintAt(now += 30000);
interrupted.get('sculpture').emit('webglcontextrestored'); interrupted.paintAt(now);
assert.equal(poses(interrupted), recoveryPose);
assert.equal(state(interrupted).showTime, recoveryTime, 'graphics recovery cannot consume a suspended act');
interrupted.render('research'); interrupted.paintAt(now += 1);
assert.equal(state(interrupted).playback, 'idle');
assert.equal(interrupted.frames.size, 0);
interrupted.dispose();
// Project actual production model/view matrices rather than assume larger
// movement fits. This covers the primary paper stack at desktop panel widths.
const transform = (matrix, vector) => [0,1,2,3].map(row => vector.reduce((sum, value, column) => sum + matrix[column*4+row]*value, 0));
const frameMatrices = instance => instance.matrices.slice(instance.matrices.map(item => item.name).lastIndexOf('uVP'));
function projectedBox(records, objectIndex){
  const points=[];
  for(const x of [-.5,.5])for(const y of [-.5,.5])for(const z of [-.5,.5]){
    const point=transform(records[0].value,transform(records[objectIndex+1].value,[x,y,z,1]));
    assert.ok(point[3]>0, 'paper remains in front of the physical camera');
    points.push([point[0]/point[3],point[1]/point[3]]);
  }
  return {points,height:Math.max(...points.map(point=>point[1]))-Math.min(...points.map(point=>point[1]))};
}
const cinematic=component();cinematic.render('presentation');cinematic.paintAt(0);
assert.ok(projectedBox(frameMatrices(cinematic),5).points.some(point=>Math.abs(point[0])>1||Math.abs(point[1])>1), 'opening deliberately crops the cover for a material close-up');
const macroDistance=state(cinematic).cameraRig.distance;
cinematic.paintAt(1450);
const shots=new Map();
for(let showTime=50;showTime<=12600;showTime+=50){
  cinematic.paintAt(1450+showTime);
  assert.equal(cinematic.frames.size,1,'camera choreography uses the original single animation request');
  if([1800,3400,4700,6400,10000,11000,12600].includes(showTime)){
    shots.set(showTime,{state:state(cinematic),matrices:frameMatrices(cinematic)});
    const eye=cinematic.vectors.filter(entry=>entry.name==='uEye').at(-1).value;
    assert.deepEqual(eye,[...state(cinematic).cameraRig.eye],'material reflections receive the actual moving camera position');
  }
}
assert.ok(shots.get(3400).state.cameraRig.distance>macroDistance*2.2,'report reveal travels far enough to change the shot scale decisively');
assert.ok(shots.get(4700).state.camera[4]-shots.get(3400).state.camera[4]>.35,'extraction changes camera angle as well as object position');
const closeEvidence=projectedBox(shots.get(11000).matrices,6),wideEvidence=projectedBox(shots.get(12600).matrices,6);
assert.ok(closeEvidence.height>wideEvidence.height*1.7,'evidence close-up visibly increases its projected size');
assert.ok(closeEvidence.points.every(point=>Math.abs(point[0])<1&&Math.abs(point[1])<1),'the evidence text card itself remains framed during its close-up');
assert.equal(shots.get(12600).state.shot,'evidence-wide');
const finalVP=JSON.stringify(shots.get(12600).matrices[0].value);
cinematic.paintAt(30000);cinematic.render('presentation');cinematic.paintAt(31000);
assert.equal(JSON.stringify(frameMatrices(cinematic)[0].value),finalVP,'completed camera settles and a Streamlit rerender cannot replay it');
cinematic.dispose();
for (const width of [480, 640, 840]) {
  const framed = component();
  const rect = () => ({width, height:440, left:0, top:0});
  framed.get('sculpture').getBoundingClientRect = rect;
  framed.get('sculpture-stage').getBoundingClientRect = rect;
  framed.render('presentation'); framed.paintAt(0);
  let time = 0;
  for (const phase of [0,1,2]) for (const sign of [-1,1]) {
    framed.clock.setStage(phase); framed.paintAt(time += 1600);
    framed.get('sculpture-stage').emit('pointermove', {clientX:sign<0?0:width, clientY:sign<0?0:440});
    for (let sample=0; sample<70; sample++) framed.paintAt(time += 16);
    const records = framed.matrices.slice(framed.matrices.map(item => item.name).lastIndexOf('uVP'));
    for (const object of records.slice(1,9)) for (const x of [-.5,.5]) for (const y of [-.5,.5]) for (const z of [-.5,.5]) {
      const point = transform(records[0].value, transform(object.value,[x,y,z,1]));
      assert.ok(Math.abs(point[0]/point[3]) < 1 && Math.abs(point[1]/point[3]) < 1, `main paper remains in view: width ${width}, act ${phase}`);
    }
  }
  framed.dispose();
}
console.log('hero three-act: real macro/wide/orbit/evidence camera matrices, framing, stable finale, one clock, rapid reversal, recovery and OS priority passed');
