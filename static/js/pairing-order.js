(() => {
  const reverseScore = value => value.replace(/(\d+)\s*-\s*(\d+)/g, '$2-$1');
  document.querySelectorAll('[data-pairing-order]').forEach(editor => {
    const form = editor.closest('form');
    const home = form.querySelector('[data-match-home]');
    if (!home) return;
    let previous = home.checked;
    const update = () => {
      const changed = previous !== home.checked;
      editor.querySelectorAll('.pairing-row').forEach(row => {
        const mr = row.querySelector('[data-pair-mr]');
        const rival = row.querySelector('[data-pair-rival]');
        const sets = row.querySelector('[data-pair-sets]');
        row.insertBefore(home.checked ? mr : rival, sets);
        row.insertBefore(home.checked ? rival : mr, sets);
        row.querySelector('[data-pair-mr-title]').textContent = `Montajes Rica · ${home.checked ? 'Local' : 'Visitante'}`;
        row.querySelector('[data-pair-rival-title]').textContent = `Rival · ${home.checked ? 'Visitante' : 'Local'} (opcional)`;
        row.querySelector('[data-pair-sets-title]').textContent = `Sets (${home.checked ? 'MR–rival' : 'rival–MR'})`;
        const input = sets.querySelector('input');
        if (changed) input.value = reverseScore(input.value);
      });
      if (changed) {
        const score = form.querySelector('[name="score"]');
        if (score) score.value = reverseScore(score.value);
      }
      previous = home.checked;
    };
    update();
    home.addEventListener('change', update);
  });
})();