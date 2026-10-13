'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const read = name => fs.readFileSync(path.join(__dirname, '../app', name), 'utf8');

async function fixture(engine = false) {
  const dom = new JSDOM('<!doctype html><body><div class="st-key-qa_input"><input value="真实未提交草稿"></div>' +
    '<div class="st-key-workspace_search_open_button"><button>搜索工作区</button></div></body>',
    {runScripts:'outside-only', pretendToBeVisual:true});
  const win = dom.window, doc = win.document, frames = new Map(), mediaListeners = new Set();
  let fid = 0, opens = 0, closes = 0, navigations = 0;
  const media = {matches:false, addEventListener:(_,fn)=>mediaListeners.add(fn), removeEventListener:(_,fn)=>mediaListeners.delete(fn)};
  win.matchMedia = () => media;
  win.HTMLElement.prototype.getBoundingClientRect = () => ({width:400,height:50,left:0,top:0,bottom:50,right:400});
  win.HTMLElement.prototype.scrollIntoView = function() { this._scrolled = true; };
  if(engine) win.eval(read('vendor/gsap/gsap.min.js'));
  win.requestAnimationFrame = fn => {frames.set(++fid,fn); return fid;};
  win.cancelAnimationFrame = id => frames.delete(id);
  const trigger = doc.querySelector('button'), origin = doc.querySelector('input');
  function mount(query='') {
    const panel = doc.createElement('div'); panel.className='st-key-workspace_search_results';
    panel.innerHTML='<div data-qm-command-query=""><i class="qm-command-rule"></i></div>' +
      '<div class="st-key-workspace_palette_query"><input></div><div class="st-key-workspace_search_close"><button>关闭搜索</button></div>' +
      '<div role="tablist"><button role="tab">页面</button></div><div role="tabpanel">' +
      '<div class="st-key-workspace_search_item_one"><button data-route="one">研究资料库</button></div>' +
      '<div class="st-key-workspace_search_item_two"><button disabled>不可用</button></div>' +
      '<div class="st-key-workspace_search_item_three"><button data-route="three">财报问数</button></div></div>' +
      '<div role="tabpanel" style="display:none"><div class="st-key-workspace_search_item_hidden"><button>隐藏分类</button></div></div>';
    panel.querySelector('[data-qm-command-query]').dataset.qmCommandQuery=query;
    panel.querySelector('input').value=query;
    panel.querySelector('.st-key-workspace_search_close button').onclick=()=>{closes++;panel.remove();};
    panel.querySelectorAll('[data-route]').forEach(node=>{node.onclick=()=>{navigations++;panel.remove();};});
    doc.body.append(panel); return panel;
  }
  trigger.onclick=()=>{opens++;mount();};
  win.eval(read('command_palette.js'));
  async function flush() {for(let i=0;i<4;i++){await Promise.resolve();const batch=[...frames.values()];frames.clear();batch.forEach(fn=>fn());}}
  function key(target,key,props={}) {const event=new win.KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,...props});target.dispatchEvent(event);return event;}
  function popup() {const modal=doc.createElement('div');modal.setAttribute('role','dialog');modal.setAttribute('aria-modal','true');doc.body.append(modal);return modal;}
  function cleanup() {win.QMCommandPalette.dispose();win.gsap?.globalTimeline.clear();win.gsap?.ticker.sleep();win.close();}
  return {win,doc,trigger,origin,media,mediaListeners,key,mount,flush,popup,cleanup,
    counts:()=>({opens,closes,navigations}),frames};
}

