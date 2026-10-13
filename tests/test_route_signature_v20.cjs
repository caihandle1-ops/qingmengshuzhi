'use strict';
// Real pinned GSAP. Tests ownership and teardown; browser review checks pixels.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const source=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8');
const delay=ms=>new Promise(done=>setTimeout(done,ms));
const dom=new JSDOM('<!doctype html><html><body><button>口径核验</button><main>真实值：-12.56 / 0</main></body></html>',{runScripts:'outside-only',pretendToBeVisual:true});
const win=dom.window,doc=win.document,media=new win.EventTarget();media.matches=false;win.matchMedia=()=>media;
win.eval(source('vendor/gsap/gsap.min.js'));win.eval(source('route_signature.js'));
(async()=>{
 const api=win.QMRouteSignature,button=doc.querySelector('button'),main=doc.querySelector('main'),text=main.textContent;
 const plane=doc.createElement('div');plane.className='qm-route-stage';doc.body.appendChild(plane);
 for(const [label,kind,count] of [['口径核验','scope',6],['反证核验','counter',3],['证据复演','replay',4],['数据资产','assets',3],['财报问数','qa',3]]){
   const record=api.begin(plane,label);assert.equal(record.type,kind);assert.equal(record.pieces.length,count);
   assert.equal(record.node.getAttribute('aria-hidden'),'true');assert.equal(record.node.querySelector('button,input,a'),null);
   await delay(50);assert.ok(win.gsap.getTweensOf(record.pieces[0]).length);
   api.land(record,{left:800,top:250,width:180,height:270},{left:260,top:60,width:1000,height:780});
   assert.equal(record.phase,'arrival');await delay(570);assert.equal(Number(record.node.style.opacity),0);
   api.end(record);assert.equal(api.inspect().active,0);assert.equal(plane.children.length,0);
 }
 const first=api.begin(plane,'口径核验');api.end(first);api.end(first);assert.equal(api.inspect().active,0);
 const active=api.begin(plane,'证据复演');media.matches=true;media.dispatchEvent(new win.Event('change'));
 assert.equal(api.inspect().active,0);assert.equal(active.node.isConnected,false);assert.equal(api.begin(plane,'口径核验'),null);
 media.matches=false;doc.documentElement.dataset.qmMotionMode='research';assert.equal(api.begin(plane,'口径核验'),null);
 doc.documentElement.dataset.qmMotionMode='presentation';api.begin(plane,'反证核验');
 win.eval(source('route_signature.js'));assert.equal(win.QMRouteSignature,api);assert.equal(api.inspect().active,1);
 assert.equal(button.style.cssText,'');assert.equal(main.style.cssText,'');assert.equal(main.textContent,text);
 api.dispose();assert.equal(plane.children.length,0);assert.equal(api.begin(plane,'口径核验'),null);
 win.eval(source('route_signature.js'));const replacement=win.QMRouteSignature;assert.notEqual(replacement,api);
 replacement.begin(plane,'口径核验');media.matches=true;media.dispatchEvent(new win.Event('change'));assert.equal(replacement.inspect().active,0);
 replacement.dispose();win.gsap.globalTimeline.clear();win.gsap.ticker.sleep();win.close();
 console.log('route signature v20: 5 motifs, GSAP landing, native controls unchanged, rapid cancel, reduced motion and disposal passed');
})().catch(error=>{console.error(error);win.close();process.exitCode=1;});
