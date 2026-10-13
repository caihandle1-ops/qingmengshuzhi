'use strict';
// Numeric geometry/upload tests. These do not certify real browser pixels or FPS.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {component}=require('./test_hero_initial_render.cjs');
const context={};vm.createContext(context);
for(const file of ['hero-paper.js','hero-runtime.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/hero_frontend',file),'utf8'),context);
const paper=context.QMHeroPaper,grid=paper.createGeometry(),size=[1.6,2.28,.028];
assert.equal(grid.data.length/9,866);assert.equal(grid.indices.length/3,1424);
assert.equal(grid.indices.length%3,0);assert.ok([...grid.indices].every(index=>index<grid.data.length/9));
const source=grid.source.slice();paper.deform(grid,size,.42,.14);
assert.deepEqual(grid.source,source,'deformation retains the immutable original geometry and UV template');
assert.ok([...grid.data].every(Number.isFinite));
for(let offset=0;offset<grid.data.length;offset+=9){
  assert.deepEqual([...grid.data.slice(offset+6,offset+9)],[...source.slice(offset+6,offset+9)],'UVs and front-face texture identity survive curling');
}
const point=index=>[0,1,2].map(axis=>grid.data[index*9+axis]*size[axis]);
const normal=index=>{const values=[0,1,2].map(axis=>grid.data[index*9+axis+3]/size[axis]),length=Math.hypot(...values);return values.map(value=>value/length);};
const subtract=(a,b)=>a.map((value,index)=>value-b[index]);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const dot=(a,b)=>a.reduce((sum,value,index)=>sum+value*b[index],0);
const corner=grid.rows*(grid.columns+1)+grid.columns;
assert.ok(point(corner)[2]>.45,'free corner has actual large world-space curl, not a material-only effect');
for(let row=0;row<=grid.rows;row++){
  const pinned=point(row*(grid.columns+1));
  assert.ok(Math.abs(pinned[0]+size[0]/2)<1e-6&&Math.abs(pinned[2]-size[2]/2)<1e-6,'binding edge remains physically pinned');
}
for(let row=2;row<grid.rows-1;row+=3)for(let col=2;col<grid.columns-1;col+=3){
  const index=row*(grid.columns+1)+col;
  const tangentU=subtract(point(index+1),point(index-1)),tangentV=subtract(point(index+grid.columns+1),point(index-grid.columns-1));
  const surface=cross(tangentU,tangentV),length=Math.hypot(...surface),agreement=dot(surface,normal(index))/length;
  assert.ok(agreement>.998,'updated surface normal agrees with actual neighboring bent vertices');
}
// Weld duplicated face-border vertices, then check every closed edge has exactly
// two oppositely wound triangles. Curled thickness must not open a seam.
const ids=new Map(),vertexIds=[];
for(let index=0;index<grid.data.length/9;index++){
  const key=point(index).map(value=>Math.round(value*1e6)).join(',');
  if(!ids.has(key))ids.set(key,ids.size);vertexIds.push(ids.get(key));
}
const edges=new Map();
for(let i=0;i<grid.indices.length;i+=3)for(let j=0;j<3;j++){
  const a=vertexIds[grid.indices[i+j]],b=vertexIds[grid.indices[i+(j+1)%3]],key=[Math.min(a,b),Math.max(a,b)].join(':');
  const edge=edges.get(key)||{count:0,winding:0};edge.count++;edge.winding+=a<b?1:-1;edges.set(key,edge);
}
assert.ok([...edges.values()].every(edge=>edge.count===2&&edge.winding===0),'paper remains watertight with consistently oriented front, back and side faces');
paper.deform(grid,size,0,0);
for(let i=0;i<grid.data.length;i+=9)for(let axis=0;axis<3;axis++)assert.ok(Math.abs(grid.data[i+axis]-source[i+axis])<1e-6,'zero flex restores every original vertex');

