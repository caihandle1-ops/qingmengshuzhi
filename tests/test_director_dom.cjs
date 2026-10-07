'use strict';
// Execute the production DOM controller without a browser or extra package.
// This adapter supplies only DOM/event/animation APIs that controller uses.
// It does not implement CSS layout and is not a visual rendering test.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {setMaxListeners} = require('node:events');
const frontend=path.resolve(__dirname,'../app/director_frontend');

function environment({reducedMotion=false, fullscreen=true}={}) {
  const allNodes=[], animations=[], observers=[], messages=[];
  class Events {
    constructor(){this.listeners=new Map();}
    addEventListener(type,callback,options={}) {
      if(options.signal?.aborted)return;
      const list=this.listeners.get(type)||new Set();list.add(callback);this.listeners.set(type,list);
      options.signal?.addEventListener('abort',()=>list.delete(callback),{once:true});
    }
    async emit(type,properties={}) {const event={type,target:this,preventDefault(){this.defaultPrevented=true;},...properties};
      return Promise.all([...this.listeners.get(type)||[]].map(callback=>callback(event)));}
    listenerCount(){return [...this.listeners.values()].reduce((n,set)=>n+set.size,0);}
  }
  let document;
  class Element extends Events {
    constructor(tag){super();this.tagName=tag.toUpperCase();this.children=[];this.parentElement=null;this.dataset={};this.style={};this.attributes={};this._text='';this.className='';this.disabled=false;this.hidden=false;allNodes.push(this);}
    set textContent(value){this._text=String(value);this.replaceChildren();}
    get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
    set innerHTML(_){throw new Error('Director must never parse content through innerHTML');}
    append(...children){for(const child of children){child.parentElement=this;this.children.push(child);}}
    replaceChildren(...children){for(const child of this.children)child.parentElement=null;this.children=[];this.append(...children);}
    get firstElementChild(){return this.children[0]||null;}
    setAttribute(name,value){assert.ok(!/^on/i.test(name),'no executable event attributes');this.attributes[name]=String(value);}
    getAttribute(name){return this.attributes[name]??null;}
    matches(selector){if(selector.startsWith('.'))return this.className.split(' ').includes(selector.slice(1));
      const attribute=selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
      if(attribute){const name=attribute[1];const value=name==='data-focus-key'?this.dataset.focusKey:this.getAttribute(name);return attribute[2]===undefined?value!==null&&value!==undefined:value===attribute[2];}
      return this.tagName.toLowerCase()===selector;}
    querySelectorAll(selector){const list=[];const visit=parent=>{for(const child of parent.children){if(selector.split(',').some(s=>child.matches(s.trim())))list.push(child);visit(child);}};visit(this);return list;}
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
    closest(selector){for(let target=this;target;target=target.parentElement){if(selector.split(',').some(s=>target.matches(s.trim())))return target;}return null;}
    focus(){document.activeElement=this;}
    async click(){if(this.disabled)return;if(this.tagName==='INPUT'&&this.type==='checkbox'){this.checked=!this.checked;await this.emit('change');}else await this.emit('click');}
    getBoundingClientRect(){return {height:720};}
    animate(frames,options){const animation={node:this,frames,options,cancelled:false,cancel(){this.cancelled=true;}};animations.push(animation);return animation;}
    async requestFullscreen(){document.fullscreenElement=this;await document.emit('fullscreenchange');}
  }
  document=new Events();document.root=new Element('body');document.activeElement=document.root;document.hidden=false;document.fullscreenEnabled=fullscreen;document.fullscreenElement=null;
  document.createElement=tag=>new Element(tag);document.getElementById=id=>[document.root,...document.root.querySelectorAll('*')].find(n=>n.id===id)||allNodes.find(n=>n.id===id&&n.parentElement);
  const originalMatches=Element.prototype.matches;Element.prototype.matches=function(selector){return selector==='*'||originalMatches.call(this,selector);};
  document.exitFullscreen=async()=>{document.fullscreenElement=null;await document.emit('fullscreenchange');};
  for(const match of fs.readFileSync(path.join(frontend,'index.html'),'utf8').matchAll(/<([a-z][a-z0-9-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)){
    const element=new Element(match[1]);element.id=match[3];element.hidden=/\bhidden\b/.test(match[2]);element.className=match[2].match(/\bclass="([^"]*)"/)?.[1]||'';document.root.append(element);
  }
  class Observer {constructor(callback){this.callback=callback;this.disconnected=false;observers.push(this);}observe(node){this.node=node;}disconnect(){this.disconnected=true;}}
  class TestAbortController extends AbortController {constructor(){super();setMaxListeners(0,this.signal);}}
  const media=new Events();media.matches=reducedMotion;
  const context=new Events();Object.assign(context,{document,AbortController:TestAbortController,IntersectionObserver:Observer,ResizeObserver:Observer,matchMedia:()=>media,
    parent:{postMessage:message=>messages.push(message)},console,Date,Number,Math,Set,Array});context.window=context;
  vm.createContext(context);for(const file of ['director-model.js','director.js'])vm.runInContext(fs.readFileSync(path.join(frontend,file),'utf8'),context,{filename:file});
  const get=id=>document.getElementById(id);
  return {context,document,allNodes,animations,observers,messages,media,get,
    render:payload=>context.emit('message',{source:context.parent,data:{type:'streamlit:render',args:{payload}}}),
    key:(key,code=key,target=document.root)=>document.emit('keydown',{key,code,target}),
    values:()=>messages.filter(message=>message.type==='streamlit:setComponentValue')};
}

const malicious='<img src=x onerror="globalThis.executed=true">';
const source={file:malicious+'超长来源名称'.repeat(25),location:'B3 · 第 2 页',identity:'用户导入',label:'2024 年 营业收入'};
const identity={label:'用户导入',coverage_text:'2024 年',note:'沿用当前记录'};
const metrics=[{label:'营业收入',value:123.45,unit:'亿元',source},{label:'归母净利润',value:-3.25,unit:'亿元',source},{label:'经营现金流',value:null,unit:'亿元',source}];
const payload={version:1,revision:'first',brand:'擎梦数智',company:'超长公司名称'.repeat(35),identity,logo:'javascript:alert(1)',chapters:[
  {id:'overview',kind:'overview',title:'企业全景',heading:'超长公司名称'.repeat(35),body:'已有记录',period:'2024',year_count:1,identity},
  {id:'metrics',kind:'metrics',title:'经营量级',heading:'真实数值',year:2024,metrics,identity},
  {id:'annual',kind:'annual',title:'年度展开',heading:'年度',rows:[{year:2024,metrics}],identity},
  {id:'answer',kind:'answer',title:'已有研究结论',heading:'保存的问题'+malicious,body:'完整答案：'+malicious,status:'待复核结果',scope:'测试企业',sources:[source],identity},
  {id:'signals',kind:'signals',title:'风险依据',heading:'规则信号',alerts:[{title:malicious,message:'已记录',basis:'缺数据',rule:'仍待核对'}],identity},
  {id:'sources',kind:'sources',title:'来源索引',heading:'原始依据',sources:[source],identity},
  {id:'report',kind:'report',title:'已有报告',heading:'已有报告',body:'报告全文'+malicious,identity},
  {id:'empty',kind:'empty',title:'资料待接入',heading:'暂无记录',body:'资料待接入',identity}
]};

(async()=>{
  const env=environment();
  assert.equal(env.messages[0].type,'streamlit:componentReady');
  await env.context.emit('message',{source:{},data:{type:'streamlit:render',args:{payload}}});
  assert.equal(env.context.__qmDirector.deck.snapshot().payload,null,'ignore messages outside Streamlit parent');
  await env.render(payload);
  assert.equal(env.get('brand-logo').hidden,true,'untrusted logo schemes are never applied');
  assert.equal(env.get('stage').firstElementChild.getAttribute('aria-label'),'企业全景');
  for(let index=1;index<payload.chapters.length;index++){
    const oldAnimations=[...env.animations],oldButtons=env.get('chapters').querySelectorAll('button');await env.get('next').click();
    assert.equal(env.context.__qmDirector.deck.snapshot().active,payload.chapters[index].id);
    assert.ok(oldAnimations.every(animation=>animation.cancelled),'prior chapter motion is cancelled');
    assert.ok(oldButtons.every(button=>button.listenerCount()===0),'detached navigation handlers are removed immediately');
  }
  assert.equal(env.get('next').disabled,true);
  await env.key('ArrowLeft');assert.equal(env.context.__qmDirector.deck.snapshot().active,'report');
  assert.ok(env.get('stage').textContent.includes(malicious));
  assert.equal(env.get('stage').querySelectorAll('img').length,0,'supplied markup is rendered as plain text');
  assert.equal(env.context.executed,undefined);
  await env.key('ArrowLeft');await env.key(' ','Space');assert.equal(env.context.__qmDirector.deck.snapshot().active,'report');
  const stage=env.get('stage').firstElementChild;const animated=env.animations.length;await env.render(payload);
  assert.equal(env.get('stage').firstElementChild,stage);assert.equal(env.animations.length,animated,'same payload must not replay');
  await env.get('configure').click();assert.equal(env.get('editor').hidden,false);
  const reportUp=env.get('editor-list').querySelectorAll('button').find(button=>button.dataset.focusKey==='up-report');
  const oldEditorControls=[...env.get('editor-list').querySelectorAll('button'),...env.get('editor-list').querySelectorAll('input')];reportUp.focus();await reportUp.click();
  assert.ok(oldEditorControls.every(control=>control.listenerCount()===0),'detached editor handlers are removed immediately');
  assert.equal(env.context.__qmDirector.deck.snapshot().active,'report');
  assert.equal(env.document.activeElement.dataset.focusKey,'up-report');
  assert.ok(env.get('stage').querySelector('.slide-label').textContent.startsWith('06 /'),'reordering updates the painted chapter number');
  await env.get('editor-list').querySelectorAll('input').find(input=>input.dataset.focusKey==='check-report').click();
  assert.notEqual(env.context.__qmDirector.deck.snapshot().active,'report');
  await env.get('reset-order').click();await env.get('close-editor').click();assert.equal(env.get('editor').hidden,true);
  assert.equal(env.values().length,0,'chapter selection, ordering and navigation stay client-side');
  await env.get('fullscreen').click();assert.equal(env.document.fullscreenElement,env.get('director'));
  await Promise.all([env.get('exit').click(),env.get('exit').click(),env.key('Escape')]);
  assert.equal(env.values().length,1,'exit is sent only once');assert.equal(env.values()[0].value.revision,'first');
  await env.context.emit('pagehide');
  assert.ok(env.observers.every(observer=>observer.disconnected));
  assert.equal(env.context.listenerCount()+env.document.listenerCount()+env.media.listenerCount(),0);
  assert.equal(env.allNodes.reduce((sum,node)=>sum+node.listenerCount(),0),0,'dispose removes retained node listeners');
  const count=env.messages.length;await env.get('next').click();await env.render({...payload,revision:'late'});assert.equal(env.messages.length,count);
  const reduced=environment({reducedMotion:true});await reduced.render(payload);await reduced.get('next').click();assert.equal(reduced.animations.length,0);
  const navButton=reduced.get('chapters').querySelectorAll('button')[3];navButton.focus();await navButton.click();
  assert.equal(reduced.document.activeElement.dataset.chapterId,'answer','chapter navigation retains keyboard focus');
  const hidden=environment();await hidden.render(payload);hidden.document.hidden=true;await hidden.document.emit('visibilitychange');assert.ok(hidden.animations.every(animation=>animation.cancelled));
  const dormant=hidden.animations.length;await hidden.get('next').click();assert.equal(hidden.animations.length,dormant);
  // A fullscreen exit may resolve after the iframe has already been destroyed.
  const race=environment();await race.render(payload);race.document.fullscreenElement=race.get('director');let finish;
  race.document.exitFullscreen=()=>new Promise(resolve=>{finish=resolve;});
  const exiting=race.get('exit').click();await race.context.emit('pagehide');finish();await exiting;
  assert.equal(race.values().length,0,'unmounted frame cannot publish a late fullscreen exit');
  reduced.context.__qmDirector.dispose();hidden.context.__qmDirector.dispose();
  console.log('director DOM controller: every chapter, editor, keyboard, escaping, single exit, reduced/hidden motion and cleanup passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
