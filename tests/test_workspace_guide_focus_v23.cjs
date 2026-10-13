'use strict';
const assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const {install}=require('../app/workspace_guide.js');
const pause=()=>new Promise(resolve=>setTimeout(resolve,40));
function visible(node){node.getBoundingClientRect=()=>({width:300,height:40});node.scrollIntoView=()=>{};return node;}
(async()=>{
 const dom=new JSDOM('<body><span data-qm-guide-focus="question" data-qm-guide-request="first"></span></body>',{pretendToBeVisual:true});
 const win=dom.window,doc=win.document;let submits=0,focuses=0;
 doc.addEventListener('submit',()=>submits++);doc.addEventListener('click',()=>submits++);
 const api=install(win,doc);
 await pause();
 const composer=doc.createElement('div');composer.className='st-key-qa_composer';
 composer.innerHTML='<form><input aria-label="自然语言问题" value="我的草稿"></form>';
 const input=visible(composer.querySelector('input'));input.addEventListener('focus',()=>focuses++);doc.body.append(composer);
 await pause();assert.equal(doc.activeElement,input);assert.equal(input.value,'我的草稿');assert.equal(submits,0);
 input.blur();api.scan();doc.body.append(doc.createElement('div'));await pause();assert.equal(focuses,1,'unrelated rerender must not steal focus');
 const marker=doc.querySelector('[data-qm-guide-focus]');marker.setAttribute('data-qm-guide-request','second');marker.setAttribute('data-qm-guide-focus','selection');
 const shell=doc.createElement('div');shell.className='st-key-qa_scope_shell';shell.innerHTML='<details><summary tabindex="0">调整研究条件</summary><div class="st-key-qa_scope"><input role="combobox"></div></details>';
 visible(shell.querySelector('summary'));shell.querySelector('input').getBoundingClientRect=()=>({width:0,height:0});doc.body.append(shell);
 api.scan();await pause();assert.equal(doc.activeElement,shell.querySelector('summary'));assert.equal(shell.querySelector('details').open,false);assert.equal(submits,0);
 marker.setAttribute('data-qm-guide-request','bad');marker.setAttribute('data-qm-guide-focus','submit');api.scan();await pause();assert.equal(submits,0);
 api.dispose();win.close();console.log('workspace guide: delayed field, preserved draft, deduplication, collapsed scope, action allowlist passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
