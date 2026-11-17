const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);

export function renderPairScoreboard(pairing = {}, index = 0, players = [], opponent = '', isHome = true) {
  const ids = Array.isArray(pairing.player_ids) ? pairing.player_ids : [];
  const snapshots = Array.isArray(pairing.player_names) ? pairing.player_names : [];
  const names = Array.from({ length: Math.max(ids.length, snapshots.length) }, (_, position) =>
    snapshots[position] || players.find((player) => player.id === ids[position])?.name || 'Jugador por confirmar'
  );
  const mrName = names.length ? names.join(' y ') : 'Pareja por confirmar';
  const rivalName = pairing.opponent_pair || 'Pareja rival por confirmar';
  const sets = Array.isArray(pairing.sets) ? pairing.sets : [];
  const hasScore = sets.some((set) => Number.isInteger(set?.home) && Number.isInteger(set?.away));
  const columns = Array.from({ length: Math.max(3, sets.length) }, (_, setIndex) => setIndex);
  const scoreCell = (setIndex, side) => {
    const set = sets[setIndex];
    const value = set?.[side];
    const other = set?.[side === 'home' ? 'away' : 'home'];
    const recorded = Number.isInteger(value) && value >= 0;
    const won = recorded && Number.isInteger(other) && value > other;
    return `<td class="set-score${won ? ' set-score-won' : ''}">${recorded ? escape(value) : '<span aria-label="Sin resultado">—</span>'}</td>`;
  };
  // Los sets históricos son MR-rival: se cambia el orden de las filas, no
  // la asociación del marcador a cada pareja.
  const sides = [
    { mr: true, name: mrName, team: 'Montajes Rica', side: 'home' },
    { mr: false, name: rivalName, team: opponent || 'Rival', side: 'away' }
  ];
  if (!isHome) sides.reverse();
  const rows = sides.map((side, position) => `<tr${side.mr ? ' class="scoreboard-mr"' : ''}><th scope="row"><span class="scoreboard-team">${escape(side.team)} · ${position === 0 ? 'Local' : 'Visitante'}</span><strong>${escape(side.name)}</strong></th>${columns.map(i => scoreCell(i, side.side)).join('')}</tr>`).join('');
  const namesInOrder = sides.map(side => escape(side.name)).join(' <span aria-hidden="true">·</span> ');
  return `<details class="pair-scoreboard"><summary><span class="pair-scoreboard-title">Partido ${index + 1}<small>${namesInOrder}</small></span><span class="pair-scoreboard-status">${hasScore ? 'Ver resultado' : 'Resultado pendiente'}</span><span class="pair-scoreboard-chevron" aria-hidden="true">⌄</span></summary><div class="scoreboard-scroll" role="region" aria-label="Resultado del partido ${index + 1}" tabindex="0"><table class="scoreboard-table"><caption class="sr-only">Partido ${index + 1}: marcador por sets en orden local–visitante</caption><thead><tr><th scope="col">Parejas</th>${columns.map((i) => `<th scope="col">Set ${i + 1}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></details>`;
}

export function renderMatchScoreboards(match, players = []) {
  const pairings = Array.isArray(match.pairings) ? match.pairings : [];
  if (!pairings.length) {
    return `<p class="pairings-pending">Las parejas todavía no están configuradas.</p>${renderPairScoreboard({}, 0, players, match.opponent, match.home !== false)}`;
  }
  return pairings.map((pairing, index) => renderPairScoreboard(pairing, index, players, match.opponent, match.home !== false)).join('');
}