function flexSamples(step){
  let now=0,id=0;const frames=new Map(),samples=[];
  const runtime=context.QMHeroRuntime.createRuntime({now:()=>now,raf:fn=>{frames.set(++id,fn);return id;},cancel:key=>frames.delete(key),hidden:()=>false},state=>samples.push({time:now,bend:state.paperFlex[0][0],curl:state.paperFlex[0][1]}),()=>{});
  for(now=0;now<5000;now+=step){const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn(now));assert.equal(frames.size,1);}
  runtime.dispose();assert.equal(frames.size,0);return samples;
}
const samples=flexSamples(1000/60),peak=(list,key)=>list.reduce((best,value)=>value[key]>best[key]?value:best,list[0]);
const bodyPeak=peak(samples,'bend'),cornerPeak=peak(samples,'curl');
assert.ok(bodyPeak.bend>.08,'unfolding creates an appreciable body bend');
assert.ok(cornerPeak.time>bodyPeak.time,'free corner lags behind the body rather than behaving as a rigid card');
assert.ok(samples.some(value=>value.bend<-.0001),'paper makes a restrained spring return after its initial flex');
assert.ok(Math.abs(samples.at(-1).bend)<1e-4&&Math.abs(samples.at(-1).curl)<1e-4,'paper relaxes rather than fluttering continuously');
for(const rate of [30,120]){
  const other=peak(flexSamples(1000/rate),'bend');
  assert.ok(Math.abs(other.bend-bodyPeak.bend)<.055,'bend amplitude remains stable across frame rates');
}

const hero=component({captureGeometry:true});hero.render('presentation');hero.paintAt(0);
const flat=hero.geometryDraws.filter(draw=>draw.indexed).map(draw=>draw.vertices.slice());
for(let time=16;time<=400;time+=16)hero.paintAt(time);
const curved=hero.geometryDraws.filter(draw=>draw.indexed);
assert.equal(curved.length,8,'all original paper objects are drawn through the subdivided path');
assert.ok(hero.geometryDraws.some(draw=>!draw.indexed),'orbits, markers and solid bars retain their original geometry');
assert.ok(curved.some((draw,index)=>draw.vertices.some((value,offset)=>offset%9<3&&Math.abs(value-flat[index][offset])>.01)),'the actual WebGL buffer receives deformed vertex positions');
for(const draw of curved){
  assert.equal(draw.count,4272);
  for(let i=0;i<draw.vertices.length;i+=9){
    const local=[draw.vertices[i+3],draw.vertices[i+4],draw.vertices[i+5]];
    const world=[0,1,2].map(row=>local.reduce((sum,value,col)=>sum+draw.normal[col*3+row]*value,0));
    assert.ok(Math.abs(Math.hypot(...world)-1)<2e-5,'uploaded normals and the inverse-transpose matrix produce correct unit lighting normals');
  }
}
const beforeHide=JSON.stringify(hero.context.__qmImmersiveHero.getState().paperFlex);
hero.doc.hidden=true;hero.doc.emit('visibilitychange');hero.paintAt(30000);
assert.equal(hero.frames.size,0);assert.equal(JSON.stringify(hero.context.__qmImmersiveHero.getState().paperFlex),beforeHide);
hero.doc.hidden=false;hero.doc.emit('visibilitychange');hero.paintAt(30000);
assert.equal(JSON.stringify(hero.context.__qmImmersiveHero.getState().paperFlex),beforeHide,'hidden time cannot wind up the spring');
hero.render('research');hero.paintAt(30001);
assert.ok(hero.context.__qmImmersiveHero.getState().paperFlex.every(value=>value.every(number=>number===0)));
assert.equal(hero.frames.size,0);
for(const draw of hero.geometryDraws.filter(draw=>draw.indexed))for(let i=0;i<draw.vertices.length;i+=9)assert.ok(Math.abs(draw.vertices[i+2])<=.500001,'research mode shows the complete flat paper thickness');
hero.dispose();

const transform=(matrix,vector)=>[0,1,2,3].map(row=>vector.reduce((sum,value,col)=>sum+matrix[col*4+row]*value,0));
for(const width of [480,640,840]){
  const framed=component({captureGeometry:true});
  framed.get('sculpture').getBoundingClientRect=()=>({width,height:440,left:0,top:0});
  framed.render('presentation');framed.paintAt(0);framed.clock.setStage(2);
  for(let time=16;time<=3200;time+=16)framed.paintAt(time);
  const vp=framed.matrices.filter(matrix=>matrix.name==='uVP').at(-1).value;
  for(const draw of framed.geometryDraws.filter(draw=>draw.indexed))for(let i=0;i<draw.vertices.length;i+=9){
    const point=transform(vp,transform(draw.model,[draw.vertices[i],draw.vertices[i+1],draw.vertices[i+2],1]));
    assert.ok(point[3]>0&&Math.abs(point[0]/point[3])<1&&Math.abs(point[1]/point[3])<1,`every actual relaxed paper vertex is framed at width ${width}`);
  }
  framed.dispose();
}
console.log('hero paper: 8 closed subdivided sheets, real dynamic vertex uploads, analytic normals, preserved UVs, delayed corner spring, bounded rebound, flat reduced mode, final framing and cleanup passed');
