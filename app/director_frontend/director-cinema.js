(() => {
  'use strict';
  // The director owns this iframe. One clock drives each chapter; one value
  // element travels between compositions. Business values are never tweened.
  function create({document, shell, quiet, visible}) {
    const win = document.defaultView, gsap = win.gsap, Flip = win.Flip, Draggable = win.Draggable;
    const byId = id => document.getElementById(id), controls = byId('cinema-controls');
    const fact = byId('focus-fact'), home = byId('focus-home'), range = byId('cinema-seek');
    const track = byId('cinema-track'), handle = byId('cinema-playhead'), progress = byId('cinema-progress');
    const phases = [...controls.querySelectorAll('[data-cinema-phase]')];
    const times = {establish: 0, inspect: 2.15, trace: 4.45}, duration = 6.4;
    const abort = new win.AbortController();
    let context = null, timeline = null, flip = null, drag = null, disposed = false, playing = false;
    let identity = '', chapterKey = '', pending = null, lastPhase = '', suspended = false;
    const available = Boolean(gsap?.timeline && gsap?.context);
    if (available) gsap.registerPlugin(...[Flip, Draggable].filter(Boolean));
    const listen = (target, event, callback) => target.addEventListener(event, callback, {signal: abort.signal});
    const text = (id, value) => {const target = byId(id);if (target.textContent !== value) target.textContent = value;};
    const usable = () => available && !disposed && !quiet();
    const running = () => usable() && visible() && !suspended;
    const factKey = state => state.fact ? JSON.stringify([state.payload.revision, state.fact.id, state.fact.year]) : '';
    function paint() {
      if (disposed) return;
      const time = timeline?.time() ?? duration, ratio = time / duration;
      const phase = time < times.inspect ? 'establish' : time < times.trace ? 'inspect' : 'trace';
      range.value = String(Math.round(ratio * 1000));
      range.setAttribute('aria-valuetext', `${time.toFixed(1)} 秒，共 ${duration} 秒，${phases.find(item => item.dataset.cinemaPhase === phase)?.textContent || ''}`);
      progress.style.transform = `scaleX(${ratio})`;
      if (available && !drag?.isDragging) gsap.set(handle, {x: ratio * Math.max(0, track.clientWidth - handle.offsetWidth)});
      text('cinema-time', `${time.toFixed(1)} / ${duration} 秒`);
      text('cinema-play', playing ? '暂停' : '播放');
      byId('cinema-play').setAttribute('aria-pressed', String(playing));
      text('cinema-state', !usable() ? '静态阅读' : suspended || !visible() ? '已暂停' : playing ? timeline?.reversed() ? '倒放中' : '播放中' : '手动定位');
      if (phase !== lastPhase) {lastPhase = phase;phases.forEach(item => item.setAttribute('aria-pressed', String(item.dataset.cinemaPhase === phase)));}
      shell.dataset.cinema = !usable() ? 'static' : playing && running() ? 'playing' : 'paused';
    }
    function pause() {playing = false;timeline?.pause();flip?.pause();paint();}
    function settleFlip() {if (flip) {flip.progress(1).kill();flip = null;}}
    function clearChapter() {playing = false;timeline?.pause();context?.revert();timeline = null;context = null;settleFlip();}
    function prepare(state) {
      const same = identity && identity === factKey(state) && !home.contains(fact);
      // Finish the prior journey before measuring a new pair of endpoints.
      settleFlip();pending = same && usable() && visible() && Flip ? Flip.getState(fact) : null;
      clearChapter();home.append(fact);
    }
    function sync() {
      if (disposed) return;
      if (!usable()) {playing = false;timeline?.progress(1).pause();settleFlip();}
      else if (!running()) {timeline?.pause();flip?.pause();}
      else {if (playing) timeline?.resume();if (flip && flip.progress() < 1) flip.resume();}
      range.disabled = !usable();byId('cinema-play').disabled = !usable();
      byId('cinema-reverse').disabled = !usable();byId('cinema-replay').disabled = !usable();
      phases.forEach(item => {item.disabled = !usable();});
      if (drag) {if (usable()) drag.enable();else drag.disable();}
      paint();
    }
    function mount(slide, state, chapter, direction) {
      if (disposed) return;
      identity = factKey(state);chapterKey = `${state.payload.revision}:${chapter.id}:${identity}`;
      const slot = slide.querySelector('[data-fact-slot]');
      (slot || home).append(fact);fact.dataset.factIdentity = identity;
      shell.dataset.factJourney = slot ? chapter.kind : 'none';
      if (pending && slot && usable() && visible() && Flip) {
        flip = Flip.from(pending, {duration: .9, ease: 'power3.inOut', scale: true, absolute: true, prune: true,
          onComplete: () => {flip = null;}});
      }
      pending = null;
      controls.hidden = false;
      if (!available) {sync();return;}
      const parts = [...slide.querySelectorAll('.plane-item')].filter(item => !item.contains(fact)).slice(0, 12);
      const hero = slide.querySelector('.sculpture');
      // The capsule is deliberately excluded from the scene transform targets:
      // Flip alone owns its geometry, so its saved value never bounces twice.
      context = gsap.context(() => {
        const clock = {elapsed: 0};
        timeline = gsap.timeline({paused: true, defaults: {ease: 'power3.out'}, onUpdate: paint,
          onComplete: () => {playing = false;paint();}, onReverseComplete: () => {playing = false;paint();}});
        Object.entries(times).forEach(([name, time]) => timeline.addLabel(name, time));
        timeline.to(clock, {elapsed: duration, duration, ease: 'none'}, 0);
        if (parts.length) timeline.fromTo(parts, {x: (direction < 0 ? -1 : 1) * 84, y: 24, rotationY: -8, opacity: .55},
          {x: 0, y: 0, rotationY: 0, opacity: 1, duration: 1.15, stagger: .065}, 0);
        if (hero) timeline.fromTo(hero, {scale: .84, rotationY: -18}, {scale: 1.06, rotationY: 8, duration: 2.3}, 0)
          .to(hero, {scale: 1, rotationY: 0, duration: 1.7}, 'trace');
        const lens = slide.querySelector('.cinema-lens');
        if (lens) timeline.fromTo(lens, {x: 110, scaleX: .62, scaleY: .7, opacity: 0, rotation: -5},
          {x: 0, scaleX: 1, scaleY: 1, opacity: .8, rotation: 0, duration: 1.05}, 'inspect')
          .to(lens, {x: -70, scaleX: 1.22, scaleY: 1.08, opacity: 0, duration: 1.35}, 'trace');
        // Each chapter has a distinct middle shot. Only non-selected cards or
        // descendants beside the fact capsule move; Flip retains exclusive
        // ownership of the capsule and all of its ancestors.
        if (chapter.kind === 'metrics') {
          const satellites = [...slide.querySelectorAll('.metric-sheet')].filter(item => !item.contains(fact));
          if (satellites.length) timeline.to(satellites, {x: 32, y: (index) => index ? 20 : -20,
            rotation: (index) => index ? 3 : -3, scale: .91, opacity: .6, duration: 1.05, stagger: .08}, 'inspect')
            .to(satellites, {x: 0, y: 0, rotation: 0, scale: 1, opacity: 1, duration: 1.2, stagger: .07}, 'trace');
        } else if (chapter.kind === 'annual') {
          const surrounding = [...slide.querySelectorAll('.annual-row')].filter(item => !item.contains(fact)).slice(0, 12);
          const selectedTrack = slide.querySelector('.annual-row.is-focused .annual-bar-track');
          if (surrounding.length) timeline.to(surrounding, {x: 38, scale: .96, opacity: .38, duration: 1, stagger: .055}, 'inspect')
            .to(surrounding, {x: 0, scale: 1, opacity: 1, duration: 1.15, stagger: .055}, 'trace');
          if (selectedTrack) timeline.to(selectedTrack, {scaleY: 1.35, duration: 1.05}, 'inspect')
            .to(selectedTrack, {scaleY: 1, duration: 1.25}, 'trace');
        } else if (chapter.kind === 'sources') {
          const locator = slide.querySelector('.source-locator'), filename = slide.querySelector('.source-spotlight h3');
          const related = [...slide.querySelectorAll('.source-row')].slice(0, 12);
          if (filename) timeline.to(filename, {x: 26, y: -6, duration: 1.1}, 'inspect')
            .to(filename, {x: 0, y: 0, duration: 1.2}, 'trace');
          if (locator) timeline.to(locator, {x: 26, y: 6, scale: 1.08, transformOrigin: 'left center', duration: 1.1}, 'inspect')
            .to(locator, {x: 0, y: 0, scale: 1, duration: 1.2}, 'trace');
          if (related.length) timeline.to(related, {x: 40, opacity: .4, duration: 1.1, stagger: .04}, 'inspect')
            .to(related, {x: 0, opacity: 1, duration: 1.2, stagger: .04}, 'trace');
        } else if (!hero) {
          const reading = slide.querySelector('.reading');
          if (reading) timeline.to(reading, {x: 22, y: 8, scale: .975, duration: 1.1}, 'inspect')
            .to(reading, {x: 0, y: 0, scale: 1, duration: 1.2}, 'trace');
        }
        // Focus rings are decoration, leaving real financial text stable during
        // the middle and ending shots, including when the playhead runs backward.
        const marker = slide.querySelector('.cinema-marker');
        if (marker) timeline.fromTo(marker, {scaleX: .05, opacity: .15}, {scaleX: 1, opacity: 1, duration: 1.1}, 'inspect')
          .to(marker, {opacity: .3, duration: 1.1}, 'trace');
      }, slide);
      timeline.progress(usable() ? 0 : 1).pause();
      playing = usable();if (playing && running()) timeline.play();sync();
    }
    function seek(value) {if (!usable() || !timeline) return;pause();settleFlip();timeline.progress(Math.min(1, Math.max(0, value)));paint();}
    listen(range, 'input', () => seek(Number(range.value) / 1000));
    listen(byId('cinema-play'), 'click', () => {
      if (!usable() || !timeline) return;
      if (playing) {pause();return;}
      settleFlip();playing = true;
      if (timeline.progress() >= .999) timeline.progress(0);
      timeline.reversed(false);if (running()) timeline.play();paint();
    });
    listen(byId('cinema-reverse'), 'click', () => {
      if (!usable() || !timeline) return;settleFlip();playing = true;
      if (timeline.progress() <= .001) timeline.progress(1);
      timeline.reversed(true);if (running()) timeline.resume();paint();
    });
    listen(byId('cinema-replay'), 'click', () => {
      if (!usable() || !timeline) return;settleFlip();playing = true;timeline.reversed(false).progress(0);
      if (running()) timeline.play();paint();
    });
    phases.forEach(item => listen(item, 'click', () => seek(times[item.dataset.cinemaPhase] / duration)));
    if (available && Draggable) {
      [drag] = Draggable.create(handle, {type: 'x', trigger: handle, bounds: track, edgeResistance: 1,
        onPress() {pause();settleFlip();this.applyBounds({minX: 0, maxX: Math.max(0, track.clientWidth - handle.offsetWidth)});},
        onDrag() {seek(this.x / Math.max(1, track.clientWidth - handle.offsetWidth));},
        onRelease() {paint();}});
    }
    listen(win, 'resize', () => {drag?.applyBounds({minX: 0, maxX: Math.max(0, track.clientWidth - handle.offsetWidth)});paint();});
    function dispose() {if (disposed) return;clearChapter();drag?.kill();drag = null;abort.abort();home.append(fact);disposed = true;}
    return {prepare, mount, sync, pause, suspend(value) {suspended = Boolean(value);sync();}, dispose,
      getState() {return {available, identity, chapterKey, time: timeline?.time() ?? duration, duration, playing,
        reversed: Boolean(timeline?.reversed()), paused: timeline?.paused() ?? true, phase: lastPhase, disposed, flipping: Boolean(flip), draggable: Boolean(drag), factParent: fact.parentElement?.dataset.factSlot || 'home'};}};
  }
  window.QMDirectorCinema = {create};
})();
