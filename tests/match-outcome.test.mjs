import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderMatchOutcome } from '../static/js/match-outcome.mjs';

test('victorias y derrotas se calculan desde el club, como local o visitante', () => {
  for (const home of [true, false]) {
    const win = renderMatchOutcome({status: 'played', score: '8-4', home});
    assert.match(win, /match-outcome-win/);
    assert.match(win, /Victoria del club/);
    assert.match(win, />✓<\/span>/);
    const loss = renderMatchOutcome({status: 'played', score: '4-8', home});
    assert.match(loss, /match-outcome-loss/);
    assert.match(loss, /Derrota del club/);
    assert.match(loss, />✕<\/span>/);
  }
});

test('empate a seis muestra una raya y la clase de empate', () => {
  const result = renderMatchOutcome({status: 'played', score: ' 6 - 6 '});
  assert.match(result, /match-outcome-draw/);
  assert.match(result, /aria-label="Empate"/);
  assert.match(result, />—<\/span>/);
});

test('marcadores de dos cifras se comparan numéricamente', () => {
  assert.match(renderMatchOutcome({status: 'played', score: '10-2'}), /match-outcome-win/);
});

test('no inventa victoria o empate si no hay resultado válido o el partido está pendiente', () => {
  for (const score of ['', null, undefined, 'pendiente', '<img>']) {
    const result = renderMatchOutcome({status: 'played', score});
    assert.match(result, /Resultado por confirmar/);
    assert.doesNotMatch(result, /match-outcome-(win|loss|draw)/);
  }
  const pending = renderMatchOutcome({status: 'scheduled', score: '6-6'});
  assert.match(pending, />→<\/span>/);
  assert.doesNotMatch(pending, /match-outcome-draw/);
});