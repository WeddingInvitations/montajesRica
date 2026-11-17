# Montajes Rica · Portal de pádel

Portal en español para los equipos Masculino 500, Masculino Future y Femenino. Permite consultar plantillas, partidos/resultados y clasificación. Las operaciones de gestión se hacen desde un panel solo para cuentas con rol `admin`.

## Tecnologías y datos


## Jugadores e historial deportivo

- Archivar un jugador cambia `active` a `false`; no elimina el documento ni sus IDs históricos. Los jugadores archivados desaparecen de las plantillas públicas y no pueden añadirse a partidos nuevos. El panel tiene una sección para revisar archivados, editar sus fichas y restaurarlos.
- Si un partido antiguo ya incluye a un jugador archivado, su referencia se conserva al editar el encuentro. Cada pareja guarda una copia del nombre en `player_names` para mostrar el resultado histórico aunque cambie la ficha actual.
- Las estadísticas son calculadas, no contadores que se incrementan al guardar: **PJ** partidos jugados, **PG/PP** resultados de la pareja del jugador y **SG/SP** sets ganados/perdidos. Se calculan desde partidos con estado `played`; si una pareja no tiene sets detallados, se usa el marcador general del equipo. El marcador general se introduce desde la perspectiva de Montajes Rica (MR primero y rival después), sea local o visitante.
- El cálculo es por pareja: los jugadores de una pareja reciben ese resultado. No hay doble conteo si un jugador aparece repetido en datos antiguos.
## Ranking individual

La pestaña Ranking muestra la clasificación general y permite filtrar por equipo
de plantilla actual. Solo incluye jugadores activos. Presenta partidos jugados,
ganados, perdidos, porcentaje de victorias y sets ganados/perdidos.

La ordenación usa el límite inferior de Wilson al 95 % sobre ganados/jugados,
expresado como índice de 0 a 100: tiene en cuenta el tamaño de la muestra para no
premiar automáticamente un 1/1 por encima de un 8/10. No mide la fuerza de los
oponentes ni la dificultad de las divisiones. Desempata por porcentaje de victorias,
victorias, diferencia de sets, sets ganados y nombre. Sin partidos no se asigna
posición. Las estadísticas provienen de los resultados existentes de las parejas;
no se generan resultados ni se modifican los datos en Firestore.

## Firebase Authentication

La configuración pública del cliente está en `static/js/firebase-config.js`; incluye el `apiKey` de la app Web, que identifica la aplicación y **no es una clave de servicio**. Nunca pongas credenciales de cuentas de servicio, claves privadas ni secretos OAuth en ese archivo.

En Firebase Console, proyecto `montajesrica`:

1. Abre Authentication → Sign-in method y habilita **Google**; selecciona el correo de soporte que corresponda.
2. En Authentication → Settings → Authorized domains añade `montajesrica.ew.r.appspot.com`, `localhost` y `127.0.0.1` (para desarrollo local). El dominio Firebase `montajesrica.firebaseapp.com` suele estar ya en la lista.
3. Verifica que `624919270102` es el proyecto correcto asociado a la app Web y a la base Firestore Native.

La aplicación ofrece acceso con Google y correo/contraseña. Las cuentas nuevas creadas con email reciben un enlace de verificación antes de poder entrar. En el primer acceso Google se pide enlazar una contraseña a la misma cuenta Firebase; los siguientes accesos pueden usar cualquiera de los dos métodos. El flujo usa Firebase JS SDK y los tokens se intercambian por una cookie `HttpOnly`, `Secure` en producción, `SameSite=Lax`, con duración de cinco días. El servidor comprueba firma, proyecto, proveedor permitido, correo verificado, inicio reciente y revocación. CSRF se exige para crear/cerrar la sesión y para cada formulario de administración.

## Roles y altas de usuarios

- Cualquier persona que pueda completar Google Sign-In puede crear su cuenta y consultar el portal; el primer acceso crea `users/{uid}` con `role: "watcher"`.
- Ser usuario de Firebase Authentication **no da rol admin/owner por sí solo**. Para evitar que un alta pública se convierta en privilegio, un owner/admin debe asignar explícitamente el rol en la colección `users`. Los roles válidos existentes, incluido `owner`, se conservan cuando el perfil se refresca al iniciar sesión.
- Un admin puede introducir en el panel el correo de una cuenta ya creada en Firebase Authentication. También se puede usar el script de bootstrap. Al retirar acceso, el rol vuelve a `watcher`; no se borra la cuenta de Firebase Auth.
- El documento almacena `uid`, `email`, `display_name`, `provider`, `role`, `active`, `created_at` y `updated_at`. Los clientes no pueden modificar esos documentos.

Para asignar el owner inicial o un admin, la cuenta debe haber iniciado sesión una vez para existir en Firebase Authentication; luego, desde una terminal autenticada como operador autorizado:

```powershell
gcloud auth login
python -m scripts.set_user_role --project montajesrica --role owner --gcloud-auth
```

El script solicita el email directamente en la terminal, verifica que la cuenta existe y tiene Google vinculado, y crea/actualiza `users/{uid}`. No escribe nombres de personas en el código ni en Git.

