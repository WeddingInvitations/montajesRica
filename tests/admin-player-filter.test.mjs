import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/js/admin.js', import.meta.url), 'utf8');

function option(value, team = '', active = 'true', selected = false) {
  return {
    value, dataset: { team, active }, selected, disabled: false,
    cloneNode() { return option(this.value, this.dataset.team, this.dataset.active, this.selected); }
  };
}

function editor(editing = false, firstTeam = 'one', secondTeam = 'two') {
  const select = {
    value: editing ? 'archived' : '',
    options: [option(''), option('a', firstTeam), option('b', secondTeam), option('archived', firstTeam, 'false', editing)],
    replaceChildren(...options) { this.options = options; }
  };
  const listeners = {};
  const teamSelect = { value: firstTeam, addEventListener(event, callback) { listeners[event] = callback; } };
  const exceptionListeners = {};
  const exception = { checked: false, addEventListener(event, callback) { exceptionListeners[event] = callback; } };
  const form = {
    dataset: { matchEditing: String(editing) },
    querySelector(selector) { return selector === '[data-team-select]' ? teamSelect : exception; },
    // Regression: pair selects are siblings of the data-match-form wrapper.
    closest() { return { querySelectorAll() { return [select]; } }; }
  };
  vm.runInNewContext(source, {
    document: { querySelector() { return null; }, querySelectorAll(selector) { return selector === '[data-match-form]' ? [form] : []; } },
    location: { hash: '' }
  });
  return { select, teamSelect, exception, toggle: () => exceptionListeners.change(), change: () => listeners.change() };
}

test('new match shows only active players in selected team and clears other selections', () => {
  const { select, teamSelect, change } = editor();
  assert.deepEqual(select.options.map(o => o.value), ['', 'a']);
  select.value = 'a';
  teamSelect.value = 'two';
  change();
  assert.deepEqual(select.options.map(o => o.value), ['', 'b']);
  assert.equal(select.value, '');
  teamSelect.value = 'empty';
  change();
  assert.deepEqual(select.options.map(o => o.value), ['']);
});

test('editing retains original archived selection only for its team', () => {
  const { select, teamSelect, change } = editor(true);
  assert.deepEqual(select.options.map(o => o.value), ['', 'a', 'archived']);
  assert.equal(select.value, 'archived');
  teamSelect.value = 'two';
  change();
  assert.deepEqual(select.options.map(o => o.value), ['', 'b']);
  assert.equal(select.value, '');
});

test('Future players appear for 500 only with explicit exception', () => {
  const { select, teamSelect, exception, change, toggle } = editor(false, 'equipo-1', 'equipo-2');
  assert.deepEqual(select.options.map(o => o.value), ['', 'a']);
  assert.equal(exception.disabled, false);
  exception.checked = true;
  toggle();
  assert.deepEqual(select.options.map(o => o.value), ['', 'a', 'b']);
  select.value = 'b';
  exception.checked = false;
  toggle();
  assert.equal(select.value, '');
  assert.deepEqual(select.options.map(o => o.value), ['', 'a']);
  teamSelect.value = 'equipo-2';
  change();
  assert.equal(exception.checked, false);
  assert.equal(exception.disabled, true);
  assert.deepEqual(select.options.map(o => o.value), ['', 'b']);
});

test('roster search combines team and name, ignoring accents and case', () => {
  const callbacks = {};
  const team = { value: '', addEventListener(event, fn) { callbacks.team = fn; } };
  const search = { value: '', addEventListener(event, fn) { callbacks.search = fn; } };
  const empty = { hidden: true };
  const rows = [['Álvaro Demo', 'equipo-1'], ['Beatriz Demo', 'equipo-2']].map(([name, teamId]) => ({
    hidden: false,
    classList: { toggle() {} },
    addEventListener() {},
    querySelector(selector) { return { value: selector === '[name="name"]' ? name : teamId }; }
  }));
  vm.runInNewContext(source, {
    document: {
      querySelector(selector) { return ({ '[data-roster-team]': team, '[data-roster-search]': search, '[data-roster-empty]': empty })[selector]; },
      querySelectorAll(selector) { return selector === '[data-roster-row]' ? rows : []; }
    },
    location: { hash: '' }
  });
  search.value = 'ALVARO';
  callbacks.search();
  assert.deepEqual(rows.map(row => row.hidden), [false, true]);
  team.value = 'equipo-2';
  callbacks.team();
  assert.deepEqual(rows.map(row => row.hidden), [true, true]);
  assert.equal(empty.hidden, false);
  search.value = '';
  callbacks.search();
  assert.deepEqual(rows.map(row => row.hidden), [true, false]);
});
