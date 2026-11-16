# Montajes Rica · Portal de pádel

Portal en español para Masculino 500, Masculino Future y Femenino. Incluye consulta de plantillas, partidos/resultados y clasificación, además de un panel protegido para administrar jugadores, partidos, parejas, sets y administradores.

## Tecnologías y datos

- Python 3.11, Flask, HTML, CSS y JavaScript.
- Google App Engine Standard, Firestore Native, Cloud Build e Identity-Aware Proxy (IAP).
- La aplicación requiere una cuenta de Google. Solo las cuentas con rol `admin` pueden modificar datos.
- Configuración del club en `club/current`; jugadores, partidos, clasificaciones y administradores en `players`, `matches`, `standings` y `admins`.
- Los datos personales no se incluyen en el código ni en GitHub. `listadoJugadores.xlsx` está excluido por `.gitignore`.
- SNP Galaxy queda aplazado; no se guarda ninguna contraseña ni se automatiza el inicio de sesión.

> Para permitir acceso de lectura a cualquier cuenta de Google, asigna `roles/iap.httpsResourceAccessor` a `allAuthenticatedUsers`. Si no queréis exponer las fichas a todas esas cuentas, restringid esa política a un Google Group/cuentas concretas antes de habilitar datos reales.

## Desarrollo local

En Windows PowerShell, con Python 3.11:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app app run --debug
```

La vista local usa los marcadores de `data/club.json`. No conecta a Firestore, no autentica usuarios y no guarda cambios. El panel real se habilita en Google Cloud tras configurar IAP y Firestore.

Para validar:

```powershell
python -m pytest
```

## Hoja de jugadores

El archivo local ignorado `listadoJugadores.xlsx` contiene:

- `Masc 500` → `equipo-1` (Masculino 500)
- `Masc Future` → `equipo-2` (Masculino Future)
- `Fem` → `equipo-3` (Femenino)
- Columnas `Jugador` y `Posición`; valores admitidos: `Drive` y `Revés`.

Primero valida y cuenta sin mostrar nombres ni escribir datos:

```powershell
python -m scripts.import_players --file .\listadoJugadores.xlsx
```

La primera carga de este archivo ya se realizó en `montajesrica`. Para repetirla en el futuro, autentícate con `gcloud auth login` y confirma expresamente la escritura:

```powershell
gcloud config set project montajesrica
python -m scripts.import_players --file .\listadoJugadores.xlsx --project montajesrica --gcloud-auth --apply
```

El importador es idempotente por fila y también evita duplicar el mismo nombre/equipo. `--replace` permite sobrescribir fichas importadas y requiere también `--apply`; úsalo solo tras revisar una copia de seguridad. No subas el Excel a GitHub.

## Partidos

El panel administra equipo, rival, división, fecha, hora, lugar, localía, estado y marcador general (por ejemplo `3-2`). Permite registrar hasta cinco parejas, elegir dos jugadores del equipo por pareja, el rival y los sets (por ejemplo `6-4, 7-5`). Las entradas se validan en el servidor; solo administradores pueden crear, actualizar o borrar.

## Configuración manual en Google Cloud

No se crean recursos ni se despliega desde este asistente:

1. El proyecto `montajesrica` tiene la base `(default)` en **Firestore Native**, región `eur3`; la estructura inicial y las fichas del Excel ya se cargaron en esta base.
2. Asociar facturación si no está hecha, habilitar App Engine Standard, Cloud Build, Secret Manager e IAP y elegir con cuidado la ubicación de App Engine.
3. En Secret Manager crear `montajes-rica-flask-secret` con un valor aleatorio largo. Conceder a la cuenta runtime de App Engine `roles/secretmanager.secretAccessor` limitado a ese secreto. La cuenta runtime y quien ejecute importaciones deben tener `roles/datastore.user` (permiso IAM usado por Firestore). No se necesitan claves JSON ni credenciales de Firebase en el navegador.
4. Habilitar IAP para App Engine y otorgar `roles/iap.httpsResourceAccessor` a `allAuthenticatedUsers` para lectura abierta a cualquier identidad Google, **o** a un Google Group/cuentas concretas. El rol de administrador de la aplicación es independiente de IAM.
5. El documento `club/current` ya está inicializado. Para crear el primer admin, usa ADC o la sesión activa de gcloud. El script solicita el email en la terminal y no lo guarda en el código:

	```powershell
	gcloud auth login
	python -m scripts.bootstrap_admin --project montajesrica --gcloud-auth
	```

	El admin inicial puede añadir y retirar otros administradores desde el panel.
6. Revisa la política de acceso y confirma que los jugadores conocen la visibilidad prevista. Ejecuta primero el importador en modo de validación y luego con `--apply`.
7. Conectar el repositorio a un trigger Cloud Build de la rama principal. Dar a la cuenta de Build permisos mínimos (`roles/appengine.deployer` y `roles/iam.serviceAccountUser` sobre la cuenta runtime apropiada). El trigger ejecuta `gcloud app deploy app.yaml --quiet`.

`app.yaml` exige IAP y usa Firestore Native en producción. La audiencia IAP se deriva del metadata server de App Engine; la clave de Flask se lee de Secret Manager al iniciar. Comprueba en Cloud Console que IAP protege el servicio antes de introducir datos reales.

## Privacidad y operación

- Si IAP concede acceso a `allAuthenticatedUsers`, cualquier persona con cuenta Google puede ver los nombres, equipo y lado de juego. Restringe IAP si eso no es adecuado y confirma el uso previsto con los jugadores.
- Las reglas Firestore no sustituyen autorización del servidor: no hay SDK cliente de Firestore. Las escrituras pasan por Flask, IAP, CSRF y comprobación del rol admin.
- No registres credenciales ni datos personales en logs o Git. Revisa cambios antes de hacer commit.
- Configura alertas de presupuesto: no limitan el gasto. No despliegues hasta haber validado IAP, Secret Manager, Firestore y accesos.
