'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{JSDOM}=require('jsdom');
const read=n=>fs.readFileSync(path.join(__dirname,'../app',n),'utf8'),wait=ms=>new Promise(r=>setTimeout(r,ms));
async function story(){
 const dom=new JSDOM('<!doctype html><html><body></body></html>',{runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,d=w.document;let scroll=0;
 const media={matches:false,addEventListener(){},removeEventListener(){}};
 w.matchMedia=()=>media;w.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};
 function mount(){
  const root=d.createElement('section');root.dataset.enterpriseStory='annual-2025';
  root.innerHTML='<span class="es-current-chapter"></span><span class="es-stage-count"></span>'+[0,1,2,3].map(i=>`<a href="#" data-es-jump="${i}">章 ${i}</a><section data-es-chapter="${i}"><i class="es-chapter-rule" aria-hidden="true"></i><strong>0.00 亿元</strong></section><section data-es-pane="${i}">财务原值</section>`).join('');
  for(const [i,n] of [...root.querySelectorAll('[data-es-chapter]')].entries()){n.getBoundingClientRect=()=>({top:100+i*420-scroll,bottom:520+i*420-scroll,height:420,width:300});n.scrollIntoView=()=>{scroll=i*420};}
  d.body.append(root);return root;
 }
 try{
  const root=mount();w.eval(read('vendor/gsap/gsap.min.js'));w.eval(read('enterprise_story.js'));await wait(80);
  const rule=root.querySelector('.es-chapter-rule');assert.ok(rule.style.transform.includes('scale'),'Real GSAP enters decoration');
  assert.equal(root.querySelector('strong').textContent,'0.00 亿元');assert.equal(root.querySelector('a').style.transform,'');
  scroll=500;d.dispatchEvent(new w.Event('scroll'));await wait(50);
  assert.equal(root.querySelector('[data-es-pane="1"]').getAttribute('aria-hidden'),'false');
  d.documentElement.dataset.qmMotionMode='research';w.dispatchEvent(new w.Event('qm-motion-preference-change'));await wait(30);
  assert.equal(w.gsap.globalTimeline.getChildren(true,true,true).length,0);assert.equal(rule.style.transform,'');
  root.remove();await wait(30);delete d.documentElement.dataset.qmMotionMode;
  const next=mount();await wait(50);assert.equal(w.gsap.globalTimeline.getChildren(true,true,true).length,0,'Rerun of the same record does not replay');
  w.__qmEnterpriseStory.dispose();assert.equal(next.style.getPropertyValue('--es-camera-x'),'');assert.equal(next.querySelector('[data-es-pane]').hasAttribute('inert'),false);
 }finally{w.gsap?.ticker.sleep();w.close();}
}
async function risk(){
 const dom=new JSDOM(read('risk_frontend/index.html'),{runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,d=w.document,events=[];
 w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});w.ResizeObserver=class{observe(){}disconnect(){}};w.IntersectionObserver=class{observe(){}disconnect(){}};
 w.postMessage=data=>events.push(data);
 w.eval(read('risk_frontend/motion.js'));w.eval(read('risk_frontend/atlas.js'));
 const rules=Array.from({length:6},(_,i)=>({id:'R0'+(i+1),domain:'规则',label:'检查 '+(i+1),status:'triggered',status_label:'已触发',level:'orange',reason:'真实规则结果',rule:'规则阈值',basis:'年度输入',facts:[{metric:'revenue',year:2025,label:'营业收入',value:'0.00',unit:'亿元',source:'annual.csv · B2',can_open:true,journey_actions:['ask','verify']}]}));
 const payload={revision:'same-snapshot',rules,company:'甲企业',year:2025,score:'数据不足',score_available:false,counts:{triggered:6,clear:0,unchecked:0},coverage_complete:true};
 const render=args=>w.dispatchEvent(new w.MessageEvent('message',{source:w,data:{type:'streamlit:render',args:{payload,motion:{version:1,mode:'research'},...args}}}));
 try{
  render({});const first=d.querySelector('.risk-zone');first.click();assert.equal(d.querySelector('#risk-detail').dataset.rule,'R01');
  const source=d.querySelector('button[data-action=source]');assert.ok(source);source.click();
  let event=events.filter(x=>x.type==='streamlit:setComponentValue').at(-1).value;
  assert.deepEqual([event.action,event.rule_id,event.metric,event.year,event.revision],['source','R01','revenue',2025,'same-snapshot']);
  render({source_selection:{revision:payload.revision,rule_id:'R01',metric:'revenue',year:2025}});
  assert.equal(d.querySelector('.risk-zone'),first,'Same snapshot keeps native rule controls');assert.equal(source.getAttribute('aria-expanded'),'true');source.click();
  event=events.filter(x=>x.type==='streamlit:setComponentValue').at(-1).value;assert.equal(event.action,'close');
  first.click();assert.equal(d.querySelector('#risk-detail').dataset.rule,undefined);assert.equal(first.getAttribute('aria-pressed'),'false');
 }finally{w.dispatchEvent(new w.Event('pagehide'));w.close();}
}
(async()=>{await story();await risk();console.log('enterprise / risk: real GSAP, quiet, rerun, disposal, exact source routing and native reversible selection passed');})().catch(e=>{console.error(e);process.exitCode=1});
