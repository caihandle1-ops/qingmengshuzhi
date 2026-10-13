/* Presentation-only enhancement. Native Streamlit events remain untouched. */
(() => {
  'use strict';
  const quiet = () => reduced.matches || document.documentElement.dataset.qmMotionMode === 'research';
  const VERSION = '2026-10-09.14-editorial-owner-body-ready20';
  const previous = window.__qingmengMotion;
  if (previous && previous.version === VERSION) {
    previous.refresh();
    return;
  }
  if (previous && typeof previous.dispose === 'function') previous.dispose();

  const root = document.documentElement;
  const mainSelector = '[data-testid="stMain"]';
  const targetSelector = [
    '.st-key-workspace_hero', '.st-key-studio_home_lower', '.st-key-workspace_context_panel', '.st-key-workspace_workflow',
    '.st-key-workspace_continue_panel', '.st-key-workspace_research_tools',
    '.st-key-workspace_research_overview', '.st-key-workspace_verification_choices',
    '.st-key-workspace_verification_context', '.st-key-qa_composer',
    '.st-key-qa_suggestions', '.st-key-qa_results', '.st-key-qa_quick_preview',
    '.st-key-qa_extra_examples', '.st-key-qa_clarification',
    '.st-key-scope_result_summary', '.st-key-scope_dimensions_panel',
    '.st-key-scope_sources_panel', '.st-key-scope_manual_panel',
    '.st-key-counter_result_summary', '.st-key-counter_correction',
    '.st-key-replay_history_summary', '.st-key-workspace_search_results',
    '[class*="st-key-answer_workbench_"]',
    '[class*="st-key-answer_check_panel_"]', '[class*="st-key-answer_export_"]',
    '[class*="st-key-guided_picker_qa_answer_panel_"]',
    '[class*="st-key-guided_picker_qa_source_panel_"]',
    '[class*="st-key-guided_picker_qa_export_panel_"]',
    '[class*="st-key-guided_content_"]', '[class*="st-key-qa_details_content_"]',
    '[class*="st-key-qa_selected_panel_"]', '[class*="st-key-qa_export_content_"]',
    '[class*="st-key-qa_report_content_"]', '.st-key-counter_detail_panel', '.st-key-replay_detail_panel'
  ].join(',');
  const buttonSelector = '[data-testid="stButton"] button, '
    + '[data-testid="stFormSubmitButton"] button, [data-testid="stDownloadButton"] button';
  const glassSelector = '[class*="st-key-guided_card_"] button';
  const drawerSelector = '[class*="st-key-answer_sources_panel_"]';
  const exitSelector = '.st-key-qa_extra_examples,.st-key-qa_quick_preview,.st-key-scope_dimensions_panel,'
    + '.st-key-scope_sources_panel,.st-key-scope_manual_panel,[class*="st-key-answer_check_panel_"],'
    + '[class*="st-key-answer_export_"],[class*="st-key-guided_picker_qa_answer_panel_"],'
    + '[class*="st-key-guided_picker_qa_source_panel_"],[class*="st-key-guided_picker_qa_export_panel_"],'
    + '[class*="st-key-guided_content_"],[class*="st-key-qa_details_content_"],'
    + '[class*="st-key-qa_selected_panel_"],[class*="st-key-qa_export_content_"],'
    + '[class*="st-key-qa_report_content_"],.st-key-counter_detail_panel,.st-key-replay_detail_panel';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = window.matchMedia('(min-width: 591px) and (hover: hover) and (pointer: fine)');
  const abort = new AbortController();
  const seen = new WeakSet();
  const observed = new Set();
  const running = new Map();
  const transient = new Set();
  const exits = new Map();
  const revealedKeys = new Set();
  let routeKey = '';
  let frame = 0;
  let pointerFrame = 0;
  let pendingPointer = null;
  let activeGlass = null;
  let pendingExit = null;
  let disposed = false;
  let revealCount = 0;
  let intersection = null;
  let mutations = null;

  const enabled = () => !disposed && !quiet() && !document.hidden;
  const diagnostic = name => root.setAttribute('data-qm-motion-last', name);
  root.setAttribute('data-qm-motion-version', VERSION);
  root.setAttribute('data-qm-motion-reveals', '0');
  const hostsDrawer = node => node.matches?.(drawerSelector) || Boolean(node.querySelector?.(drawerSelector));
  const exitKey = node => String(node?.className || '').split(/\s+/).find(name => name.startsWith('st-key-'));
  const findKey = key => {
    const candidate = key ? document.querySelector('.' + key.replace(/[^a-zA-Z0-9_-]/g, character => '\\' + character)) : null;
    return candidate && exitKey(candidate) === key ? candidate : null;
  };
  function remember(node) {
    const key = exitKey(node);
    if (key) revealedKeys.add(key);
    while (revealedKeys.size > 256) revealedKeys.delete(revealedKeys.values().next().value);
  }

  function cancelExitsFor(node) {
    const record = exits.get(exitKey(node));
    if (record?.playing) record.dispose();
  }
  function discardExits() { pendingExit = null;for (const record of Array.from(exits.values())) record.dispose(); }

  function claim(node) {
    if (!node) return;
    cancelExitsFor(node);
    seen.add(node);remember(node);observed.delete(node);intersection?.unobserve(node);
    for (const [animation, item] of Array.from(running)) {
      if ((animation.id === 'qm-enter' || animation.id === 'qm-layout')
          && (item.node === node || item.node.contains(node))) {
        animation.cancel();item.finish();
      }
    }
  }

  function captureExit(node, options = {}) {
    if (!enabled() || typeof node.cloneNode !== 'function') return null;
    const rect = options.rect || node.getBoundingClientRect(),key = exitKey(node);
    if (!key || ![rect.width,rect.height].every(value => Number.isFinite(value) && value > 0)) return null;
    const originals=[node];
    if (typeof document.createTreeWalker === 'function') {
      const walker=document.createTreeWalker(node,1);let child;
      // Stop after 241 descendants instead of allocating a large table subtree.
      while ((child=walker.nextNode())) {if(originals.length>240)return null;originals.push(child);}
    } else {
      const children=node.querySelectorAll('*');if(children.length>240)return null;
      originals.push(...children);
    }
    exits.get(key)?.dispose();
    const layer = node.cloneNode(true);
    // Freeze shallow presentation while the live panel still has its ancestors.
    // No field value or financial text is read; native cloneNode keeps the visible DOM.
    if (typeof getComputedStyle === 'function') {
      const copies=[layer,...layer.querySelectorAll('*')];
      // Keep the native click path bounded: one panel and twelve shallow nodes.
      // Inherited fonts cover the rest; large panels use the static close fallback.
      for (let index=0;index < Math.min(originals.length,12);index++) {
        const computed=getComputedStyle(originals[index]);
        for (const name of ['display','fontFamily','fontSize','fontWeight','lineHeight','color','padding','margin','gap','alignItems','flexDirection','gridTemplateColumns']) copies[index].style[name]=computed[name];
      }
    }
    // Presentation only: never duplicate forms, executable surfaces or live media.
    for (const unsafe of layer.querySelectorAll('input,textarea,select,iframe,script,style,link,object,embed,video,audio,canvas,[contenteditable]')) unsafe.remove();
    for (const element of [layer,...layer.querySelectorAll('*')]) {
      for (const name of element.getAttributeNames()) {
        if (['id','name','for','tabindex','autofocus','href','srcdoc','formaction','aria-live','aria-controls','aria-labelledby','aria-describedby'].includes(name)
            || /^on/i.test(name) || name.startsWith('data-studio-')) element.removeAttribute(name);
      }
      const classes = String(element.getAttribute('class') || '').split(/\s+/).filter(name => name && !name.startsWith('st-key-') && !name.startsWith('qm-motion-'));
      element.setAttribute('class',classes.join(' '));
      element.style.animation = 'none';element.style.transition = 'none';
      if (element.tagName === 'BUTTON') element.disabled = true;
      if (['BUTTON','A','SUMMARY'].includes(element.tagName)) element.setAttribute('tabindex','-1');
    }
    const computed = typeof getComputedStyle === 'function' ? getComputedStyle(node) : null;
    if (computed) for (const name of ['background','color','fontFamily','fontSize','lineHeight','border','padding','boxShadow','boxSizing']) layer.style[name] = computed[name];
    layer.className = 'qm-motion-exit';layer.inert = true;layer.setAttribute('data-qm-visual-exit','true');layer.setAttribute('aria-hidden','true');layer.setAttribute('role','presentation');
    Object.assign(layer.style,{position:'fixed',left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px',maxWidth:'none',maxHeight:'none',margin:'0',overflow:'hidden',pointerEvents:'none',zIndex:options.direction === 'right' ? '10002' : '9997',transform:'none',opacity:'0'});
    const visibleOpacity = Number.parseFloat(computed?.opacity);
    const opacity = Number.isFinite(visibleOpacity) ? visibleOpacity : 1;
    const scroll = node.scrollTop || 0;let animation = null,expired = false,timer = 0;
    const record = {playing:false,play() {
      if (expired || record.playing || !enabled()) { if (!enabled()) record.dispose();return false; }
      if (timer) clearTimeout(timer);timer = 0;record.playing = true;
      document.body.appendChild(layer);layer.scrollTop = scroll;
      const right = options.direction === 'right';
      // Inline content has already left native layout. Never move or rescale its
      // visual copy back across the remaining content; fade from this exact frame.
      const frames = right ? [{opacity,transform:'translateX(0)'},{opacity:0,transform:'translateX(110%)'}]
        : [{opacity,clipPath:'inset(0 0 0 0)'},{opacity:0,clipPath:'inset(0 0 12% 0)'}];
      animation = animate(layer,frames,
        {duration:right?340:180,easing:'cubic-bezier(.4,0,.75,0)',fill:'forwards'},'qm-exit',record.dispose);
      return Boolean(animation);
    },dispose() {
      if (expired) return;expired = true;
      if (timer) clearTimeout(timer);timer = 0;
      animation?.cancel();layer.remove();layer.replaceChildren();transient.delete(layer);
      if (exits.get(key) === record) exits.delete(key);
    }};
    transient.add(layer);exits.set(key,record);
    while (exits.size > 4) exits.values().next().value.dispose();
    if (typeof setTimeout === 'function') timer = setTimeout(record.dispose,1500);
    return record;
  }

  function exitDetachedPanels() {
    if (!pendingExit) return;
    const record = pendingExit;
    if (performance.now() - record.started > 1500) {record.visual.dispose();pendingExit = null;return;}
    if (record.node.isConnected) return;
    pendingExit = null;
    // React may replace a container without closing it. Wait until the paint
    // boundary and reject that replacement before showing any old content.
    if (findKey(record.key)) record.visual.dispose();
    else record.visual.play();
  }

  function protectDrawers() {
    for (const [animation, item] of Array.from(running)) {
      if (item.transforms && hostsDrawer(item.node)) {
        animation.cancel();
        item.finish();
      }
    }
  }

  function animate(node, frames, options, id, cleanup) {
    if (!enabled() || typeof node.animate !== 'function') {
      if (cleanup) cleanup();
      return null;
    }
    // A transformed ancestor changes the containing block of a fixed drawer.
    // The dedicated studio controller owns its horizontal entrance animation.
    if ((id === 'qm-enter' || id === 'qm-layout') && hostsDrawer(node)) {
      frames = frames.map(frame => ({opacity: frame.opacity ?? 1}));
    }
    // Cancel only this module's animation of the same type on the same node.
    for (const [animation, item] of running) {
      if (item.node === node && animation.id === id) animation.cancel();
    }
    let animation;
    try {
      animation = node.animate(frames, options);
      animation.id = id;
    } catch (_) {
      if (cleanup) cleanup();
      return null;
    }
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      running.delete(animation);
      if (cleanup) cleanup();
    };
    running.set(animation, {node, finish, transforms: frames.some(frame => 'transform' in frame)});
    animation.finished.then(finish, finish);
    diagnostic(id);
    return animation;
  }

  function visibleTargets() {
    const main = document.querySelector(mainSelector);
    if (!main) return [];
    return Array.from(main.querySelectorAll(targetSelector)).filter(node => !node.matches?.(drawerSelector)).slice(0, 64);
  }

  function reveal(nodes) {
    const candidates = nodes.filter(node => node.isConnected && !seen.has(node));
    candidates.forEach(node => {
      seen.add(node);
      remember(node);
      observed.delete(node);
      if (intersection) intersection.unobserve(node);
    });
    candidates.filter(node => !candidates.some(parent => parent !== node && parent.contains(node)))
      .forEach((node, index) => {
        if (!enabled()) return;
        const playingParent = Array.from(running.values()).some(item =>
          item.node !== node && item.node.contains(node));
        if (playingParent) return;
        const frames = node.matches?.(exitSelector) ? [{opacity: 0.3}, {opacity: 1}] : [
          {opacity: 0.3, transform: 'translateY(18px)'},
          {opacity: 1, transform: 'translateY(0)'}
        ];
        if (animate(node, frames, {duration: 460, delay: Math.min(index * 40, 120),
          easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'none'}, 'qm-enter')) {
          revealCount += 1;
          root.setAttribute('data-qm-motion-reveals', String(revealCount));
        }
      });
  }

  function refreshTargets() {
    const header = document.querySelector('[data-studio-location]');
    const location = header?.getAttribute?.('data-studio-scene') || header?.getAttribute?.('data-studio-location') || '';
    if (location && location !== routeKey) {revealedKeys.clear();routeKey = location;}
    for (const node of observed) {
      if (!node.isConnected) {
        if (intersection) intersection.unobserve(node);
        observed.delete(node);
      }
    }
    if (!enabled()) return;
    const visible = visibleTargets();visible.forEach(node => {
      cancelExitsFor(node);
      if (revealedKeys.has(exitKey(node))) {seen.add(node);observed.delete(node);intersection?.unobserve(node);}
    });
    const targets = visible.filter(node => !seen.has(node) && !observed.has(node));
    if (intersection) targets.forEach(node => { observed.add(node); intersection.observe(node); });
    else reveal(targets.filter(node => {
      const rect = node.getBoundingClientRect();
      return rect.bottom > 0 && rect.top < window.innerHeight && rect.width > 0;
    }));
  }

  function schedule() {
    if (!enabled() || frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      protectDrawers();
      exitDetachedPanels();
      refreshTargets();
    });
  }

  function nativeButton(target) {
    if (!(target instanceof Element)) return null;
    const button = target.closest(buttonSelector);
    return button && !button.disabled && button.getAttribute('aria-disabled') !== 'true'
      && button.closest('[data-testid="stMain"], [data-testid="stSidebar"]') ? button : null;
  }

  function ripple(button, x, y, measuredRect) {
    if (!enabled()) return;
    if (button.dataset.qmUiButton === 'true') {if (activeGlass === button) resetGlass();return;}
    const rect = measuredRect || button.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const size = Math.min(900, Math.hypot(rect.width, rect.height) * 2);
    const layer = document.createElement('span');
    layer.className = 'qm-motion-ripple';
    layer.setAttribute('aria-hidden', 'true');
    layer.style.width = layer.style.height = `${size}px`;
    layer.style.left = `${Math.max(0, Math.min(rect.width, x - rect.left)) - size / 2}px`;
    layer.style.top = `${Math.max(0, Math.min(rect.height, y - rect.top)) - size / 2}px`;
    button.appendChild(layer);
    transient.add(layer);
    animate(layer, [{transform: 'scale(0.05)', opacity: 0.18},
      {transform: 'scale(1)', opacity: 0}],
    {duration: 360, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'none'}, 'qm-ripple', () => {
      layer.remove();
      transient.delete(layer);
    });
  }

  function resetGlass() {
    pendingPointer = null;
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    pointerFrame = 0;
    if (!activeGlass) return;
    activeGlass.style.removeProperty('--qm-pointer-x');
    activeGlass.style.removeProperty('--qm-pointer-y');
    activeGlass.style.removeProperty('--qm-sheen-active');
    activeGlass.classList.remove('qm-motion-glass');
    const layer = activeGlass.querySelector(':scope > .qm-motion-sheen');
    if (layer) { layer.remove(); transient.delete(layer); }
    activeGlass = null;
  }

  function pointerMove(event) {
    if (!enabled() || !finePointer.matches || event.pointerType === 'touch') return;
    const target = event.target instanceof Element ? event.target : null;
    const button = target && target.closest(glassSelector);
    if (button?.dataset.qmUiButton === 'true') {resetGlass();return;}
    if (!button || button.disabled || !button.closest(mainSelector)) return;
    if (activeGlass !== button) {
      resetGlass();
      activeGlass = button;
      button.classList.add('qm-motion-glass');
      button.style.setProperty('--qm-sheen-active', '1');
      const layer = document.createElement('span');
      layer.className = 'qm-motion-sheen';
      layer.setAttribute('aria-hidden', 'true');
      button.appendChild(layer);
      transient.add(layer);
      animate(layer, [{opacity: 0}, {opacity: 1}], {duration: 180, fill: 'none'}, 'qm-sheen');
    }
    pendingPointer = {button, x: event.clientX, y: event.clientY};
    if (!pointerFrame) pointerFrame = requestAnimationFrame(() => {
      pointerFrame = 0;
      const point = pendingPointer;
      pendingPointer = null;
      if (!point || !enabled() || !finePointer.matches || !point.button.isConnected) return;
      if (point.button.dataset.qmUiButton === 'true') {resetGlass();return;}
      const rect = point.button.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      point.button.style.setProperty('--qm-pointer-x',
        `${Math.max(0, Math.min(100, (point.x - rect.left) / rect.width * 100))}%`);
      point.button.style.setProperty('--qm-pointer-y',
        `${Math.max(0, Math.min(100, (point.y - rect.top) / rect.height * 100))}%`);
    });
  }

  function detailTarget(button) {
    const owner=button.closest('[class*="st-key-"]'),key=owner?exitKey(owner):'';
    // Fixed source drawers have a separate owner; never prepare them twice.
    if (!key || /answer_sources_/.test(key)) return null;
    let targetKey=null,selected=true;
    if (/^st-key-qa_more_examples$/.test(key)) targetKey='st-key-qa_extra_examples';
    else if (/^st-key-(recommended_[01]|qa_quick_close)$/.test(key)) {
      targetKey='st-key-qa_quick_preview';
      selected=/qa_quick_close$/.test(key)||button.getAttribute('kind')==='primary';
    }
    else if (/^st-key-answer_check_(close|toggle)_/.test(key)) targetKey=key.replace(/answer_check_(close|toggle)_/,'answer_check_panel_');
    else if (/^st-key-scope_detail_(dimensions|sources|manual)$/.test(key)) targetKey='st-key-scope_'+key.match(/scope_detail_(dimensions|sources|manual)/)[1]+'_panel';
    else if (/^st-key-(data_center_view|library_view|asset_source_view|benchmark_view)_pick_\d+$/.test(key)) {
      targetKey=key.replace(/^st-key-/, 'st-key-guided_content_').replace(/_pick_\d+$/, '');
      selected=button.getAttribute('kind')==='primary';
    }
    else if (/^st-key-qa_(source|verify)_panel_.+_pick_\d+$/.test(key)) {
      targetKey=key.replace(/^st-key-/, 'st-key-guided_content_').replace(/_pick_\d+$/, '');
      selected=button.getAttribute('kind')==='primary';
    }
    else if (/^st-key-qa_(answer|export)_panel_.+_pick_\d+$/.test(key)) {
      targetKey=key.replace(/^st-key-qa_answer_panel_/, 'st-key-qa_selected_panel_')
        .replace(/^st-key-qa_export_panel_/, 'st-key-qa_export_content_').replace(/_pick_\d+$/, '');
      selected=button.getAttribute('kind')==='primary';
    }
    else if (/^st-key-qa_(details|report)_\d+$/.test(key)) {
      const answer=exitKey(button.closest('[class*="st-key-answer_workbench_"]'));
      if(answer)targetKey=answer.replace('answer_workbench_', /qa_details_/.test(key)?'qa_details_content_':'qa_report_content_');
    }
    else if (/^st-key-(counter_detail_checks|counter_locate|counter_detail_review)$/.test(key)) {
      targetKey='st-key-counter_detail_panel';selected=button.getAttribute('kind')==='primary';
    }
    else if (/^st-key-replay_detail_(answer|query|source|check)$/.test(key)) {
      targetKey='st-key-replay_detail_panel';selected=button.getAttribute('kind')==='primary';
    }
    else if (/^st-key-(workspace_search_open_button|workspace_search_close|mobile_search_dismiss)$/.test(key)) targetKey='st-key-workspace_search_results';
    if (!targetKey) return null;
    return {key:targetKey,node:findKey(targetKey),selected};
  }

  function snapshotAround(button) {
    discardExits();
    if (button.closest('[data-testid="stSidebar"]')) return;
    const target=detailTarget(button);
    if (!target) return; // Ordinary submit/navigation does no page geometry scan.
    if (!target.node) {revealedKeys.delete(target.key);return;}
    if (!target.selected) return; // Selecting a different metric replaces content.
    const node=target.node,rect=node.getBoundingClientRect(),visual=captureExit(node,{rect});
    claim(node);
    if (visual) pendingExit={started:performance.now(),node,key:target.key,visual};
  }

  function clearMotion() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    pendingExit = null;
    resetGlass();
    discardExits();
    for (const [animation, item] of Array.from(running)) {
      animation.cancel();
      item.finish();
    }
    for (const layer of transient) layer.remove();
    transient.clear();
    if (intersection) intersection.disconnect();
    observed.clear();
  }

  if (typeof IntersectionObserver === 'function') {
    intersection = new IntersectionObserver(entries => {
      if (enabled()) reveal(entries.filter(entry => entry.isIntersecting).map(entry => entry.target));
    }, {threshold: 0.05, rootMargin: '0px 0px -12px 0px'});
  }
  mutations = new MutationObserver(records => {
    if (!enabled()) return;
    // Ignore our decorative layers; they must not trigger a self-sustaining scan.
    const changed = records.some(record => Array.from(record.addedNodes).concat(Array.from(record.removedNodes))
      .some(node => !(node instanceof Element) ||
        !node.matches('.qm-motion-ripple, .qm-motion-sheen, .qm-motion-exit, script, style')));
    if (changed) { protectDrawers();schedule(); }
  });
  mutations.observe(document, {childList: true, subtree: true});

  const options = {capture: true, passive: true, signal: abort.signal};
  document.addEventListener('pointerdown', event => {
    const button = nativeButton(event.target);
    if (button && event.button === 0) ripple(button, event.clientX, event.clientY);
  }, options);
  document.addEventListener('click', event => {
    if (!enabled()) return;
    const started=performance.now();
    const button = nativeButton(event.target);
    if (!button) return;
    if (event.detail === 0) {
      const rect = button.getBoundingClientRect();
      ripple(button, rect.left + rect.width / 2, rect.top + rect.height / 2,rect);
    }
    snapshotAround(button);
    root.setAttribute('data-qm-click-work-ms',(performance.now()-started).toFixed(2));
  }, options);
  document.addEventListener('pointermove', pointerMove, options);
  document.addEventListener('pointerout', event => {
    if (activeGlass && (!(event.relatedTarget instanceof Node) || !activeGlass.contains(event.relatedTarget))) resetGlass();
  }, options);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearMotion();
    else schedule();
  }, {signal: abort.signal});
  const mediaChange = () => {
    clearMotion();
    root.setAttribute('data-qm-motion-reduced', reduced.matches ? 'true' : 'false');
    schedule();
  };
  reduced.addEventListener('change', mediaChange);
  finePointer.addEventListener('change', mediaChange);
  window.addEventListener?.('resize',discardExits,{passive:true,signal:abort.signal});
  root.setAttribute('data-qm-motion-reduced', reduced.matches ? 'true' : 'false');

  window.addEventListener('qm-motion-preference-change', () => {
    const header = document.querySelector('[data-studio-location]');
    const location = header?.getAttribute?.('data-studio-scene') || header?.getAttribute?.('data-studio-location') || '';
    if (location !== routeKey) { revealedKeys.clear(); routeKey = location; }
    for (const node of document.querySelectorAll(targetSelector)) claim(node);
    mediaChange();
  }, {signal: abort.signal});
  window.__qingmengMotion = {
    version: VERSION,
    refresh: schedule,
    claim,
    captureExit,
    discardExits,
    dispose() {
      disposed = true;
      abort.abort();
      mutations.disconnect();
      clearMotion();
      reduced.removeEventListener('change', mediaChange);
      finePointer.removeEventListener('change', mediaChange);
    }
  };
  schedule();
})();
