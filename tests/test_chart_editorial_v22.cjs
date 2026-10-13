'use strict';
// Exercise the actual pinned GSAP and production chart: decoration must never
// own any number, financial geometry, hit target, or source identity.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const read=name=>fs.readFileSync(path.join(__dirname,'../app/chart_frontend',name),'utf8');
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',error=>errors.push(error.message));
const dom=new JSDOM(read('index.html'),{runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc}),win=dom.window,doc=win.document;
const media=new win.EventTarget();media.matches=false;win.matchMedia=()=>media;
let intersection,resize;win.IntersectionObserver=class{constructor(callback){this.callback=callback;intersection=this;}observe(){}disconnect(){this.closed=true;}};
win.ResizeObserver=class{constructor(callback){this.callback=callback;resize=this;}observe(){}disconnect(){this.closed=true;}};
win.HTMLElement.prototype.getBoundingClientRect=()=>({left:20,top:20,width:800,height:400,right:820,bottom:420});
win.SVGElement.prototype.getBoundingClientRect=()=>({left:20,top:20,width:800,height:300,right:820,bottom:320});
win.SVGElement.prototype.getTotalLength=()=>100;
Object.defineProperty(doc.getElementById('chart-viewport'),'clientWidth',{value:800,configurable:true});
const messages=[];win.postMessage=message=>messages.push(message);
win.eval(read('gsap.min.js'));const gsap=win.gsap;win.eval(read('chart.js'));
const points=[{id:'A|2023|revenue',company:'A',year:2023,metric:'revenue',value:0,source:'revenue.csv',location:'B2',source_index:0,source_id:'revenue-2023'},
 {id:'A|2025|revenue',company:'A',year:2025,metric:'revenue',value:8,source:'revenue.csv',location:'B3',source_index:1,source_id:'revenue-2025'},
 {id:'A|2023|net_profit',company:'A',year:2023,metric:'net_profit',value:-7,source:'profit.csv',location:'C2',source_index:2,source_id:'profit-2023'},
 {id:'A|2025|net_profit',company:'A',year:2025,metric:'net_profit',value:0,source:'profit.csv',location:'C3',source_index:3,source_id:'profit-2025'}];
const payload={revision:'real-financial-records',mode:'bar',target_year:2025,metrics:[{id:'revenue',label:'营业收入',unit:'亿元'},{id:'net_profit',label:'净利润',unit:'亿元'}],points};
const render=args=>win.dispatchEvent(new win.MessageEvent('message',{source:win,data:{type:'streamlit:render',args:{payload,motion:{version:1,mode:'presentation'},...args}}}));
const valueEvents=()=>messages.filter(m=>m.type==='streamlit:setComponentValue');
const band=doc.getElementById('chart-turn-band'),trace=doc.getElementById('chart-turn-trace');
function assertOnlyDecoration(){
 const tweens=gsap.globalTimeline.getChildren(true,true,false).filter(t=>t.targets().some(node=>node===band||node===trace));
 assert.ok(tweens.length>=2,'The metric change has real GSAP tweens.');
 for(const tween of tweens)assert.ok(tween.targets().every(node=>node===band||node===trace));
 for(const node of doc.querySelectorAll('#marks *,#grid *,#readout-value,button'))assert.equal(gsap.getTweensOf(node).length,0,'No actual value or native hit target is tweened.');
}
try{
 render();gsap.globalTimeline.progress(1);assert.equal(doc.querySelectorAll('.chart-bar')[0].getAttribute('height'),'0');
 doc.querySelectorAll('#metric-tabs button')[1].click();
 assert.equal(doc.getElementById('chart-shell').dataset.chartTransition,'turning');assertOnlyDecoration();
 assert.deepEqual([...doc.querySelectorAll('.value-label')].map(node=>node.textContent),['-7.00','0.00']);
 assert.equal(doc.getElementById('chart').getAttribute('viewBox'),'0 0 800 300');
 assert.equal(doc.querySelectorAll('.chart-bar')[1].getAttribute('height'),'0');
 assert.equal(doc.getElementById('selection-band').dataset.year,'2025');
 const actualGeometry=doc.getElementById('chart').innerHTML;
 const transitions=gsap.getTweensOf(band);transitions[0].progress(.45);assert.equal(doc.getElementById('chart').innerHTML,actualGeometry);
 render();assert.equal(gsap.getTweensOf(band)[0],transitions[0],'Same revision keeps the same pass.');
 doc.querySelectorAll('.mark')[0].dispatchEvent(new win.Event('pointerenter'));
 assert.equal(doc.getElementById('selection-band').dataset.year,'2023');assert.match(doc.getElementById('readout-value').textContent,/-7.00/);
 assert.equal(valueEvents().length,0,'Hover remains browser-local.');
 doc.getElementById('source-button').click();assert.equal(valueEvents().at(-1).value.source_id,'profit-2023');
 assert.equal(valueEvents().at(-1).value.index,2);assert.equal(valueEvents().at(-1).value.revision,payload.revision);
 render({source_highlight:1});assert.equal(doc.getElementById('selection-band').dataset.point,'A|2025|revenue');assert.match(doc.getElementById('readout-source').textContent,/revenue.csv.*B3/);
 intersection.callback([{isIntersecting:false}]);assert.equal(gsap.getTweensOf(band).length,0);
 doc.querySelectorAll('#metric-tabs button')[1].click();assert.equal(gsap.getTweensOf(band).length,0,'Offscreen changes do not start decoration.');
 intersection.callback([{isIntersecting:true}]);media.matches=true;media.dispatchEvent(new win.Event('change'));
 doc.querySelectorAll('#metric-tabs button')[0].click();assert.equal(gsap.getTweensOf(band).length,0,'Reduced motion remains still.');
 media.matches=false;media.dispatchEvent(new win.Event('change'));doc.querySelectorAll('#metric-tabs button')[1].click();assertOnlyDecoration();
 win.__qmChart.dispose();assert.equal(gsap.getTweensOf(band).length,0);assert.equal(gsap.getTweensOf(trace).length,0);assert.ok(resize.closed&&intersection.closed);
 assert.deepEqual(errors,[]);console.log('annual chart v22: real GSAP decoration, exact zero/negative geometry, authority-bound source/year sync, same revision, offscreen/reduced/dispose passed');
}finally{win.__qmChart.dispose();gsap.globalTimeline.clear();gsap.ticker.sleep();win.close();}
