(() => {
  document.querySelectorAll('[data-match-form]').forEach((form) => {
    const teamSelect = form.querySelector('[data-team-select]');
    const playerSelects = form.querySelectorAll('[data-player-select]');
    const editingMatch = form.dataset.matchEditing === 'true';
    if (!teamSelect) return;

    const filterPlayers = (clearOtherTeams) => {
      const teamId = teamSelect.value;
      playerSelects.forEach((select) => {
        Array.from(select.options).forEach((option) => {
          const belongsToTeam = option.dataset.team === teamId;
          const archivedSelection = editingMatch && option.dataset.active === 'false' && option.selected;
          option.disabled = option.value !== '' && (!belongsToTeam || (option.dataset.active === 'false' && !archivedSelection));
          if (!belongsToTeam && clearOtherTeams) option.selected = false;
        });
      });
    };

    filterPlayers(false);
    teamSelect.addEventListener('change', () => filterPlayers(true));
  });
})();
