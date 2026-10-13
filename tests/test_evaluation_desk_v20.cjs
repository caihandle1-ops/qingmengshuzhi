'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const dom=new JSDOM('<!doctype html><html><head></head><body></body></html>',{runScripts:'outside-only',pretendToBeVisual:true});
const win=dom.window,doc=win.document,listeners=new Set(),observers=[];
const media={matches:false,addEventListener:(_name,fn)=>listeners.add(fn),removeEventListener:(_name,fn)=>listeners.delete(fn)};
win.matchMedia=()=>media;
win.IntersectionObserver=class {constructor(fn){this.fn=fn;this.nodes=new Set();observers.push(this);}observe(node){this.nodes.add(node);}unobserve(node){this.nodes.delete(node);}disconnect(){this.nodes.clear();}};
const read=name=>fs.readFileSync(path.join(__dirname,'../app',name),'utf8'),wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function mount(id='saved-case'){
 const node=doc.createElement('section');node.dataset.evaluationScene='case';node.dataset.evaluationId=id;
 node.innerHTML='<h3>失败</h3><pre>{"value":0,"actual":null}</pre><i class="evaluation-accent" aria-hidden="true"></i><button>查看结果</button>';
 node.getBoundingClientRect=()=>({top:20,bottom:200,left:20,right:600,width:580,height:180});doc.body.append(node);return node;
}
(async()=>{
 win.eval(read('vendor/gsap/gsap.min.js'));doc.body.remove();
 assert.doesNotThrow(()=>win.eval(read('evaluation_desk.js')),'Head bootstrap observes Document before body exists.');
 const body=doc.createElement('body');doc.documentElement.appendChild(body);
 const draft=doc.createElement('input');draft.value='评测不应改动的草稿';doc.body.append(draft);draft.focus();
 const first=mount(),button=first.querySelector('button');let clicks=0;button.onclick=()=>clicks++;
 await wait(100);const progress=+first.style.getPropertyValue('--evaluation-reveal');
 assert.ok(progress>0&&progress<1,'Real bundled GSAP reveals only the decorative accent.');
 assert.equal(first.querySelector('h3').textContent,'失败');assert.equal(first.querySelector('pre').textContent,'{"value":0,"actual":null}');
 assert.equal(first.style.transform,'');assert.equal(button.style.transform,'');assert.equal(draft.value,'评测不应改动的草稿');assert.equal(doc.activeElement,draft);
 button.click();assert.equal(clicks,1);
 const api=win.QMEvaluationDesk;win.eval(read('evaluation_desk.js'));assert.equal(win.QMEvaluationDesk,api);
 doc.documentElement.dataset.qmMotionMode='research';win.dispatchEvent(new win.Event('qm-motion-preference-change'));
 assert.equal(+first.style.getPropertyValue('--evaluation-reveal'),1);assert.equal(win.gsap.globalTimeline.getChildren(true,true,true).length,0);
 delete doc.documentElement.dataset.qmMotionMode;first.remove();await wait(45);assert.equal(first.style.getPropertyValue('--evaluation-reveal'),'');
 const repeated=mount();await wait(60);assert.equal(repeated.style.getPropertyValue('--evaluation-reveal'),'','Native rerun does not replay a saved case.');
 const second=mount('new-case');await wait(70);assert.ok(+second.style.getPropertyValue('--evaluation-reveal')<1);
 observers[0].fn([{target:second,isIntersecting:false}]);assert.equal(+second.style.getPropertyValue('--evaluation-reveal'),1);
 media.matches=true;listeners.forEach(fn=>fn());const quiet=mount('quiet-case');await wait(55);assert.equal(+quiet.style.getPropertyValue('--evaluation-reveal'),1);
 api.dispose();assert.equal(listeners.size,0);assert.equal(observers[0].nodes.size,0);assert.equal(second.style.getPropertyValue('--evaluation-reveal'),'');
 mount('after-dispose');await wait(35);assert.equal(win.gsap.globalTimeline.getChildren(true,true,true).length,0);
 // Disposal before late body creation cannot leave a deferred mount alive.
 doc.body.remove();win.eval(read('evaluation_desk.js'));win.QMEvaluationDesk.dispose();
 doc.documentElement.appendChild(doc.createElement('body'));const late=mount('late');await wait(40);
 assert.equal(late.style.getPropertyValue('--evaluation-reveal'),'');assert.equal(listeners.size,0);
 console.log('evaluation desk: real GSAP, native verdict/value/focus/click safety, rerun, quiet/offscreen, body readiness and disposal passed');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{win.QMEvaluationDesk?.dispose();win.gsap?.ticker.sleep();dom.window.close();});
