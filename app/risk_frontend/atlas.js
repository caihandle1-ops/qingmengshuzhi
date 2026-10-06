/* Every amount remains a supplied text value. The camera changes only geometry. */
(() => {
  'use strict';
  const shell = document.getElementById('atlas'), stage = document.getElementById('map-stage');
  const scene = document.getElementById('map-scene'), zones = document.getElementById('risk-zones');
  const detail = document.getElementById('risk-detail'), resetButton = document.getElementById('reset-camera');
  const positions = [[.20,.30],[.50,.30],[.80,.30],[.16,.70],[.46,.70],[.76,.70]];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let payload = null, selected = null, sourceSelection = null, camera = null, buttons = [], factButtons = [];
  let pose = null, nonce = 0, disposed = false, visible = true, resize = null, intersection = null;
  let returnRevision = null, returnRequest = 0, lastAnchor = '';
  const send = (type, data = {}) => parent.postMessage({isStreamlitMessage: true, type, ...data}, '*');
  const text = (id, value) => { document.getElementById(id).textContent = value || ''; };
  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function height() { if (!disposed) send('streamlit:setFrameHeight', {height: Math.ceil(shell.getBoundingClientRect().height) + 3}); }
  function sameSource(rule, fact) {
    return sourceSelection?.rule_id === rule.id && sourceSelection.metric === fact.metric && sourceSelection.year === fact.year;
  }
  function syncSources() {
    for (const {button, rule, fact} of factButtons) {
      const opened = sameSource(rule, fact);
      button.setAttribute('aria-expanded', String(opened)); button.textContent = opened ? '收起这一指标来源 ↙' : '查看这一指标来源 ↗';
    }
  }
  function sourceAnchor(rule, fact, button) {
    if (disposed || !payload || !button) return;
    const box = button.getBoundingClientRect();
    const rect = {left: box.left, top: box.top, width: box.width, height: box.height};
    if (!Object.values(rect).every(Number.isFinite) || rect.width <= 0 || rect.height <= 0) return;
    const anchor = {type: 'qm:risk-source-anchor', version: 1, revision: payload.revision,
      rule_id: rule.id, metric: fact.metric, year: fact.year, rect};
    const stamp = JSON.stringify(anchor);
    if (stamp === lastAnchor) return;
    lastAnchor = stamp; parent.postMessage(anchor, '*');
  }
  function currentSourceAnchor() {
    const current = factButtons.find(({rule,fact}) => sameSource(rule,fact));
    if (current) sourceAnchor(current.rule, current.fact, current.button);
  }
  function sourceEvent(rule, fact, button) {
    if (disposed || !fact.can_open) return;
    const action = sameSource(rule, fact) ? 'close' : 'source';
    lastAnchor = ''; sourceAnchor(rule, fact, button);
    send('streamlit:setComponentValue', {value: {action,
      rule_id: rule.id, metric: fact.metric, year: fact.year, revision: payload.revision,
      nonce: `${Date.now()}-${++nonce}`}, dataType: 'json'});
  }
  function journeyEvent(action, rule, fact) {
    if (disposed || !['ask','verify'].includes(action) || !fact.journey_actions?.includes(action)) return;
    send('streamlit:setComponentValue', {value: {action, rule_id: rule.id, metric: fact.metric,
      year: fact.year, revision: payload.revision, nonce: `${Date.now()}-${++nonce}`}, dataType: 'json'});
  }
  function showDetail(index) {
    selected = index; factButtons = [];
    const overview = document.getElementById('overview'), selectedRule = document.getElementById('selected-rule');
    overview.hidden = index !== null; selectedRule.hidden = index === null; resetButton.hidden = index === null;
    for (const [position, button] of buttons.entries()) {
      button.classList.toggle('is-selected', position === index); button.setAttribute('aria-pressed', String(position === index));
    }
    if (index === null) { delete detail.dataset.state; height(); return; }
    const rule = payload.rules[index]; detail.dataset.state = rule.status;
    text('rule-domain', `${rule.id} / ${rule.domain}`); text('rule-title', rule.label); text('rule-status', rule.status_label);
    text('rule-reason', rule.reason); text('rule-definition', rule.rule); text('rule-basis', rule.basis);
    const facts = document.getElementById('rule-facts'); facts.replaceChildren();
    for (const fact of rule.facts) {
      const card = element('article', 'risk-fact'); card.appendChild(element('span', '', `${fact.year} 年 / ${fact.label}`));
      const classes = fact.value === '暂无数据' || fact.value === '多条记录待核对' ? 'missing-value' : fact.metric === 'audit_opinion' ? 'text-value' : '';
      card.appendChild(element('strong', classes, fact.value)); card.appendChild(element('small', '', fact.unit));
      card.appendChild(element('p', '', fact.source));
      if (fact.can_open) {
        const button = element('button', '', '查看这一指标来源 ↗'); button.type = 'button';
        button.dataset.action = 'source';
        button.addEventListener('click', () => sourceEvent(rule, fact, button));
        card.appendChild(button); factButtons.push({button, rule, fact});
      }
      const actions = element('div', 'risk-fact-actions');
      for (const [action,label] of [['ask','追问这个变化'],['verify','核验这项指标']]) {
        if (!fact.journey_actions?.includes(action)) continue;
        const button = element('button', 'journey-action', label); button.type = 'button'; button.dataset.action = action;
        button.setAttribute('aria-label', `${fact.year} 年 ${fact.label}：${label}`);
        button.addEventListener('click', () => journeyEvent(action,rule,fact)); actions.appendChild(button);
      }
      if (actions.children.length) card.appendChild(actions);
      facts.appendChild(card);
    }
    if (!rule.facts.length) facts.appendChild(element('p', 'empty-facts', '没有可用于该规则的年度记录，暂不展示数值。'));
    syncSources(); currentSourceAnchor(); height();
  }
  function paint(next) {
    if (disposed) return;
    pose = next; shell.dataset.phase = next.phase;
    scene.style.transform = `translate3d(${stage.clientWidth * next.x}px,${stage.clientHeight * next.y}px,0) scale(${next.zoom})`;
    for (const [index, button] of buttons.entries()) button.style.opacity = String(.28 + .72 * (next.weights[index] ?? 1));
  }
  function choose(index) {
    if (!payload?.rules[index]) return;
    showDetail(index);
    const [x,y] = positions[index], zoom = 1.32;
    camera?.focus(index, .5 - x * zoom, .5 - y * zoom, zoom);
  }
  function reset() { showDetail(null); camera?.reset(); }
  function keys(event, index) {
    if (event.key === 'Escape') { event.preventDefault(); reset(); buttons[index].focus({preventScroll: true}); return; }
    if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
      Math.max(0, Math.min(buttons.length - 1, index + (event.key === 'ArrowLeft' ? -1 : event.key === 'ArrowUp' ? -3 : event.key === 'ArrowDown' ? 3 : 1)));
    choose(next); buttons[next].focus({preventScroll: true});
  }
  function build(next) {
    camera?.dispose(); payload = next; selected = null; buttons = []; zones.replaceChildren();
    returnRevision = next.revision; returnRequest = 0; lastAnchor = '';
    text('atlas-scope', `${payload.company} · ${payload.year == null ? '年度未记录' : payload.year + ' 年度规则记录'}`);
    text('score-value', payload.score); text('score-note', payload.score_available ? '沿用现有评分结果' : payload.score_reason || '所需指标尚不完整');
    text('coverage-label', payload.coverage_complete ? '六项规则均已检查' : `覆盖不完整 · ${payload.counts.unchecked} 项未检查`);
    const counts = document.getElementById('coverage-counts'); counts.replaceChildren();
    for (const [status, label] of [['triggered','已触发'],['clear','已检未触发'],['unchecked','未检查']]) {
      const item = element('span', 'count-' + status); item.appendChild(element('strong', '', String(payload.counts[status])));
      item.appendChild(element('span', '', label)); counts.appendChild(item);
    }
    payload.rules.forEach((rule,index) => {
      const button = element('button', 'risk-zone'); button.type = 'button';
      button.dataset.rule = rule.id; button.dataset.state = rule.status; button.dataset.level = rule.level;
      button.style.left = positions[index][0] * 100 + '%'; button.style.top = positions[index][1] * 100 + '%';
      button.setAttribute('aria-label', `${rule.id} ${rule.label}：${rule.status_label}，点击查看指标与依据`);
      const id = element('span', 'zone-id'); id.appendChild(element('span', '', rule.id)); id.appendChild(element('i'));
      button.appendChild(id); button.appendChild(element('strong', '', rule.label)); button.appendChild(element('small', '', rule.domain));
      button.appendChild(element('span', 'zone-status', rule.status_label));
      button.addEventListener('click', () => selected === index ? reset() : choose(index));
      button.addEventListener('keydown', event => keys(event,index)); buttons.push(button); zones.appendChild(button);
    });
    showDetail(null);
    camera = window.QMRiskCamera.createCamera({reduced: reduced.matches || !window.requestAnimationFrame,
      now: () => performance.now(), hidden: () => document.hidden,
      raf: callback => window.requestAnimationFrame ? requestAnimationFrame(callback) : setTimeout(() => callback(performance.now()), 0),
      cancel: id => window.cancelAnimationFrame ? cancelAnimationFrame(id) : clearTimeout(id)}, paint, buttons.length);
    camera.setVisible(visible); height();
  }
  function restoreFocus(request) {
    if (!request || request.revision !== payload.revision || !Number.isInteger(request.request) || request.request <= 0) return;
    if (returnRevision === request.revision && request.request <= returnRequest) return;
    const index = payload.rules.findIndex(rule => rule.id === request.rule_id && rule.facts.some(fact =>
      fact.metric === request.metric && fact.year === request.year));
    if (index < 0) return;
    returnRevision = request.revision; returnRequest = request.request;
    choose(index); buttons[index].focus({preventScroll: true});
  }
  function onRender(event) {
    if (disposed || event.source !== window.parent || event.data?.type !== 'streamlit:render') return;
    const args = event.data.args || {}, next = args.payload;
    if (!next || typeof next.revision !== 'string' || !Array.isArray(next.rules) || next.rules.length !== 6) return;
    const prior = sourceSelection, candidate = args.source_selection;
    sourceSelection = candidate && candidate.revision === next.revision && next.rules.some(rule => rule.id === candidate.rule_id &&
      rule.facts.some(fact => fact.can_open && fact.metric === candidate.metric && fact.year === candidate.year)) ? candidate : null;
    if (!payload || payload.revision !== next.revision) build(next);
    restoreFocus(args.return_focus);
    syncSources();
    if (prior && !sourceSelection) {
      const previous = factButtons.find(({rule,fact}) => rule.id === prior.rule_id && fact.metric === prior.metric && fact.year === prior.year);
      previous?.button.focus({preventScroll: true});
    }
    currentSourceAnchor(); height();
  }
  const visibility = () => camera?.syncVisibility();
  const reduce = () => camera?.setReduced(reduced.matches || !window.requestAnimationFrame);
  function dispose() {
    if (disposed) return; disposed = true; camera?.dispose(); resize?.disconnect(); intersection?.disconnect();
    window.removeEventListener('message', onRender); document.removeEventListener('visibilitychange', visibility);
    reduced.removeEventListener('change', reduce); resetButton.removeEventListener('click', reset);
  }
  resetButton.addEventListener('click', reset); window.addEventListener('message', onRender);
  document.addEventListener('visibilitychange', visibility); reduced.addEventListener('change', reduce);
  window.addEventListener('pagehide', dispose, {once: true});
  if (window.ResizeObserver) { resize = new ResizeObserver(() => { if (pose) paint(pose); currentSourceAnchor(); height(); }); resize.observe(shell); resize.observe(stage); }
  if (window.IntersectionObserver) {
    intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting !== false; camera?.setVisible(visible); }, {threshold: 0}); intersection.observe(shell);
  }
  send('streamlit:componentReady', {apiVersion: 1}); height();
})();
