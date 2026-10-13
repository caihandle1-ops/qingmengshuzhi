'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<!doctype html><html><body></body></html>',{runScripts:'outside-only',pretendToBeVisual:true});
const win=dom.window,doc=win.document,listeners=new Set(),observers=[];
const media={matches:false,addEventListener:(_,fn)=>listeners.add(fn),removeEventListener:(_,fn)=>listeners.delete(fn)};
win.matchMedia=()=>media;
win.IntersectionObserver=class{constructor(callback){this.callback=callback;this.nodes=new Set();observers.push(this)}observe(n){this.nodes.add(n)}unobserve(n){this.nodes.delete(n)}disconnect(){this.nodes.clear()}};
const read=n=>fs.readFileSync(path.join(__dirname,'../app',n),'utf8'),wait=ms=>new Promise(r=>setTimeout(r,ms));
function scene(id='record-1'){
 const node=doc.createElement('section');node.dataset.deskScene='answer';node.dataset.deskId=id;
 node.innerHTML='<strong>0.00 亿元</strong><input value="未提交备注"><button>查看来源</button><i data-desk-line aria-hidden="true"></i>';
 node.getBoundingClientRect=()=>({top:20,bottom:180,width:650,height:160});doc.body.append(node);return node;
}
(async()=>{
 const first=scene(),input=first.querySelector('input'),button=first.querySelector('button');input.focus();let clicks=0;button.onclick=()=>clicks++;
 win.eval(read('vendor/gsap/gsap.min.js'));win.eval(read('research_desks.js'));await wait(90);
 const progress=+first.style.getPropertyValue('--desk-progress');assert.ok(progress>0&&progress<1,'Real GSAP animates the decorative reveal.');
 assert.equal(first.querySelector('strong').textContent,'0.00 亿元');assert.equal(input.value,'未提交备注');assert.equal(doc.activeElement,input);assert.equal(first.style.transform,'');assert.equal(button.style.transform,'');
 button.click();assert.equal(clicks,1);
 doc.documentElement.dataset.qmMotionMode='research';win.dispatchEvent(new win.Event('qm-motion-preference-change'));assert.equal(+first.style.getPropertyValue('--desk-progress'),1);assert.equal(win.gsap.globalTimeline.getChildren(true,true,true).length,0);
 delete doc.documentElement.dataset.qmMotionMode;win.dispatchEvent(new win.Event('qm-motion-preference-change'));
 const singleton=win.QMResearchDesks;win.eval(read('research_desks.js'));assert.equal(win.QMResearchDesks,singleton);
 first.remove();await wait(60);assert.equal(first.style.getPropertyValue('--desk-progress'),'');
 const replacement=scene();await wait(80);assert.equal(replacement.style.getPropertyValue('--desk-progress'),'','Same saved answer remount does not replay and uses CSS final state.');
 const second=scene('record-2');await wait(65);assert.ok(+second.style.getPropertyValue('--desk-progress')<1);
 observers[0].callback([{target:second,isIntersecting:false}]);assert.equal(+second.style.getPropertyValue('--desk-progress'),1);
 media.matches=true;listeners.forEach(fn=>fn());const third=scene('record-3');await wait(60);assert.equal(+third.style.getPropertyValue('--desk-progress'),1);
 singleton.dispose();assert.equal(listeners.size,0);assert.equal(observers[0].nodes.size,0);assert.equal(second.style.getPropertyValue('--desk-progress'),'');
 win.gsap.ticker.sleep();dom.window.close();console.log('research desks: native value/focus/click safety, real GSAP, rerun, quiet/offscreen and cleanup passed');
})().catch(error=>{win.gsap?.ticker.sleep();dom.window.close();console.error(error);process.exitCode=1;});
