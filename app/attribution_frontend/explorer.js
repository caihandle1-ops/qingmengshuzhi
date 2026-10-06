/* Frozen values are text nodes. Only a deliberate, revision-bound source selection leaves this frame. */
(() => {
  'use strict';
  const shell = document.getElementById('explorer'), canvas = document.getElementById('canvas');
  const nodeHost = document.getElementById('nodes'), branches = document.getElementById('branches');
  const detail = document.getElementById('detail'), evidenceButton = document.getElementById('evidence-button');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)'), svgNS = 'http://www.w3.org/2000/svg';
  let payload = null, motion = null, selected = 'root', evidenceNode = null, buttons = [], paths = [], joints = [];
  let lastPose = null, nonce = 0, disposed = false, visible = true, sizeObserver = null, intersection = null;
  const send = (type, data = {}) => parent.postMessage({isStreamlitMessage: true, type, ...data}, '*');
  const text = (id, value) => { document.getElementById(id).textContent = value || ''; };
  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function svg(tag, className) {
    const node = document.createElementNS(svgNS, tag); node.setAttribute('class', className); branches.appendChild(node); return node;
  }
  function height() {
    if (!disposed) send('streamlit:setFrameHeight', {height: Math.ceil(shell.getBoundingClientRect().height) + 3});
  }
  function updateEvidenceButton() {
    const node = payload?.nodes.find(item => item.id === selected);
    evidenceButton.hidden = !node?.has_evidence;
    evidenceButton.setAttribute('aria-expanded', String(evidenceNode === selected));
    evidenceButton.textContent = evidenceNode === selected ? '收起本节点依据 ↙' : '查看本节点依据 ↗';
  }
  function detailFor(node) {
    selected = node.id;
    detail.dataset.node = node.id; detail.dataset.status = node.status;
    text('detail-role', node.role); text('detail-title', node.label); text('detail-status', node.status_label);
    document.getElementById('detail-status').dataset.status = node.status;
    text('previous-year', payload.previous_year + ' 年'); text('current-year', payload.current_year + ' 年');
    text('previous-value', node.previous); text('current-value', node.current);
    for (const unit of document.querySelectorAll('.unit')) unit.textContent = node.unit;
    text('delta', node.delta); text('growth', node.growth); text('interpretation', node.interpretation); text('reason', node.reason);
    const list = document.getElementById('source-list'); list.replaceChildren();
    const sources = node.sources || [];
    for (const source of sources.slice(0, 4)) list.appendChild(element('li', '', source));
    if (sources.length > 4) list.appendChild(element('li', '', `另有 ${sources.length - 4} 条，展开本节点依据查看。`));
    if (!sources.length) list.appendChild(element('li', '', '本节点未保留可展示来源；不借用其他节点依据。'));
    for (const button of buttons) {
      button.classList.toggle('is-selected', button.dataset.node === node.id);
      button.setAttribute('aria-pressed', String(button.dataset.node === node.id));
    }
    updateEvidenceButton(); height();
  }
  function paint(pose) {
    if (disposed || !payload) return;
    lastPose = pose;
    shell.dataset.phase = pose.phase;
    shell.dataset.expanded = String(pose.expanded);
    const width = canvas.clientWidth, rootX = width * (.5 - .28 * pose.open), rootY = 204;
    const root = buttons[0], rootW = root.offsetWidth || 240, rootH = root.offsetHeight || 190;
    root.style.transform = `translate3d(${rootX - rootW / 2}px,${rootY - rootH / 2}px,0)`;
    root.setAttribute('aria-expanded', String(pose.expanded));
    root.querySelector('.root-action-label').textContent = pose.expanded ? '收回分项线索' : (buttons.length > 1 ? '展开分项线索' : '当前没有分项线索');
    root.querySelector('.root-action-symbol').textContent = pose.expanded ? '−' : '+';
    text('canvas-caption', pose.expanded ? '选择一条分项线索，核对变化与出处' : '点击观察结果，展开分项线索');
    text('branch-state', pose.expanded ? `${buttons.length - 1} 条分项线索 · ${payload.previous_year} → ${payload.current_year}` : '观察结果 · 点击展开');
    const count = buttons.length - 1;
    buttons.slice(1).forEach((button, index) => {
      const targetY = count === 1 ? 204 : count === 2 ? 137 + index * 134 : 81 + index * 123;
      const focus = pose.focus[index + 1] || 0, scale = .82 + .18 * pose.open + .025 * focus;
      const x = rootX + (width * .74 - rootX) * pose.open - focus * 10;
      const y = rootY + (targetY - rootY) * pose.open;
      button.hidden = !pose.expanded && pose.open < .001;
      const cardW = button.offsetWidth || 214, cardH = button.offsetHeight || 114;
      button.disabled = !pose.expanded;
      button.tabIndex = pose.expanded ? 0 : -1;
      button.setAttribute('aria-hidden', String(!pose.expanded));
      button.style.transform = `translate3d(${x - cardW / 2}px,${y - cardH / 2}px,0) scale(${scale})`;
      button.style.opacity = String(pose.open);
      button.style.zIndex = focus > .5 ? '2' : '1';
      const startX = rootX + rootW / 2 - 1, endX = x - cardW * scale / 2 + 1;
      const middle = startX + (endX - startX) * .52, path = paths[index], joint = joints[index];
      path.setAttribute('d', `M${startX},${rootY} C${middle},${rootY} ${middle},${y} ${endX},${y}`);
      path.style.opacity = String(pose.open);
      path.classList.toggle('is-active', selected === payload.nodes[index + 1].id);
      joint.setAttribute('cx', String(endX)); joint.setAttribute('cy', String(y)); joint.setAttribute('r', '3');
      joint.style.opacity = String(pose.open);
    });
  }
  function choose(index) {
    if (!payload?.nodes[index]) return;
    detailFor(payload.nodes[index]); motion?.focus(index);
  }
  function rootToggle() {
    detailFor(payload.nodes[0]);
    if (buttons.length > 1) motion?.toggle();
  }
  function nodeKey(event, index) {
    if (event.key === 'Escape') {
      event.preventDefault(); motion?.close(); detailFor(payload.nodes[0]); buttons[0].focus({preventScroll: true}); return;
    }
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    let next = event.key === 'Home' || event.key === 'ArrowLeft' ? 0 : event.key === 'End' ? buttons.length - 1 :
      Math.max(0, Math.min(buttons.length - 1, index + (event.key === 'ArrowUp' ? -1 : 1)));
    choose(next); buttons[next].focus({preventScroll: true});
  }
  function build(next) {
    motion?.dispose(); payload = next; selected = 'root'; buttons = []; paths = []; joints = [];
    nodeHost.replaceChildren(); branches.replaceChildren();
    text('scope', `${payload.company} · ${payload.previous_year} → ${payload.current_year}`);
    payload.nodes.forEach((node, index) => {
      const button = element('button', 'atlas-node' + (index === 0 ? ' is-root' : '') + (node.status === 'insufficient' ? ' is-missing' : ''));
      button.type = 'button'; button.dataset.node = node.id;
      button.setAttribute('aria-label', `${node.role}：${node.label}，${node.current} ${node.unit}。${node.status_label}`);
      button.appendChild(element('span', 'node-role', node.role)); button.appendChild(element('strong', 'node-title', node.label));
      const number = element('span', 'node-number', node.current); number.appendChild(element('small', '', node.unit)); button.appendChild(number);
      button.appendChild(element('span', 'node-status', node.status_label));
      if (index === 0) {
        const action = element('span', 'root-action'); action.appendChild(element('span', 'root-action-label', '展开分项线索'));
        action.appendChild(element('span', 'root-action-symbol', '+')); button.appendChild(action);
      } else {
        const path = svg('path', 'branch-line' + (node.auxiliary ? ' is-auxiliary' : '') + (node.status === 'insufficient' ? ' is-missing' : ''));
        paths.push(path); joints.push(svg('circle', 'branch-joint')); button.hidden = true;
      }
      button.addEventListener('click', () => index === 0 ? rootToggle() : choose(index));
      button.addEventListener('keydown', event => nodeKey(event, index));
      buttons.push(button); nodeHost.appendChild(button);
    });
    detailFor(payload.nodes[0]);
    motion = window.QMAttributionMotion.createMotion({
      reduced: reduced.matches || !window.requestAnimationFrame,
      now: () => performance.now(), hidden: () => document.hidden,
      raf: callback => window.requestAnimationFrame ? requestAnimationFrame(callback) : setTimeout(() => callback(performance.now()), 0),
      cancel: id => window.cancelAnimationFrame ? cancelAnimationFrame(id) : clearTimeout(id),
    }, paint, buttons.length);
    motion.setVisible(visible); height();
  }
  function componentEvent() {
    const node = payload?.nodes.find(item => item.id === selected);
    if (!node?.has_evidence || disposed) return;
    const action = evidenceNode === selected ? 'source_close' : 'source_focus';
    send('streamlit:setComponentValue', {value: {action, node_id: node.id, revision: payload.revision,
      nonce: `${Date.now()}-${++nonce}`}, dataType: 'json'});
  }
  function onRender(event) {
    if (disposed || event.source !== window.parent || event.data?.type !== 'streamlit:render') return;
    const args = event.data.args || {}, next = args.payload;
    if (!next || typeof next.revision !== 'string' || !Array.isArray(next.nodes) || !next.nodes.length || next.nodes.length > 4) return;
    const priorEvidence = evidenceNode;
    evidenceNode = next.nodes.some(node => node.id === args.evidence_node && node.has_evidence) ? args.evidence_node : null;
    if (!payload || next.revision !== payload.revision) build(next);
    updateEvidenceButton();
    if (priorEvidence && !evidenceNode) evidenceButton.focus({preventScroll: true});
    height();
  }
  const visibility = () => motion?.syncVisibility();
  const reduce = () => motion?.setReduced(reduced.matches || !window.requestAnimationFrame);
  function dispose() {
    if (disposed) return;
    disposed = true; motion?.dispose(); sizeObserver?.disconnect(); intersection?.disconnect();
    window.removeEventListener('message', onRender); document.removeEventListener('visibilitychange', visibility);
    reduced.removeEventListener('change', reduce); evidenceButton.removeEventListener('click', componentEvent);
  }
  evidenceButton.addEventListener('click', componentEvent);
  window.addEventListener('message', onRender); document.addEventListener('visibilitychange', visibility);
  reduced.addEventListener('change', reduce); window.addEventListener('pagehide', dispose, {once: true});
  if (window.ResizeObserver) {
    sizeObserver = new ResizeObserver(() => { if (lastPose) paint(lastPose); height(); }); sizeObserver.observe(shell); sizeObserver.observe(canvas);
  }
  if (window.IntersectionObserver) {
    intersection = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting !== false; motion?.setVisible(visible); }, {threshold: 0});
    intersection.observe(shell);
  }
  send('streamlit:componentReady', {apiVersion: 1}); height();
})();
