// El marcador general se guarda como local-visitante.
export function renderMatchOutcome(match) {
  if (match.status !== 'played') {
    return '<span class="match-arrow" role="img" aria-label="Próximo partido" title="Próximo partido">→</span>';
  }
  const score = /^(\d+)\s*-\s*(\d+)$/.exec(String(match.score ?? '').trim());
  if (!score) {
    return '<span class="match-arrow" role="img" aria-label="Resultado por confirmar" title="Resultado por confirmar">?</span>';
  }
  const isHome = match.home !== false;
  const club = Number(score[isHome ? 1 : 2]);
  const opponent = Number(score[isHome ? 2 : 1]);
  const [outcome, symbol, label] = club > opponent
    ? ['win', '✓', 'Victoria del club']
    : club < opponent
      ? ['loss', '✕', 'Derrota del club']
      : ['draw', '—', 'Empate'];
  return `<span class="match-arrow match-outcome-${outcome}" role="img" aria-label="${label}" title="${label}">${symbol}</span>`;
}