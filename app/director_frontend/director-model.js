(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.QMDirector = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  // No timers or automatic advance. A command commits exactly one final state.
  function createDeck(onChange = () => {}) {
    let payload = null, order = [], selected = new Set(), active = '', disposed = false, focus = {metric:null,year:null};
    const visible = () => order.filter(id => selected.has(id));
    const focused = () => {const row=payload?.focus?.rows?.find(item=>item.year===focus.year);const metric=row?.metrics?.find(item=>item.id===focus.metric);return metric?{...metric,year:row.year,ambiguous:row.ambiguous===true}:null;};
    const snapshot = () => ({payload, order: [...order], selected: [...selected], active, focus:{...focus},fact:focused(),
      visible: visible(), index: visible().indexOf(active)});
    const publish = (direction = 0, changed = false) => {
      if (!disposed) onChange({...snapshot(), direction, changed});
    };
    function go(id) {
      const list = visible(), target = list.indexOf(id), old = list.indexOf(active);
      if (disposed || target < 0 || id === active) return false;
      active = id; publish(Math.sign(target - old), true); return true;
    }
    return {
      snapshot,
      setPayload(next) {
        if (disposed || !next || !Array.isArray(next.chapters) || !next.chapters.length) return false;
        if (!next.chapters.every(c => c && typeof c.id === 'string' && c.id && typeof c.kind === 'string')) return false;
        const ids = next.chapters.map(c => c.id);
        if (new Set(ids).size !== ids.length) return false;
        if (payload?.revision === next.revision) return false;
        payload = next; order = ids; selected = new Set(ids); active = ids[0];
        const focusRows=next.focus?.rows,metricOptions=next.focus?.metrics;
        focus={metric:Array.isArray(metricOptions)?metricOptions[0]?.id:null,year:Array.isArray(focusRows)?focusRows.at(-1)?.year:null};
        publish(0, true); return true;
      },
      go,
      setFocus(metric,year) {
        if(disposed||!payload?.focus?.metrics?.some(item=>item.id===metric)||!payload?.focus?.rows?.some(row=>row.year===year))return false;
        if(focus.metric===metric&&focus.year===year)return false;
        focus={metric,year};publish(0,true);return true;
      },
      step(delta) {const list = visible(); return go(list[Math.max(0, Math.min(list.length - 1, list.indexOf(active) + delta))]);},
      toggle(id) {
        if (disposed || !order.includes(id) || (selected.has(id) && selected.size === 1)) return false;
        const prior = visible(), old = prior.indexOf(active);
        if (selected.has(id)) selected.delete(id); else selected.add(id);
        const list = visible(); let changed = false;
        if (!selected.has(active)) {active = list[Math.min(Math.max(old, 0), list.length - 1)]; changed = true;}
        publish(0, changed); return true;
      },
      move(id, delta) {
        if (disposed) return false;
        const index = order.indexOf(id), target = index + delta;
        if (index < 0 || target < 0 || target >= order.length || Math.abs(delta) !== 1) return false;
        [order[index], order[target]] = [order[target], order[index]]; publish(); return true;
      },
      reset() {if (!payload || disposed) return; const changed = active !== payload.chapters[0].id;
        order = payload.chapters.map(c => c.id); selected = new Set(order); active = order[0]; publish(0, changed);},
      dispose() {disposed = true; payload = null; order = []; selected.clear(); active = '';focus={metric:null,year:null};}
    };
  }
  return {createDeck};
});
