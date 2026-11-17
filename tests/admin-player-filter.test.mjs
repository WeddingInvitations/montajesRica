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

function editor(editing = false) {
  const select = {
    value: editing ? 'archived' : '',
    options: [option(''), option('a', 'one'), option('b', 'two'), option('archived', 'one', 'false', editing)],
    replaceChildren(...options) { this.options = options; }
  };
  const listeners = {};
  const teamSelect = { value: 'one', addEventListener(event, callback) { listeners[event] = callback; } };
  const form = {
    dataset: { matchEditing: String(editing) },
    querySelector() { return teamSelect; },
    // Regression: pair selects are siblings of the data-match-form wrapper.
    closest() { return { querySelectorAll() { return [select]; } }; }
  };
  vm.runInNewContext(source, {
    document: { querySelectorAll(selector) { return selector === '[data-match-form]' ? [form] : []; } },
    location: { hash: '' }
  });
  return { select, teamSelect, change: () => listeners.change() };
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
