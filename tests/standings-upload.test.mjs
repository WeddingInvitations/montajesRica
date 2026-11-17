import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/js/standings-upload.js', import.meta.url), 'utf8');

function upload({ response, failure, file = { name: 'clasificaciones.xlsx', size: 80000 }, confirm = true } = {}) {
  const attributes = {};
  const input = { files: file ? [file] : [], disabled: false };
  const button = { textContent: 'Importar las tres hojas', disabled: false };
  const feedback = { hidden: true, textContent: '', dataset: {}, setAttribute() {}, focus() {} };
  const reload = { hidden: true };
  let submit;
  const requests = [];
  const form = {
    action: '/admin/standings/import',
    querySelector(selector) {
      return ({ '[name="standings_file"]': input, '[type="submit"]': button, '[data-upload-feedback]': feedback, '[data-upload-reload]': reload })[selector];
    },
    addEventListener(event, callback) { submit = callback; },
    setAttribute(key, value) { attributes[key] = value; }
  };
  class FormData {
    constructor(element) {
      assert.equal(element, form);
      assert.equal(input.disabled, false, 'el archivo debe incluirse en FormData');
      this.file = input.files[0];
      this.csrf = 'token-del-formulario';
    }
  }
  vm.runInNewContext(source, {
    document: { querySelector: () => form }, window: { confirm: () => confirm }, FormData, TypeError,
    fetch: async (url, options) => {
      requests.push({url, options});
      if (failure) throw failure;
      return response;
    }
  });
  return { send: () => submit({ preventDefault() {} }), requests, button, input, feedback, reload, attributes };
}

const jsonResponse = (status, data) => ({ status, ok: status < 400, headers: { get: () => 'application/json' }, json: async () => data });

test('una subida envía archivo y CSRF y muestra el resultado de las tres hojas', async () => {
  const ui = upload({ response: jsonResponse(200, {
    ok: true, message: '500: 6 · Future: 6 · Fem: 5', sheets: [{count:6}, {count:6}, {count:5}]
  }) });
  const pending = ui.send();
  assert.equal(ui.button.disabled, true);
  await ui.send();
  assert.equal(ui.requests.length, 1, 'no permite doble envío');
  await pending;
  assert.equal(ui.requests[0].options.headers.Accept, 'application/json');
  assert.equal(ui.requests[0].options.credentials, 'same-origin');
  assert.equal(ui.requests[0].options.body.csrf, 'token-del-formulario');
  assert.equal(ui.feedback.textContent, '500: 6 · Future: 6 · Fem: 5');
  assert.equal(ui.feedback.dataset.state, 'success');
  assert.equal(ui.reload.hidden, false);
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.input.disabled, false);
  assert.equal(ui.attributes['aria-busy'], 'false');
});

test('muestra errores detallados del servidor como texto, sin interpretar HTML', async () => {
  const message = 'Hoja Fem, fila 4, columna D: <img src=x> no es un entero';
  const ui = upload({ response: jsonResponse(400, {ok:false, message}) });
  await ui.send();
  assert.equal(ui.feedback.textContent, message);
  assert.equal(ui.feedback.dataset.state, 'error');
  assert.equal(ui.feedback.innerHTML, undefined);
  assert.equal(ui.button.disabled, false);
});

test('archivo incorrecto, ausente, excesivo o confirmación cancelada no envían nada', async () => {
  for (const options of [{file:null}, {file:{name:'data.csv',size:10}}, {file:{name:'data.xlsx',size:3*1024*1024}}, {confirm:false}]) {
    const ui = upload(options);
    await ui.send();
    assert.equal(ui.requests.length, 0);
  }
});

test('errores HTML de CSRF, permisos y tamaño no quedan como éxito silencioso', async () => {
  for (const status of [400, 401, 403, 413, 500, 200]) {
    const ui = upload({ response: {status, ok:status<400, headers:{get:()=> 'text/html'}} });
    await ui.send();
    assert.equal(ui.feedback.dataset.state, 'error');
    assert.ok(ui.feedback.textContent.length > 20);
    assert.equal(ui.button.disabled, false);
  }
});

test('conexión perdida muestra incertidumbre y permite comprobar las tablas', async () => {
  const ui = upload({ failure: new TypeError('Failed to fetch') });
  await ui.send();
  assert.match(ui.feedback.textContent, /comprobar si se guardaron/);
  assert.equal(ui.reload.hidden, false);
  assert.equal(ui.button.disabled, false);
});

test('no afirma éxito si el servidor no informa de las tres hojas', async () => {
  const ui = upload({ response: jsonResponse(200, {ok:true, message:'Importado', sheets:[{}]}) });
  await ui.send();
  assert.equal(ui.feedback.dataset.state, 'error');
  assert.match(ui.feedback.textContent, /tres hojas/);
});