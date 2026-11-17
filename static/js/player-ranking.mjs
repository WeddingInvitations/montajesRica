const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[character]);
const count = (value) => Number.isSafeInteger(value) && value >= 0 ? value : 0;

// Wilson lower confidence bound (95%): rewards win rate while accounting for
// sample size. Unresolved played matches do not contribute invented victories.
export function rankingIndex(wins, played) {
  if (!played) return 0;
  const z = 1.96;
  const p = wins / played;
  return (p + z * z / (2 * played) - z * Math.sqrt((p * (1 - p) + z * z / (4 * played)) / played))
    / (1 + z * z / played);
}

export function buildPlayerRanking(players, statistics = {}, teamId = 'all') {
  return players.filter(player => player.active !== false && (teamId === 'all' || player.team_id === teamId))
    .map(player => {
      const stats = statistics[player.id] || {};
      const played = count(stats.played);
      const wins = Math.min(count(stats.wins), played);
      const losses = Math.min(count(stats.losses), played - wins);
      return { ...player, played, wins, losses, sets_won: count(stats.sets_won), sets_lost: count(stats.sets_lost),
        winRate: played ? wins / played : null, index: rankingIndex(wins, played) };
    })
    .sort((a, b) => Number(b.played > 0) - Number(a.played > 0)
      || b.index - a.index || b.winRate - a.winRate || b.wins - a.wins
      || (b.sets_won - b.sets_lost) - (a.sets_won - a.sets_lost)
      || b.sets_won - a.sets_won || a.name.localeCompare(b.name, 'es'));
}

export function renderPlayerRanking(players, statistics, teams, teamId = 'all') {
  const ranking = buildPlayerRanking(players, statistics, teamId);
  if (!ranking.length) return '<div class="empty-state"><strong>No hay jugadores para este filtro</strong></div>';
  const percent = value => new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(value * 100);
  let position = 0;
  return `<div class="roster-table-scroll" role="region" aria-label="Ranking de jugadores" tabindex="0"><table class="roster-table ranking-table"><caption class="sr-only">Ranking ${teamId === 'all' ? 'general del club' : 'del equipo seleccionado'}</caption><thead><tr><th scope="col">Posición</th><th scope="col">Jugador</th><th scope="col">Equipo</th><th scope="col">Índice ajustado</th><th scope="col">Victorias (%)</th><th scope="col">Partidos jugados</th><th scope="col">Ganados</th><th scope="col">Perdidos</th><th scope="col">Sets ganados</th><th scope="col">Sets perdidos</th></tr></thead><tbody>${ranking.map(player => `<tr><td class="roster-number">${player.played ? ++position : '—'}</td><th scope="row">${escape(player.name)}${!player.played ? '<small class="ranking-unplayed">Sin partidos</small>' : ''}</th><td>${escape(teams.find(team => team.id === player.team_id)?.name || 'Equipo por confirmar')}</td><td class="roster-number ranking-index">${player.played ? percent(player.index) : '—'}</td><td class="roster-number">${player.played ? `${percent(player.winRate)} %` : '—'}</td><td class="roster-number">${player.played}</td><td class="roster-number">${player.wins}</td><td class="roster-number">${player.losses}</td><td class="roster-number">${player.sets_won}</td><td class="roster-number">${player.sets_lost}</td></tr>`).join('')}</tbody></table></div>`;
}