## Cargar jugadores desde el Excel

`listadoJugadores.xlsx` se mantiene local y está excluido de Git. Sus hojas/columnas se mapean así:

- `Masc 500` → `equipo-1` (Masculino 500)
- `Masc Future` → `equipo-2` (Masculino Future)
- `Fem` → `equipo-3` (Femenino)
- `Jugador` y `Posición` (`Drive` o `Revés`).

El archivo ya se validó y cargó en el proyecto `montajesrica`: 65 perfiles en `players` (20, 23 y 22 por equipo). Para validar un Excel futuro sin imprimir nombres ni escribir datos:

```powershell
python -m scripts.import_players --file .\listadoJugadores.xlsx
```

Para una importación confirmada:

```powershell
gcloud config set project montajesrica
python -m scripts.import_players --file .\listadoJugadores.xlsx --project montajesrica --gcloud-auth --apply
```

El importador evita repetidos por ID o por nombre/equipo. `--replace` sobrescribe y requiere `--apply`; úsalo solo tras revisar una copia de seguridad.

## Desarrollo local

Con Python 3.11 en Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app app run --debug
```

Flask carga automáticamente `.flaskenv` (configuración pública del proyecto) y `.env`
(configuración privada local) mediante `python-dotenv`, incluido en las dependencias.
No lee `app.yaml` al arrancar en local: ese archivo solo configura App Engine.
Por eso habilitar el dominio en Firebase no basta si el servidor desconoce
`FIREBASE_PROJECT_ID` o no tiene credenciales ADC.

Para probar las plantillas y administración con los datos ya importados, establece
`USE_FIRESTORE=true` en `.env`. **Aunque la web esté en localhost, las escrituras
del panel modificarán la base real de `montajesrica`.** El valor por defecto de
`.flaskenv` es `false` para mostrar únicamente los datos provisionales del club.
La autenticación y los roles siguen usando Firebase/Firestore en ambos casos;
no es un modo offline ni una copia local de la base.

Puedes comprobar el proyecto y todos los permisos necesarios sin escribir datos:

```powershell
python -m scripts.check_local_auth
```

Si cambias `.env` o las credenciales ADC, detén Flask con Ctrl+C y vuelve a arrancarlo.

Configura en Firebase Auth `localhost` y el dominio local que uses. Flask también necesita ADC de una cuenta que tenga acceso a Firestore y Firebase Auth; `gcloud auth login` por sí solo no configura esas credenciales para Python. En el flujo de autorización, selecciona una cuenta con permisos en `montajesrica` (no una cuenta sin acceso):

```powershell
gcloud config set project montajesrica
gcloud auth application-default login
gcloud auth application-default set-quota-project montajesrica
```

La cuenta local necesita `roles/datastore.user` para los perfiles en Firestore y `roles/firebaseauth.viewer` para comprobar usuario/sesión revocada. No uses credenciales de servicio descargadas en el repositorio. La página no carga ningún dato del club hasta validar una sesión.

Si Google autentica pero `/auth/session` devuelve HTTP 503, revisa el detalle de Flask: en local normalmente significa que ADC pertenece a una cuenta sin IAM en el proyecto. El login interactivo del frontend no sustituye ADC. En la autorización de `gcloud auth application-default login`, elige la cuenta del proyecto y acepta los ámbitos solicitados; no copies tokens ni claves al chat. HTTP 401 significa que el token de Firebase es inválido, ha caducado o no se ha verificado el correo.

Pruebas:

```powershell
python -m pytest
```

## Seguridad de Firestore y App Engine

- `firestore.rules` deniega todo acceso desde clientes Firebase. Flask usa Admin SDK/ADC y el permiso IAM de la cuenta runtime, por lo que las reglas Firestore no reemplazan la autorización del servidor.
- La cuenta de servicio runtime de App Engine necesita `roles/datastore.user` para acceder a Firestore Native y `roles/secretmanager.secretAccessor` **solo** al secreto `montajes-rica-flask-secret`.
- La clave de Flask se lee de Secret Manager al iniciar. No se debe poner en `app.yaml`, GitHub, Firebase Web config ni en el navegador.
- App Engine está configurado con `FIREBASE_PROJECT_ID=montajesrica`, Firestore habilitado, mínimo cero y máximo dos instancias.
- `firebase.json` apunta a las reglas de Firestore. Tras revisar cambios, se pueden desplegar desde la raíz con Firebase CLI: `firebase deploy --only firestore:rules --project montajesrica`.
- Configura alertas de presupuesto: son avisos, no límites de gasto.

## Despliegue

Cloud Build ejecuta las pruebas Python y después `gcloud app deploy app.yaml --quiet`. El propietario del proyecto debe mantener configurado el trigger de la rama principal y permisos mínimos en la cuenta de Build (`roles/appengine.deployer` y `roles/iam.serviceAccountUser` sobre la cuenta runtime). Los cambios de aplicación se despliegan únicamente al subirlos a la rama conectada; las reglas Firebase se despliegan por separado.
