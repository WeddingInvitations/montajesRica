(() => {
  const form = document.querySelector('[data-standings-upload]');
  if (!form) return;
  const input = form.querySelector('[name="standings_file"]');
  const button = form.querySelector('[type="submit"]');
  const feedback = form.querySelector('[data-upload-feedback]');
  const reload = form.querySelector('[data-upload-reload]');
  const originalLabel = button.textContent;
  let busy = false;

  function report(message, error = false) {
    feedback.hidden = false;
    feedback.textContent = message;
    feedback.dataset.state = error ? 'error' : 'success';
    feedback.setAttribute('role', error ? 'alert' : 'status');
    feedback.focus();
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy) return;
    reload.hidden = true;
    const file = input.files[0];
    if (!file || !/\.xlsx$/i.test(file.name)) {
      report('Selecciona un archivo Excel .xlsx con las tres hojas de clasificación.', true);
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      report('El archivo supera el límite de 2 MB. No se ha enviado ninguna hoja.', true);
      return;
    }
    if (!window.confirm('¿Importar las tres hojas y reemplazar las tablas con datos? Las hojas vacías no borrarán ninguna clasificación.')) return;
    busy = true;
    button.disabled = true;
    input.disabled = true;
    form.setAttribute('aria-busy', 'true');
    button.textContent = 'Importando las tres hojas…';
    report('Leyendo, validando y guardando las tres hojas. Espera al resultado antes de salir.');
    feedback.dataset.state = 'pending';
    try {
      // FormData debe incluir el archivo y el CSRF original. No fijar Content-Type:
      // el navegador añade el boundary de multipart/form-data.
      input.disabled = false;
      const body = new FormData(form);
      input.disabled = true;
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body
      });
      const type = response.headers.get('content-type') || '';
      if (!type.includes('application/json')) {
        const messages = {
          400: 'El servidor rechazó el formulario. Recarga la página para renovar la protección CSRF.',
          401: 'Tu sesión ha caducado. Inicia sesión de nuevo.',
          403: 'No tienes permisos de administración para importar.',
          413: 'El servidor rechazó el archivo por tamaño. El máximo es 2 MB.'
        };
        throw new Error(messages[response.status] || `El servidor no devolvió el resultado de importación (HTTP ${response.status}). Recarga la página; si persiste, comprueba que está desplegada la versión actual del importador.`);
      }
      const result = await response.json();
      if (!response.ok || result.ok !== true) {
        throw new Error(result.message || `No se pudo completar la importación (HTTP ${response.status}).`);
      }
      if (!Array.isArray(result.sheets) || result.sheets.length !== 3) {
        throw new Error('El servidor no informó del resultado de las tres hojas. Recarga las clasificaciones para comprobar qué se ha guardado.');
      }
      report(result.message);
      reload.hidden = false;
    } catch (error) {
      report(error instanceof TypeError
        ? 'No se ha podido contactar con el servidor o se perdió la conexión. Recarga las clasificaciones para comprobar si se guardaron antes de volver a intentarlo.'
        : error.message || 'Respuesta no válida del servidor. Recarga las clasificaciones para comprobar su estado.', true);
      reload.hidden = false;
    } finally {
      busy = false;
      button.disabled = false;
      input.disabled = false;
      button.textContent = originalLabel;
      form.setAttribute('aria-busy', 'false');
    }
  });
})();