(async()=>{
  const f=await fixture();
  try {
    const {win,doc,origin,trigger,key}=f;
    origin.focus(); origin.setSelectionRange(2,4);
    assert.equal(key(origin,'k',{ctrlKey:true}).defaultPrevented,true); await f.flush();
    let panel=doc.querySelector('.st-key-workspace_search_results'), input=panel.querySelector('input');
    assert.equal(f.counts().opens,1);assert.equal(doc.activeElement,input);assert.equal(origin.value,'真实未提交草稿');
    assert.equal(trigger.getAttribute('aria-keyshortcuts'),'Control+k Meta+k');
    assert.equal(key(input,'ArrowDown').defaultPrevented,true);
    assert.equal(doc.activeElement.dataset.route,'one');
    key(doc.activeElement,'ArrowDown');assert.equal(doc.activeElement.dataset.route,'three','Disabled and inactive-tab results are skipped');
    key(doc.activeElement,'ArrowDown');assert.equal(doc.activeElement.dataset.route,'one');
    key(doc.activeElement,'ArrowUp');assert.equal(doc.activeElement,input);
    key(input,'ArrowUp');assert.equal(doc.activeElement.dataset.route,'three');
    assert.equal(key(doc.activeElement,'Enter').defaultPrevented,false,'Enter uses exactly one native button activation');
    key(doc.activeElement,'Escape'); await f.flush();
    assert.equal(f.counts().closes,1);assert.equal(doc.activeElement,origin);assert.equal(origin.selectionStart,2);
    assert.equal(origin.selectionEnd,4);

    key(origin,'k',{metaKey:true});await f.flush();panel=doc.querySelector('.st-key-workspace_search_results');input=panel.querySelector('input');
    key(input,'k',{ctrlKey:true});await f.flush();assert.equal(f.counts().opens,2,'Open palette shortcut only refocuses');
    input.value='新的未提交词';assert.equal(key(input,'ArrowDown').defaultPrevented,false);assert.equal(doc.activeElement,input);
    assert.equal(key(input,'Enter').defaultPrevented,false,'Dirty input Enter commits native Streamlit search');
    input.value='';input.dispatchEvent(new win.CompositionEvent('compositionstart',{bubbles:true}));
    assert.equal(key(input,'Escape').defaultPrevented,false,'IME Escape remains native');
    assert.equal(key(input,'k',{ctrlKey:true}).defaultPrevented,false);
    input.dispatchEvent(new win.CompositionEvent('compositionend',{bubbles:true}));
    assert.equal(key(input,'ArrowDown',{isComposing:true}).defaultPrevented,false);
    assert.equal(key(input,'ArrowDown',{keyCode:229}).defaultPrevented,false);
    const tab=panel.querySelector('[role=tab]');tab.focus();assert.equal(key(tab,'ArrowDown').defaultPrevented,false);
    const popup=f.popup();assert.equal(key(input,'Escape').defaultPrevented,false);assert.equal(key(input,'k',{ctrlKey:true}).defaultPrevented,false);popup.remove();
    key(input,'k',{ctrlKey:true});key(input,'ArrowDown');doc.activeElement.click();await f.flush();
    assert.equal(f.counts().navigations,1);assert.notEqual(doc.activeElement,origin,'Resource navigation does not restore the old task focus');

    win.eval(read('command_palette.js'));win.eval(read('command_palette.js'));
    key(origin,'k',{ctrlKey:true});await f.flush();assert.equal(f.counts().opens,3,'Rerun injection has only one key handler');
    panel=doc.querySelector('.st-key-workspace_search_results');input=panel.querySelector('input');key(input,'ArrowDown');
    const replacement=f.mount();panel.remove();await f.flush();
    assert.equal(replacement.querySelector('[data-qm-command-active]'),null,'Replaced controls never retain stale selection');
    win.QMCommandPalette.dispose();
    assert.equal(trigger.hasAttribute('aria-keyshortcuts'),false);
    assert.equal(key(origin,'k',{ctrlKey:true}).defaultPrevented,false);
    assert.equal(f.frames.size,0);
  } finally {f.cleanup();}

  const f2=await fixture(true);
  try {
    f2.origin.focus();f2.key(f2.origin,'k',{ctrlKey:true});await f2.flush();
    const panel=f2.doc.querySelector('.st-key-workspace_search_results'), rule=panel.querySelector('.qm-command-rule');
    const tween=f2.win.gsap.getTweensOf(rule)[0];assert.ok(tween);tween.pause().progress(.5);
    assert.ok(rule.style.transform);assert.equal(panel.style.transform,'');
    for(const node of panel.querySelectorAll('input,button')) assert.equal(node.getAttribute('style'),null);
    f2.media.matches=true;for(const listener of f2.mediaListeners)listener();
    assert.equal(rule.style.transform,'');assert.equal(f2.win.gsap.getTweensOf(rule).length,0);
    f2.key(panel.querySelector('input'),'Escape');await f2.flush();
    f2.key(f2.origin,'k',{ctrlKey:true});await f2.flush();
    assert.equal(f2.win.gsap.getTweensOf(f2.doc.querySelector('.qm-command-rule')).length,0,'Reduced motion remains static and usable');
  } finally {f2.cleanup();}
  const f3=await fixture();
  try {
    const {doc,win,origin,trigger}=f3;
    let persistedDraft='', preservedDraft='', changes=0;
    const order=[];
    origin.addEventListener('input',()=>changes++);
    origin.addEventListener('change',()=>changes++);
    origin.addEventListener('blur',()=>{
      order.push('blur');
      // Emulate the native input's local state commit after its event handler.
      // The controller must allow this before the server's preserve callback.
      win.queueMicrotask(()=>{persistedDraft=origin.value;order.push('commit');});
    });
    trigger.onclick=()=>{
      order.push('open');preservedDraft=persistedDraft;
      origin.closest('.st-key-qa_input').remove();
      const panel=f3.mount();
      panel.querySelector('.st-key-workspace_search_close button').onclick=()=>{
        const wrapper=doc.createElement('div');wrapper.className='st-key-qa_input';
        const restored=doc.createElement('input');restored.value=preservedDraft;wrapper.append(restored);doc.body.prepend(wrapper);
        panel.remove();
      };
    };
    origin.focus();origin.value='桌面验收草稿，暂不提交';origin.setSelectionRange(4,6);
    f3.key(origin,'k',{ctrlKey:true});
    assert.equal(preservedDraft,'','Opening waits for native blur to commit');
    await f3.flush();
    assert.deepEqual(order,['blur','commit','open']);
    assert.equal(preservedDraft,'桌面验收草稿，暂不提交');assert.equal(changes,0,'No synthetic input/change or state injection');
    f3.key(doc.querySelector('.st-key-workspace_palette_query input'),'Escape');await f3.flush();
    const restored=doc.querySelector('.st-key-qa_input input');
    assert.equal(restored.value,'桌面验收草稿，暂不提交');assert.equal(doc.activeElement,restored);
    assert.equal(restored.selectionStart,4);assert.equal(restored.selectionEnd,6);
    f3.key(restored,'k',{ctrlKey:true});win.QMCommandPalette.dispose();await f3.flush();
    assert.equal(doc.querySelector('.st-key-workspace_search_results'),null,'Disposal cancels a queued open');
  } finally {f3.cleanup();}
  const f4=await fixture();
  try {
    const {doc,win,trigger}=f4, timers=new Map();let timerId=0, height=2400, scrolls=0;
    win.setTimeout=fn=>{timers.set(++timerId,fn);return timerId;};win.clearTimeout=id=>timers.delete(id);
    const main=doc.createElement('main');main.dataset.testid='stMain';doc.body.prepend(main);
    Object.defineProperty(main,'scrollHeight',{get:()=>height});Object.defineProperty(main,'clientHeight',{get:()=>800});
    main.scrollTop=740;main.scrollTo=({top,left,behavior})=>{
      assert.equal(behavior,'instant','Return uses no smooth scrolling or bounce');main.scrollTop=top;main.scrollLeft=left;scrolls++;
    };
    const marker=doc.createElement('span');marker.dataset.studioLocation='财报问数';main.append(marker);
    main.append(f4.origin.parentElement);
    function attach(stale=false) {
      const wrapper=doc.createElement('div');wrapper.className='st-key-qa_input';wrapper.dataset.stale=String(stale);
      const input=doc.createElement('input');input.value='分批重建仍保留的草稿';wrapper.append(input);main.append(wrapper);return input;
    }
    trigger.onclick=()=>{
      doc.querySelector('.st-key-qa_input')?.remove();main.scrollTop=0;
      const panel=f4.mount();panel.querySelector('.st-key-workspace_search_close button').onclick=()=>panel.remove();
    };
    async function closeBeforeOriginalMounts(input) {
      input.focus();input.setSelectionRange(3,5);main.scrollTop=740;
      f4.key(input,'k',{ctrlKey:true});await f4.flush();
      f4.key(doc.querySelector('.st-key-workspace_palette_query input'),'Escape');await f4.flush();
      assert.notEqual(doc.activeElement,trigger,'Missing original does not immediately discard the recovery record');
    }
    await closeBeforeOriginalMounts(f4.origin);
    await f4.flush();await f4.flush(); // Separate native batches, not one atomic replacement.
    let restored=attach(true);await f4.flush();assert.notEqual(doc.activeElement,restored,'Stale native widgets are ignored');
    height=1000;restored.parentElement.dataset.stale='false';await f4.flush();
    assert.notEqual(doc.activeElement,restored,'Partial short content must not clamp the scroll position');assert.equal(scrolls,0);
    height=2400;main.append(doc.createElement('p'));await f4.flush();
    assert.equal(doc.activeElement,restored);assert.equal(restored.selectionStart,3);assert.equal(restored.selectionEnd,5);
    assert.equal(main.scrollTop,740);assert.equal(scrolls,1);
    const remounted=restored.cloneNode();restored.replaceWith(remounted);await f4.flush();restored=remounted;
    assert.equal(doc.activeElement,restored,'One later React replacement recovers focus without another scroll');assert.equal(scrolls,1);
    trigger.dispatchEvent(new win.Event('pointerdown',{bubbles:true}));
    const afterPointer=restored.cloneNode();restored.replaceWith(afterPointer);await f4.flush();restored=afterPointer;
    assert.notEqual(doc.activeElement,restored,'A pointer action cancels recovery immediately');assert.equal(timers.size,0);

    for (const gesture of ['Tab','wheel']) {
      await closeBeforeOriginalMounts(restored);
      if(gesture==='Tab') f4.key(doc.body,'Tab'); else doc.dispatchEvent(new win.Event('wheel',{bubbles:true}));
      restored=attach();await f4.flush();assert.notEqual(doc.activeElement,restored,gesture+' must win over automatic focus');
      assert.equal(timers.size,0);
    }
    await closeBeforeOriginalMounts(restored);
    marker.dataset.studioLocation='企业分析';main.append(doc.createElement('p'));await f4.flush();
    restored=attach();await f4.flush();assert.notEqual(doc.activeElement,restored,'New route cancels an old focus request');
    assert.equal(timers.size,0);marker.dataset.studioLocation='财报问数';
    await closeBeforeOriginalMounts(restored);
    const expiry=[...timers.values()];timers.clear();expiry.forEach(fn=>fn());
    assert.equal(doc.activeElement,trigger,'Only final timeout falls back to the visible search entry');
    restored=attach();await f4.flush();assert.notEqual(doc.activeElement,restored,'A late widget cannot steal focus after expiry');
    assert.equal(timers.size,0);
  } finally {f4.cleanup();}
  process.stdout.write('command palette: native navigation, IME, query commit, focus return, rerun cleanup and actual GSAP passed\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
