/* Native report scrolling. Decorative paper never carries financial text. */
(() => {
  const quiet = () => reduced.matches || document.documentElement.dataset.qmMotionMode === 'research';
  'use strict';
  const VERSION = 'report-reader-20261011-22-editorial';
  if (window.__qmReportReader?.version === VERSION) { window.__qmReportReader.refresh(); return; }
  window.__qmReportReader?.dispose();
  const abort = new AbortController(), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const readers = new Map(), seen = new Set(), motions = new Map();
  let frame = 0, disposed = false, pendingSource = null;
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  function stopMotion(node) {
    const context = motions.get(node);
    if (context) { motions.delete(node); context.revert(); }
  }
  function enterPaper(root, node, key, cover=false) {
    if (!node || seen.has(key)) return;
    const box=node.getBoundingClientRect();
    if (box.width<=0 || box.height<=0 || box.bottom<=0 || box.top>=innerHeight) return;
    if (quiet()) { seen.add(key); return; }
    if (!window.gsap?.context) return;
    const art=node.querySelector(cover?'.rr-cover-art>em':'.rr-chapter-art>b');
    if (!art) return;
    seen.add(key); while(seen.size>128) seen.delete(seen.values().next().value);
    const context=window.gsap.context(()=>{},root);motions.set(node,context);
    let timeline;
    context.add(()=>{
      timeline=window.gsap.timeline({paused:true,onComplete:()=>stopMotion(node)});
      timeline.from(art,cover?{scale:1.6,rotation:-28,x:170,opacity:0,duration:1.2,ease:'power4.out'}:
        {x:220,rotation:-22,scaleX:.15,opacity:0,duration:.95,ease:'power4.out'});
    });
    timeline.play();
  }
  function finishSourceJump() {
    if (!pendingSource) return;
    if (performance.now() - pendingSource.started > 6000) { pendingSource = null; return; }
    const exact = [...document.querySelectorAll('[data-research-source-id][data-research-source-prefix]')]
      .find(node => node.dataset.researchSourceId === pendingSource.id && node.dataset.researchSourcePrefix === pendingSource.prefix);
    if (!exact) return;
    const target = document.getElementById('report_source_reader_' + pendingSource.prefix) || exact;
    if (!window.__qmSourceDock || !matchMedia('(min-width:1001px)').matches)
      target.scrollIntoView({behavior: quiet() ? 'auto' : 'smooth', block: 'start'});
    const container = target.closest('[data-testid="stVerticalBlock"]') || target.parentElement || target;
    container.setAttribute('tabindex', '-1'); container.focus({preventScroll: true});
    pendingSource = null;
  }
  function draw() {
    frame = 0;
    if (disposed || document.hidden) return;
    for(const [node] of motions){const box=node.getBoundingClientRect();if(box.bottom<=0||box.top>=innerHeight)stopMotion(node);}
    for (const [root, state] of readers) {
      if (!root.isConnected || !state.chapters.length) continue;
      const host = root.closest('[data-testid="stMain"]');
      const top = host ? Math.max(0, host.getBoundingClientRect().top) : 0;
      const viewHeight = host ? host.clientHeight : innerHeight;
      const focus = top + Math.min(240, viewHeight * .33);
      const rects = state.chapters.map(node => node.getBoundingClientRect());
      let selected = 0;
      rects.forEach((box, index) => { if (box.top <= focus) selected = index; });
      const local = clamp((focus - rects[selected].top) / Math.max(1, rects[selected].height), 0, 1);
      const progress = clamp((selected + local) / state.chapters.length, 0, 1);
      root.style.setProperty('--rr-progress', progress.toFixed(4));
      if (state.current !== selected) {
        state.current = selected;
        state.chapters.forEach((chapter, index) => chapter.classList.toggle('is-current', index === selected));
        state.links.forEach((link, index) => { if (index === selected) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current'); });
        const position = root.querySelector('.rr-position'), description = root.querySelector('.rr-reading-position');
        if (position) position.textContent = String(selected + 1).padStart(2, '0');
        if (description) description.textContent = '正在阅读第 ' + (selected + 1) + ' / ' + state.chapters.length + ' 章';
      }
      if (!quiet()) {
        const rootBox = root.getBoundingClientRect();
        const coverProgress = clamp((top - rootBox.top + 120) / 580, 0, 1);
        root.style.setProperty('--rr-cover-x', (-75 * coverProgress).toFixed(2) + 'px');
        root.style.setProperty('--rr-cover-y', (42 * coverProgress).toFixed(2) + 'px');
        state.chapters.forEach((chapter, index) => {
          const box = rects[index];
          if (box.bottom < top || box.top > top + viewHeight) return;
          const phase = clamp((focus - box.top) / Math.max(1, box.height), -.5, 1.2);
          chapter.style.setProperty('--rr-paper-x', (-58 * phase).toFixed(2) + 'px');
          chapter.style.setProperty('--rr-paper-y', (28 * phase).toFixed(2) + 'px');
          chapter.style.setProperty('--rr-paper-turn', (8 + 18 * phase).toFixed(2) + 'deg');
        });
      }
      enterPaper(root,root.querySelector('.rr-cover'),root.dataset.reportReader+'|cover',true);
      state.chapters.forEach(chapter=>enterPaper(root,chapter,root.dataset.reportReader+'|'+chapter.dataset.reportChapter));
    }
    finishSourceJump();
  }
  function schedule() { if (!frame && !disposed && !document.hidden) frame = requestAnimationFrame(draw); }
  const resize = new ResizeObserver(schedule);
  function refresh() {
    if (disposed) return;
    for (const [node] of motions) if (!node.isConnected) stopMotion(node);
    for (const [root] of readers) if (!root.isConnected) { resize.unobserve(root); readers.delete(root); }
    document.querySelectorAll('[data-report-reader]').forEach(root => {
      if (readers.has(root)) return;
      readers.set(root, {current: -1, chapters: [...root.querySelectorAll('[data-report-chapter]')], links: [...root.querySelectorAll('[data-report-jump]')]});
      resize.observe(root);
    });
    schedule();
  }
  document.addEventListener('click', event => {
    const link = event.target.closest?.('[data-report-jump],[data-report-cover],[data-report-source-target]');
    if (!link) return;
    const root = link.closest('[data-report-reader]');
    if (!root) return;
    const sourceAnchor = link.dataset.reportSourceTarget;
    if (sourceAnchor) {
      const button = document.querySelector('.st-key-' + CSS.escape(sourceAnchor) + ' button');
      const target = document.getElementById(sourceAnchor) || document.querySelector('.st-key-' + CSS.escape(sourceAnchor));
      if (button && !button.disabled) {
        event.preventDefault();
        pendingSource = {id: link.dataset.reportSourceId, prefix: root.dataset.reportPrefix, started: performance.now()};
        window.__qmSourceDock?.prepare(link);
        button.click();
        schedule();
      } else if (target) {
        event.preventDefault();
        target.scrollIntoView({behavior: quiet() ? 'auto' : 'smooth', block: 'center'});
      }
      return;
    }
    const chapter = link.hasAttribute('data-report-cover') ? root : root.querySelector('[data-report-chapter="' + CSS.escape(link.dataset.reportJump) + '"]');
    if (!chapter) return;
    event.preventDefault(); pendingSource = null;
    chapter.scrollIntoView({behavior: quiet() ? 'auto' : 'smooth', block: 'start'});
    if (chapter !== root) chapter.focus({preventScroll: true});
    schedule();
  }, {signal: abort.signal});
  document.addEventListener('scroll', schedule, {capture: true, passive: true, signal: abort.signal});
  window.addEventListener('resize', schedule, {passive: true, signal: abort.signal});
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { if (frame) cancelAnimationFrame(frame); frame = 0; pendingSource = null; for(const [node] of motions)stopMotion(node); }
    else schedule();
  }, {signal: abort.signal});
  function preferenceChanged(){for(const [node] of motions)stopMotion(node);schedule();}
  reduced.addEventListener('change', preferenceChanged, {signal: abort.signal});
  const observer = new MutationObserver(refresh);
  observer.observe(document, {childList: true, subtree: true});
  window.addEventListener('qm-motion-preference-change', preferenceChanged, {signal: abort.signal});
  const api = {version: VERSION, refresh, dispose() {
    if (disposed) return;
    disposed = true; abort.abort(); resize.disconnect(); observer.disconnect();
    if (frame) cancelAnimationFrame(frame);
    frame = 0; pendingSource = null; readers.clear(); for(const [node] of motions)stopMotion(node);seen.clear();
    if (window.__qmReportReader === api) delete window.__qmReportReader;
  }};
  window.__qmReportReader = api;
  refresh();
})();
