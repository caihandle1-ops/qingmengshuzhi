/* Local concept theatre powered by GSAP. The studio owns lifecycle; native
   controls and financial state are never read. Individual CSS transforms keep
   the artwork's authored rotations and the existing pointer parallax intact. */
(() => {
  const VERSION = '20261009.6';
  const SCENES = ['qa', 'scope', 'counter', 'replay', 'assets'];
  const BASE = {x: 0, y: 0, xp: 0, rotation: 0, scaleX: 1, scaleY: 1, alpha: 1};
  const STYLE_KEYS = ['translate', 'rotate', 'scale', 'opacity', 'visibility'];
  const LABELS = {
    qa: ['question', 'trace', 'answer'], scope: ['separate', 'align', 'lock'],
    counter: ['compare', 'inspect', 'resolve'], replay: ['unfold', 'sequence', 'archive'],
    assets: ['gather', 'fan', 'index']
  };
  function opening(scene, kind, index) {
    const side = index % 2 ? 1 : -1;
    let from = {x: side * 140, y: 36, scaleX: .72, scaleY: .72, alpha: 0};
    let at = .12 * index, duration = 1.25, via = null;
    if (scene === 'qa') {
      if (kind === 'question') {from = {x: -185, y: -70, rotation: -32, scaleX: .42, scaleY: .42, alpha: 0};at = 0;duration = 1.4;}
      else if (kind === 'answer') {from = {x: 155, y: 76, rotation: 24, scaleX: .58, scaleY: .58, alpha: 0};at = 1.15;duration = 1.35;}
      else if (kind === 'token') {from = {x: -110 + index * 24, y: side * 98, rotation: side * 45, scaleX: .2, scaleY: .2, alpha: 0};at = .38 + index * .15;duration = 1.15;}
      else if (kind === 'title') {from = {x: 0, y: -80, rotation: 12, alpha: 0};at = .15;duration = 1.5;}
      else {from = {rotation: -85, scaleX: .18, scaleY: .18, alpha: 0};at = .12;duration = 2.05;}
    } else if (scene === 'scope') {
      if (kind === 'axis') {from = {x: side * 230, rotation: side * 12, scaleX: .65, alpha: 0};at = .25 + index * .12;duration = 1.45;via = {x: side * 24, rotation: 0, scaleX: 1, alpha: 1};}
      else {from = {y: 70, scaleX: .65, scaleY: .65, alpha: 0};at = 0;duration = 1.6;}
    } else if (scene === 'counter') {
      if (kind === 'claim' || kind === 'evidence') {const direction = kind === 'claim' ? -1 : 1;from = {x: direction * 210, y: direction * 48, rotation: direction * 42, scaleX: .65, scaleY: .65, alpha: 0};at = direction < 0 ? 0 : .3;duration = 1.65;}
      else if (kind === 'lens') {from = {x: -150, y: 70, rotation: -48, scaleX: .28, scaleY: .28, alpha: 0};via = {x: 68, y: -20, rotation: 14, scaleX: 1.14, scaleY: 1.14, alpha: 1};at = .55;duration = 2.1;}
    } else if (scene === 'replay') {
      if (kind === 'record') {from = {x: 250, y: 92, rotation: 34, scaleX: .58, scaleY: .58, alpha: 0};via = {x: 26, y: -12, rotation: 3, scaleX: 1, scaleY: 1, alpha: 1};at = .3 + index * .24;duration = 1.5;}
      else {from = {x: -140, scaleX: .1, alpha: 0};at = kind === 'anchor' ? 1.45 : 0;duration = 1.45;}
    } else if (scene === 'assets') {
      if (kind === 'document') {from = {x: 130 - index * 80, y: 145, rotation: 36 - index * 24, scaleX: .38, scaleY: .38, alpha: 0};via = {x: 0, y: -22, rotation: 0, scaleX: 1.04, scaleY: 1.04, alpha: 1};at = .22 + index * .16;duration = 1.65;}
      else {from = {y: 86, scaleX: .66, alpha: 0};at = 0;duration = 1.35;}
    }
    return {from: {...BASE, ...from}, via, at, duration};
  }

  function create({document: doc, quiet = () => false, IntersectionObserver: Observe = globalThis.IntersectionObserver, gsap: preferredEngine}) {
    let engine = preferredEngine || globalThis.gsap;
    const validEngine = candidate => !!(candidate && typeof candidate.timeline === 'function' && typeof candidate.context === 'function');
    function ready() {
      if (!validEngine(engine)) engine = preferredEngine || globalThis.gsap;
      return validEngine(engine);
    }
    const records = new Map(), ambientTimes = new Map();
    let disposed = false, route = '', visit = 0;
    const observer = typeof Observe === 'function' ? new Observe(entries => {
      for (const entry of entries) {const record = records.get(entry.target);if (record) {record.visible = entry.isIntersecting;update(record);}}
    }, {threshold: .04}) : null;
    const usable = record => !disposed && record.node.isConnected && !quiet() && !doc.hidden && record.visible && !record.held;

    function pose(record, element, layer) {
      let item = record.poses.get(element);
      if (!item) {
        const style = element.style;
        if (!style) return null;
        item = {element, entry: {...BASE}, ambient: {...BASE}, isPiece: !!element.getAttribute('data-feature-piece'), saved: {}};
        for (const key of STYLE_KEYS) item.saved[key] = {value: style.getPropertyValue?.(key) || style[key] || '', priority: style.getPropertyPriority?.(key) || ''};
        record.poses.set(element, item);
      }
      return item[layer];
    }
    function paint(record) {
      if (quiet()) {restoreStyles(record);return;}
      for (const item of record.poses.values()) {
        const a = item.entry, b = item.ambient, style = item.element.style;
        const driftX = item.isPiece ? ' + var(--scene-drift-x,0px) * var(--piece-depth,.5)' : '';
        const driftY = item.isPiece ? ' + var(--scene-drift-y,0px) * var(--piece-depth,.5)' : '';
        style.translate = 'calc(' + (a.x + b.x) + 'px + ' + (a.xp + b.xp) + '%' + driftX + ') calc(' + (a.y + b.y) + 'px' + driftY + ')';
        style.rotate = (a.rotation + b.rotation) + 'deg';
        style.scale = (a.scaleX * b.scaleX) + ' ' + (a.scaleY * b.scaleY);
        style.opacity = String(a.alpha * b.alpha);
        style.visibility = a.alpha * b.alpha <= .001 ? 'hidden' : item.saved.visibility.value || 'inherit';
      }
    }
    function restoreStyles(record) {
      for (const item of record.poses.values()) for (const key of STYLE_KEYS) {
        const old = item.saved[key], style = item.element.style;
        if (old.value) style.setProperty ? style.setProperty(key, old.value, old.priority) : style[key] = old.value;
        else if (style.removeProperty) style.removeProperty(key);
        else style[key] = '';
      }
    }
    function restore(record) {
      restoreStyles(record);record.poses.clear();
    }
    function inContext(record, build, owner = 'context') {
      if (!ready()) return;
      if (!record[owner]) record[owner] = engine.context(() => {}, record.node);
      record[owner].add(build);
    }
    function startEntrance(record) {
      if (record.entered) return;
      record.entered = true;
      if (!ready() || quiet()) return;
      inContext(record, () => {
        const timeline = engine.timeline({paused: true, defaults: {ease: 'power4.out', overwrite: 'auto'}, onUpdate: () => paint(record), onComplete: () => {record.entranceDone = true;}});
        record.entrance = timeline;
        LABELS[record.scene].forEach((label, index) => timeline.addLabel(label, index * .7));
        const counts = {};
        for (const piece of [...record.node.querySelectorAll('[data-feature-piece]')].slice(0, 24)) {
          const kind = piece.getAttribute('data-feature-piece'), index = counts[kind] || 0;
          counts[kind] = index + 1;
          const value = pose(record, piece, 'entry');if (!value) continue;
          const spec = opening(record.scene, kind, index);Object.assign(value, spec.from);
          if (spec.via) {
            timeline.to(value, {...spec.via, duration: spec.duration * .56, ease: 'power3.out'}, spec.at);
            timeline.to(value, {...BASE, duration: spec.duration * .44, ease: 'power3.inOut'}, spec.at + spec.duration * .56);
          } else timeline.to(value, {...BASE, duration: spec.duration}, spec.at);
        }
        timeline.addLabel('settled', timeline.duration());
        paint(record);
      }, 'entryContext');
    }
    function startAmbient(record) {
      if (record.ambient || quiet() || !ready()) return;
      inContext(record, () => {
        const timeline = engine.timeline({paused: true, repeat: -1, defaults: {ease: 'sine.inOut', overwrite: 'auto'}, onUpdate: () => paint(record)});
        record.ambient = timeline;
        timeline.addLabel('gather', 0).addLabel('transform', 1.4).addLabel('resolve', 2.8).addLabel('return', 4.2);
        // A visible 5.6-second phrase, rather than a long nearly-still loop.
        // All main silhouettes reform inside the fixed artwork rectangle.
        timeline.to({beat: 0}, {beat: 1, duration: 5.6, ease: 'none'}, 0);
        const counts = {};
        for (const element of [...record.node.querySelectorAll('[data-feature-ambient]')].slice(0, 16)) {
          const kind = element.getAttribute('data-feature-ambient'), index = counts[kind] || 0;
          counts[kind] = index + 1;
          const value = pose(record, element, 'ambient');if (!value) continue;
          const at = index * .18, side = index % 2 ? 1 : -1;
          if (kind === 'orbit') {
            timeline.to(value, {rotation: 85, scaleX: 1.12, scaleY: .82, duration: 2.8}, 0).to(value, {...BASE, duration: 2.8}, 2.8);
          } else if (kind === 'signal') {
            timeline.to(value, {x: side * 28, y: -24, rotation: side * 14, scaleX: 1.12, scaleY: 1.12, duration: 1.2}, at).to(value, {x: -side * 20, y: 12, rotation: -side * 9, duration: 1.6}, 1.2 + at).to(value, {...BASE, duration: 2}, 3 + at);
          } else if (kind === 'trace') {
            timeline.to(value, {xp: 680, scaleX: 2.4, alpha: .3, duration: 2.2, ease: 'power2.inOut'}, .1 + at).to(value, {...BASE, duration: 2.3, ease: 'power2.inOut'}, 2.4 + at);
          } else if (kind === 'alignment') {
            timeline.to(value, {xp: -30, alpha: .3, duration: 1.2}, 0).to(value, {xp: 30, alpha: 1, duration: 2, ease: 'power2.inOut'}, 1.2).to(value, {...BASE, duration: 2.4}, 3.2);
          } else if (kind === 'scan') {
            timeline.to(value, {y: 174, scaleY: 3, duration: 2.8, ease: 'power2.inOut'}, 0).to(value, {...BASE, duration: 2.8, ease: 'power2.inOut'}, 2.8);
          } else if (kind === 'lens') {
            timeline.to(value, {scaleX: 1.6, scaleY: 1.6, alpha: .26, duration: 1.3}, 0).to(value, {...BASE, duration: 1.3}, 1.3).to(value, {scaleX: 1.4, scaleY: 1.4, alpha: .45, duration: 1.3}, 2.6).to(value, {...BASE, duration: 1.7}, 3.9);
          } else if (kind === 'playhead') {
            timeline.to(value, {xp: 800, scaleY: 1.8, duration: 4.5, ease: 'power1.inOut'}, 0).to(value, {alpha: 0, duration: .3}, 4.5).set(value, {xp: 0, scaleY: 1}, 4.8).to(value, {alpha: 1, duration: .5}, 4.9);
          } else if (kind === 'float') {
            timeline.to(value, {y: -7, x: side * 4, rotation: side * 2, duration: 1.3}, at).to(value, {y: 6, x: -side * 3, rotation: -side * 2, duration: 1.6}, 1.3 + at).to(value, {...BASE, duration: 1.9}, 3 + at);
          } else if (kind === 'index') {
            timeline.to(value, {scaleX: .12, alpha: .3, duration: .7}, .8 + at).to(value, {...BASE, duration: 1.4, ease: 'power3.out'}, 1.5 + at).to(value, {scaleX: .35, duration: .7}, 3.1 + at).to(value, {...BASE, duration: 1.2}, 3.8 + at);
          }
        }
        const pieceCounts = {};
        for (const element of [...record.node.querySelectorAll('[data-feature-piece]')].slice(0, 24)) {
          const kind = element.getAttribute('data-feature-piece'), index = pieceCounts[kind] || 0;
          pieceCounts[kind] = index + 1;
          const value = pose(record, element, 'ambient');if (!value) continue;
          if (record.scene === 'qa') {
            if (kind === 'question') timeline.to(value, {x: 18, y: -12, rotation: -10, scaleX: 1.04, scaleY: 1.04, duration: 1.35}, 0).to(value, {x: -12, y: 14, rotation: 8, duration: 1.45}, 1.35).to(value, {...BASE, duration: 2.8}, 2.8);
            else if (kind === 'answer') timeline.to(value, {x: -28, y: -24, rotation: -9, scaleX: 1.1, scaleY: 1.1, duration: 1.8}, .3).to(value, {x: 8, y: 7, rotation: 6, scaleX: 1, scaleY: 1, duration: 1.5}, 2.1).to(value, {...BASE, duration: 2}, 3.6);
            else if (kind === 'title') timeline.to(value, {y: 12, rotation: -8, scaleX: 1.12, scaleY: 1.12, duration: 2.8}, 0).to(value, {...BASE, duration: 2.8}, 2.8);
          } else if (record.scene === 'scope' && kind === 'axis') {
            const side = index % 2 ? 1 : -1, at = index * .13;
            timeline.to(value, {x: side * 44, y: side * 5, rotation: side * 5, scaleX: .9, duration: 1.2}, at).to(value, {...BASE, duration: 1.4, ease: 'power3.inOut'}, 1.25 + at).to(value, {x: -side * 14, duration: .65}, 3.3 + at).to(value, {...BASE, duration: .8}, 3.95 + at);
          } else if (record.scene === 'counter') {
            if (kind === 'lens') timeline.to(value, {x: -55, y: -8, rotation: -18, scaleX: 1.08, scaleY: 1.08, duration: 1.6}, 0).to(value, {x: 55, y: 8, rotation: 18, scaleX: 1.18, scaleY: 1.18, duration: 2.2}, 1.6).to(value, {...BASE, duration: 1.8}, 3.8);
            else if (kind === 'claim' || kind === 'evidence') {const side = kind === 'claim' ? -1 : 1;timeline.to(value, {x: side * 10, y: 14, rotation: side * 9, scaleX: 1.02, scaleY: 1.02, duration: 2.2}, 0).to(value, {...BASE, duration: 3.4}, 2.2);}
          } else if (record.scene === 'replay') {
            if (kind === 'record') {const at = index * .28;timeline.to(value, {x: -14 + index * 14, y: -26, rotation: (index - 1) * 8, scaleX: 1.07, scaleY: 1.07, duration: 1.2}, at).to(value, {x: 14 - index * 14, y: 9, rotation: (1 - index) * 8, scaleX: .98, scaleY: .98, duration: 1.5}, 1.2 + at).to(value, {...BASE, duration: 2.2}, 2.7 + at);}
            else if (kind === 'track') timeline.to(value, {x: -12, y: 10, rotation: 3, scaleX: 1.08, duration: 2.8}, 0).to(value, {...BASE, duration: 2.8}, 2.8);
          } else if (record.scene === 'assets') {
            if (kind === 'document') {const at = index * .13, baseRotation = [-21, -8, 8, 22][index] || 0;timeline.to(value, {x: (1.5 - index) * 33, y: 35, rotation: -baseRotation, scaleX: .88, scaleY: .88, duration: 1.2}, at).to(value, {x: (index - 1.5) * 10, y: -8, rotation: (index - 1.5) * 6, scaleX: 1.05, scaleY: 1.05, duration: 1.3, ease: 'power3.inOut'}, 1.4 + at).to(value, {...BASE, duration: 2.3}, 2.8 + at);}
            else if (kind === 'index') timeline.to(value, {y: 8, scaleX: 1.03, duration: 2.2}, 0).to(value, {...BASE, duration: 3.4}, 2.2);
          }
        }
        const previous = ambientTimes.get(record.scene);
        if (Number.isFinite(previous)) timeline.totalTime(previous, true);
        paint(record);
      });
    }
    function settleEntrance(record) {
      record.entryContext?.revert();record.entryContext = null;
      record.entrance?.kill();record.entrance = null;record.entranceDone = true;
      for (const item of record.poses.values()) Object.assign(item.entry, BASE);
    }
    function updateControls(record) {
      const available = ready(), still = quiet(), blocked = !available || still || record.held;
      const title = !available ? '动效暂未就绪，请刷新页面后重试。' : still ? '当前为静态展示；演示模式开启且系统允许动态效果后可重播。' : record.held ? '页面切换完成后可重播。' : '重新播放上方的概念演示。';
      if (record.button) {
        if (record.button.disabled !== blocked) record.button.disabled = blocked;
        if (record.button.title !== title) record.button.title = title;
      }
      const status = !available ? '动效准备中' : still ? '静态展示' : !usable(record) ? '等待播放' : record.entrance || record.ambient ? '动态演示' : '动效准备中';
      if (record.status && record.status.textContent !== status) record.status.textContent = status;
    }
    function update(record) {
      if (ready() && record.node.getAttribute('data-feature-motion') !== 'gsap') record.node.setAttribute?.('data-feature-motion', 'gsap');
      if (quiet()) {settleEntrance(record);record.ambient?.pause();paint(record);updateControls(record);return;}
      startAmbient(record);paint(record);
      for (const timeline of [record.entrance, record.ambient].filter(Boolean)) {
        if (usable(record)) {if (timeline.paused()) timeline.play();}
        else timeline.pause();
      }
      updateControls(record);
    }
    function replay(node) {
      const record = records.get(node);
      if (!record || disposed || !ready() || quiet() || record.held) return false;
      settleEntrance(record);record.entered = false;record.entranceDone = false;
      record.ambient?.totalTime(0, true);ambientTimes.delete(record.scene);
      record.replays++;startEntrance(record);update(record);return true;
    }
    function remove(record, remember = false) {
      if (remember && record.ambient && Number.isFinite(record.ambient.totalTime())) ambientTimes.set(record.scene, record.ambient.totalTime());
      record.entryContext?.revert();record.context?.revert();
      record.node.removeEventListener?.('click', record.onClick);
      restore(record);
      if (record.button) {record.button.disabled = true;record.button.title = '动效正在准备。';}
      if (record.status) record.status.textContent = '动效准备中';
      if (record.savedOwner) record.node.setAttribute?.('data-feature-motion', record.savedOwner);
      else record.node.removeAttribute?.('data-feature-motion');
      observer?.unobserve(record.node);records.delete(record.node);
    }
    function bind(node, entrance = false, hold = false) {
      if (disposed || !node?.isConnected) return;
      if (records.has(node)) {
        const record = records.get(node);
        if (hold) record.held = true;
        if (entrance) startEntrance(record);
        update(record);return;
      }
      const scene = node.getAttribute('data-feature-scene');if (!SCENES.includes(scene)) return;
      const box = node.getBoundingClientRect();
      const record = {node, scene, visit, entered: false, entranceDone: false, visible: box.width > 0 && box.height > 0 && box.bottom > 0 && box.top < (doc.defaultView?.innerHeight || 1200), entrance: null, ambient: null, context: null, entryContext: null, held: hold, replays: 0, button: node.querySelector?.('[data-feature-replay]'), status: node.querySelector?.('[data-feature-status]'), poses: new Map(), savedOwner: node.getAttribute('data-feature-motion')};
      records.set(node, record);observer?.observe(node);
      if (ready()) node.setAttribute?.('data-feature-motion', 'gsap');
      record.onClick = event => {
        const target = event.target;
        if (record.button && (target === record.button || record.button.contains?.(target))) {
          event.preventDefault?.();replay(record.node);
        }
      };
      node.addEventListener?.('click', record.onClick);
      if (entrance) startEntrance(record);
      update(record);
    }
    return {
      version: VERSION,
      setRoute(next) {if (disposed || next === route) return;route = next;visit++;for (const record of [...records.values()]) remove(record);ambientTimes.clear();},
      enter(node, {hold = false} = {}) {bind(node, true, hold);},
      release(node, {settle = false} = {}) {const record = records.get(node);if (!record || disposed) return;if (settle) settleEntrance(record);record.held = false;update(record);},
      replay,
      sync(nodes) {if (disposed) return;const live = new Set(nodes);for (const record of [...records.values()]) if (!record.node.isConnected || !live.has(record.node)) remove(record, true);for (const node of live) bind(node);},
      refresh() {if (!disposed) for (const record of records.values()) update(record);},
      getState() {return [...records.values()].map(record => {
        const finished = record.entranceDone || (record.entrance && record.entrance.progress() === 1);
        const active = [finished ? null : record.entrance, record.ambient].filter(Boolean);
        return {scene: record.scene, visit: record.visit, visible: record.visible, connected: record.node.isConnected, engine: ready() ? 'gsap' : 'static', held: record.held, replays: record.replays, animations: active.length, running: usable(record) ? active.filter(timeline => !timeline.paused()).length : 0, entranceTime: record.entrance?.totalTime() || 0, ambientTime: record.ambient?.totalTime() ?? ambientTimes.get(record.scene) ?? 0, labels: record.entrance ? {...record.entrance.labels} : {}, phase: quiet() || !ready() ? 'static' : record.held ? 'held' : (!record.visible || doc.hidden) ? 'paused' : record.entrance && !finished ? 'entering' : 'ambient'};
      });},
      dispose() {if (disposed) return;disposed = true;for (const record of [...records.values()]) remove(record);ambientTimes.clear();observer?.disconnect();}
    };
  }
  globalThis.QMFeatureSceneMotion = {version: VERSION, create};
})();

